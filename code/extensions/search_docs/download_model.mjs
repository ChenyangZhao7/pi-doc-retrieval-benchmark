/**
 * 下载本地 embedding 模型（BAAI/bge-small-zh-v1.5，ONNX int8）。
 *
 * HuggingFace 在本机网络下不可达，改用魔搭（ModelScope）的 Xenova ONNX 转换版。
 * 只下载推理需要的 5 个文件，约 24 MB。
 *
 * 用法：
 *   node extensions/search_docs/download_model.mjs
 *   node extensions/search_docs/download_model.mjs --out .cache/models/bge-small-zh-v1.5
 */

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HOME, "..", "..");
const REPO_ID = "Xenova/bge-small-zh-v1.5";
const REVISION = "master";
const BASE = `https://www.modelscope.cn/models/${REPO_ID}/resolve/${REVISION}`;
const FILES = [
  "config.json",
  "tokenizer.json",
  "tokenizer_config.json",
  "special_tokens_map.json",
  "onnx/model_quantized.onnx",
];

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { out: path.join(REPO, ".cache", "models", "bge-small-zh-v1.5") };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--out") out.out = path.resolve(args[++i]);
    else if (args[i] === "--help" || args[i] === "-h") {
      console.log("node download_model.mjs [--out <dir>]");
      process.exit(0);
    } else throw new Error(`unknown argument: ${args[i]}`);
  }
  return out;
}

async function download(url, dest) {
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length === 0) throw new Error(`empty response: ${url}`);
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.writeFile(dest, buf);
  return buf.length;
}

const { out } = parseArgs();
console.log(`model: ${REPO_ID}`);
console.log(`dest : ${out}`);

for (const rel of FILES) {
  const dest = path.join(out, rel);
  const size = await download(`${BASE}/${rel}`, dest);
  console.log(`  ${rel.padEnd(32)} ${(size / 1024 / 1024).toFixed(2)} MB`);
}

await fs.writeFile(
  path.join(out, "SOURCE.json"),
  JSON.stringify({ repo: REPO_ID, revision: REVISION, base: BASE, files: FILES }, null, 2) + "\n",
  "utf8",
);
console.log("done.");
