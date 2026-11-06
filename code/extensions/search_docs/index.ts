/**
 * pi extension: search_docs
 *
 * 在 pi 进程内注册一个检索工具，实际检索由本地 sidecar（server.mjs）完成：
 * 查询文本用 bge-small-zh 编码，从 LanceDB 取 top-k 段落，返回文件名 + 页码 + 原文。
 *
 * 这样 G3 的端到端耗时不会把「每个 pi 进程重新加载 20–30 秒模型」算进去；
 * sidecar 在第一次调用时自动拉起，之后所有题目复用。
 *
 * 环境变量：
 *   SEARCH_DOCS_URL        默认 http://127.0.0.1:8765
 *   SEARCH_DOCS_INDEX      默认 <repo>/.cache/search_docs/S
 *   SEARCH_DOCS_MODEL      默认 <repo>/.cache/models/bge-small-zh-v1.5
 *   SEARCH_DOCS_AUTOSTART  默认 1；设 0 时不自动拉起 sidecar
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HOME, "..", "..");
const URL_BASE = process.env.SEARCH_DOCS_URL || "http://127.0.0.1:8765";
const INDEX_DIR = process.env.SEARCH_DOCS_INDEX || path.join(REPO, ".cache", "search_docs", "S");
const MODEL_DIR = process.env.SEARCH_DOCS_MODEL || path.join(REPO, ".cache", "models", "bge-small-zh-v1.5");
const MODE = process.env.SEARCH_DOCS_MODE === "dense" ? "dense" : "hybrid";

let starting: Promise<void> | null = null;

async function health(timeoutMs = 1500) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${URL_BASE}/health`, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureServer() {
  if (await health()) return;
  if (process.env.SEARCH_DOCS_AUTOSTART === "0") {
    throw new Error(
      `search_docs sidecar 未运行（${URL_BASE}）。请先启动：` +
        `node extensions/search_docs/server.mjs --index "${INDEX_DIR}" --model "${MODEL_DIR}"`,
    );
  }
  if (!starting) {
    starting = (async () => {
      const logDir = path.join(REPO, ".cache", "search_docs");
      fs.mkdirSync(logDir, { recursive: true });
      const logPath = path.join(logDir, "server.log");
      const logFd = fs.openSync(logPath, "a");
      const server = path.join(HOME, "server.mjs");
      const child = spawn(
        process.execPath,
        [server, "--index", INDEX_DIR, "--model", MODEL_DIR, "--port", String(new URL(URL_BASE).port || 8765)],
        { detached: true, stdio: ["ignore", logFd, logFd], cwd: HOME, windowsHide: true },
      );
      child.unref();
      fs.closeSync(logFd);
      for (let i = 0; i < 240; i++) {
        await sleep(500);
        if (await health()) return;
        if (child.exitCode !== null) break;
      }
      starting = null;
      throw new Error(`search_docs sidecar 启动失败，日志：${logPath}`);
    })();
  }
  await starting;
}

async function postSearch(query: string, k: number) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 60_000);
  try {
    const res = await fetch(`${URL_BASE}/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, k, mode: MODE }),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export default function searchDocsExtension(pi: ExtensionAPI) {
  pi.registerTool({
    name: "search_docs",
    label: "search_docs",
    description:
      "语义 + 关键词混合检索文档集：输入自然语言问题或关键词，返回最相关的原文段落（含文件名、页码、相似度）。" +
      "当你不确定原文用词、或需要跨多份文档找相关内容时使用；要读完整文件仍可用 read。",
    parameters: Type.Object({
      query: Type.String({ description: "要检索的问题或关键词" }),
      k: Type.Optional(
        Type.Integer({ minimum: 1, maximum: 10, default: 5, description: "返回段落数，默认 5" }),
      ),
    }),

    async execute(_toolCallId, params) {
      const query = String(params.query || "").trim();
      const k = Math.max(1, Math.min(Number(params.k) || 5, 10));
      if (!query) throw new Error("query 不能为空");

      await ensureServer();
      const data = await postSearch(query, k);
      const results = Array.isArray(data.results) ? data.results : [];

      if (results.length === 0) {
        return {
          content: [{ type: "text", text: "没有检索到相关段落。" }],
          details: { query, k, results: [], latency_ms: data.latency_ms },
        };
      }

      const lines = [`检索到 ${results.length} 个相关段落（余弦相似度，越高越相关）：`, ""];
      results.forEach((r: any, i: number) => {
        const body = String(r.text || "").replace(/\s+\n/g, "\n").trim();
        const clipped = body.length > 1200 ? `${body.slice(0, 1200)}\n…（段落已截断）` : body;
        lines.push(`[${i + 1}] ${r.file} 第 ${r.page} 页（score ${r.score}）`);
        lines.push(clipped);
        lines.push("");
      });

      return {
        content: [{ type: "text", text: lines.join("\n").trim() }],
        details: {
          query,
          k,
          latency_ms: data.latency_ms,
          results: results.map((r: any) => ({ file: r.file, page: r.page, score: r.score })),
        },
      };
    },
  });
}
