"""清理 q366 的 recheck 标记（参考答案已修正，模型回答一致）。"""

import json
from pathlib import Path

P = Path(r"<repo-root>\questions_all163.jsonl")
RESULT = Path(r"<repo-root>\human_review_40_result.json")


def main():
    qs = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()]
    for q in qs:
        if q["id"] == "q366":
            q["recheck_needed"] = False
            q["review_resolved"] = True
            q["review_note"] = (
                "2026-11-04 用户确认清理：联创光电净利润已由 1.16 亿元更正为 "
                "4.80 亿元（480,172,675.11 元）；模型三条回答均为 4.80 亿元。"
            )
            print("q366 cleared", {k: q.get(k) for k in ("recheck_needed", "review_resolved", "review_label")})
    with open(P, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    if RESULT.exists():
        data = json.loads(RESULT.read_text(encoding="utf-8"))
        data.setdefault("revisions", {})["q366_resolved"] = True
        data["q366_note"] = "参考答案已修正；模型回答一致；用户确认清理 recheck 标记。"
        RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", P)


if __name__ == "__main__":
    main()
