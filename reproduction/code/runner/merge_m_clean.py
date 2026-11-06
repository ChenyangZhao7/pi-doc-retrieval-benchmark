"""合并 M 档干净指标：旧 240 复用 + 带 guard 的新 249。"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
PARTS = [
    ROOT / "runs" / "metrics_M_reused.jsonl",
    ROOT / "runs" / "metrics_M_new_v2.jsonl",
]
OUT = ROOT / "runs" / "metrics_M_clean.jsonl"


def main():
    rows = {}
    for p in PARTS:
        part = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        print(p.name, len(part))
        for r in part:
            rows[r["run_id"]] = r
    out = sorted(rows.values(), key=lambda r: (r["qid"], r.get("repeat", 0)))
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("merged", len(out), OUT)
    print("qids", len({r["qid"] for r in out}))
    print("repeats", dict(sorted(Counter(r.get("repeat") for r in out).items())))
    print("cost", round(sum(r.get("cost_usd_corrected") or 0 for r in out), 4))


if __name__ == "__main__":
    main()
