"""汇总判分结果与运行指标，按题型出表。

用法：
    python runner/summarize_scores.py \
        --scores runs/_grade/scores_final.jsonl \
        --runs runs/metrics.jsonl \
        --out runs/_grade/summary.json
"""

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default="runs/_grade/scores_final.jsonl")
    ap.add_argument("--runs", default="runs/metrics.jsonl")
    ap.add_argument("--out", default="runs/_grade/summary.json")
    args = ap.parse_args()

    metrics = {r["run_id"]: r for r in read_jsonl(args.runs)}
    scores = {r["run_id"]: r for r in read_jsonl(args.scores)}

    joined = []
    for rid, s in scores.items():
        m = metrics.get(rid)
        if not m:
            continue
        joined.append((s, m))

    by_cat = defaultdict(list)
    for s, m in joined:
        by_cat[s["category"]].append((s, m))

    def agg(items):
        ev = [s["evidence_hit"] for s, _ in items if s.get("evidence_hit") is not None]
        return {
            "n": len(items),
            "score_mean": round(st.mean(s["score"] for s, _ in items), 3),
            "score_min": min(s["score"] for s, _ in items),
            "score_max": max(s["score"] for s, _ in items),
            "evidence_mean": round(st.mean(ev), 3) if ev else None,
            "turns_mean": round(st.mean(m["turns"] for _, m in items), 1),
            "tools_mean": round(st.mean(m["tool_calls_total"] for _, m in items), 1),
            "tokens_mean": round(st.mean(m["tokens"]["total"] for _, m in items)),
            "seconds_mean": round(st.mean(m["wall_ms"] for _, m in items) / 1000, 1),
            "cost_mean_usd": round(st.mean(
                m.get("cost_usd_corrected") or 0 for _, m in items), 5),
            "cost_total_usd": round(sum(
                m.get("cost_usd_corrected") or 0 for _, m in items), 4),
        }

    report = {cat: agg(by_cat[cat]) for cat in sorted(by_cat)}
    report["ALL"] = agg(joined)

    print("%-4s %4s %6s %8s %7s %8s %9s %7s %8s" % (
        "类", "n", "得分", "证据", "轮", "工具", "token", "秒", "费用$"))
    for cat in list(report):
        r = report[cat]
        ev = f"{r['evidence_mean']:.3f}" if r["evidence_mean"] is not None else "n/a"
        print("%-4s %4d %6.3f %8s %7.1f %8.1f %9d %7.1f %8.5f" % (
            cat, r["n"], r["score_mean"], ev,
            r["turns_mean"], r["tools_mean"], r["tokens_mean"],
            r["seconds_mean"], r["cost_mean_usd"]))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n写出 {args.out}")


if __name__ == "__main__":
    main()
