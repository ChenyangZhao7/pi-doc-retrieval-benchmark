/**
 * 构建 search_docs 索引：Markdown 按页切块 -> bge-small-zh 向量 -> LanceDB。
 *
 * 设计要点：
 * - 只用公开语料目录里的 .md 文件；跳过 INDEX.md / AGENTS.md / analysis/ 等非年报文件；
 * - 切块不跨 `<!-- page: n -->`，因此每个块都带确定的页码，便于算 page-level recall@5；
 * - 文档侧不加 BGE query 指令，查询侧在 serve.mjs 里加；
 * - 输出目录默认 .cache/search_docs/<语料目录名>，不入库。
 *
 * 用法：
 *   node extensions/search_docs/build_index.mjs --corpus <corpus-root>/S
 *   node extensions/search_docs/build_index.mjs --corpus <corpus-root>/S --limit 5
 */

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as lancedb from "@lancedb/lancedb";
import { env, pipeline } from "@huggingface/transformers";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HOME, "..", "..");
const TABLE = "chunks";

function parseArgs() {
  const argv = process.argv.slice(2);
  const args = {
    corpus: null,
    out: null,
    model: path.join(REPO, ".cache", "models", "bge-small-zh-v1.5"),
    chunkSize: 420,
    overlap: 80,
    batch: 32,
    limit: 0,
    force: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--corpus") args.corpus = path.resolve(argv[++i]);
    else if (a === "--out") args.out = path.resolve(argv[++i]);
    else if (a === "--model") args.model = path.resolve(argv[++i]);
    else if (a === "--chunk-size") args.chunkSize = Number(argv[++i]);
    else if (a === "--overlap") args.overlap = Number(argv[++i]);
    else if (a === "--batch") args.batch = Number(argv[++i]);
    else if (a === "--limit") args.limit = Number(argv[++i]);
    else if (a === "--force") args.force = true;
    else if (a === "--help" || a === "-h") {
      console.log("node build_index.mjs --corpus <dir> [--out <dir>] [--model <dir>] [--limit N] [--force]");
      process.exit(0);
    } else throw new Error(`unknown argument: ${a}`);
  }
  if (!args.corpus) throw new Error("--corpus is required");
  if (!args.out) args.out = path.join(REPO, ".cache", "search_docs", path.basename(args.corpus));
  return args;
}

function sha256(buf) {
  return crypto.createHash("sha256").update(buf).digest("hex");
}

/** 与 runner/run_one.py 的 corpus_sha256 保持同一口径。 */
async function corpusSha256(root, files) {
  const h = crypto.createHash("sha256");
  for (const rel of files) {
    const abs = path.join(root, rel);
    h.update(rel, "utf8");
    h.update(Buffer.from([0]));
    h.update(sha256(await fs.readFile(abs)), "ascii");
    h.update(Buffer.from("\n"));
  }
  return h.digest("hex");
}

function isCorpusDoc(rel) {
  const posix = rel.replaceAll("\\", "/");
  if (!posix.toLowerCase().endsWith(".md")) return false;
  const name = posix.split("/").pop().toLowerCase();
  if (name === "index.md" || name === "agents.md" || name === "readme.md") return false;
  if (posix.split("/").includes("analysis")) return false;
  return true;
}

async function listDocs(root) {
  const out = [];
  async function walk(dir, prefix) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name, "zh"));
    for (const e of entries) {
      const rel = prefix ? `${prefix}/${e.name}` : e.name;
      if (e.isDirectory()) await walk(path.join(dir, e.name), rel);
      else if (e.isFile() && isCorpusDoc(rel)) out.push(rel);
    }
  }
  await walk(root, "");
  return out.sort((a, b) => a.localeCompare(b, "zh"));
}

function splitLongBlock(block, target, overlap) {
  const parts = block
    .split(/(?<=[。！？；：\n])/)
    .map((s) => s.trim())
    .filter(Boolean);
  const chunks = [];
  let cur = "";
  for (const part of parts) {
    if (part.length > target * 2) {
      if (cur) {
        chunks.push(cur);
        cur = "";
      }
      for (let i = 0; i < part.length; i += target - overlap) {
        chunks.push(part.slice(i, i + target));
      }
      continue;
    }
    if (cur && cur.length + part.length + 1 > target) {
      chunks.push(cur);
      const tail = cur.slice(-overlap);
      cur = tail + "\n" + part;
    } else {
      cur = cur ? `${cur}\n${part}` : part;
    }
  }
  if (cur) chunks.push(cur);
  return chunks;
}

/** 按空行分段后装箱；不跨页。 */
function chunkPage(text, target, overlap) {
  const blocks = text
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  const chunks = [];
  let cur = "";
  for (const block of blocks) {
    if (block.length > target * 1.6) {
      if (cur) {
        chunks.push(cur);
        cur = "";
      }
      chunks.push(...splitLongBlock(block, target, overlap));
      continue;
    }
    if (cur && cur.length + block.length + 2 > target * 1.3) {
      chunks.push(cur);
      cur = "";
    }
    cur = cur ? `${cur}\n\n${block}` : block;
  }
  if (cur) chunks.push(cur);
  return chunks.filter((c) => c.trim().length >= 30);
}

