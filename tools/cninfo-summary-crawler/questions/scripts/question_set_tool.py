#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""80 道题的校验 / 渲染工具。

默认读取 `questions/official_80.jsonl`，也可以 `--input` 指向候选题文件。
用途：
- 校验分类数量、probe、证据文件和 D 类长度/结构；
- 重新生成审阅表 Markdown 和校验报告；
- 不调用 LLM，不修改题目内容。

用法：
    python questions/scripts/question_set_tool.py all
    python questions/scripts/question_set_tool.py check --strict
    python questions/scripts/question_set_tool.py render
    python questions/scripts/question_set_tool.py check --input questions/questions_s_80_candidates.jsonl

默认路径都相对于项目根目录，不依赖当前工作目录。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "questions" / "official_80.jsonl"
DEFAULT_CORPUS = ROOT / "corpus" / "incoming" / "summaries"
DEFAULT_MD = ROOT / "questions" / "official_80.md"
DEFAULT_VALIDATION = ROOT / "questions" / "official_80.validation.md"

EXPECTED_COUNTS = {"A": 20, "B": 20, "C": 15, "D": 15, "E": 10}
REQUIRED = ("id", "category", "question", "answer", "evidence")
D_LENGTH = re.compile(r"\d{3,4}\s*[–-]\s*\d{3,4}\s*字")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"缺少题集: {path}")
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{lineno} JSON 错误: {e}")
    return rows


def corpus_text(path: Path) -> str:
    if not path.exists():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in path.rglob("*.md"))


def validate(rows: list[dict[str, Any]], corpus: Path | None, text: str) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    check_corpus = corpus is not None and corpus.exists()
    if not check_corpus:
        warnings.append("语料目录不存在：已跳过 probe 和证据文件检查，只做结构校验")
    counts = Counter(r.get("category") for r in rows)

    if len(rows) != sum(EXPECTED_COUNTS.values()):
        errors.append(f"总数 {len(rows)}，应为 {sum(EXPECTED_COUNTS.values())}")
    for cat, n in EXPECTED_COUNTS.items():
        if counts.get(cat, 0) != n:
            errors.append(f"{cat} 类 {counts.get(cat, 0)} 道，应为 {n}")

    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)):
        errors.append("存在重复 id")
    for r in rows:
        rid = r.get("id", "?")
        for key in REQUIRED:
            if key not in r:
                errors.append(f"{rid}: 缺少字段 {key}")
        if not str(rid).startswith("q"):
            errors.append(f"{rid}: id 格式不对")

        cat = r.get("category")
        evidence = r.get("evidence") or []
        if cat in ("A", "B", "E"):
            probe = r.get("probe", "")
            if not probe:
                errors.append(f"{rid}: {cat} 类缺少 probe")
                continue
            if check_corpus:
                n = text.count(probe)
                if cat == "A" and n == 0:
                    errors.append(f"{rid}: A 类 probe 0 命中: {probe!r}")
                if cat in ("B", "E") and n > 0:
                    errors.append(f"{rid}: {cat} 类 probe 命中 {n} 次: {probe!r}")

        if cat == "C" and len(evidence) < 2:
            errors.append(f"{rid}: C 类证据不足 2 份")
        if cat == "D" and len(evidence) < 3:
            errors.append(f"{rid}: D 类证据不足 3 份")

        for e in evidence:
            f = e.get("file")
            if not f:
                errors.append(f"{rid}: evidence 缺少 file")
            elif check_corpus and not (corpus / f).exists():
                errors.append(f"{rid}: 证据文件不存在: {f}")

        if cat == "D":
            q = r.get("question", "")
            if not D_LENGTH.search(q):
                errors.append(f"{rid}: D 类缺少长度要求（如 1200–1500 字）")
            if str(rid) >= "q362" and "结构" not in q:
                errors.append(f"{rid}: D 类缺少结构要求")

    # exact duplicate questions
    norm = [re.sub(r"\s+", "", r.get("question", "")) for r in rows]
    for q, n in Counter(norm).items():
        if n > 1:
            warnings.append(f"完全重复的题面 {n} 次: {q[:50]}")

    # cross-category duplicate report: same answer text
    ans_groups: dict[str, list[str]] = {}
    for r in rows:
        key = re.sub(r"\s+", "", r.get("answer", ""))
        if key:
            ans_groups.setdefault(key, []).append(r.get("id", "?"))
    for ans, ids2 in ans_groups.items():
        cats = {next(r["category"] for r in rows if r["id"] == i) for i in ids2}
        # A/B 同答案是有意的：A 测关键词，B 测语义改写。
        if len(ids2) > 1 and len(cats) > 1 and cats != {"A", "B"}:
            warnings.append(f"跨类别相同答案: {ids2}")

    stats = {
        "total": len(rows),
        "counts": dict(counts),
        "errors": len(errors),
        "warnings": len(warnings),
    }
    return errors, warnings, stats


