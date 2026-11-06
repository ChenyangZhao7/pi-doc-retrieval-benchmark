/**
 * bash_guard：G2 用，拦截可能越界的 bash 命令。
 *
 * 这是启发式防护，不是安全沙箱；G2 仍需专用目录 + 事后审计。
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const BLOCK_WORDS = [
  "pi-docbench",
  "powershell",
  "pwsh",
  "cmd.exe",
  "wsl",
  "python",
  "python3",
  "node",
];

function norm(s: string): string {
  return s.replace(/\\/g, "/");
}

export default function bashGuard(pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;
    const input = (event.input || {}) as Record<string, unknown>;
    const cmd = String(input.command || "");
    const cwd = norm(ctx.cwd).replace(/\/+$/, "").toLowerCase();
    const low = norm(cmd).toLowerCase();

    for (const word of BLOCK_WORDS) {
      if (low.includes(word)) {
        return { block: true, reason: `bash_guard: 命令包含禁用词 ${word}` };
      }
    }
    if (/(^|[\s"'`=:])\.\.([\/\s"'`;|&)]|$)/.test(low)) {
      return { block: true, reason: "bash_guard: 禁止 .. 跳出当前目录" };
    }
    // 绝对路径必须在 cwd 内
    const abs = low.match(/[a-z]:\/[^\s"'`;|&)]+/g) || [];
    for (const p of abs) {
      if (!(p === cwd || p.startsWith(cwd + "/"))) {
        return { block: true, reason: `bash_guard: 拒绝 cwd 外绝对路径 ${p}` };
      }
    }
    // Git Bash 的 /c/ /z/ 形式
    if (/(^|[\s"'`=:])\/[a-z]\//.test(low) || /(^|[\s"'`=:])\/(etc|home|root|tmp|usr|var)\//.test(low)) {
      return { block: true, reason: "bash_guard: 拒绝 Git Bash 绝对路径" };
    }
    // cd 只允许 cwd 内
    const cdMatches = low.match(/(?:^|[;&|]\s*)cd\s+([^\s;&|]+)/g) || [];
    for (const m of cdMatches) {
      const target = m.replace(/^.*?cd\s+/, "").replace(/["']/g, "").replace(/\/+$/, "");
      if (target.startsWith("..") || target === "-") {
        return { block: true, reason: "bash_guard: 禁止 cd 到 cwd 外" };
      }
      if (target.startsWith("/") || /^[a-z]:/.test(target)) {
        if (!(target === cwd || target.startsWith(cwd + "/"))) {
          return { block: true, reason: `bash_guard: 禁止 cd 到 cwd 外 ${target}` };
        }
      }
    }
    return undefined;
  });
}
