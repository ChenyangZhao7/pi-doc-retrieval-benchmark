"""对 auto 路由的判分做交叉复核，并用 V4 Pro 裁决分歧。

auto 路由：A/B/C/E → Kimi，D → V4 Pro。
本脚本只复核 A/B/C/E：
- 所有分数 < 1 的（漏判风险）；
- 所有带 unsupported_claims / omission_claims 的（误判风险）；
- 再随机抽 20%，补足样本。

输出：
    runs/scores_crosscheck.jsonl   V4 Pro 的复核记录
    runs/scores_final.jsonl        以 auto 为主，分歧处用 V4 Pro 覆盖

用法：
    python runner/grade.py --judge auto
    python runner/cross_check.py
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judges  # noqa: E402
from grade import (  # noqa: E402
    SYSTEM_PROMPT, build_user_prompt, citation_level, evidence_hit, finalize,
)
from run_one import ROOT  # noqa: E402


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def needs_check(rec):
    if rec.get("score", 1) < 1:
        return True
    if rec.get("unsupported_claims"):
        return True
    if any(c.get("source_has_value") for c in rec.get("omission_claims") or []):
        return True
    return False


def pick(primary, ratio, seed):
    by_cat = defaultdict(list)
    for rec in primary.values():
        if rec.get("category") == "D":
            continue
        by_cat[rec.get("category")].append(rec)

    rng = random.Random(seed)
    selected = []
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        must = [r for r in rows if needs_check(r)]
        rest = [r for r in rows if not needs_check(r)]
        rng.shuffle(rest)
        target = max(1, round(len(rows) * ratio))
        need = max(0, target - len(must))
        selected += must + rest[:need]
    return selected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "questions" / "questions_s_all.jsonl"))
    ap.add_argument("--runs", default=str(ROOT / "runs" / "metrics.jsonl"))
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "S"))
    ap.add_argument("--primary", default=str(ROOT / "runs" / "scores_routed.jsonl"))
    ap.add_argument("--judge", default="deepseek-v4-pro")
    ap.add_argument("--ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--out", default=str(ROOT / "runs" / "scores_crosscheck.jsonl"))
    ap.add_argument("--final", default=str(ROOT / "runs" / "scores_final.jsonl"))
    ap.add_argument("--rejudge", action="store_true")
    args = ap.parse_args()

    primary_rows = read_jsonl(args.primary)
    primary = {r["run_id"]: r for r in primary_rows}
    questions = {q["id"]: q for q in read_jsonl(args.questions)}
    runs = {r["run_id"]: r for r in read_jsonl(args.runs) if r.get("run_id") in primary}

    chosen = pick(primary, args.ratio, args.seed)
    print(f"auto 判分 {len(primary)} 条；复核 {len(chosen)} 条 "
          f"（{dict(Counter(r['category'] for r in chosen))}）")

    out_path = Path(args.out)
    done = set()
    if out_path.exists() and not args.rejudge:
        done = {r["run_id"] for r in read_jsonl(out_path)}

    judge_cfg = judges.CONFIG[args.judge]
    if not judges.get_key(judge_cfg["api_key_env"]):
        raise SystemExit(f"未找到 key（{args.judge}）")

    period = "off-peak"
    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for i, rec in enumerate(chosen, 1):
        rid = rec["run_id"]
        if rid in done:
            continue
        q = questions[rec["qid"]]
        run = runs[rid]
        result, usage, error = judges.call_judge(
            args.judge, SYSTEM_PROMPT, build_user_prompt(q, run, args.corpus))
        if result is None:
            print(f"[{i}/{len(chosen)}] {rid} 失败: {error}")
            continue
        score, content, caps, ratio = finalize(q, result)
        native, currency = judges.judge_cost(args.judge, usage, period)
        record = {
            "run_id": rid,
            "qid": rec["qid"],
            "category": rec["category"],
            "score": score,
            "content_score": content,
            "score_caps": caps,
            "present_ratio": round(ratio, 3) if ratio is not None else None,
            "evidence_hit": evidence_hit(result, q, run, args.corpus),
            "citation_level": citation_level(result),
            "unsupported_claims": result.get("unsupported_claims", []),
            "omission_claims": result.get("omission_claims", []),
            "reason": result.get("reason", ""),
            "judge": args.judge,
            "judge_snapshot": judge_cfg.get("snapshot"),
            "prompt_sha256": prompt_hash,
            "judge_cost_usd": judges.to_usd(native, currency),
            "primary_score": rec["score"],
            "primary_judge": rec.get("judge"),
            "agreement": score == rec["score"],
            "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(chosen)}] {rid} primary={rec['score']} "
              f"pro={score} {'AGREE' if record['agreement'] else 'DIFF'}")

    checked = {r["run_id"]: r for r in read_jsonl(out_path)}
    common = [checked[r["run_id"]] for r in chosen if r["run_id"] in checked]
    agree = sum(1 for r in common if r["agreement"])
    print(f"\n复核 {len(common)} 条，一致 {agree} "
          f"({agree / len(common):.1%})" if common else "\n没有复核结果")

    # 合并：auto 为主，分歧用 V4 Pro 覆盖
    final_rows = []
    for rec in primary_rows:
        c = checked.get(rec["run_id"])
        if c and not c["agreement"]:
            merged = dict(rec)
            merged.update({
                "score": c["score"],
                "content_score": c["content_score"],
                "score_caps": c["score_caps"],
                "evidence_hit": c["evidence_hit"],
                "reason": c["reason"],
                "resolved_by": c["judge"],
                "primary_score": rec["score"],
                "primary_judge": rec.get("judge"),
            })
            final_rows.append(merged)
        else:
            final_rows.append(rec)

    with open(args.final, "w", encoding="utf-8", newline="\n") as f:
        for r in final_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"合并结果: {args.final}")


if __name__ == "__main__":
    main()
