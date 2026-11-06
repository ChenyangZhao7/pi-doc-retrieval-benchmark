r"""分档判分薄层：expected=answer 走原 grade.py，expected=refuse 走规则判分。

不改原 grade.py。用法：

    python runner/grade_scaled.py --scale S \
      --questions <repo-root>\questions_all163.jsonl \
      --expectations <repo-root>\scale_expectations.json \
      --runs runs/metrics.jsonl \
      --corpus <repo-root>\S

输出：runs/scores_scaled_<scale>.jsonl
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRADE = Path(__file__).resolve().parent / "grade.py"

REFUSAL_PHRASES = [
    "未找到", "未披露", "未提及", "未包含", "未出现", "未发现", "未提供", "未给出",
    "没有找到", "没有披露", "没有提及", "没有提供", "没有给出",
    "无法回答", "无法确定", "无法从", "无法核实", "查无", "不存在", "不在",
    "无相关信息", "无相关数据", "资料中没有", "文档中没有", "语料中没有",
    "未能找到", "未收录", "不包含", "没有相关信息", "没有相关数据",
]
AMOUNT_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:亿元|万元|亿美元|万千瓦|元|%|股|户|辆|台|吨|亿|万)"
    r"(?=[\s，。；、）)]|$)"
)
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
FILE_RE = re.compile(r"[^\s`'\"，,。；;]+\.(?:md|pdf|docx?|xlsx?)", re.I)
PAGE_RE = re.compile(r"第\s*\d+\s*[页节]|第\s*\d+(?:-\d+)?\s*页")


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def numeric_value(text):
    return NUM_RE.search(text).group(0).replace(",", "") if NUM_RE.search(text) else ""


def specific_amounts(answer, question):
    """回答里出现、且题目里没有的具体金额/比例/数量。"""
    qnums = {n.replace(",", "") for n in NUM_RE.findall(question or "")}
    out = []
    for m in AMOUNT_RE.findall(answer or ""):
        v = numeric_value(m)
        if v and v not in qnums:
            out.append(m.strip())
    return out


def citation_info(answer, corpus):
    rels = []
    for m in FILE_RE.findall(answer or ""):
        name = Path(m.replace("\\", "/")).name
        matches = [p for p in corpus.rglob("*.md") if p.name == name]
        if len(matches) == 1:
            rels.append(matches[0].relative_to(corpus).as_posix())
    has_locator = bool(PAGE_RE.search(answer or ""))
    level = 2 if (rels and has_locator) else (1 if rels else 0)
    return {
        "cited_files": rels,
        "only_directory": False,
        "has_locator": has_locator,
        "level": level,
    }


def score_refuse(question, run, corpus, expected):
    answer = (run.get("answer") or "").strip()
    refused = any(p in answer for p in REFUSAL_PHRASES)
    amounts = specific_amounts(answer, question["question"])
    cite = citation_info(answer, corpus)

    if not answer:
        score = 0.0
        reason = "应拒题：回答为空，未拒答。"
    elif refused and not amounts:
        score = 1.0
        reason = "应拒题：明确拒答，未给出具体数值。"
    elif refused and amounts:
        score = 0.5
        reason = "应拒题：有拒答表述，但仍给出了具体数值/金额。"
    elif amounts:
        score = 0.0
        reason = "应拒题：未拒答，且给出具体数值/金额，按编造计。"
    else:
        score = 0.5
        reason = "应拒题：未明确拒答，也未给出可核实的数值，表述含糊。"

    return {
        "run_id": run.get("run_id") or run.get("id"),
        "qid": run["qid"],
        "category": question["category"],
        "scale": run.get("scale"),
        "expected": expected,
        "score": score,
        "content_score": score,
        "score_caps": [],
        "present_ratio": None,
        "evidence_hit": None,
        "citation_level": cite["level"],
        "citation": {
            "cited_files": cite["cited_files"],
            "only_directory": cite["only_directory"],
            "has_locator": cite["has_locator"],
        },
        "answer_matches_reference": None,
        "checklist": [],
        "unsupported_claims": amounts,
        "omission_claims": [],
        "e_class": (
            {
                "refused": refused,
                "gives_number": bool(amounts),
                "extra_unverifiable": False,
                "extra_claims": [],
            }
            if question["category"] == "E"
            else None
        ),
        "rubric": None,
        "reason": reason,
        "refuse_type": "e_class" if question["category"] == "E" else "scale_out",
        "judge": "refuse_rule",
        "judge_mode": "rule",
        "judge_provider": "local",
        "judge_model": "refusal_heuristic_v1",
        "judge_snapshot": "rule-v1",
        "judge_params": {},
        "prompt_sha256": None,
        "judge_input_tokens": 0,
        "judge_output_tokens": 0,
        "judge_cost_native": 0,
        "judge_currency": "USD",
        "judge_cost_usd": 0.0,
        "judge_billing": "local",
        "pricing_period": None,
        "human_checked": False,
        "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_answer_judge(args, runs, tmpdir):
    """把 expected=answer 的子集交给原 grade.py。"""
    tmp_runs = Path(tmpdir) / "answer_runs.jsonl"
    tmp_out = Path(tmpdir) / "answer_scores.jsonl"
    write_jsonl(tmp_runs, runs)
    cmd = [
        sys.executable, str(GRADE),
        "--questions", args.questions,
        "--runs", str(tmp_runs),
        "--corpus", args.corpus,
        "--judge", args.judge,
        "--out", str(tmp_out),
        "--rejudge",
    ]
    if args.limit:
        # limit 已在外层应用；传给 grade.py 会重复截断，故不传。
        pass
    print(f"[answer] 调原 grade.py：{len(runs)} 条")
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"原 grade.py 失败，退出码 {proc.returncode}")
    if not tmp_out.exists():
        return []
    return read_jsonl(tmp_out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", required=True, choices=["S", "M", "L"])
    ap.add_argument("--questions", default=r"<repo-root>\questions_all163.jsonl")
    ap.add_argument("--expectations", default=r"<repo-root>\scale_expectations.json")
    ap.add_argument("--runs", default=str(ROOT / "runs" / "metrics.jsonl"))
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--judge", default="auto")
    ap.add_argument("--out", default=None)
    ap.add_argument("--qid", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--rejudge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.corpus:
        args.corpus = str(Path(r"<repo-root>") / args.scale)
    corpus = Path(args.corpus)
    if not corpus.is_dir():
        raise SystemExit(f"语料目录不存在: {corpus}")

    out_path = Path(args.out or (ROOT / "runs" / f"scores_scaled_{args.scale}.jsonl"))

    questions = {q["id"]: q for q in read_jsonl(args.questions)}
    exp_all = json.loads(Path(args.expectations).read_text(encoding="utf-8"))["scales"][args.scale]
    expected_by_qid = {r["id"]: r["expected"] for r in exp_all["questions"]}

    runs = []
    for r in read_jsonl(args.runs):
        rid = r.get("run_id") or r.get("id")
        if not rid or r.get("qid") not in questions:
            continue
        r["run_id"] = rid
        if args.qid and r["qid"] != args.qid:
            continue
        if args.run_id and r["run_id"] != args.run_id:
            continue
        if r.get("scale") and r["scale"] != args.scale:
            continue
        runs.append(r)
    runs.sort(key=lambda r: (r["qid"], r.get("repeat", 0)))
    if args.limit:
        runs = runs[: args.limit]

    if not runs:
        raise SystemExit("没有可判分的运行记录")

    existing = [] if not out_path.exists() else read_jsonl(out_path)
    if args.rejudge:
        selected = {r["run_id"] for r in runs}
        existing = [x for x in existing if x.get("run_id") not in selected]
    done = {x["run_id"] for x in existing}

    answer_runs, refuse_runs = [], []
    for r in runs:
        if r["run_id"] in done:
            continue
        exp = expected_by_qid.get(r["qid"], "answer")
        (answer_runs if exp == "answer" else refuse_runs).append(r)

    print(
        f"[plan] scale={args.scale} total={len(runs)} "
        f"answer={len(answer_runs)} refuse={len(refuse_runs)} existing={len(existing)}"
    )
    if args.dry_run:
        return

    new_rows = []
    if answer_runs:
        with tempfile.TemporaryDirectory(prefix="grade_scaled_") as tmpdir:
            new_rows.extend(run_answer_judge(args, answer_runs, tmpdir))
    for r in refuse_runs:
        q = questions[r["qid"]]
        new_rows.append(score_refuse(q, r, corpus, "refuse"))

    # 合并、去重、补 expected/scale
    merged = {x["run_id"]: x for x in existing}
    for x in new_rows:
        x["expected"] = expected_by_qid.get(x["qid"], x.get("expected"))
        x["scale"] = x.get("scale") or args.scale
        merged[x["run_id"]] = x
    rows = sorted(merged.values(), key=lambda x: (x["qid"], x.get("scale") or "", x["run_id"]))
    write_jsonl(out_path, rows)

    print(f"\n[write] {out_path}  ({len(rows)} 条)")
    by_exp = defaultdict(list)
    for x in rows:
        by_exp[x.get("expected", "?")].append(x)
    for exp in ("answer", "refuse"):
        items = by_exp.get(exp, [])
        if not items:
            continue
        scores = [x["score"] for x in items]
        print(f"[{exp}] n={len(items)} mean={sum(scores) / len(scores):.3f}")
        if exp == "refuse":
            print(
                f"  拒答(1分)={sum(1 for s in scores if s == 1)} "
                f"含糊(0.5)={sum(1 for s in scores if s == 0.5)} "
                f"编造(0分)={sum(1 for s in scores if s == 0)}"
            )
    by_cat = Counter(x["category"] for x in rows)
    print("[category]", dict(sorted(by_cat.items())))


if __name__ == "__main__":
    main()
