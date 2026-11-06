"""用负样本检查打分器的区分力。

负样本是人工构造的坏答案，预期分数已知。打分器把它们判成预期分数，
才说明它不只是"看到答案就给 1"。

用法：
    python runner/check_discrimination.py \
        --expected questions/negatives.jsonl \
        --scores runs/scores_neg.jsonl

输出：
- 完全一致率、相邻一致率；
- 每个缺陷类型的判对情况；
- 漏判（expected < 1 但打分器给 1）——最危险；
- 误判（expected = 1 但打分器扣分）。
"""

import argparse
import json
from collections import defaultdict


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
    ap.add_argument("--expected", default="questions/negatives.jsonl")
    ap.add_argument("--scores", default="runs/scores_neg.jsonl")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    expected = {r["id"]: r for r in read_jsonl(args.expected)}
    scores = {r["run_id"]: r for r in read_jsonl(args.scores)}

    common = sorted(set(expected) & set(scores))
    missing = sorted(set(expected) - set(scores))
    if missing:
        print(f"未打分: {len(missing)} 条 -> {', '.join(missing[:5])}")

    exact = 0
    adjacent = 0
    false_neg = []   # 该扣分却没扣
    false_pos = []   # 不该扣却扣了
    by_defect = defaultdict(lambda: [0, 0])

    for sid in common:
        exp = expected[sid]["expected_score"]
        got = scores[sid]["score"]
        defect = expected[sid].get("defect", "?")
        by_defect[defect][1] += 1
        if exp == got:
            exact += 1
            by_defect[defect][0] += 1
        elif abs(exp - got) <= 0.5:
            adjacent += 1
        if exp < 1 and got == 1:
            false_neg.append((sid, exp, got, defect))
        if exp == 1 and got < 1:
            false_pos.append((sid, exp, got, defect))

    n = len(common)
    print(f"\n负样本 {n} 条")
    print(f"完全一致: {exact}/{n} = {exact / n:.1%}" if n else "没有可比较的样本")
    if n:
        print(f"相邻一致: {(exact + adjacent)}/{n} = {(exact + adjacent) / n:.1%}")
    print(f"漏判（该扣未扣）: {len(false_neg)}")
    print(f"误判（不该扣却扣）: {len(false_pos)}")

    print("\n按缺陷类型:")
    for defect, (hit, total) in sorted(by_defect.items(), key=lambda x: -x[1][1]):
        print(f"  {defect:12} {hit}/{total}")

    if false_neg:
        print("\n漏判明细（最需要修）:")
        for sid, exp, got, defect in false_neg:
            print(f"- {sid} [{defect}] 预期 {exp} / 打分 {got}")
            print(f"  理由: {scores[sid].get('reason', '')[:180]}")

    if false_pos:
        print("\n误判明细:")
        for sid, exp, got, defect in false_pos:
            print(f"- {sid} [{defect}] 预期 {exp} / 打分 {got}")
            print(f"  理由: {scores[sid].get('reason', '')[:180]}")

    if args.verbose:
        print("\n全部样本:")
        for sid in common:
            exp = expected[sid]["expected_score"]
            got = scores[sid]["score"]
            mark = "OK " if exp == got else "XX "
            print(f"{mark}{sid} 预期 {exp} / 打分 {got}  {expected[sid].get('defect','')}")


if __name__ == "__main__":
    main()
