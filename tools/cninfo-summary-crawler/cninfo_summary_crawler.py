#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""年报摘要抓取器（cninfo-summary-crawler）。

抓取巨潮资讯网 A 股年报摘要，输出一个合并 Markdown + 单份 Markdown + manifest。

特点：
- 只抓公开披露文件；
- 只做 PDF -> 文本/Markdown 的格式转换，不调用 LLM，不摘要、不改写、不翻译；
- 每页保留 <!-- page: N -->，每份文件保留来源 URL、抓取时间、sha256；
- 默认按体积优先选样，保证 50 份尽量接近 1.5 MB；--random 可随机抽。

用法：
    pip install -r requirements.txt
    python cninfo_summary_crawler.py --year 2025 --target 50
    python cninfo_summary_crawler.py --year 2025 --target 50 --random
    python cninfo_summary_crawler.py --year 2025 --target 50 --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("缺少 pypdf：先运行 pip install -r requirements.txt")

warnings.filterwarnings("ignore")
logging.getLogger("pypdf").setLevel(logging.ERROR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

__version__ = "0.1.0"

BASE = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
STATIC = "https://static.cninfo.com.cn/"
CST = timezone(timedelta(hours=8))
TAG = re.compile(r"<[^>]+>")
A_SHARE = re.compile(r"^(000|001|002|003|300|301|600|601|603|605|688|689)")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "cninfo-summary-crawler/0.1"
)


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_title(s: str) -> str:
    s = TAG.sub("", s or "")
    s = s.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'")
    return re.sub(r"\s+", " ", s).strip()


def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\s]+', "", s or "")
    return s[:40] or "unknown"


def period_of(title: str) -> str:
    m = re.search(r"(20\d{2})", title)
    return m.group(1) if m else ""


def valid_title(title: str, year: int) -> bool:
    if "年度报告摘要" not in title and "年度报告_摘要" not in title:
        return False
    if period_of(title) != str(year):
        return False
    bad = (
        "半年度", "英文", "English", "已取消", "取消公告",
        "摘要的更正", "关于", "更正公告",
    )
    return not any(x in title for x in bad)


def headers(user_agent: str) -> dict[str, str]:
    return {"User-Agent": user_agent, "Referer": "https://www.cninfo.com.cn/"}


def request_bytes(
    url: str,
    data: bytes | None,
    timeout: int,
    retries: int,
    user_agent: str,
) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers(user_agent))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429):
                wait = 30 * (attempt + 1)
                print(f"  HTTP {e.code}，等待 {wait}s 后重试", flush=True)
                time.sleep(wait)
            else:
                time.sleep(2 + attempt * 3)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"请求失败: {url} ({last})")


def query_page(
    page: int,
    year: int,
    timeout: int,
    retries: int,
    user_agent: str,
    late: bool,
) -> dict[str, Any]:
    # 主窗口：报告期当年 12 月 + 次年 1-4 月（年报季）；
    # --late 时扩到次年 12 月，收补披露/更正版本。
    end = f"{year + 1}-12-31" if late else f"{year + 1}-04-30"
    window = f"{year}-12-01~{end}"
    body = urllib.parse.urlencode({
        "pageNum": page,
        "pageSize": 30,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": "年度报告摘要",
        "secid": "",
        "category": "category_ndbg_szsh",
        "trade": "",
        "seDate": window,
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }).encode()
    raw = request_bytes(BASE, body, timeout, retries, user_agent)
    return json.loads(raw.decode("utf-8"))


def collect(
    year: int,
    pool: int,
    max_pages: int,
    include_st: bool,
    interval: float,
    timeout: int,
    retries: int,
    user_agent: str,
    late: bool,
) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for page in range(1, max_pages + 1):
        data = query_page(page, year, timeout, retries, user_agent, late)
        anns = data.get("announcements") or []
        if not anns:
            break
        for a in anns:
            code = str(a.get("secCode") or "")
            title = clean_title(a.get("announcementTitle"))
            if not code or not valid_title(title, year):
                continue
            if not A_SHARE.match(code):
                continue
            name = clean_title(a.get("secName") or a.get("tileSecName") or "")
            if not name:
                continue
            if not include_st and ("ST" in name.upper() or "退" in name):
                continue
            old = by_code.get(code)
            if old is None or int(a.get("announcementTime") or 0) > int(old.get("announcementTime") or 0):
                by_code[code] = a
        print(f"元数据第 {page} 页：{len(by_code)} 家公司", flush=True)
        if len(by_code) >= pool:
            break
        time.sleep(interval * 1.2 + random.random() * 0.3)
    return list(by_code.values())


def extract_pdf(path: Path) -> tuple[list[str], str, str]:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for p in reader.pages:
        try:
            t = p.extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        t = t.replace("\x00", "").replace("\x0c", "")
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        pages.append(t)
    body = "\n\n".join(
        f"<!-- page: {i} -->\n{t}" if t else f"<!-- page: {i} -->"
        for i, t in enumerate(pages, 1)
    )
    return pages, body, "".join(pages)


