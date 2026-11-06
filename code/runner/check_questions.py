"""题目机械校验：证据文件存在、A/B 类关键词命中符合定义。

用法：
    python runner/check_questions.py --questions questions/questions_s_samples.jsonl --corpus corpus/S
    python runner/check_questions.py --questions questions/questions.jsonl --corpus corpus/S --targets

规则：
- A 类：probe 关键词必须在语料中命中（>0）；
- B 类：probe 关键词必须全库 0 命中，否则测的是 A 类；
- C/D/E：不检查 probe；
- 所有题：证据文件必须存在（E 类除外），id 不重复。
"""

import argparse
import json
from collections import Counter
from pathlib import Path

TARGETS = {"A": 20, "B": 20, "C": 15, "D": 15, "E": 10}


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
    ap.add_argument("--questions", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--targets", action="store_true", help="按 80 题目标检查分布")
    ap.add_argument(
        "--probe-scope",
        choices=["corpus", "evidence"],
        default="corpus",
        help="B 类 probe 的检查范围：corpus=全库（旧口径），evidence=仅证据文档（扩大语料后推荐）",
    )
    args = ap.parse_args()

    questions = read_jsonl(args.questions)
    corpus = Path(args.corpus)
    if not corpus.is_dir():
        raise SystemExit(f"语料目录不存在: {corpus}")

    texts = {}
    for p in corpus.rglob("*.md"):
        texts[p] = p.read_text(encoding="utf-8", errors="ignore")

    ids = Counter(q["id"] for q in questions)
    dup = {k: v for k, v in ids.items() if v > 1}

    failures = []
    for q in questions:
        qid, cat = q["id"], q.get("category")
        if cat not in TARGETS:
            failures.append((qid, f"类别非法: {cat}"))
            continue

        if cat != "E":
            for e in q.get("evidence", []):
                if not (corpus / e["file"]).exists():
                    failures.append((qid, f"证据文件不存在: {e['file']}"))

        probe = q.get("probe")
        if cat in ("A", "B"):
            if not probe:
                failures.append((qid, "A/B 类缺少 probe 关键词"))
                continue
            if args.probe_scope == "corpus":
                hits = sum(t.count(probe) for t in texts.values())
            else:
                hits = sum(
                    texts[corpus / e["file"]].count(probe)
                    for e in q.get("evidence", [])
                    if (corpus / e["file"]) in texts
                )
            if cat == "A" and hits == 0:
                failures.append((qid, f"A 类 probe 0 命中: {probe}"))
            if cat == "B" and hits > 0:
                failures.append((qid, f"B 类 probe 命中 {hits} 次（应为 0）: {probe}"))

    dist = Counter(q.get("category") for q in questions)
    print(f"题目 {len(questions)} 道：" + "  ".join(
        f"{c}={dist.get(c, 0)}" for c in ("A", "B", "C", "D", "E")))
    if dup:
        print(f"[FAIL] 重复 id: {dup}")
    if args.targets:
        for c, want in TARGETS.items():
            got = dist.get(c, 0)
            mark = "OK" if got == want else "DIFF"
            print(f"  {c}: {got}/{want} [{mark}]")

    if failures:
        print(f"\n[FAIL] {len(failures)} 项：")
        for qid, msg in failures:
            print(f"  {qid}: {msg}")
        raise SystemExit(1)
    print("\n[PASS] 全部通过")


if __name__ == "__main__":
    main()
