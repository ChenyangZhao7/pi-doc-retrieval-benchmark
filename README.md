# pi-docbench: A Chinese Document Retrieval Benchmark for CLI Agents

[中文](#中文) · [English](#english)

---

## 中文

**pi-docbench** 是一个面向命令行文档检索 Agent 的中文基准。它使用 10 / 50 / 100 份公开上市公司年报摘要构成 S / M / L 三档语料，包含 163 道中文问题，对比全量上下文、`grep`/`read`、目录索引、`bash`、向量检索与混合检索等策略。项目提供题集、语料、运行代码、逐题指标、汇总结果和复现材料，主实验使用 `DeepSeek-V4.1-Flash-1017`。

### 主要结论

| 档 | G0 | G1 | G1+ | G2 | G3 | G4 |
|---|---:|---:|---:|---:|---:|---:|
| S | 0.975 | **0.975** | 0.950 | 0.967 | 0.958 | 0.958 |
| M | 0.950 | **0.958** | 0.933 | 0.967 | 0.900 | 0.942 |
| L | — | **0.975** | 0.950 | 0.975 | 0.950 | 0.950 |

- `grep`/`read`（G1）在效果与成本之间最均衡；
- G3/G4 没有稳定超过 G1；
- 全量上下文 G0 的单次 token 消耗约为 G1 的 18 倍；
- S/M 主要组重复 3 次，L 与 hybrid 为 1 次；core20 用于所有对照实验。

### 仓库结构

```text
code/                 运行、判分、汇总脚本与配置
corpus/               S / M / L 公开年报摘要与索引副本
docs/                 任务书、判分与出题说明
questions/            163 题、core20、分档标签
report/               最终报告、讲稿、幻灯片与轨迹分析
results/              汇总指标、判分结果、审计与人工复核
reproduction/         第二人独立复现包（S 档 G1）
scripts/              复现脚本
tools/                巨潮资讯年报摘要采集工具
```

### 快速开始

```powershell
# 1. 安装 Python 依赖（按需）
pip install -r tools/cninfo-summary-crawler/requirements.txt

# 2. 设置模型密钥
$env:DEEPSEEK_API_KEY = "sk-..."

# 3. 跑 core20 的 S 档 G1（在 reproduction/ 下执行）
cd reproduction
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
```

也可以手动运行：

```powershell
python code/runner/batch.py `
  --questions questions_core20.jsonl `
  --corpus corpus/S `
  --groups G1 `
  --scale S `
  --repeats 3 `
  --metrics results/metrics_G1_S_core20.jsonl
```

> 复现由第二人独立执行；当前只提供脚本、协议与基线，不声称独立复现已完成。

### 数据来源与边界

- 语料来自巨潮资讯公开的上市公司 2025 年年度报告摘要；
- 不包含企业内部资料、个人身份证号、银行卡号或私人联系方式；
- 年报摘要中的股东、高管姓名与公司联系方式属于公开披露；
- 语料版权归原公司/原披露平台所有，使用前请确认相关条款。

### 复现状态

复现包位于 `reproduction/`，包含 S 档语料、core20、运行/判分脚本、基线与记录表。第二人独立复现尚待执行；仓库中不包含作者的本地运行轨迹。

---

## English

**pi-docbench** is a Chinese document-retrieval benchmark for CLI agents. It uses S/M/L corpora of 10/50/100 public annual-report summaries and 163 Chinese questions to compare full-context, `grep`/`read`, directory-index, `bash`, vector-retrieval, and hybrid strategies. The repository provides questions, corpora, runner code, per-run metrics, aggregate results, and reproduction materials. The main experiments use `DeepSeek-V4.1-Flash-1017`.

### Key results

| Scale | G0 | G1 | G1+ | G2 | G3 | G4 |
|---|---:|---:|---:|---:|---:|---:|
| S | 0.975 | **0.975** | 0.950 | 0.967 | 0.958 | 0.958 |
| M | 0.950 | **0.958** | 0.933 | 0.967 | 0.900 | 0.942 |
| L | — | **0.975** | 0.950 | 0.975 | 0.950 | 0.950 |

- `grep`/`read` (G1) offers the best balance between accuracy and cost;
- G3/G4 do not consistently outperform G1;
- full-context G0 consumes about 18× more tokens per run than G1;
- S/M main groups use 3 repeats; L and hybrid use 1 repeat; all comparisons use core20.

### Repository layout

```text
code/                 Runner, grading, aggregation code and configs
corpus/               S / M / L public annual-report summaries and index copies
docs/                 Task book, grading and question-design notes
questions/            163 questions, core20, scale expectations
report/               Final report, talk, slides, trajectory analysis
results/              Aggregate metrics, scores, audits, human review
reproduction/         Second-person reproduction kit (S / G1)
scripts/              Reproduction scripts
tools/                CNINFO annual-report summary crawler
```

### Quick start

```powershell
# 1. Install Python dependencies as needed
pip install -r tools/cninfo-summary-crawler/requirements.txt

# 2. Set the model key
$env:DEEPSEEK_API_KEY = "sk-..."

# 3. Run core20 on S / G1 (from reproduction/)
cd reproduction
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
```

Manual run:

```powershell
python code/runner/batch.py `
  --questions questions_core20.jsonl `
  --corpus corpus/S `
  --groups G1 `
  --scale S `
  --repeats 3 `
  --metrics results/metrics_G1_S_core20.jsonl
```

> Reproduction is intended to be performed independently by a second person. This repository provides scripts, protocol, and baselines; it does not claim that independent reproduction has been completed.

### Data and scope

- Corpora are public 2025 annual-report summaries from CNINFO;
- No internal company documents, personal ID numbers, bank accounts, or private contact details are included;
- Shareholder/executive names and company contact details in annual reports are public disclosures;
- Copyright in the underlying reports belongs to the respective companies/platforms; check their terms before reuse.

### Reproduction status

The reproduction kit is under `reproduction/` and includes the S corpus, core20 questions, runner/grading code, baseline, and record sheet. Independent reproduction by a second person is still pending; the repository does not include the author's local run traces.
