#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投资者问答挖掘器（cninfo-question-miner）。

从深交所互动易抓取投资者对企业的提问，输出：
- questions.jsonl：每家公司的问题、回答、点赞数、日期、原文链接；
- questions.md：全市场高频关注点 + 每家公司最受关注的问题；
- REPORT.md：抓取统计。

只做抓取、清洗、关键词计数：
- 不调用 LLM；
- 不生成摘要、不改写问题；
- 关键词统计是固定词表的字符串计数，可复现。

用法：
    python cninfo_question_miner.py --manifest cninfo_output/manifest.jsonl
    python cninfo_question_miner.py --companies companies.csv --out questions_output
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

__version__ = "0.1.0"

SEARCH = "https://irm.cninfo.com.cn/newircs/index/search"
STOCK_LIST = "https://www.cninfo.com.cn/new/data/szse_stock.json"
DETAIL = "https://irm.cninfo.com.cn/ircs/question/questionDetail?questionId="
SSE_COMPANY = "https://sns.sseinfo.com/company.do?stockcode={}"
SSE_FEEDS = (
    "https://sns.sseinfo.com/ajax/userfeeds.do"
    "?typeCode=company&type=10&pageSize={page_size}&uid={uid}&page={page}"
)
CST = timezone(timedelta(hours=8))
TAG = re.compile(r"<[^>]+>")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "cninfo-question-miner/0.1"
)

# 固定词表：只做字符串计数，不做语义聚类，保证可复现。
TOPIC_KEYWORDS = (
    "股东户数", "分红", "中期分红", "特别分红", "分红率", "股息率",
    "回购", "增持", "减持", "解禁", "质押", "股权激励",
    "业绩", "业绩预告", "业绩快报", "净利润", "营收", "毛利率", "净利率",
    "现金流", "应收账款", "存货", "合同负债", "研发费用", "销售费用",
    "政府补助", "估值", "市盈率", "破净", "市值管理", "市值",
    "股价", "重组", "并购", "定增", "可转债", "融资",
    "订单", "新签订单", "中标", "产能", "产能利用率", "扩产", "停产", "复产",
    "研发", "研发管线", "专利", "注册证", "临床", "审批", "集采", "医保",
    "人工智能", "机器人", "新能源", "半导体", "算力", "大模型",
    "海外", "出海", "关税", "汇率", "原材料", "锂价", "硅料", "猪价", "房价",
    "政策", "补贴", "项目进度", "交付", "市占率", "客户", "供应商",
    "诉讼", "担保", "关联交易", "处罚", "立案", "调查", "问询函", "监管函", "关注函",
    "实控人", "董事长", "总经理", "辞职", "换届", "转型", "战略",
    "退市", "ST", "风险", "事故", "环保",
)


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def ms_to_iso(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000, CST).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""


def strip_tags(s: Any) -> str:
    return html.unescape(TAG.sub("", str(s or ""))).strip()


def parse_sse_date(raw: str) -> tuple[str, str]:
    """上证e互动返回的是“昨天 09:04”“2026年10月29日 15:20”这类文本。"""
    raw = (raw or "").strip()
    now = datetime.now(CST)
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", raw)
    if m:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                      int(m.group(4)), int(m.group(5)), tzinfo=CST)
        return dt.isoformat(timespec="seconds"), raw
    m = re.match(r"(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", raw)
    if m:
        dt = datetime(now.year, int(m.group(1)), int(m.group(2)),
                      int(m.group(3)), int(m.group(4)), tzinfo=CST)
        return dt.isoformat(timespec="seconds"), raw
    m = re.match(r"(昨天|今天)\s*(\d{1,2}):(\d{2})", raw)
    if m:
        day = now - timedelta(days=1 if m.group(1) == "昨天" else 0)
        dt = datetime(day.year, day.month, day.day,
                      int(m.group(2)), int(m.group(3)), tzinfo=CST)
        return dt.isoformat(timespec="seconds"), raw
    if "刚刚" in raw:
        return now.isoformat(timespec="seconds"), raw
    return "", raw


def request_bytes(
    url: str,
    data: bytes | None,
    timeout: int,
    retries: int,
    user_agent: str,
    referer: str = "https://irm.cninfo.com.cn/views/interactiveAnswer",
) -> bytes:
    last: Exception | None = None
    headers = {
        "User-Agent": user_agent,
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "sendtype": "formdata",
        "Accept": "application/json, text/plain, */*",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429):
                time.sleep(30 * (attempt + 1))
            else:
                time.sleep(2 + attempt * 3)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"请求失败: {url} ({last})")


