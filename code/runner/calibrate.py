"""比较标注与 LLM 打分器的一致率（默认是助手预标注，不是人工）。

用法：
    python runner/calibrate.py --labels runs/prelabels_assistant.jsonl --scores runs/scores.jsonl
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="runs/prelabels_assistant.jsonl")
    ap.add_argument("--scores", default="runs/scores.jsonl")
    ap.add_argument("--min-agreement", type=float, default=0.85)
    args = ap.parse_args()

    labels = {r["run_id"]: r for r in read_jsonl(args.labels)}
    scores = {r["run_id"]: r for r in read_jsonl(args.scores)}

    common = sorted(set(labels) & set(scores))
    missing_scores = sorted(set(labels) - set(scores))
    missing_labels = sorted(set(scores) - set(labels))

    agree = 0
    diffs = []
    by_cat = defaultdict(lambda: [0, 0])

    for run_id in common:
        human = labels[run_id]["score"]
        judge = scores[run_id]["score"]
        cat = labels[run_id].get("category", scores[run_id].get("category", "?"))
        by_cat[cat][1] += 1
        if human == judge:
            agree += 1
            by_cat[cat][0] += 1
        else:
            diffs.append((run_id, human, judge, scores[run_id].get("reason", "")))

    total = len(common)
    rate = agree / total if total else 0

    print(f"可比较: {total} 条")
    if missing_scores:
        print(f"缺少打分: {len(missing_scores)} 条")
    if missing_labels:
        print(f"缺少人工标签: {len(missing_labels)} 条")
    print()
    for cat in sorted(by_cat):
        a, n = by_cat[cat]
        print(f"{cat}: {a}/{n} = {a / n:.0%}")
    print(f"\n总体一致率: {agree}/{total} = {rate:.1%}")
    print(f"门槛: {args.min_agreement:.0%} -> {'通过' if rate >= args.min_agreement else '未通过'}")

    if diffs:
        print("\n不一致明细：")
        for run_id, human, judge, reason in diffs:
            print(f"- {run_id}: 人工 {human} / 打分器 {judge}")
            print(f"  理由: {reason}")


if __name__ == "__main__":
    main()
