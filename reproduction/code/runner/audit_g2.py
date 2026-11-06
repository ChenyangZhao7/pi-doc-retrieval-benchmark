"""审计 G2 S/M：成功越界、被 guard 拦截、答案引用外部路径。"""

import argparse
import json
from pathlib import Path

ROOT = Path(r"<repo-root>\code")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--allow", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    allow = args.allow.replace("\\", "/").lower().rstrip("/")
    rows = [json.loads(l) for l in open(args.metrics, encoding="utf-8") if l.strip()]
    outside, blocked, cites = {}, {}, {}
    for r in rows:
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
                    name, cargs = starts.get(e.get("toolCallId"), (e.get("toolName"), {}))
                    if e.get("isError"):
                        if any(x in str(e.get("result") or "") for x in ("bash_guard", "corpus_guard")):
                            blocked.setdefault(r["run_id"], []).append(name)
                        continue
                    for k, v in cargs.items():
                        if isinstance(v, str):
                            s = v.replace("\\", "/").lower()
                            if "pi-docbench" in s or ".." in s.split("/") or (
                                len(s) >= 3 and s[1] == ":" and s[2] == "/" and not s.startswith(allow)
                            ):
                                outside.setdefault(r["run_id"], []).append((name, k, v))
        ans = (r.get("answer") or "").replace("\\", "/").lower()
        if "pi-docbench" in ans or "/l/" in ans and "000" in ans:
            cites[r["run_id"]] = True
    print("runs", len(rows), "successful_outside", len(outside), "blocked_runs", len(blocked), "cite_hits", len(cites))
    if outside:
        for rid, hits in list(outside.items())[:10]:
            print(" OUT", rid, hits[:3])
    Path(args.out).write_text(json.dumps({
        "n_runs": len(rows),
        "successful_outside": outside,
        "blocked_runs": {k: len(v) for k, v in blocked.items()},
        "cite_hits": list(cites),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
