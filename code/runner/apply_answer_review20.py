"""记录 20 条人工标签（用户判断全 1），并与自动判分比较。"""

import csv
import json
from pathlib import Path

ROOT = Path(r"<repo-root>")
CODE = ROOT / "code"
KEY = ROOT / "human_review_answers_20_key.json"
CSV = ROOT / "human_review_answers_20.csv"
TODAY = "2026-11-04"

import sys
sys.path.insert(0, str(CODE / "runner"))
from grade_scaled import score_refuse


def main():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    ids = key["ids"]
    qs = {q["id"]: q for q in [json.loads(l) for l in open(ROOT / "questions_all163.jsonl", encoding="utf-8") if l.strip()]}
    exp = {r["id"]: r["expected"] for r in json.loads((ROOT / "scale_expectations.json").read_text(encoding="utf-8"))["scales"]["M"]["questions"]}
    metrics = {r["run_id"]: r for r in [json.loads(l) for l in open(CODE / "runs" / "metrics_M_clean.jsonl", encoding="utf-8") if l.strip()]}

    def read_scores(name):
        p = CODE / "runs" / name
        return {r["run_id"]: r for r in [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]} if p.exists() else {}

    reused = read_scores("scores_M_reused.jsonl")
    calib6 = read_scores("scores_M_calib6.jsonl")

    rows = []
    for qid in ids:
        rid = "G1_M_" + qid + "_r1"
        if exp[qid] == "refuse":
            auto = score_refuse(qs[qid], metrics[rid], ROOT / "M", "refuse")["score"]
            source = "rule"
        else:
            s = reused.get(rid) or calib6.get(rid)
            auto = s["score"] if s else None
            source = "reused" if rid in reused else ("calib6" if rid in calib6 else "missing")
        rows.append({"id": qid, "expected": exp[qid], "human": 1, "auto": auto, "source": source})

    exact = sum(1 for r in rows if r["auto"] == 1)
    acceptable = sum(1 for r in rows if r["auto"] is not None and r["auto"] >= 0.5)
    disagreements = [r for r in rows if r["auto"] != 1]

    # 填 CSV
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.DictReader(f))
        fields = list(csv_rows[0].keys()) if csv_rows else []
    for row in csv_rows:
        row["label"] = "1"
        if row["id"] == "q375":
            row["comment"] = "人工 1；自动 0.5：回答明确拒答，但补充了行业销量百分比。"
    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    result = {
        "reviewed_at": TODAY,
        "reviewer": "user",
        "n": len(rows),
        "human_labels": "all 1",
        "auto_exact": f"{exact}/{len(rows)} = {exact / len(rows):.1%}",
        "auto_acceptable": f"{acceptable}/{len(rows)} = {acceptable / len(rows):.1%}",
        "disagreements": disagreements,
        "items": rows,
    }
    (ROOT / "human_review_answers_20_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = [
        "# 20 条模型回答复核结果（判分器校准）",
        "",
        f"- 复核人：user；日期：{TODAY}",
        "- 人工标签：**20 条全部为 1**",
        f"- 自动判分完全一致：**{exact}/20 = {exact / 20:.1%}**",
        f"- 含 0.5 可接受：**{acceptable}/20 = {acceptable / 20:.1%}**",
        "- 任务书要求：≥85%",
        "",
        "## 分歧",
        "",
    ]
    if disagreements:
        for r in disagreements:
            md.append(f"- {r['id']}：人工 1，自动 {r['auto']}；{r['source']}")
    else:
        md.append("- 无")
    md += [
        "",
        "q375 的自动 0.5 是因为回答在拒答后又补充了行业销量百分比；人工认为仍算正确拒答。",
        "",
    ]
    (ROOT / "human_review_answers_20_result.md").write_text("\n".join(md), encoding="utf-8")

    print(f"exact {exact}/20 = {exact / 20:.1%}")
    print(f"acceptable {acceptable}/20 = {acceptable / 20:.1%}")
    print("disagreements", disagreements)
    print("wrote result md/json and updated csv")


if __name__ == "__main__":
    main()
