#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一次抓取的结果切成多个不同份数的合并 Markdown。

用法：
    python make_bundles.py --out cninfo_output --sizes 10 20 50

读取 <out>/manifest.jsonl 和 <out>/summaries/ 下的单文件 Markdown，
按 manifest 顺序取前 N 份，生成 <out>/bundles/<N>_summaries.md。
较小的包是较大包的子集，不会重复下载 PDF。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
HEADER_TAGS = ("<!-- source:", "<!-- company:")


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def read_body(md: str) -> str:
    """去掉单文件顶部的 source/company 注释，只留正文。"""
    lines = md.split("\n")
    i = 0
    while i < len(lines) and lines[i].startswith(HEADER_TAGS):
        i += 1
    return "\n".join(lines[i:]).strip()


def build(rows: list[dict], out: Path, size: int) -> Path:
    selected = sorted(rows, key=lambda r: r["company_code"])[:size]
    if len(selected) < size:
        raise SystemExit(f"manifest 只有 {len(rows)} 份，不够生成 {size} 份")

    total_bytes = sum(r["bytes"] for r in selected)
    total_chars = sum(r["chars"] for r in selected)
    total_pages = sum(r["pages"] for r in selected)

    toc = "\n".join(
        f"| {i:02d} | {r['company_code']} | {r['company_name']} | "
        f"{r['period']} | {r['pages']} | {r['bytes'] / 1024:.1f} KB |"
        for i, r in enumerate(selected, 1)
    )
    parts = [
        f"# {len(selected)} 份 A 股年报摘要（{selected[0]['period']} 年度）\n",
        "> 来源：巨潮资讯网（cninfo.com.cn）  ",
        f"> 生成时间：{now_iso()}  ",
        f"> 文件数：{len(selected)}；总文本：{total_bytes / 1e6:.2f} MB；"
        f"总页数：{total_pages}；总字符：{total_chars:,}  ",
        "> 说明：正文由 PDF 文本层逐页转换，**未做 LLM 摘要、改写或翻译**；"
        "每份文件用 document 注释分隔，页内保留 page 注释。  ",
        "> 生成程序：`make_bundles.py`（数据来自 `cninfo_summary_crawler.py`）\n",
        "## 目录\n",
        "| # | 代码 | 公司 | 期间 | 页数 | 大小 |",
        "|---:|---|---|---|---:|---:|",
        toc,
        "\n---\n",
    ]
    for r in selected:
        md = (out / r["path"]).read_text(encoding="utf-8")
        parts.append(
            f"<!-- document: {r['company_code']} {r['company_name']} | {r['period']} | "
            f"{r['doc_type']} | {r['source_url']} | sha256: {r['sha256']} -->\n"
        )
        parts.append(f"# {r['company_code']} {r['company_name']} — {r['period']} 年年度报告摘要\n")
        parts.append(
            f"- 来源：{r['source_url']}\n"
            f"- 抓取时间：{r['retrieved_at']}\n"
            f"- 页数：{r['pages']}；字符：{r['chars']:,}；大小：{r['bytes'] / 1024:.1f} KB\n"
        )
        parts.append(read_body(md) + "\n\n---\n")

    dest = out / "bundles" / f"{size}_summaries.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    print(f"已生成 {dest}（{len(selected)} 份 / {total_bytes / 1e6:.2f} MB / {total_pages} 页）")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description="按份数切分已抓取的年报摘要")
    ap.add_argument("--out", type=Path, default=Path("cninfo_output"), help="抓取输出目录")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 50], help="要生成的份数")
    args = ap.parse_args()

    out = args.out.resolve()
    manifest = out / "manifest.jsonl"
    if not manifest.exists():
        raise SystemExit(f"找不到 {manifest}，请先运行 cninfo_summary_crawler.py")

    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"manifest：{len(rows)} 份，将生成：{', '.join(str(s) for s in args.sizes)}")
    for size in sorted(set(args.sizes)):
        build(rows, out, size)


if __name__ == "__main__":
    main()
