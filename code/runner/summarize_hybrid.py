#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总 hybrid 正式表（G3h/G4h，S/M/L，1 次重复）。"""

import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CELLS = {
    "G3h_S": ("metrics_G3h_S_core20_r1.jsonl", "scores_G3h_S_core20_r1.jsonl"),
    "G3h_M": ("metrics_G3h_M_core20_r1.jsonl", "scores_G3h_M_core20_r1.jsonl"),
    "G3h_L": ("metrics_G3h_L_core20_r1.jsonl", "scores_G3h_L_core20_r1.jsonl"),
    "G4h_S": ("metrics_G4h_S_core20_r1.jsonl", "scores_G4h_S_core20_r1.jsonl"),
    "G4h_M": ("metrics_G4h_M_core20_r1.jsonl", "scores_G4h_M_core20_r1.jsonl"),
    "G4h_L": ("metrics_G4h_L_core20_r1.jsonl", "scores_G4h_L_core20_r1.jsonl"),
}


def read(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    out = {}
    for name, (mf, sf) in CELLS.items():
        metrics = read(ROOT / "runs" / mf)
        scores = read(ROOT / "runs" / sf)
        raw = st.mean(r["score"] for r in scores)
        fixed = st.mean(1.0 if r["category"] == "E" and r["score"] < 1 else r["score"] for r in scores)
        cats = defaultdict(list)
        for r in scores:
            cats[r["category"]].append(r["score"])
        out[name] = {
            "n": len(scores),
            "score": round(raw, 3),
            "e_fixed": round(fixed, 3),
            "tokens": round(st.mean(r["tokens"]["total"] for r in metrics)),
            "seconds": round(st.mean(r["wall_ms"] for r in metrics) / 1000, 1),
            "cost_mean": round(st.mean(r.get("cost_usd_corrected") or 0 for r in metrics), 4),
            "cost_total": round(sum(r.get("cost_usd_corrected") or 0 for r in metrics), 4),
            "judge_cost": round(sum(r.get("judge_cost_usd") or 0 for r in scores), 4),
            "by_category": {k: round(st.mean(v), 3) for k, v in sorted(cats.items())},
        }

    (ROOT / "runs" / "matrix_hybrid.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with open(ROOT.parent / "report" / "hybrid_core20.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "n", "score", "e_fixed", "tokens", "seconds", "cost_mean", "cost_total", "A", "B", "C", "D", "E"])
        for name, r in out.items():
            c = r["by_category"]
            w.writerow([name, r["n"], r["score"], r["e_fixed"], r["tokens"], r["seconds"],
                        r["cost_mean"], r["cost_total"], c.get("A"), c.get("B"), c.get("C"), c.get("D"), c.get("E")])
    print("| cell | n | raw | E-fixed | token | sec | $/run |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name, r in out.items():
        print(f"| {name} | {r['n']} | {r['score']:.3f} | {r['e_fixed']:.3f} | {r['tokens']} | {r['seconds']} | {r['cost_mean']:.4f} |")
    print("run total", round(sum(r["cost_total"] for r in out.values()), 4),
          "judge total", round(sum(r["judge_cost"] for r in out.values()), 4))


if __name__ == "__main__":
    main()
