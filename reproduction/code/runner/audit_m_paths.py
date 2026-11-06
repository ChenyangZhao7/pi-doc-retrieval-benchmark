"""审计 M 档运行是否越界读取 S/L 或其他目录。"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"<repo-root>\code")

PATH_KEYS = {"path", "file", "file_path", "filepath", "dir", "directory", "cwd"}
EXTERNAL_PATTERNS = [
    re.compile(r"pi-docbench[\\/]+[SL][\\/]", re.I),
    re.compile(r"(^|[\\/])[SL][\\/][0-9]{6}_"),
    re.compile(r"(^|[\\/])\.\.([\\/]|$)"),
    re.compile(r"Z:[\\/]+pi-docbench[\\/]*$", re.I),
]
ANSWER_PATTERNS = [
    re.compile(r"pi-docbench[\\/]+[SL][\\/]", re.I),
    re.compile(r"(^|[\s`(（])[SL][\\/][0-9]{6}_"),
    re.compile(r"Z:[\\/]+pi-docbench[\\/]+[SL][\\/]", re.I),
]


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default=str(ROOT / "runs" / "metrics_M.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "runs" / "audit_M_paths.json"))
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(args.metrics, encoding="utf-8") if l.strip()]
    flagged = {}
    reasons = Counter()
    by_q = defaultdict(int)
    for r in rows:
        old_root = "<corpus-root>/s"
        new_root = "<repo-root>/m"
        allow = old_root if r.get("reused_from") else new_root
        hits = []
        for call in r.get("tool_calls") or []:
            args = call.get("args") or {}
            for k, v in args.items():
                if not isinstance(v, str):
                    continue
                s = v.replace("\\", "/").lower()
                is_abs = len(s) >= 3 and s[1] == ":" and s[2] == "/"
                if is_abs and not (s.startswith(allow) or s == allow.rstrip("/")):
                    hits.append((call.get("name"), k, v))
                elif ".." in s.split("/"):
                    hits.append((call.get("name"), k, v))
        answer = (r.get("answer") or "").replace("\\", "/").lower()
        for pat in ANSWER_PATTERNS:
            m = pat.search(answer)
            if m and not (r.get("reused_from") and "pi_bench/s" in m.group(0)):
                hits.append(("answer", "citation", m.group(0)))
                break
        if hits:
            flagged[r["run_id"]] = hits
            by_q[r["qid"]] += 1
            for h in hits:
                reasons[h[0]] += 1
    print("runs", len(rows), "flagged", len(flagged), "qids", len(by_q))
    print("by tool", dict(reasons))
    print("flagged qids:", sorted(by_q.items(), key=lambda x: (-x[1], x[0])))
    print("\nexamples:")
    for rid, hits in list(flagged.items())[:15]:
        print(" ", rid)
        for h in hits[:3]:
            print("    ", h)
    out = Path(args.out)
    out.write_text(json.dumps({
        "n_runs": len(rows),
        "n_flagged": len(flagged),
        "by_qid": dict(sorted(by_q.items())),
        "details": {k: v for k, v in flagged.items()},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
