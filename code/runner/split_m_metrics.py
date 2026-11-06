"""把 M 档指标拆成：新补 33 题（需新判分）与应拒题（规则判分）。"""

import json
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
METRICS = ROOT / "runs" / "metrics_M.jsonl"
EXP = Path(r"<repo-root>\scale_expectations.json")


def main():
    rows = [json.loads(l) for l in open(METRICS, encoding="utf-8") if l.strip()]
    exp = json.loads(EXP.read_text(encoding="utf-8"))["scales"]["M"]
    expected = {r["id"]: r["expected"] for r in exp["questions"]}

    new33 = [r for r in rows if 431 <= int(r["qid"][1:]) <= 463]
    refuse = [r for r in rows if expected.get(r["qid"]) == "refuse"]
    answer = [r for r in rows if expected.get(r["qid"]) == "answer"]

    for name, data in [
        ("metrics_M_new33.jsonl", new33),
        ("metrics_M_refuse.jsonl", refuse),
        ("metrics_M_answer.jsonl", answer),
    ]:
        p = ROOT / "runs" / name
        with open(p, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(name, len(data))
    print("total", len(rows))


if __name__ == "__main__":
    main()
