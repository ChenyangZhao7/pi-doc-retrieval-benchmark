"""把剩余 63 道 candidate 题标为 official（用户确认可跳过逐题复核）。"""

import json
from collections import Counter
from pathlib import Path

P = Path(r"<repo-root>\questions_all163.jsonl")
TODAY = "2026-11-04"


def main():
    qs = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()]
    n = 0
    for q in qs:
        if q.get("status") == "candidate":
            q["status"] = "official"
            q["official"] = True
            q["approved_by"] = "user"
            q["approved_at"] = TODAY
            q["review_note"] = "用户确认：剩余 63 题可直接 official，未逐题人工复核。"
            n += 1
    with open(P, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print("promoted", n)
    print("status", dict(Counter(q["status"] for q in qs)))
    print("official", sum(1 for q in qs if q.get("official")))


if __name__ == "__main__":
    main()
