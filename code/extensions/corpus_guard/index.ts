/**
 * corpus_guard：把只读工具限制在当前工作目录内。
 *
 * 背景：pi 的工作目录不是安全边界，read/grep/find/ls 可以读绝对路径。
 * 这个 extension 在 tool_call 阶段拦截越界路径，避免 M/S 档读到同级的 L 档。
 *
 * 只拦截 read/grep/find/ls；bash 不在 G1 工具集里，G2/G4 另需容器。
 */

import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const TOOLS = new Set(["read", "grep", "find", "ls"]);
const PATH_KEYS = ["path", "file", "file_path", "filePath", "dir", "directory"];

function isOutside(raw: string, cwd: string): boolean {
  if (!raw || typeof raw !== "string") return false;
  // 只检查像路径的参数；纯关键词/glob 不拦
  const looksLikePath =
    raw.includes("/") || raw.includes("\\") || raw.startsWith(".") || /^[A-Za-z]:/.test(raw);
  if (!looksLikePath) return false;
  const abs = path.resolve(cwd, raw);
  const rel = path.relative(cwd, abs);
  return rel === ".." || rel.startsWith(".." + path.sep) || path.isAbsolute(rel);
}

export default function corpusGuard(pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (!TOOLS.has(event.toolName)) return undefined;
    const input = (event.input || {}) as Record<string, unknown>;
    for (const key of PATH_KEYS) {
      const value = input[key];
      if (typeof value === "string" && isOutside(value, ctx.cwd)) {
        return {
          block: true,
          reason:
            `corpus_guard: 只允许访问当前工作目录内的文件；` +
            `拒绝 ${event.toolName} ${key}=${value}（cwd=${ctx.cwd}）`,
        };
      }
    }
    return undefined;
  });
}
