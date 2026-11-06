"""从 matrix_core20.json 生成对比 CSV。"""

import csv
import json
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
OUT = Path(r"<repo-root>\report\comparison_core20.csv")
m = json.loads((ROOT / "runs" / "matrix_core20.json").read_text(encoding="utf-8"))
order = ["G0_S", "G1_S", "G1+_S", "G2_S", "G3_S", "G4_S",
         "G0_M", "G1_M", "G1+_M", "G2_M", "G3_M", "G4_M",
         "G1_L", "G1+_L", "G2_L", "G3_L", "G4_L"]
with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cell", "n", "score", "answer", "refuse", "evidence", "tokens", "seconds",
                "cost_mean", "cost_total", "A", "B", "C", "D", "E"])
    for name in order:
        r = m[name]
        c = r["by_category"]
        w.writerow([name, r["n"], r["score"], r["answer"], r["refuse"], r["evidence"],
                    r["tokens"], r["seconds"], r["cost_mean"], r["cost_total"],
                    c.get("A"), c.get("B"), c.get("C"), c.get("D"), c.get("E")])
print("wrote", OUT)
print("run total", round(sum(m[n]['cost_total'] for n in order), 4))