def load_stock_map(timeout: int, retries: int, user_agent: str) -> dict[str, dict[str, str]]:
    raw = request_bytes(STOCK_LIST, None, timeout, retries, user_agent)
    data = json.loads(raw.decode("utf-8-sig"))
    out: dict[str, dict[str, str]] = {}
    for s in data.get("stockList") or []:
        code = str(s.get("code") or "")
        if code:
            out[code] = {
                "name": s.get("zwjc") or "",
                "org_id": s.get("orgId") or "",
            }
    return out


def load_companies(manifest: Path | None, csv_path: Path | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if csv_path:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                code = str(r.get("company_code") or r.get("code") or "").strip()
                name = str(r.get("company_name") or r.get("name") or "").strip()
                if code:
                    rows.append({"code": code, "name": name})
    elif manifest:
        if not manifest.exists():
            raise SystemExit(f"缺少 manifest: {manifest}")
        with open(manifest, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                code = str(r.get("company_code") or "")
                name = str(r.get("company_name") or "")
                if code:
                    rows.append({"code": code, "name": name})
    else:
        raise SystemExit("需要 --manifest 或 --companies")

    seen, out = set(), []
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        out.append(r)
    return out


def search_questions(
    code: str,
    org_id: str,
    page: int,
    page_size: int,
    search_types: str,
    timeout: int,
    retries: int,
    user_agent: str,
) -> dict[str, Any]:
    body = urllib.parse.urlencode({
        "pageNo": page,
        "pageSize": page_size,
        "searchTypes": search_types,
        "stockCode": f"{org_id}_{code}",
        "highLight": "true",
    }).encode()
    raw = request_bytes(SEARCH, body, timeout, retries, user_agent)
    return json.loads(raw.decode("utf-8-sig"))


def collect_company(
    code: str,
    name: str,
    org_id: str,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, args.max_pages + 1):
        data = search_questions(
            code, org_id, page, args.page_size, args.search_types,
            args.timeout, args.retries, args.user_agent,
        )
        results = data.get("results") or []
        if not results:
            break
        for r in results:
            if str(r.get("stockCode") or "") != code:
                continue
            qid = str(r.get("indexId") or "")
            if not qid or qid in seen:
                continue
            seen.add(qid)
            question = strip_tags(r.get("mainContent"))
            if not question:
                continue
            rows.append({
                "company_code": code,
                "company_name": name or strip_tags(r.get("companyShortName")),
                "question_id": qid,
                "question": question,
                "answer": strip_tags(r.get("attachedContent")),
                "asked_at": ms_to_iso(r.get("pubDate")),
                "answered_at": ms_to_iso(r.get("attachedPubDate")),
                "praise_count": int(r.get("praiseCount") or 0),
                "content_type": int(r.get("contentType") or 0),
                "qa_status": r.get("qaStatus"),
                "source_platform": "深交所互动易",
                "source_url": DETAIL + qid,
                "fetched_at": now_iso(),
            })
            if args.limit_per_company and len(rows) >= args.limit_per_company:
                return rows
        total_pages = int(data.get("totalPage") or 1)
        if page >= total_pages:
            break
        time.sleep(args.interval + random.random() * 0.3)
    return rows


def sse_uid(code: str, args: argparse.Namespace) -> str:
    referer = SSE_COMPANY.format(code)
    for attempt in range(3):
        raw = request_bytes(referer, None, args.timeout, args.retries, args.user_agent, referer)
        text = raw.decode("utf-8", "replace")
        m = re.search(r"uid=(\d+)", text)
        if m:
            return m.group(1)
        time.sleep(3 + attempt * 2)
    return ""


def collect_sse(code: str, name: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    uid = sse_uid(code, args)
    if not uid:
        return []
    referer = SSE_COMPANY.format(code)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, args.max_pages + 1):
        url = SSE_FEEDS.format(page_size=args.page_size, uid=uid, page=page)
        raw = request_bytes(url, None, args.timeout, args.retries, args.user_agent, referer)
        text = raw.decode("utf-8", "replace")
        chunks = re.split(r'<div class="m_feed_item m_question"', text)[1:]
        if not chunks:
            break
        for chunk in chunks:
            m_id = re.search(r'id="item-(\d+)"', chunk)
            m_txt = re.search(r'<div class="m_feed_txt"[^>]*>(.*?)</div>', chunk, re.S)
            if not m_id or not m_txt:
                continue
            qid = m_id.group(1)
            if qid in seen:
                continue
            seen.add(qid)
            question = strip_tags(m_txt.group(1))
            question = re.sub(r"^:[^ ]+\(\d{6}\)", "", question).strip()
            if not question:
                continue
            m_date = re.search(r'<div class="m_feed_from">\s*<span>(.*?)</span>', chunk, re.S)
            asked_at, asked_raw = parse_sse_date(strip_tags(m_date.group(1)) if m_date else "")
            rows.append({
                "company_code": code,
                "company_name": name,
                "question_id": qid,
                "question": question,
                "answer": "",
                "asked_at": asked_at,
                "asked_at_raw": asked_raw,
                "answered_at": "",
                "praise_count": 0,
                "content_type": 10,
                "qa_status": "",
                "source_platform": "上证e互动",
                "source_url": f"https://sns.sseinfo.com/company.do?stockcode={code}#item-{qid}",
                "fetched_at": now_iso(),
            })
            if args.limit_per_company and len(rows) >= args.limit_per_company:
                return rows
        if len(chunks) < args.page_size:
            break
        time.sleep(args.interval + random.random() * 0.3)
    return rows


def rank_questions(rows: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in sorted(
        rows,
        key=lambda x: (int(x.get("praise_count") or 0), x.get("asked_at") or ""),
        reverse=True,
    ):
        key = re.sub(r"\s+", "", r["question"])[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= top:
            break
    return out


def keyword_stats(rows: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        q = r["question"]
        for kw in TOPIC_KEYWORDS:
            if kw in q:
                counts[kw] += 1
                if len(examples[kw]) < 2:
                    examples[kw].append(r["source_url"])
    return [
        {"keyword": kw, "count": n, "examples": examples[kw]}
        for kw, n in counts.most_common(top)
    ]


def build_markdown(
    rows: list[dict[str, Any]],
    companies: list[dict[str, str]],
    keywords: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_company[r["company_code"]].append(r)

    lines = [
        "# 投资者最常问企业的问题",
        "",
        "> 来源：深交所互动易（irm.cninfo.com.cn）+ 上证e互动（sns.sseinfo.com，沪市）  ",
        f"> 抓取时间：{now_iso()}  ",
        f"> 公司数：{len(companies)}；问题数：{len(rows)}  ",
        "> 说明：问题原文来自互动易，**未做 LLM 改写或总结**；"
        "“高频关注点”是固定词表的字符串计数，可复现。  ",
        "> 生成程序：`cninfo_question_miner.py`",
        "",
        "## 样本内高频关注点",
        "",
        "| # | 关键词 | 出现次数 | 示例问题 |",
        "|---:|---|---:|---|",
    ]
    for i, k in enumerate(keywords, 1):
        example = ""
        if k["examples"]:
            example = f"[示例]({k['examples'][0]})"
        lines.append(f"| {i:02d} | {k['keyword']} | {k['count']} | {example} |")

    lines += ["", "## 问题样例（按点赞数、日期排序）", "",
              "| # | 公司 | 问题 | 点赞 | 日期 |", "|---:|---|---|---:|---|"]
    for i, r in enumerate(rank_questions(rows, 20), 1):
        q = r["question"].replace("|", "\\|")
        if len(q) > 100:
            q = q[:100] + "…"
        lines.append(
            f"| {i:02d} | {r['company_code']} {r['company_name']} | "
            f"[{q}]({r['source_url']}) | {r['praise_count']} | {r['asked_at'][:10]} |"
        )

    lines += ["", "## 分公司问题", ""]
    for c in companies:
        code = c["code"]
        items = by_company.get(code) or []
        lines.append(f"### {code} {c['name']}（{len(items)} 条）")
        lines.append("")
        if not items:
            lines.append("_互动易没有抓到该公司的提问。_")
            lines.append("")
            continue
        for i, r in enumerate(rank_questions(items, args.top_per_company), 1):
            q = r["question"]
            lines.append(f"{i}. **{r['asked_at'][:10]}** · 赞 {r['praise_count']} · "
                         f"[原文]({r['source_url']})")
            lines.append("")
            lines.append(f"   {q}")
            lines.append("")
            if r.get("answer"):
                a = r["answer"].replace("\n", " ")
                if len(a) > 300:
                    a = a[:300] + "…"
                lines.append(f"   > 回答：{a}")
                lines.append("")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="投资者问答挖掘器：抓取互动易提问，输出高频关注点和每家公司的问题",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--manifest", type=Path, default=Path("cninfo_output/manifest.jsonl"),
                    help="年报摘要爬虫产出的 manifest，读取 company_code/company_name")
    ap.add_argument("--companies", type=Path, help="CSV：company_code,company_name 或 code,name")
    ap.add_argument("--out", type=Path, default=Path("questions_output"))
    ap.add_argument("--limit-per-company", type=int, default=30, help="每家公司最多抓多少条，0=不限")
    ap.add_argument("--max-pages", type=int, default=3, help="每家公司最多翻多少页")
    ap.add_argument("--page-size", type=int, default=30)
    ap.add_argument("--search-types", default="1,11", help="1=未回复，11=已回复")
    ap.add_argument("--top-per-company", type=int, default=10, help="Markdown 里每家公司展示多少条")
    ap.add_argument("--top-keywords", type=int, default=20)
    ap.add_argument("--interval", type=float, default=1.0, help="请求间隔秒数")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--user-agent", default=DEFAULT_UA)
    ap.add_argument("--dry-run", action="store_true", help="只列公司，不抓取")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    companies = load_companies(args.manifest, args.companies)
    if not companies:
        raise SystemExit("没有公司")
    print(f"公司数：{len(companies)}", flush=True)

    if args.dry_run:
        for c in companies:
            print(f"{c['code']} {c['name']}")
        return

    stock_map = load_stock_map(args.timeout, args.retries, args.user_agent)
    args.out.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for i, c in enumerate(companies, 1):
        code = c["code"]
        if code.startswith("6"):
            rows = collect_sse(code, c["name"], args)
            if not rows:
                print(f"[{i:02d}/{len(companies)}] {code} 上证e互动近1个月无提问/未取到 uid", flush=True)
                missing.append(code)
        else:
            meta = stock_map.get(code)
            if not meta or not meta.get("org_id"):
                print(f"[{i:02d}/{len(companies)}] {code} 缺少 orgId，跳过", flush=True)
                missing.append(code)
                continue
            rows = collect_company(code, c["name"] or meta["name"], meta["org_id"], args)
        all_rows.extend(rows)
        print(f"[{i:02d}/{len(companies)}] {code} {c['name']}：{len(rows)} 条", flush=True)
        time.sleep(args.interval + random.random() * 0.3)

    # 去重
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for r in all_rows:
        dedup[(r["company_code"], r["question_id"])] = r
    rows = list(dedup.values())

    with open(args.out / "questions.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in sorted(rows, key=lambda x: (x["company_code"], x["asked_at"], x["question_id"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    keywords = keyword_stats(rows, args.top_keywords)
    md = build_markdown(rows, companies, keywords, args)
    (args.out / "questions.md").write_text(md, encoding="utf-8", newline="\n")

    platform_counts = Counter(r.get("source_platform") or "未知" for r in rows)
    report = f"""# 投资者问答抓取报告

- 抓取时间：{now_iso()}
- 来源：深交所互动易 `https://irm.cninfo.com.cn/` + 上证e互动 `https://sns.sseinfo.com/`（沪市）
- 公司数：{len(companies)}；抓到问题的公司：{len({r['company_code'] for r in rows})}
- 问题数：{len(rows)}；平台分布：{dict(platform_counts)}
- 无数据/缺少 orgId 跳过：{len(missing)} {missing[:10]}
- 每家公司上限：{args.limit_per_company or '不限'} 条；最多翻 {args.max_pages} 页
- 关键词表：固定 {len(TOPIC_KEYWORDS)} 个词，字符串计数，无 LLM
- 输出：`questions.jsonl`（全量）、`questions.md`（高频关注点 + 分公司问题）

## 免责声明

互动易内容版权归原平台/用户所有；本工具只做公开信息的抓取与统计，不构成投资建议。
"""
    (args.out / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    print(f"完成：{len(rows)} 条问题，输出 {args.out}", flush=True)


if __name__ == "__main__":
    main()
