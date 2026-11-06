# 年报摘要抓取器（cninfo-summary-crawler）

> 建议仓库名：`cninfo-summary-crawler`  
> 作者：ChenyangZhao7  
> 版本：v0.1.0  
> 本项目中的位置：**辅助语料采集工具**。完整独立版在此目录；实验用精简副本见 `corpus/scripts/`。

抓取巨潮资讯网（cninfo.com.cn）A 股**年报摘要**，把 PDF 文本层逐页转成 Markdown；附带一个互动易**投资者问答挖掘器**。输出：

- 一个合并版 Markdown（适合直接阅读、全文检索）；
- 每份摘要一个单文件 Markdown；
- `manifest.jsonl`：来源 URL、抓取时间、sha256、页数、字符数；
- `REPORT.md`：抓取与选样报告；
- `raw/`：原始 PDF（默认保留，`--no-raw` 可删）。

**只做格式转换：不调用 LLM，不摘要、不改写、不翻译。**

## 环境

- Python 3.9+
- 依赖：`pypdf`

```bash
pip install -r requirements.txt
```

## 快速开始

抓 50 份 2025 年年报摘要：

```bash
python cninfo_summary_crawler.py --year 2025 --target 50
```

输出在 `cninfo_output/`：

```
cninfo_output/
  50_summaries.md          # 合并版
  summaries/               # 50 份单文件
  manifest.jsonl
  REPORT.md
  raw/                     # 原始 PDF
```

只看看候选、不下载：

```bash
python cninfo_summary_crawler.py --year 2025 --target 50 --dry-run
```

随机抽 50 份（默认是按体积优先）：

```bash
python cninfo_summary_crawler.py --year 2025 --target 50 --random
```

扩大候选池，确保能凑够 50 份：

```bash
python cninfo_summary_crawler.py --year 2025 --target 50 --pool 120 --max-pages 15
```

转换完删除原始 PDF：

```bash
python cninfo_summary_crawler.py --year 2025 --target 50 --no-raw
```

## 参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--year` | 去年 | 报告期，如 `2025` |
| `--target` | 50 | 最终交付份数 |
| `--pool` | 90 | 候选公司数，必须 ≥ target |
| `--max-pages` | 12 | 元数据最多翻页数 |
| `--out` | `cninfo_output` | 输出目录 |
| `--random` | 关 | 随机抽 target 份；默认按体积优先 |
| `--include-st` | 关 | 包含 ST/退市风险公司 |
| `--late` | 关 | 查询窗口扩到次年 12 月，包含补披露/更正版本 |
| `--min-chars` | 2000 | 单份最少字符数 |
| `--min-chars-per-page` | 100 | 单页最少字符数，用于排除扫描件 |
| `--interval` | 1.0 | PDF 请求间隔秒数 |
| `--timeout` | 120 | 下载超时秒数 |
| `--retries` | 3 | 请求重试次数 |
| `--no-raw` | 关 | 转换后删除原始 PDF |
| `--dry-run` | 关 | 只列候选，不下载 |

## 选样逻辑

1. 用 `category_ndbg_szsh` + `searchkey=年度报告摘要` 查年报摘要；
2. 默认查询报告期当年 12 月到次年 4 月 30 日（年报季）；`--late` 扩到次年 12 月；
3. 过滤：只保留报告期匹配、标题含“年度报告摘要”的公告；
4. 排除：半年度、英文版、已取消、“关于…更正公告”本身、ST/退市风险公司；
5. 同一公司同一报告期只保留最新版本；“更正后/更新后”的摘要会保留；
6. 默认按 Markdown 字节数从大到小取 `target` 份，保证 50 份尽量接近 1.5 MB；
7. `--random` 则用固定种子随机抽。

## 输出格式

合并版顶部有目录，每份摘要：

```markdown
<!-- document: 000001 平安银行 | 2025 | 年度报告摘要 | https://... | sha256: ... -->
# 000001 平安银行 — 2025 年年度报告摘要

- 来源：https://...
- 抓取时间：2026-11-02T18:00:00+08:00
- 页数：14；字符：12,561；大小：25.5 KB

<!-- page: 1 -->
...原文...
```