def quality_ok(text: str, page_count: int, min_chars: int, min_cpp: int) -> tuple[bool, str]:
    if len(text) < min_chars:
        return False, f"chars={len(text)} < {min_chars}"
    if page_count and len(text) / page_count < min_cpp:
        return False, f"chars/page={len(text) / page_count:.0f} < {min_cpp}"
    bad = text.count("\ufffd")
    if bad / max(1, len(text)) > 0.02:
        return False, f"replacement chars={bad}"
    return True, ""


def fetch_one(
    a: dict[str, Any],
    year: int,
    out: Path,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    code = str(a["secCode"])
    name = clean_title(a.get("secName") or a.get("tileSecName") or "")
    title = clean_title(a.get("announcementTitle"))
    url = STATIC + a["adjunctUrl"]
    sub = f"{code}_{safe_name(name)}"
    pdf_path = out / "raw" / sub / f"{a['announcementId']}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if not pdf_path.exists():
            data = request_bytes(url, None, args.timeout, args.retries, args.user_agent)
            if not data.startswith(b"%PDF"):
                print(f"  {code} 不是 PDF，跳过", flush=True)
                return None
            pdf_path.write_bytes(data)
            time.sleep(args.interval + random.random() * 0.3)
        pdf_sha = sha256_file(pdf_path)
        pages, body, text = extract_pdf(pdf_path)
    except Exception as e:  # noqa: BLE001
        print(f"  {code} 失败：{type(e).__name__}: {e}", flush=True)
        return None

    ok, why = quality_ok(text, len(pages), args.min_chars, args.min_chars_per_page)
    if not ok:
        print(f"  {code} 跳过：{why}", flush=True)
        return None

    retrieved = now_iso()
    header = (
        f"<!-- source: {url} | retrieved: {retrieved} | sha256: {pdf_sha} -->\n"
        f"<!-- company: {code} {name} | period: {year} | doc_type: 年度报告摘要 "
        f"| pages: {len(pages)} | chars: {len(text)} -->\n"
    )
    md = header + body + "\n"
    md_bytes = len(md.encode("utf-8"))
    rel = Path("summaries") / sub / f"{year}_年度报告摘要.md"

    return {
        "path": str(rel).replace("\\", "/"),
        "company_code": code,
        "company_name": name,
        "doc_type": "年度报告摘要",
        "period": str(year),
        "announcement_title": title,
        "source_url": url,
        "retrieved_at": retrieved,
        "sha256": sha256_bytes(md.encode("utf-8")),
        "pdf_sha256": pdf_sha,
        "bytes": md_bytes,
        "chars": len(text),
        "pages": len(pages),
        "announcement_id": str(a["announcementId"]),
        "announcement_time": int(a.get("announcementTime") or 0),
        "converter": "pypdf",
        "loss_notes": "表格按文本行保留，未做结构化表格转换",
        "body": body,
        "md": md,
    }


def build_outputs(
    selected: list[dict[str, Any]],
    year: int,
    out: Path,
    args: argparse.Namespace,
) -> None:
    selected.sort(key=lambda r: r["company_code"])

    for r in selected:
        p = out / r["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(r["md"], encoding="utf-8", newline="\n")

    manifest = out / "manifest.jsonl"
    with open(manifest, "w", encoding="utf-8", newline="\n") as f:
        for r in selected:
            row = {k: v for k, v in r.items() if k not in ("md", "body")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    total_bytes = sum(r["bytes"] for r in selected)
    total_chars = sum(r["chars"] for r in selected)
    total_pages = sum(r["pages"] for r in selected)
    retrieved = now_iso()

    toc = "\n".join(
        f"| {i:02d} | {r['company_code']} | {r['company_name']} | "
        f"{r['period']} | {r['pages']} | {r['bytes'] / 1024:.1f} KB |"
        for i, r in enumerate(selected, 1)
    )
    parts = [
        f"# {len(selected)} 份 A 股年报摘要（{year} 年度）\n",
        "> 来源：巨潮资讯网（cninfo.com.cn）  ",
        f"> 抓取时间：{retrieved}  ",
        f"> 文件数：{len(selected)}；总文本：{total_bytes / 1e6:.2f} MB；"
        f"总页数：{total_pages}；总字符：{total_chars:,}  ",
        "> 说明：正文由 PDF 文本层逐页转换，**未做 LLM 摘要、改写或翻译**；"
        "每份文件用 document 注释分隔，页内保留 page 注释。  ",
        "> 生成程序：`cninfo_summary_crawler.py`\n",
        "## 目录\n",
        "| # | 代码 | 公司 | 期间 | 页数 | 大小 |",
        "|---:|---|---|---|---:|---:|",
        toc,
        "\n---\n",
    ]
    for r in selected:
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
        parts.append(r["body"].strip() + "\n\n---\n")

    combined = out / f"{len(selected)}_summaries.md"
    combined.write_text("\n".join(parts), encoding="utf-8", newline="\n")

    sizes = sorted(r["bytes"] for r in selected)
    sample_note = "固定种子随机抽样" if args.random else "按体积优先（偏向较长摘要，不是随机抽样）"
    raw_note = "已删除（--no-raw）" if args.no_raw else "`raw/`（默认保留）"
    raw_bullet = "" if args.no_raw else "- `raw/`：原始 PDF，便于对照\n"
    window_end = f"{year + 1}-12-31" if args.late else f"{year + 1}-04-30"
    report = f"""# 年报摘要抓取报告

- 抓取时间：{retrieved}
- 来源：巨潮资讯网 `https://www.cninfo.com.cn/`
- 报告期：{year}
- 查询窗口：{year}-12-01 ~ {window_end}
- 交付：{len(selected)} 份
- 选样：{sample_note}
- 总文本：{total_bytes / 1e6:.2f} MB；总页数：{total_pages}；总字符：{total_chars:,}
- 单份大小：min {sizes[0] / 1024:.1f} KB / median {sizes[len(sizes) // 2] / 1024:.1f} KB / max {sizes[-1] / 1024:.1f} KB
- 转换：pypdf，PDF 文本层逐页提取，表格按文本行保留
- 未使用 LLM：没有摘要、改写、翻译或补全
- 原始 PDF：{raw_note}

## 交付物

- `{len(selected)}_summaries.md`：合并版，适合直接阅读/全文检索
- `summaries/`：单文件 Markdown
- `manifest.jsonl`：来源、sha256、页数、字符数
{raw_bullet}
## 说明

单份摘要平均约 {total_bytes / len(selected) / 1024:.1f} KB；总量 {total_bytes / 1e6:.2f} MB。
如需更多文件，加大 `--target` 和 `--pool`；如需随机样本，加 `--random`。
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    print(f"完成：{len(selected)} 份 / {total_bytes / 1e6:.2f} MB / {total_pages} 页", flush=True)
    print(f"合并文件：{combined}", flush=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="年报摘要抓取器：抓取巨潮资讯网 A 股年报摘要，输出 Markdown（不调用 LLM）",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--year", type=int, default=datetime.now().year - 1,
                    help="报告期，默认去年（如 2025）")
    ap.add_argument("--target", type=int, default=50, help="最终交付份数")
    ap.add_argument("--pool", type=int, default=90, help="候选公司数，需 >= target")
    ap.add_argument("--max-pages", type=int, default=12, help="元数据最多翻页数")
    ap.add_argument("--out", type=Path, default=Path("cninfo_output"), help="输出目录")
    ap.add_argument("--random", action="store_true", help="随机抽 target 份（默认按体积优先）")
    ap.add_argument("--include-st", action="store_true", help="包含 ST/退市风险公司")
    ap.add_argument("--late", action="store_true",
                    help="查询窗口扩到次年 12 月，包含补披露/更正版本")
    ap.add_argument("--min-chars", type=int, default=2000, help="单份最少字符数")
    ap.add_argument("--min-chars-per-page", type=int, default=100, help="单页最少字符数")
    ap.add_argument("--interval", type=float, default=1.0, help="PDF 请求间隔秒数")
    ap.add_argument("--timeout", type=int, default=120, help="下载超时秒数")
    ap.add_argument("--retries", type=int, default=3, help="请求重试次数")
    ap.add_argument("--user-agent", default=DEFAULT_UA, help="User-Agent")
    ap.add_argument("--no-raw", action="store_true", help="转换后删除原始 PDF")
    ap.add_argument("--dry-run", action="store_true", help="只列候选，不下载")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.pool < args.target:
        raise SystemExit("--pool 必须 >= --target")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"报告期 {args.year}，目标 {args.target} 份，候选 {args.pool} 家", flush=True)

    candidates = collect(
        year=args.year,
        pool=args.pool,
        max_pages=args.max_pages,
        include_st=args.include_st,
        interval=args.interval,
        timeout=min(args.timeout, 30),
        retries=args.retries,
        user_agent=args.user_agent,
        late=args.late,
    )
    print(f"候选公司：{len(candidates)} 家", flush=True)

    if args.dry_run:
        for a in candidates:
            t = clean_title(a.get("announcementTitle"))
            print(f"{a['secCode']} {a.get('secName', '')} {t[:80]}", flush=True)
        return

    rows: list[dict[str, Any]] = []
    for i, a in enumerate(candidates[: args.pool], 1):
        print(f"[{i:02d}/{min(len(candidates), args.pool)}] {a['secCode']}", flush=True)
        row = fetch_one(a, args.year, out, args)
        if row:
            rows.append(row)

    if len(rows) < args.target:
        raise SystemExit(
            f"有效摘要只有 {len(rows)} 份，少于目标 {args.target}；"
            "加大 --pool / --max-pages 后重跑"
        )

    if args.random:
        random.Random(42).shuffle(rows)
    else:
        rows.sort(key=lambda r: -r["bytes"])
    selected = rows[: args.target]

    build_outputs(selected, args.year, out, args)

    if args.no_raw:
        shutil.rmtree(out / "raw", ignore_errors=True)
        print("已删除原始 PDF（--no-raw）", flush=True)


if __name__ == "__main__":
    main()
