#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测量中文格式对 grep（字面量匹配）的影响。

用法：
    python runner/probe_grep_cn.py --corpus <repo-root>/S --scale S
    python runner/probe_grep_cn.py --corpus <repo-root>/M --scale M
    python runner/probe_grep_cn.py --corpus <repo-root>/L --scale L

说明：
- 这里模拟 grep 的字面量匹配（大小写敏感、逐行、不跨行），不是调用 pi 的 grep；
- 页码来自语料里的 `<!-- page: n -->` 标记；
- 输出：runs/_grep_cn/probe_<scale>.json 与同目录的 .md 表。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")

PROBES = [
    # 基线：正常简体、无空格、半角数字
    ("baseline", "研发投入占营业收入", "简体无空格基线"),
    ("baseline", "归属于上市公司股东的净利润", "简体无空格基线"),
    ("baseline", "标准无保留意见", "简体无空格基线"),
    ("baseline", "每10股派发现金红利", "简体无空格基线"),
    ("baseline", "2025", "半角数字基线"),
    ("baseline", "1,649 万辆", "千分位 + 空格基线"),
    ("baseline", "342,496,653.85", "千分位数字基线"),
    # 分词/空格
    ("space", "研发 投入 占 营业收入", "中文词之间加半角空格"),
    ("space", "研发　投入", "中文词之间加全角空格"),
    ("space", "每 10 股派发现金红利", "数字与单位之间加空格"),
    # 繁简
    ("traditional", "研發投入", "繁体「研發」"),
    ("traditional", "營業收入", "繁体「營業」"),
    ("traditional", "淨利潤", "繁体「淨利潤」"),
    ("traditional", "審計意見", "繁体「審計」"),
    # 全角/半角
    ("fullwidth", "２０２５", "全角数字"),
    ("fullwidth", "％", "全角百分号"),
    # 数字格式
    ("number", "1,649万辆", "去掉数字与单位之间的空格"),
    ("number", "1649万辆", "同时去掉空格和千分位"),
    ("number", "342496653.85", "去掉千分位逗号"),
    ("number", "3.42亿元", "亿口径改写"),
    ("number", "120,000,000", "千分位 + 元"),
    # 同义改写（不是格式问题，作为对照）
    ("synonym", "职工薪酬", "原文常用词"),
    ("synonym", "员工成本", "同义改写"),
]


def load_docs(corpus: Path):
    docs = []
    for path in sorted(corpus.rglob("*.md")):
        rel = path.relative_to(corpus).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        docs.append((rel, text))
    return docs


def count(docs, needle: str):
    """返回 (命中文件数, 命中页数, 匹配次数)。"""
    files = 0
    pages = set()
    matches = 0
    for rel, text in docs:
        if needle not in text:
            continue
        files += 1
        page = 1
        for line in text.split("\n"):
            m = PAGE_RE.search(line)
            if m:
                page = int(m.group(1))
                continue
            if needle in line:
                matches += line.count(needle)
                pages.add((rel, page))
    return files, len(pages), matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    corpus = Path(args.corpus).resolve()
    docs = load_docs(corpus)
    rows = []
    for axis, query, note in PROBES:
        files, pages, matches = count(docs, query)
        rows.append(
            {
                "axis": axis,
                "query": query,
                "note": note,
                "docs_hit": files,
                "pages_hit": pages,
                "matches": matches,
                "hit": files > 0,
            }
        )

    out_dir = ROOT / "runs" / "_grep_cn"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else out_dir / f"probe_{args.scale}.json"
    out.write_text(
        json.dumps(
            {"scale": args.scale, "corpus": str(corpus), "documents": len(docs), "probes": rows},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    md = [
        f"# 中文格式对 grep 的影响（{args.scale}，{len(docs)} 份文档）",
        "",
        "> 字面量匹配模拟；页码来自 `<!-- page: n -->`。",
        "",
        "| 维度 | 查询 | 说明 | 命中文件 | 命中页 | 匹配次数 | 结果 |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['axis']} | `{r['query']}` | {r['note']} | {r['docs_hit']} | "
            f"{r['pages_hit']} | {r['matches']} | {'命中' if r['hit'] else '**0 命中**'} |"
        )
    (out_dir / f"probe_{args.scale}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[probe] {args.scale}: {len(docs)} docs, wrote {out}")


if __name__ == "__main__":
    main()
