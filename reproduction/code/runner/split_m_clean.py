"""拆分 M 干净指标。"""

import json
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
METRICS = ROOT / "runs" / "metrics_M_clean.jsonl"
EXP = Path(r"<repo-root>\scale_expectations.json")


def main():
    rows = [json.loads(l) for l in open(METRICS, encoding="utf-8") if l.strip()]
    exp = json.loads(EXP.read_text(encoding="utf-8"))["scales"]["M"]
    expected = {r["id"]: r["expected"] for r in exp["questions"]}
    groups = {
        "metrics_M_clean_new33.jsonl": [r for r in rows if 431 <= int(r["qid"][1:]) <= 463],
        "metrics_M_clean_refuse.jsonl": [r for r in rows if expected.get(r["qid"]) == "refuse"],
        "metrics_M_clean_answer.jsonl": [r for r in rows if expected.get(r["qid"]) == "answer"],
    }
    for name, data in groups.items():
        p = ROOT / "runs" / name
        with open(p, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(name, len(data))
    print("total", len(rows))


if __name__ == "__main__":
    main()