def render_md(rows: list[dict[str, Any]]) -> str:
    official = bool(rows) and all(r.get("official") is True for r in rows)
    lines = [
        "# 80 道题（official）" if official else "# 80 道 AI 候选题（非 official）",
        "",
        "> 由 `questions/scripts/question_set_tool.py` 生成。",
        "> 正式使用前仍建议逐题对照原文，核对答案和页码。" if official
        else "> 依据 `questions/HUMAN_AUTHORING.md`：正式 80 题必须由人写/确认；",
        "" if official else "> 本文件只是 AI 候选，`status=ai_candidate`，不能直接当作 official。",
        "",
        f"- 总数：{len(rows)}",
        f"- 分类：{dict(Counter(r.get('category') for r in rows))}",
        "",
        "| ID | 类 | 问题 | 答案 | 证据 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        qtext = str(r.get("question", "")).replace("|", "\\|")
        ans = str(r.get("answer", "")).replace("|", "\\|").replace("\n", " ")
        if len(ans) > 180:
            ans = ans[:180] + "…"
        evs = "<br>".join(e.get("file", "") for e in (r.get("evidence") or [])) or "—"
        lines.append(f"| {r.get('id')} | {r.get('category')} | {qtext} | {ans} | {evs} |")
    return "\n".join(lines) + "\n"


def render_validation(rows: list[dict[str, Any]], errors: list[str], warnings: list[str], stats: dict[str, Any]) -> str:
    official = bool(rows) and all(r.get("official") is True for r in rows)
    lines = [
        "# 80 道题校验报告（official）" if official else "# 80 道 AI 候选题校验报告",
        "",
        "> 由 `questions/scripts/question_set_tool.py` 生成；正式使用前仍需人工复核。",
        "",
        f"- 总数：{stats['total']}",
        f"- 分类：{stats['counts']}",
        f"- 错误：{stats['errors']}",
        f"- 警告：{stats['warnings']}",
        "",
        "## 错误",
        "",
    ]
    lines += [f"- {e}" for e in errors] or ["无。"]
    lines += ["", "## 警告", ""]
    lines += [f"- {w}" for w in warnings] or ["无。"]
    lines += [
        "",
        "## 仍需人工做的事",
        "",
        "1. 逐题对照原文，确认答案逐字/逐数正确；",
        "2. 改写题面，使其符合你自己的出题风格；",
        "3. 核对页码和章节名；",
        "4. 对 D 类参考答案补充“必须覆盖要点”和评分口径；",
        "5. 通过后把 `status` 改成 `official` 或另存为 `questions/official.jsonl`。",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="80 道候选题的校验 / 渲染工具")
    ap.add_argument("command", nargs="?", choices=["all", "check", "render"], default="all")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    ap.add_argument("--strict", action="store_true", help="有错误时退出码 1")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_rows(args.input)
    text = corpus_text(args.corpus)
    errors, warnings, stats = validate(rows, args.corpus, text)

    print(f"题数：{stats['total']}；分类：{stats['counts']}")
    print(f"错误：{stats['errors']}；警告：{stats['warnings']}")
    for e in errors[:10]:
        print(f"[ERROR] {e}")
    for w in warnings[:10]:
        print(f"[WARN] {w}")

    if args.command in ("render", "all"):
        args.md.write_text(render_md(rows), encoding="utf-8", newline="\n")
        print(f"写出审阅表：{args.md}")
    if args.command in ("check", "all"):
        args.validation.write_text(
            render_validation(rows, errors, warnings, stats),
            encoding="utf-8",
            newline="\n",
        )
        print(f"写出校验报告：{args.validation}")

    if args.strict and errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
