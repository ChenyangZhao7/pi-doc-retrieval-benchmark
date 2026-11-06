"""按当前解析规则重算 evidence_hit，不重新调用 API。"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import evidence_hit  # noqa: E402


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True)
    ap.add_argument("--questions", default="questions/official_80.jsonl")
    ap.add_argument("--runs", default="runs/metrics.jsonl")
    ap.add_argument("--corpus", default=r"<corpus-root>\S")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    qs = {q["id"]: q for q in read_jsonl(args.questions)}
    runs = {r["run_id"]: r for r in read_jsonl(args.runs)}
    rows = read_jsonl(args.scores)

    before = [r["evidence_hit"] for r in rows if r.get("evidence_hit") is not None]
    for r in rows:
        q = qs.get(r["qid"])
        run = runs.get(r["run_id"])
        if q and run:
            r["evidence_hit"] = evidence_hit(r, q, run, args.corpus)

    after = [r["evidence_hit"] for r in rows if r.get("evidence_hit") is not None]
    avg = lambda xs: sum(xs) / len(xs) if xs else 0
    print(f"evidence mean {avg(before):.3f} -> {avg(after):.3f}")

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
