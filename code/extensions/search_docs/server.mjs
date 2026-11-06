/**
 * search_docs 本地检索服务（sidecar）。
 *
 * 为什么单独起进程：bge 模型在每次 pi 进程里重新加载约 20–30 秒，会把 G3 的
 * 端到端耗时算歪。这里只加载一次，pi extension 通过 localhost HTTP 调用。
 *
 * 接口：
 *   GET  /health          -> {ok, chunks, dim, model, retrieval}
 *   POST /search          -> {query, k, mode} => {results:[{file,page,score,text,...}], latency_ms}
 *   mode: dense | hybrid（默认 hybrid：0.65 向量 + 0.35 BM25）
 *
 * 只监听 127.0.0.1，不对外网开放。
 *
 * 用法：
 *   node extensions/search_docs/server.mjs --index .cache/search_docs/S
 */

import fs from "node:fs";
import fsp from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as lancedb from "@lancedb/lancedb";
import { env, pipeline } from "@huggingface/transformers";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HOME, "..", "..");
const TABLE = "chunks";
const QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章：";
const BM25_K1 = 1.2;
const BM25_B = 0.75;
const DENSE_WEIGHT = Math.min(1, Math.max(0, Number(process.env.SEARCH_DOCS_DENSE_WEIGHT || 0.9)));
const LEXICAL_WEIGHT = 1 - DENSE_WEIGHT;

/** 中文按 bigram、英文/数字按词切；用于 BM25 词法通道。 */
function tokenize(text) {
  const s = String(text || "").toLowerCase();
  const out = [];
  for (const m of s.matchAll(/[a-z0-9]+(?:\.[0-9]+)?/g)) out.push(m[0]);
  for (const run of s.match(/[\u3400-\u9fff]+/g) || []) {
    if (run.length === 1) out.push(run);
    else for (let i = 0; i < run.length - 1; i++) out.push(run.slice(i, i + 2));
  }
  return out;
}

function buildLexical(rows) {
  const docs = rows.map((row) => {
    const tf = new Map();
    for (const t of tokenize(row.text)) tf.set(t, (tf.get(t) || 0) + 1);
    let dl = 0;
    for (const v of tf.values()) dl += v;
    return { row, tf, dl };
  });
  const df = new Map();
  let total = 0;
  for (const d of docs) {
    total += d.dl;
    for (const t of d.tf.keys()) df.set(t, (df.get(t) || 0) + 1);
  }
  return { docs, df, avgdl: total / Math.max(1, docs.length), N: docs.length };
}

