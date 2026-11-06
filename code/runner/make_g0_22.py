"""生成 G0 的 22 题固定样本：A5/B5/C5/D2/E5，全部来自 S 档可答子集（E 除外）。"""

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(r"<repo-root>")
QUESTIONS = ROOT / "questions_all163.jsonl"
EXPECT = ROOT / "scale_expectations.json"
OUT_Q = ROOT / "questions_g0_22.jsonl"
OUT_KEY = ROOT / "g0_22_key.json"
SEED = 20261104
ALLOC = {"A": 5, "B": 5, "C": 5, "D": 2, "E": 5}


def main():
    qs = {q["id"]: q for q in [json.loads(l) for l in open(QUESTIONS, encoding="utf-8") if l.strip()]}
    exp = json.loads(EXPECT.read_text(encoding="utf-8"))["scales"]["S"]
    expected = {r["id"]: r["expected"] for r in exp["questions"]}

    pools = {c: [] for c in "ABCDE"}
    for qid, q in qs.items():
        c = q["category"]
        if c == "E":
            pools[c].append(qid)
        elif expected.get(qid) == "answer":
            pools[c].append(qid)
    for c in pools:
        pools[c].sort()

    rng = random.Random(SEED)
    chosen = []
    for c, n in ALLOC.items():
        if len(pools[c]) < n:
            raise SystemExit(f"{c}: need {n}, only {len(pools[c])}")
        chosen.extend(rng.sample(pools[c], n))
    chosen.sort(key=lambda x: int(x[1:]))

    with open(OUT_Q, "w", encoding="utf-8") as f:
        for qid in chosen:
            f.write(json.dumps(qs[qid], ensure_ascii=False) + "\n")
    key = {
        "seed": SEED,
        "allocation": ALLOC,
        "n": len(chosen),
        "ids": chosen,
        "category_counts": dict(Counter(qs[q]["category"] for q in chosen)),
        "expected_S": dict(Counter(expected.get(q, "refuse") for q in chosen)),
        "items": [{"id": q, "category": qs[q]["category"], "expected_S": expected.get(q, "refuse")} for q in chosen],
    }
    OUT_KEY.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_Q, len(chosen))
    print("ids", " ".join(chosen))
    print("cats", key["category_counts"])
    print("expected", key["expected_S"])


if __name__ == "__main__":
    main()