function splitPages(text) {
  const re = /<!--\s*page:\s*(\d+)\s*-->/g;
  const marks = [...text.matchAll(re)];
  if (marks.length === 0) return [{ page: 1, text: text.trim() }];
  const pages = [];
  for (let i = 0; i < marks.length; i++) {
    const start = marks[i].index + marks[i][0].length;
    const end = i + 1 < marks.length ? marks[i + 1].index : text.length;
    pages.push({ page: Number(marks[i][1]), text: text.slice(start, end).trim() });
  }
  return pages;
}

function docTitle(text, rel) {
  const first = text.split("\n").find((line) => line.trim().startsWith("# "));
  if (first) return first.replace(/^#\s*/, "").trim();
  return path.basename(rel, ".md");
}

async function main() {
  const args = parseArgs();
  if (!(await fs.stat(args.corpus).catch(() => null))) {
    throw new Error(`corpus not found: ${args.corpus}`);
  }
  const stat = await fs.stat(args.out).catch(() => null);
  if (stat && !args.force) {
    throw new Error(`output exists: ${args.out} (use --force to overwrite)`);
  }

  const allDocs = await listDocs(args.corpus);
  const docs = args.limit > 0 ? allDocs.slice(0, args.limit) : allDocs;
  if (docs.length === 0) throw new Error("no .md documents found");
  console.log(`[index] corpus : ${args.corpus}`);
  console.log(`[index] docs   : ${docs.length}${args.limit ? ` / ${allDocs.length} (limit)` : ""}`);

  const chunks = [];
  for (const rel of docs) {
    const text = (await fs.readFile(path.join(args.corpus, rel), "utf8")).replace(/\r\n/g, "\n");
    const title = docTitle(text, rel);
    const company = rel.split("/")[0] || "";
    for (const { page, text: pageText } of splitPages(text)) {
      if (!pageText) continue;
      for (const [i, body] of chunkPage(pageText, args.chunkSize, args.overlap).entries()) {
        chunks.push({
          id: `${rel}#p${page}#${i}`,
          file: rel,
          company,
          title,
          page,
          text: body,
          embed_text: `【${company}｜${title}｜第${page}页】\n${body}`,
          chars: body.length,
        });
      }
    }
  }
  console.log(`[index] chunks : ${chunks.length}`);
  const lens = chunks.map((c) => c.chars).sort((a, b) => a - b);
  console.log(
    `[index] chars  : min ${lens[0]} / p50 ${lens[Math.floor(lens.length / 2)]} / max ${lens[lens.length - 1]}`,
  );

  env.localModelPath = path.dirname(args.model);
  env.allowRemoteModels = false;
  env.allowLocalModels = true;
  console.log(`[index] model  : ${args.model}`);
  const extractor = await pipeline("feature-extraction", path.basename(args.model), { dtype: "q8" });

  const vectors = [];
  const t0 = Date.now();
  for (let start = 0; start < chunks.length; start += args.batch) {
    const batch = chunks.slice(start, start + args.batch);
    const out = await extractor(
      batch.map((c) => c.embed_text),
      { pooling: "cls", normalize: true },
    );
    const dim = out.dims[1];
    for (let i = 0; i < batch.length; i++) {
      vectors.push(Array.from(out.data.slice(i * dim, (i + 1) * dim), (x) => Math.fround(x)));
    }
    if (start % (args.batch * 8) === 0) {
      console.log(`[index] embed  : ${Math.min(start + batch.length, chunks.length)}/${chunks.length}`);
    }
  }
  console.log(`[index] embed ms: ${Date.now() - t0}`);
  const dim = vectors[0].length;

  await fs.mkdir(args.out, { recursive: true });
  const db = await lancedb.connect(args.out);
  const rows = chunks.map((c, i) => ({
    id: c.id,
    vector: vectors[i],
    file: c.file,
    company: c.company,
    title: c.title,
    page: c.page,
    text: c.text,
  }));
  await db.createTable(TABLE, rows, { mode: "overwrite" });
  console.log(`[index] lancedb: ${path.join(args.out, `${TABLE}.lance`)} (${rows.length} rows x ${dim}d)`);

  // 便于人工核查的纯文本副本（不含向量）
  const jsonl = chunks.map(({ embed_text, ...rest }) => JSON.stringify(rest)).join("\n") + "\n";
  await fs.writeFile(path.join(args.out, "chunks.jsonl"), jsonl, "utf8");

  const meta = {
    built_at: new Date().toISOString(),
    corpus: args.corpus,
    corpus_sha256: await corpusSha256(args.corpus, docs),
    documents: docs.length,
    chunks: chunks.length,
    dim,
    model: {
      name: "BAAI/bge-small-zh-v1.5",
      source: "Xenova/bge-small-zh-v1.5 (ModelScope ONNX int8)",
      dir: args.model,
      pooling: "cls",
      normalize: true,
      query_instruction: "为这个句子生成表示以用于检索相关文章：",
      dtype: "q8",
    },
    chunking: {
      target_chars: args.chunkSize,
      overlap_chars: args.overlap,
      page_bounded: true,
      min_chars: 30,
    },
    store: { backend: "LanceDB", table: TABLE, metric: "cosine" },
  };
  await fs.writeFile(path.join(args.out, "meta.json"), JSON.stringify(meta, null, 2) + "\n", "utf8");
  console.log(`[index] done   : ${args.out}`);
}

main().catch((err) => {
  console.error(`[index] ERROR: ${err.stack || err.message}`);
  process.exit(1);
});
