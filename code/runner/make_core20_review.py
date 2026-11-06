#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为 core20 的某一组生成 20 条盲评表（不显示自动分）。

用法：
    python runner/make_core20_review.py --runs runs/metrics_G3_L_core20_r1.jsonl \
        --sheet <repo-root>/review_G3_L.md \
        --template <repo-root>/review_G3_L.template.jsonl
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT.parent / "questions_core20.jsonl"


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--template", required=True)
    args = ap.parse_args()

    questions = read_jsonl(QUESTIONS)
    runs = {r["run_id"]: r for r in read_jsonl(args.runs)}
    picked = []
    for q in questions:
        run = runs.get(f"{Path(args.runs).stem.split('_')[0]}_{q['id']}_r1")
        if run is None:
            # 兼容 group 名里带 + 的情况：按 qid + repeat=1 找
            cand = [r for r in runs.values() if r["qid"] == q["id"] and r.get("repeat") == 1]
            run = cand[0] if cand else None
        if run is None:
            raise SystemExit(f"missing run for {q['id']}")
        picked.append((q, run))

    md = [
        "# 20 条模型回答复核（盲评）",
        "",
        f"> 来源：`{args.runs}`",
        "> 不显示自动判分。可答题按 0 / 0.5 / 1；应拒题按 1 / 0.5 / 0。",
        "",
        "## 填写说明",
        "",
        "- **可答题**：1 = 与参考答案一致；0.5 = 部分正确；0 = 错误。",
        "- **应拒题**：1 = 明确拒答且未给具体答案；0.5 = 含糊/不确定；0 = 编造或给出具体答案。",
        "",
        "---",
        "",
    ]
    template = []
    for i, (q, run) in enumerate(picked, 1):
        ev = "\n".join(
            f"- `{e['file']}` — {e['locator']}" for e in (q.get("evidence") or [])
        ) or "（无，E 类题）"
        md += [
            f"## {i}. {run['run_id']}  [{q['category']}]",
            "",
            f"**题目**：{q['question']}",
            "",
            f"**参考答案**：{q['answer']}",
            "",
            "**证据位置**：",
            ev,
            "",
            "**模型回答**：",
            "",
            "```text",
            (run.get("answer") or "")[:4000],
            "```",
            "",
            "**评分**：☐ 0　☐ 0.5　☐ 1　　备注：________________",
            "",
            "---",
            "",
        ]
        template.append(
            {
                "run_id": run["run_id"],
                "qid": q["id"],
                "category": q["category"],
                "score": None,
                "labeler": "human",
                "note": "",
            }
        )

    Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
    Path(args.sheet).write_text("\n".join(md), encoding="utf-8")
    with open(args.template, "w", encoding="utf-8", newline="\n") as f:
        for row in template:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"生成 {len(picked)} 项")
    print(f"  打分表: {args.sheet}")
    print(f"  模板:   {args.template}")


if __name__ == "__main__":
    main()
