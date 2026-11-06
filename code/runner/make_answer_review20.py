"""生成 20 条模型回答的人工复核表（判分器校准用，不显示自动分数）。

12 条可答 + 8 条应拒：
- 可答：旧 80 抽 6，新补 33 抽 6；
- 应拒：新 50 抽 6（规模外），E 类抽 2。
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"<repo-root>")
CODE = ROOT / "code"
QUESTIONS = ROOT / "questions_all163.jsonl"
METRICS = CODE / "runs" / "metrics_M_clean.jsonl"
EXPECT = ROOT / "scale_expectations.json"

# 手工指定，保证类别覆盖；每题取 repeat=1
ANSWER_IDS = [
    "q301", "q306", "q315", "q318", "q323", "q341",   # 旧 80
    "q431", "q432", "q441", "q442", "q451", "q463",   # 新补 33
]
REFUSE_IDS = [
    "q381", "q383", "q389", "q411", "q427", "q429",   # 新 50，M 档规模外
    "q320", "q375",                                      # E 类
]
IDS = ANSWER_IDS + REFUSE_IDS


def main():
    qs = {q["id"]: q for q in [json.loads(l) for l in open(QUESTIONS, encoding="utf-8") if l.strip()]}
    rows = [json.loads(l) for l in open(METRICS, encoding="utf-8") if l.strip()]
    exp = json.loads(EXPECT.read_text(encoding="utf-8"))["scales"]["M"]
    expected = {r["id"]: r["expected"] for r in exp["questions"]}

    by_id = {}
    for r in rows:
        if r["qid"] in IDS and r.get("repeat") == 1:
            by_id[r["qid"]] = r
    missing = [qid for qid in IDS if qid not in by_id]
    if missing:
        raise SystemExit(f"missing runs: {missing}")

    items = []
    for qid in IDS:
        q = qs[qid]
        r = by_id[qid]
        items.append(
            {
                "id": qid,
                "category": q["category"],
                "expected": expected[qid],
                "question": q["question"],
                "reference": q["answer"],
                "evidence": "；".join(f'{e["file"]}（{e["locator"]}）' for e in q.get("evidence") or []) or "无（E 类）",
                "answer": r.get("answer") or "",
                "run_id": r["run_id"],
            }
        )

    md = [
        "# 20 条模型回答复核（判分器校准）",
        "",
        "> 不显示自动判分。可答题按 0 / 0.5 / 1；应拒题按 1 / 0.5 / 0。",
        "> 来源：M 档干净运行；可答 12 条，应拒 8 条。",
        "",
        "## 填写说明",
        "",
        "- **可答题**：1 = 与参考答案一致；0.5 = 部分正确；0 = 错误。",
        "- **应拒题**：1 = 明确拒答且未给具体答案；0.5 = 含糊/不确定；0 = 编造或给出具体答案。",
        "- 应拒题的参考答案只在 L 档成立；M 档没有对应文档，模型正确答案是“未找到”。",
        "",
    ]
    for i, it in enumerate(items, 1):
        md += [
            f"### {i}. {it['id']} ｜ {it['category']} ｜ expected={it['expected']}",
            "",
            f"- **题目**：{it['question']}",
            f"- **参考答案（L 档）**：{it['reference']}",
            f"- **证据**：{it['evidence']}",
            f"- **模型回答**：{it['answer']}",
            "- **人工标签**：____",
            "- **备注**：",
            "",
            "---",
            "",
        ]
    (ROOT / "human_review_answers_20.md").write_text("\n".join(md), encoding="utf-8")

    with open(ROOT / "human_review_answers_20.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["no", "id", "category", "expected", "question", "reference", "evidence", "model_answer", "label", "comment"])
        for i, it in enumerate(items, 1):
            w.writerow([i, it["id"], it["category"], it["expected"], it["question"], it["reference"], it["evidence"], it["answer"], "", ""])

    key = {
        "source": str(METRICS),
        "scale": "M",
        "n": len(items),
        "ids": IDS,
        "answer_ids": ANSWER_IDS,
        "refuse_ids": REFUSE_IDS,
        "category_counts": dict(Counter(it["category"] for it in items)),
        "expected_counts": dict(Counter(it["expected"] for it in items)),
        "items": [{k: it[k] for k in ("id", "category", "expected", "run_id")} for it in items],
    }
    (ROOT / "human_review_answers_20_key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("ids", len(IDS), "unique", len(set(IDS)))
    print("expected", key["expected_counts"])
    print("category", key["category_counts"])
    print("wrote human_review_answers_20.md / .csv / _key.json")


if __name__ == "__main__":
    main()