- UTF-8 无 BOM，LF 换行；
- 每页保留 `<!-- page: N -->`；
- 每份文件保留 `source_url`、`retrieved_at`、`sha256`；
- 正文来自 PDF 文本层，表格按文本行保留，尚未做结构化 Markdown 表格。

## 按份数切成多个合并文件

只抓一次，再切成不同份数（较小的包是较大包的子集，不重复下载）：

```bash
python make_bundles.py --out cninfo_output --sizes 10 20 50
```

输出 `cninfo_output/bundles/10_summaries.md`、`20_summaries.md`、`50_summaries.md`，格式与合并版一致（含目录与来源注释）。

注意：

- 当前默认抓取结果是 100 份 / 约 3 MB，因此只做小规模合并包；`--sizes` 超过 manifest 份数会直接报错；
- M/L 档（约 20 MB / 100 MB）需要先扩抓，当前环境没有本地模型权限、API 长文本成本高，**测试范围收缩为 S 档**；
- 这里的合并包主要给 G0（整篇塞上下文）用，不是 S/M/L 正式语料分档；正式分档用 `corpus/scripts/plan_scales.py` + `materialize_scale.py`。

## 抓取投资者问答（可选）

`cninfo_question_miner.py` 抓取投资者对企业的提问，统计“大家最常问什么”：

- 深市/北交所：深交所互动易；
- 沪市：上证e互动；
- 输出每家公司的问题、回答、日期、原文链接，以及样本内高频关注词。

```powershell
# 用年报摘要爬虫产出的 manifest（推荐）
python cninfo_question_miner.py --manifest cninfo_output/manifest.jsonl

# 或者自己准备一个 CSV
# company_code,company_name
# 000001,平安银行
# 600519,贵州茅台
python cninfo_question_miner.py --companies companies.csv
```

输出：

```text
questions_output/
  questions.md        # 高频关注点 + 分公司问题
  questions.jsonl     # 全量问题、回答、日期、链接
  REPORT.md
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--limit-per-company` | 30 | 每家公司最多抓多少条，0=不限 |
| `--max-pages` | 3 | 每家公司最多翻页数 |
| `--top-per-company` | 10 | Markdown 里每家公司展示多少条 |
| `--top-keywords` | 20 | 高频关注词展示多少个 |
| `--interval` | 1.0 | 请求间隔秒数 |

说明：

- “高频关注点”是固定词表的字符串计数，**不调用 LLM**，可复现；
- 每家公司的问题按点赞数、日期排序；互动易点赞通常为 0，所以日期是主要排序依据；
- 上证e互动的问题来自公司页 HTML，回答内容暂未抓取；互动易带回答；
- 只抓公开问答，不绕过登录/验证码。

## 已知限制

- 扫描件没有文本层，会被直接跳过，不做 OCR；
- 表格可能被 PDF 文本层拆成多行，阅读时不如原 PDF 直观；
- 巨潮接口、字段和反爬策略可能变化，脚本不保证长期可用；
- 只抓公开披露文件，不绕过登录、验证码或付费墙。

## 合规

- 仅用于公开资料的整理与研究；
- 默认单线程、1 秒级间隔，遇到 403/429 会退避；
- 上传/发布前请自行确认巨潮资讯网的服务条款和当地法律；
- 与本项目无关的任何数据再分发风险由使用者承担。

## 示例题集

`questions/` 下附了用 50 份年报摘要生成的 **80 道 AI 候选题**：

- `questions/questions_s_80_candidates.jsonl`
- `questions/questions_s_80_candidates.md`
- `questions/questions_s_80_candidates.validation.md`

这些是候选，不是正式题集；正式使用前需要人工核对答案、页码和题面。

## License

未附带 LICENSE 文件；上传 GitHub 前请按你的需要选择许可证。
