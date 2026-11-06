"""对比多个组的准确率、token、费用。

用法：
    python runner/compare_groups.py \
        --group G0=runs/_g0/metrics_50docs.jsonl=runs/_g0/scores_50docs.jsonl \
        --group G1=runs/metrics.jsonl=runs/_grade/scores_final_clean_ev.jsonl \
        --group G1+=runs/_g1plus/metrics.jsonl=runs/_g1plus/scores.jsonl
"""

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True,
                    help="name=metrics_path=scores_path")
    ap.add_argument("--by-category", action="store_true")
    args = ap.parse_args()

    rows = []
    for spec in args.group:
        parts = spec.split("=")
        if len(parts) != 3:
            raise SystemExit(f"格式应为 name=metrics=scores: {spec}")
        name, metrics_path, scores_path = parts
        metrics = {r["run_id"]: r for r in read_jsonl(metrics_path)}
        scores = read_jsonl(scores_path)
        joined = [(s, metrics[s["run_id"]]) for s in scores if s["run_id"] in metrics]
        if not joined:
            print(f"[skip] {name}: 没有可匹配记录")
            continue
        rows.append((name, joined))

    def agg(items):
        ev = [s["evidence_hit"] for s, _ in items if s.get("evidence_hit") is not None]
        return {
            "n": len(items),
            "score": st.mean(s["score"] for s, _ in items),
            "evidence": st.mean(ev) if ev else None,
            "turns": st.mean(m["turns"] for _, m in items),
            "tools": st.mean(m["tool_calls_total"] for _, m in items),
            "tokens": st.mean(m["tokens"]["total"] for _, m in items),
            "seconds": st.mean(m["wall_ms"] for _, m in items) / 1000,
            "cost": st.mean(m.get("cost_usd_corrected") or 0 for _, m in items),
        }

    print("| 组 | n | 得分 | 证据 | 轮 | 工具 | token | 秒 | 费用$ |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, joined in rows:
        a = agg(joined)
        ev = f"{a['evidence']:.3f}" if a["evidence"] is not None else "n/a"
        print(f"| {name} | {a['n']} | {a['score']:.3f} | {ev} | "
              f"{a['turns']:.1f} | {a['tools']:.1f} | {a['tokens']:.0f} | "
              f"{a['seconds']:.1f} | {a['cost']:.5f} |")

    if args.by_category:
        print("\n| 组 | 类 | n | 得分 | token | 费用$ |")
        print("|---|---|---:|---:|---:|---:|")
        for name, joined in rows:
            by = defaultdict(list)
            for s, m in joined:
                by[s["category"]].append((s, m))
            for cat in sorted(by):
                a = agg(by[cat])
                print(f"| {name} | {cat} | {a['n']} | {a['score']:.3f} | "
                      f"{a['tokens']:.0f} | {a['cost']:.5f} |")


if __name__ == "__main__":
    main()
