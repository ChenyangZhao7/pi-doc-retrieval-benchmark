"""审计工具调用是否成功读到 cwd 之外的文件（区分被 guard 拦截的尝试）。"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
PATH_KEYS = {"path", "file", "file_path", "filePath", "dir", "directory"}


def is_outside(raw, allow):
    if not isinstance(raw, str) or not raw:
        return False
    s = raw.replace("\\", "/").lower()
    is_abs = len(s) >= 3 and s[1] == ":" and s[2] == "/"
    if is_abs:
        return not (s.startswith(allow) or s == allow.rstrip("/"))
    return ".." in s.split("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.metrics, encoding="utf-8") if l.strip()]
    success_outside = {}
    blocked = {}
    answer_hits = {}
    for r in rows:
        old_root = "<corpus-root>/s"
        allow = old_root if r.get("reused_from") else "<repo-root>/m"
        raw = Path(r.get("raw_file") or "")
        if not raw.is_absolute():
            raw = ROOT / raw
        starts = {}
        if raw.exists():
            for line in open(raw, encoding="utf-8", errors="ignore"):
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") == "tool_execution_start":
                    starts[e.get("toolCallId")] = (e.get("toolName"), e.get("args") or {})
                elif e.get("type") == "tool_execution_end":
                    tid = e.get("toolCallId")
                    name, cargs = starts.get(tid, (e.get("toolName"), {}))
                    text = str(e.get("result") or "")
                    if e.get("isError"):
                        if "corpus_guard" in text:
                            blocked.setdefault(r["run_id"], []).append((name, cargs))
                        continue
                    for k, v in cargs.items():
                        if k in PATH_KEYS and is_outside(v, allow):
                            success_outside.setdefault(r["run_id"], []).append((name, k, v))
        ans = (r.get("answer") or "").replace("\\", "/").lower()
        if "pi-docbench/l/" in ans or "pi-docbench/s/" in ans:
            answer_hits[r["run_id"]] = "citation"
        elif not r.get("reused_from") and ("l/" in ans and "000892" in ans):
            answer_hits[r["run_id"]] = "citation"

    print("runs", len(rows))
    print("successful outside", len(success_outside), "qids", len({r.split('_')[2] for r in success_outside}))
    print("blocked attempts", len(blocked), "calls", sum(len(v) for v in blocked.values()))
    print("answer citations", len(answer_hits))
    if success_outside:
        print("examples successful:")
        for rid, hits in list(success_outside.items())[:8]:
            print(" ", rid, hits[:2])
    out = Path(args.out)
    out.write_text(json.dumps({
        "n_runs": len(rows),
        "successful_outside": success_outside,
        "blocked_attempts": {k: len(v) for k, v in blocked.items()},
        "answer_citations": answer_hits,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
