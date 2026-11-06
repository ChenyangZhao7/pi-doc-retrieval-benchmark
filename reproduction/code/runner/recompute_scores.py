"""用当前封顶规则重算已有判分记录，避免重复调用 API。

用途：判分器把“与原文一致”误写进 unsupported_claims 时，
不必重新判分，直接按新过滤器重算 score。

用法：
    python runner/recompute_scores.py --scores runs/_grade/scores_pro.jsonl --out runs/_grade/scores_pro_fixed.jsonl
"""

import argparse
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import citation_level, clean_claims  # noqa: E402


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = read_jsonl(args.scores)
    before = [r["score"] for r in rows]
    changed = 0

    for r in rows:
        if r.get("resolved_by"):
            # 已被 V4 Pro 裁决，保留覆盖后的分数
            continue
        content = r.get("content_score")
        if content is None:
            continue
        caps = []
        if r.get("category") in ("A", "B", "C") and citation_level(r) == 0:
            caps.append(0.5)
        if clean_claims(r.get("unsupported_claims")):
            caps.append(0.5)
        if any(o.get("source_has_value") for o in (r.get("omission_claims") or [])):
            caps.append(0.5)
        new_score = min([content] + caps)
        if new_score != r["score"]:
            changed += 1
        r["score"] = new_score
        r["score_caps"] = caps

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    after = [r["score"] for r in rows]
    print(f"records {len(rows)}, changed {changed}")
    print(f"mean before {st.mean(before):.3f} -> after {st.mean(after):.3f}")
    print(f"written {args.out}")


if __name__ == "__main__":
    main()
