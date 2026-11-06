"""汇总 core20 矩阵：G0/G1/G1+/G2 × S/M。"""

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
CORE = set(json.loads((Path(r"<repo-root>\core20_key.json")).read_text(encoding="utf-8"))["ids"])

CELLS = {
    "G0_S": ("runs/_g0/metrics_S.jsonl", "runs/_g0/scores_S.jsonl"),
    "G0_M": ("runs/_g0/metrics_M.jsonl", "runs/_g0/scores_M.jsonl"),
    "G1_S": ("runs/metrics_G1_S_core20.jsonl", "runs/scores_G1_S_core20.jsonl"),
    "G1_M": ("runs/metrics_G1_M_core20_reused.jsonl", "runs/scores_G1_M_core20_reused.jsonl"),
    "G1+_S": ("runs/metrics_G1plus_S_core20.jsonl", "runs/scores_G1plus_S_core20.jsonl"),
    "G1+_M": ("runs/metrics_G1plus_M_core20.jsonl", "runs/scores_G1plus_M_core20.jsonl"),
    "G2_S": ("runs/metrics_G2_S_core20.jsonl", "runs/scores_G2_S_core20.jsonl"),
    "G2_M": ("runs/metrics_G2_M_core20.jsonl", "runs/scores_G2_M_core20.jsonl"),
    "G3_S": ("runs/metrics_G3_S_core20.jsonl", "runs/scores_G3_S_core20.jsonl"),
    "G3_M": ("runs/metrics_G3_M_core20.jsonl", "runs/scores_G3_M_core20.jsonl"),
    "G4_S": ("runs/metrics_G4_S_core20.jsonl", "runs/scores_G4_S_core20.jsonl"),
    "G4_M": ("runs/metrics_G4_M_core20.jsonl", "runs/scores_G4_M_core20.jsonl"),
    "G1_L": ("runs/metrics_G1_L_core20_r1.jsonl", "runs/scores_G1_L_core20_r1.jsonl"),
    "G1+_L": ("runs/metrics_G1plus_L_core20_r1.jsonl", "runs/scores_G1plus_L_core20_r1.jsonl"),
    "G2_L": ("runs/metrics_G2_L_core20_r1.jsonl", "runs/scores_G2_L_core20_r1.jsonl"),
    "G3_L": ("runs/metrics_G3_L_core20_r1.jsonl", "runs/scores_G3_L_core20_r1.jsonl"),
    "G4_L": ("runs/metrics_G4_L_core20_r1.jsonl", "runs/scores_G4_L_core20_r1.jsonl"),
}


def read(path):
    return [json.loads(l) for l in open(ROOT / path, encoding="utf-8") if l.strip()]


def main():
    result = {}
    for name, (mp, sp) in CELLS.items():
        metrics = {r["run_id"]: r for r in read(mp) if r["qid"] in CORE}
        scores = {r["run_id"]: r for r in read(sp) if r["qid"] in CORE}
        rows = [(scores[k], metrics[k]) for k in scores if k in metrics]
        if not rows:
            continue
        scores_all = [s["score"] for s, _ in rows]
        ans = [s["score"] for s, _ in rows if s.get("expected") == "answer"]
        ref = [s["score"] for s, _ in rows if s.get("expected") == "refuse"]
        ev = [s["evidence_hit"] for s, _ in rows if s.get("evidence_hit") is not None]
        cats = defaultdict(list)
        for s, _ in rows:
            cats[s["category"]].append(s["score"])
        result[name] = {
            "n": len(rows),
            "score": round(st.mean(scores_all), 3),
            "answer": round(st.mean(ans), 3) if ans else None,
            "refuse": round(st.mean(ref), 3) if ref else None,
            "evidence": round(st.mean(ev), 3) if ev else None,
            "tokens": round(st.mean(m["tokens"]["total"] for _, m in rows)),
            "seconds": round(st.mean(m["wall_ms"] for _, m in rows) / 1000, 1),
            "cost_mean": round(st.mean(m.get("cost_usd_corrected") or 0 for _, m in rows), 4),
            "cost_total": round(sum(m.get("cost_usd_corrected") or 0 for _, m in rows), 4),
            "by_category": {c: round(st.mean(v), 3) for c, v in sorted(cats.items())},
        }
    (ROOT / "runs" / "matrix_core20.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("| 格 | n | 总分 | 可答 | 应拒 | 证据 | token/次 | 秒/次 | 费用/次 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("G0_S", "G1_S", "G1+_S", "G2_S", "G3_S", "G4_S",
                 "G0_M", "G1_M", "G1+_M", "G2_M", "G3_M", "G4_M",
                 "G1_L", "G1+_L", "G2_L", "G3_L", "G4_L"):
        r = result.get(name)
        if not r:
            continue
        print(
            f"| {name} | {r['n']} | {r['score']:.3f} | {r['answer'] if r['answer'] is not None else '-'} | "
            f"{r['refuse'] if r['refuse'] is not None else '-'} | {r['evidence'] if r['evidence'] is not None else '-'} | "
            f"{r['tokens']} | {r['seconds']} | {r['cost_mean']:.5f} |"
        )
    print("\n分类别：")
    for name, r in result.items():
        print(name, r["by_category"])
    print(f"\n合计运行费用：${sum(r['cost_total'] for r in result.values()):.4f}")


if __name__ == "__main__":
    main()
