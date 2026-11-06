"""合并 M 档复用指标与新增指标。"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
PARTS = [
    ROOT / "runs" / "metrics_M_reused.jsonl",
    ROOT / "runs" / "metrics_M_new.jsonl",
]
OUT = ROOT / "runs" / "metrics_M.jsonl"


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    rows = {}
    for p in PARTS:
        part = read_jsonl(p)
        print(f"{p.name}: {len(part)}")
        for r in part:
            rows[r["run_id"]] = r
    out = sorted(rows.values(), key=lambda r: (r["qid"], r.get("repeat", 0)))
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"merged: {len(out)} -> {OUT}")
    print("qids:", len({r["qid"] for r in out}))
    print("repeats:", dict(sorted(Counter(r.get("repeat") for r in out).items())))
    print("scales:", dict(Counter(r.get("scale") for r in out)))
    print("groups:", dict(Counter(r.get("group") for r in out)))
    missing = [f"q{i}" for i in range(301, 464) if f"q{i}" not in {r["qid"] for r in out}]
    print("missing qids:", missing)
    print("cost total:", round(sum(r.get("cost_usd_corrected") or 0 for r in out), 4))


if __name__ == "__main__":
    main()