function bm25Search(index, query, k) {
  const q = [...new Set(tokenize(query))];
  if (!q.length) return [];
  const scored = [];
  for (const d of index.docs) {
    let s = 0;
    for (const t of q) {
      const f = d.tf.get(t);
      if (!f) continue;
      const n = index.df.get(t) || 0;
      const idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
      s += (idf * f * (BM25_K1 + 1)) / (f + BM25_K1 * (1 - BM25_B + (BM25_B * d.dl) / index.avgdl));
    }
    if (s > 0) scored.push({ row: d.row, score: s });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}

function parseArgs() {
  const argv = process.argv.slice(2);
  const args = {
    index: path.join(REPO, ".cache", "search_docs", "S"),
    model: path.join(REPO, ".cache", "models", "bge-small-zh-v1.5"),
    host: "127.0.0.1",
    port: Number(process.env.SEARCH_DOCS_PORT || 8765),
    log: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--index") args.index = path.resolve(argv[++i]);
    else if (a === "--model") args.model = path.resolve(argv[++i]);
    else if (a === "--host") args.host = argv[++i];
    else if (a === "--port") args.port = Number(argv[++i]);
    else if (a === "--no-log") args.log = false;
    else if (a === "--help" || a === "-h") {
      console.log("node server.mjs [--index <dir>] [--model <dir>] [--port 8765] [--no-log]");
      process.exit(0);
    } else throw new Error(`unknown argument: ${a}`);
  }
  return args;
}

function json(res, code, body) {
  const buf = Buffer.from(JSON.stringify(body));
  res.writeHead(code, {
    "content-type": "application/json; charset=utf-8",
    "content-length": buf.length,
  });
  res.end(buf);
}

async function readBody(req, limit = 64 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new Error("request body too large");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function main() {
  const args = parseArgs();
  const metaPath = path.join(args.index, "meta.json");
  const meta = JSON.parse(await fsp.readFile(metaPath, "utf8"));
  if (!(await fs.existsSync(path.join(args.model, "onnx", "model_quantized.onnx")))) {
    throw new Error(`model not found: ${args.model} (run download_model.mjs first)`);
  }

  env.localModelPath = path.dirname(args.model);
  env.allowRemoteModels = false;
  env.allowLocalModels = true;
  const t0 = Date.now();
  console.error(`[search_docs] loading model ${args.model} ...`);
  const extractor = await pipeline("feature-extraction", path.basename(args.model), { dtype: "q8" });
  console.error(`[search_docs] model ready in ${Date.now() - t0} ms`);

  const db = await lancedb.connect(args.index);
  const table = await db.openTable(TABLE);
  const chunks = await table.countRows();
  // 词法通道：索引不大（S/M/L 最多几千块），启动时全量载入一次。
  const allRows = await table.query().toArray();
  const lexical = buildLexical(allRows);
  console.error(`[search_docs] index ${args.index}: ${chunks} chunks x ${meta.dim}d, lexical docs ${lexical.N}`);

  let logStream = null;
  if (args.log) {
    logStream = fs.createWriteStream(path.join(args.index, "queries.jsonl"), { flags: "a" });
  }

  async function embedQuery(query) {
    const out = await extractor([QUERY_INSTRUCTION + query], { pooling: "cls", normalize: true });
    return Array.from(out.data, (x) => Math.fround(x));
  }

  async function denseSearch(query, k) {
    const vector = await embedQuery(query);
    const rows = await table.search(vector).distanceType("cosine").limit(k).toArray();
    return rows.map((row) => ({
      id: row.id,
      file: row.file,
      company: row.company,
      title: row.title,
      page: row.page,
      score: Number((1 - row._distance).toFixed(6)),
      text: row.text,
    }));
  }

  function fuse(dense, lex, k) {
    const maxLex = Math.max(...lex.map((x) => x.score), 1e-9);
    const byId = new Map();
    for (const r of dense) byId.set(r.id, { ...r, dense_score: r.score, lexical_score: 0 });
    for (const { row, score } of lex) {
      const norm = score / maxLex;
      const cur = byId.get(row.id);
      if (cur) {
        cur.lexical_score = Number(score.toFixed(6));
        cur.score = Number((DENSE_WEIGHT * cur.dense_score + LEXICAL_WEIGHT * norm).toFixed(6));
      } else {
        byId.set(row.id, {
          id: row.id,
          file: row.file,
          company: row.company,
          title: row.title,
          page: row.page,
          score: Number((LEXICAL_WEIGHT * norm).toFixed(6)),
          dense_score: 0,
          lexical_score: Number(score.toFixed(6)),
          text: row.text,
        });
      }
    }
    return [...byId.values()].sort((a, b) => b.score - a.score).slice(0, k);
  }

  async function search(query, k, mode) {
    const started = Date.now();
    const candidate = Math.max(k * 5, 30);
    const dense = await denseSearch(query, candidate);
    let results;
    if (mode === "dense") {
      results = dense.slice(0, k);
    } else {
      const lex = bm25Search(lexical, query, candidate);
      results = fuse(dense, lex, k);
    }
    const latency = Date.now() - started;
    if (logStream) {
      logStream.write(
        JSON.stringify({
          ts: new Date().toISOString(),
          query,
          k,
          mode,
          latency_ms: latency,
          top: results.map((r) => ({ file: r.file, page: r.page, score: r.score })),
        }) + "\n",
      );
    }
    return { results, latency_ms: latency, mode };
  }

  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, `http://${args.host}:${args.port}`);
      if (req.method === "GET" && url.pathname === "/health") {
        return json(res, 200, {
          ok: true,
          chunks,
          dim: meta.dim,
          model: meta.model?.name || path.basename(args.model),
          corpus_sha256: meta.corpus_sha256,
          index: args.index,
          retrieval: "hybrid",
          lexical_docs: lexical.N,
        });
      }
      if (req.method === "POST" && url.pathname === "/search") {
        const body = JSON.parse((await readBody(req)) || "{}");
        const query = String(body.query || "").trim();
        if (!query) return json(res, 400, { error: "query is required" });
        const k = Math.max(1, Math.min(Number(body.k) || 5, 20));
        const mode = body.mode === "dense" ? "dense" : "hybrid";
        const out = await search(query, k, mode);
        return json(res, 200, out);
      }
      return json(res, 404, { error: "not found" });
    } catch (err) {
      console.error(`[search_docs] ${err.stack || err.message}`);
      return json(res, 500, { error: String(err.message || err) });
    }
  });

  server.listen(args.port, args.host, () => {
    console.error(`[search_docs] listening on http://${args.host}:${args.port}`);
  });

  const shutdown = () => {
    server.close(() => process.exit(0));
    if (logStream) logStream.end();
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((err) => {
  console.error(`[search_docs] ERROR: ${err.stack || err.message}`);
  process.exit(1);
});
