"""合并 M 档三部分判分：旧 70 题复用、新 33 题、180 条应拒题。"""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
PARTS = [
    ROOT / "runs" / "scores_M_reused.jsonl",
    ROOT / "runs" / "scores_M_new33.jsonl",
    ROOT / "runs" / "scores_M_refuse.jsonl",
]
METRICS = ROOT / "runs" / "metrics_M.jsonl"
OUT = ROOT / "runs" / "scores_scaled_M.jsonl"


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    merged = {}
    for p in PARTS:
        rows = read_jsonl(p)
        print(f"{p.name}: {len(rows)}")
        for r in rows:
            merged[r["run_id"]] = r
    rows = sorted(merged.values(), key=lambda r: (r["qid"], r["run_id"]))
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    metric_ids = {r["run_id"] for r in read_jsonl(METRICS)}
    score_ids = {r["run_id"] for r in rows}
    print(f"merged: {len(rows)} -> {OUT}")
    print("missing scores:", len(metric_ids - score_ids))
    print("extra scores:", len(score_ids - metric_ids))
    print("expected:", dict(Counter(r.get("expected") for r in rows)))
    print("score dist:", dict(Counter(r.get("score") for r in rows)))
    by = defaultdict(list)
    for r in rows:
        by[r.get("expected")].append(r["score"])
    for k, v in by.items():
        print(f"  {k}: n={len(v)} mean={sum(v) / len(v):.3f}")
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r["score"])
    print("by category:", {k: f"{len(v)}/{sum(v) / len(v):.3f}" for k, v in sorted(by_cat.items())})


if __name__ == "__main__":
    main()
