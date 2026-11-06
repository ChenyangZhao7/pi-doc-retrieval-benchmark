"""生成人工打分表：盲评，不显示打分器分数。

用法：
    python runner/make_label_sheet.py --n 20
    python runner/make_label_sheet.py --n 20 --include-negatives 5

产出：
    runs/human_label_sheet.md        给人看的表格（含题目、参考答案、证据、回答）
    runs/human_labels.template.jsonl 填写模板（score 为空）

规则：
- 分层抽样：按 qid 均匀取；
- 不包含 judge 的分数和理由，避免锚定；
- 打分标准见 docs/grading.md，只有 0 / 0.5 / 1。
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stratified(rows, n, seed):
    """按题型配额随机抽，保证覆盖 q301–q380，而不是只抽前 20 道。"""
    by_cat = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cat[r["category"]][r["qid"]].append(r)

    quotas = {"A": 5, "B": 5, "C": 5, "D": 3, "E": 2}
    if n != sum(quotas.values()):
        counts = {k: sum(len(v) for v in by_cat.get(k, {}).values()) for k in "ABCDE"}
        total = sum(counts.values()) or 1
        quotas = {k: max(1, round(n * counts[k] / total)) for k in "ABCDE"}
        keys = list("ABCDE")
        while sum(quotas.values()) > n:
            k = max(keys, key=lambda x: quotas[x])
            quotas[k] -= 1
        while sum(quotas.values()) < n:
            k = max(keys, key=lambda x: quotas[x])
            quotas[k] += 1

    rng = random.Random(seed)
    picked = []
    for cat in "ABCDE":
        qids = list(by_cat.get(cat, {}))
        rng.shuffle(qids)
        for qid in qids[: quotas[cat]]:
            picked.append(rng.choice(by_cat[cat][qid]))
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "questions" / "questions_clean.jsonl"))
    ap.add_argument("--runs", default=str(ROOT / "runs" / "metrics.jsonl"))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--include-negatives", type=int, default=0,
                    help="额外混入多少条负样本，用来检验打分器区分力")
    ap.add_argument("--seed", type=int, default=20261102)
    ap.add_argument("--sheet", default=str(ROOT / "runs" / "human_label_sheet.md"))
    ap.add_argument("--template", default=str(ROOT / "runs" / "human_labels.template.jsonl"))
    args = ap.parse_args()

    questions = {q["id"]: q for q in read_jsonl(args.questions)}
    runs = [r for r in read_jsonl(args.runs) if r.get("qid") in questions]
    for r in runs:
        r["category"] = questions[r["qid"]]["category"]
    picked = stratified(runs, args.n, args.seed)

    if args.include_negatives:
        negatives = read_jsonl(ROOT / "questions" / "negatives.jsonl")
        rng = random.Random(args.seed + 1)
        rng.shuffle(negatives)
        picked += negatives[: args.include_negatives]

    lines = [
        "# 人工打分表（盲评）",
        "",
        "> 不要看 `runs/_samples/scores_*.jsonl` 或 `runs/scores_*.jsonl`，先独立打分。",
        "> 标准见 `docs/grading.md`：只有 0 / 0.5 / 1。",
        "> 填到 `runs/human_labels.csv` 的 `score` 列，或 `runs/human_labels.template.jsonl`。",
        "",
        f"共 {len(picked)} 项。",
        "",
        "## 评分速查",
        "",
        "| 分数 | 含义 |",
        "|---|---|",
        "| 1 | 要点齐全、值正确、有可定位引用 |",
        "| 0.5 | 核心对但漏要点 / 无引用 / 有多余错误信息 |",
        "| 0 | 答错、编造、可答题拒答 |",
        "",
        "---",
        "",
    ]

    template = []
    for idx, run in enumerate(picked, 1):
        q = questions[run["qid"]]
        evidence = "\n".join(
            f"- `{e['file']}` — {e['locator']}" for e in q.get("evidence", [])
        ) or "（无，E 类题）"
        answer = (run.get("answer") or "").strip()
        lines += [
            f"## {idx}. {run.get('run_id') or run.get('id')}  [{q['category']}]",
            "",
            f"**题目**：{q['question']}",
            "",
            f"**参考答案**：{q['answer']}",
            "",
            "**证据位置**：",
            evidence,
            "",
            "**模型回答**：",
            "",
            "```text",
            answer[:4000],
            "```",
            "",
            "**评分**：☐ 0　☐ 0.5　☐ 1　　备注：________________",
            "",
            "---",
            "",
        ]
        template.append({
            "run_id": run.get("run_id") or run.get("id"),
            "qid": run["qid"],
            "category": q["category"],
            "score": None,
            "labeler": "human",
            "note": "",
        })

    Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
    Path(args.sheet).write_text("\n".join(lines), encoding="utf-8")
    with open(args.template, "w", encoding="utf-8", newline="\n") as f:
        for row in template:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"生成 {len(picked)} 项")
    print(f"  打分表: {args.sheet}")
    print(f"  模板:   {args.template}")


if __name__ == "__main__":
    main()
