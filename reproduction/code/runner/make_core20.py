"""从 G0 的 22 题里取 20 题核心集：A5/B5/C5/D2/E3。"""

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(r"<repo-root>")
G0_KEY = ROOT / "g0_22_key.json"
QUESTIONS = ROOT / "questions_all163.jsonl"
OUT_Q = ROOT / "questions_core20.jsonl"
OUT_KEY = ROOT / "core20_key.json"
ALLOC = {"A": 5, "B": 5, "C": 5, "D": 2, "E": 3}
SEED = 20261104


def main():
    qs = {q["id"]: q for q in [json.loads(l) for l in open(QUESTIONS, encoding="utf-8") if l.strip()]}
    g0_ids = json.loads(G0_KEY.read_text(encoding="utf-8"))["ids"]
    pools = {c: [] for c in "ABCDE"}
    for qid in g0_ids:
        pools[qs[qid]["category"]].append(qid)
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
        "items": [{"id": q, "category": qs[q]["category"]} for q in chosen],
    }
    OUT_KEY.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_Q, len(chosen))
    print("ids", " ".join(chosen))
    print("cats", key["category_counts"])


if __name__ == "__main__":
    main()
