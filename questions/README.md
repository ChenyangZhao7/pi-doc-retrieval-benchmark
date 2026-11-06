# 题集

题集文件在仓库根目录：

| 文件 | 用途 |
|---|---|
| `questions_all163.jsonl` | 163 题正式题集（A70/B42/C22/D19/E10） |
| `questions_core20.jsonl` | 20 题试点固定样本（A5/B5/C5/D2/E3） |
| `questions_g0_22.jsonl` | G0 用的 22 题样本 |
| `core20_key.json` | core20 抽样种子与题号 |
| `scale_expectations.json` | S/M/L 每档 expected=answer/refuse |
| `QUESTIONS.md` | 题集说明与覆盖 |

每题字段：`id`、`category`、`question`、`answer`、`evidence`（文件 + 页码/章节）、`status`、`review_label` 等。

## 说明

- 163 题中 40 题有人工复核标签；新增题以 AI 出题为主；
- 20 题 core20 用于所有对照实验；
- 按最终决定，不跑 163 题全量。
