"""比较多个打分器（以及预标注/人工标注）的一致率。

用法：
    python runner/compare_judges.py
    python runner/compare_judges.py --scores runs/scores.jsonl runs/scores_moonshot.jsonl
    python runner/compare_judges.py --labels runs/prelabels_assistant.jsonl

输出：
- 两两完全一致率、相邻一致率（差 0.5 以内）、平均绝对差；
- 线性加权 kappa（0.5 档位的分歧按半错处理）；
- 分题型一致率；
- 不一致明细（含两边理由，便于人工裁决）。
"""

import argparse
import itertools
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


def weighted_kappa(pairs, categories=(0, 0.5, 1)):
    """线性加权 Cohen's kappa。pairs 是 [(a, b), ...]。"""
    n = len(pairs)
    if not n:
        return None
    idx = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    obs = [[0.0] * k for _ in range(k)]
    for a, b in pairs:
        obs[idx[a]][idx[b]] += 1
    total = float(n)
    # 观测一致度（线性权重）
    po = 0.0
    for i in range(k):
        for j in range(k):
            w = 1 - abs(i - j) / (k - 1)
            po += w * obs[i][j] / total
    rows = [sum(obs[i]) / total for i in range(k)]
    cols = [sum(obs[i][j] for i in range(k)) / total for j in range(k)]
    pe = 0.0
    for i in range(k):
        for j in range(k):
            w = 1 - abs(i - j) / (k - 1)
            pe += w * rows[i] * cols[j]
    if pe >= 1:
        return 1.0
    return (po - pe) / (1 - pe)


def compare(name_a, rows_a, name_b, rows_b):
    a = {r["run_id"]: r for r in rows_a}
    b = {r["run_id"]: r for r in rows_b if r.get("valid") is not False}
    excluded = [r["run_id"] for r in rows_b if r.get("valid") is False]
    if excluded:
        print(f"\n{name_b}: 排除无效标签 {len(excluded)} 条 -> {', '.join(sorted(excluded)[:5])}")
    common = sorted(set(a) & set(b))
    if not common:
        print(f"{name_a} vs {name_b}: 没有共同的 run_id")
        return

    pairs = [(a[r]["score"], b[r]["score"]) for r in common]
    exact = sum(1 for x, y in pairs if x == y)
    adjacent = sum(1 for x, y in pairs if abs(x - y) <= 0.5)
    mad = sum(abs(x - y) for x, y in pairs) / len(pairs)
    kappa = weighted_kappa(pairs)

    print(f"\n=== {name_a} vs {name_b} ===")
    print(f"共同样本: {len(common)}")
    print(f"完全一致: {exact}/{len(common)} = {exact / len(common):.1%}")
    print(f"相邻一致: {adjacent}/{len(common)} = {adjacent / len(common):.1%}")
    print(f"平均绝对差: {mad:.3f}")
    if kappa is not None:
        print(f"线性加权 kappa: {kappa:.3f}")

    # 分题型
    by_cat = defaultdict(lambda: [0, 0])
    for r in common:
        cat = a[r].get("category", "?")
        by_cat[cat][1] += 1
        if a[r]["score"] == b[r]["score"]:
            by_cat[cat][0] += 1
    print("分题型完全一致率: " + "  ".join(
        f"{cat} {hit}/{n} ({hit / n:.0%})" for cat, (hit, n) in sorted(by_cat.items())
    ))

    # 分布
    for name, rows in ((name_a, a), (name_b, b)):
        dist = defaultdict(int)
        for r in common:
            dist[rows[r]["score"]] += 1
        print(f"  {name} 分布: " + ", ".join(f"{k}:{v}" for k, v in sorted(dist.items())))

    diffs = [(r, a[r]["score"], b[r]["score"]) for r in common if a[r]["score"] != b[r]["score"]]
    if diffs:
        print("不一致明细:")
        for run_id, sa, sb in diffs:
            print(f"- {run_id}: {name_a}={sa} / {name_b}={sb}")
            print(f"    {name_a}: {a[run_id].get('reason', '')[:160]}")
            print(f"    {name_b}: {b[run_id].get('reason', '')[:160]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", nargs="+", default=None)
    ap.add_argument("--labels", default=None,
                    help="标注文件；默认预标注不是人工校准，人工结果请另存 human_labels.jsonl")
    args = ap.parse_args()

    paths = args.scores or [
        p for p in ("runs/scores.jsonl", "runs/scores_moonshot.jsonl") if Path(p).exists()
    ]
    if not paths:
        raise SystemExit("没有找到打分结果文件")

    data = {Path(p).stem.replace("scores_", "").replace("scores", "deepseek"): read_jsonl(p)
            for p in paths}
    if args.labels:
        data["human"] = read_jsonl(args.labels)

    names = list(data)
    for name_a, name_b in itertools.combinations(names, 2):
        compare(name_a, data[name_a], name_b, data[name_b])


if __name__ == "__main__":
    main()
