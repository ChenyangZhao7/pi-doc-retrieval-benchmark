# 163 题题集（80 旧 + 50 新 + 33 补）

> 执行口径见 [`docs/task.md`](docs/task.md)：163 题题库，正式实验用固定种子抽 core20 ×3。
>
> 状态：**163 题全部 official**。旧 80 题、40 题抽样中的 20 道新题、以及剩余 63 题均由用户确认转 official。  
> 判分器校准：20 条模型回答，人工全 1；自动判分完全一致 **19/20 = 95%**，含 0.5 可接受 **20/20 = 100%**，达到任务书 ≥85% 要求。

## 文件

| 文件 | 用途 |
|---|---|
| `questions_all163.jsonl` | **统一题集（当前正式使用）** |
| `archive/intermediate/questions_new50.jsonl` | 新增 50 题（q381–q430），中间产物 |
| `archive/intermediate/questions_new33.jsonl` | 补充 33 题（q431–q463），中间产物 |
| `archive/intermediate/questions_all130.jsonl` | 中间版本，仅保留，不再使用 |
| `scale_expectations.json` | 163 题 × 三档的 `answer` / `refuse` 标签 |
| `human_review_40.md` | 40 题人工复核表（盲评） |
| `human_review_40.csv` | 填写后的复核表 |
| `human_review_40_result.md` | 复核结果摘要 |
| `human_review_40_result.json` | 复核结果机器可读版 |
| `human_review_40_key.json` | 抽样清单、种子、分层统计 |
| `human_review_answers_20.md` | 20 条模型回答盲评表（判分校准） |
| `human_review_answers_20.csv` | 20 条回答复核表（已填人工标签） |
| `human_review_answers_20_result.md` | 判分器校准结果 |
| `human_review_answers_20_result.json` | 校准结果机器可读版 |
| `human_review_answers_20_key.json` | 20 条抽样清单 |
| `archive/scripts/make_new_questions.py` | 新 50 题生成与校验（历史脚本） |
| `archive/scripts/make_new33.py` | 补 33 题生成与校验（历史脚本） |
| `archive/scripts/make_review40.py` | 40 题分层抽样（历史脚本） |
| `archive/deprecated/_deprecated_questions_S51.jsonl` | 旧的 S 专用 51 题，不再使用 |

## 题量与分布

| 类别 | 旧 80 | 新 50 | 补 33 | 合计 |
|---|---:|---:|---:|---:|
| A 精确事实 | 20 | 30 | 20 | 70 |
| B 语义改写 | 20 | 12 | 10 | 42 |
| C 跨文档汇总 | 15 | 5 | 2 | 22 |
| D 开放研究 | 15 | 3 | 1 | 19 |
| E 无答案 | 10 | 0 | 0 | 10 |
| **合计** | **80** | **50** | **33** | **163** |

## 三档 expected 标签

| 档 | 文档数 | 应回答 | 应拒答 | A 答/拒 | B 答/拒 | C 答/拒 | D 答/拒 | E 答/拒 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S | 10 | 41 | 122 | 13/57 | 15/27 | 8/14 | 5/14 | 0/10 |
| M | 50 | 103 | 60 | 40/30 | 30/12 | 17/5 | 16/3 | 0/10 |
| L | 100 | 153 | 10 | 70/0 | 42/0 | 22/0 | 19/0 | 0/10 |

规则：

- `answer`：题目证据文档全部在该档，且不是 E 类；
- `refuse`：证据文档不在该档，或 E 类；
- “规模外拒答”是正确行为，不计为错误；但必须和“可答题答错”“可答题错误拒答”分开统计。

## 覆盖情况

**100 / 100 份语料**至少被一道题引用。

- 旧 80 题覆盖 17 份旧文档；
- 新 50 题覆盖 50 份新增文档；
- 补 33 题覆盖剩余 33 份旧文档。

## 校验结果

- 163 题 id 唯一；
- 每份 L 档文档至少作为一道题的主证据；
- 证据文件、页码存在；
- A 类 probe 在证据文档命中 >0；
- B 类 probe 在**其证据文档**命中 =0（扩到 L 后，全库口径会被其他文档误报；
  例如 q350 的“收入下降”在别的文档出现 2 次，但在海目星原文 0 次）；
- 答案关键数字/表述能在标注页找到；
- 新 50 题证据只在 L 档；补 33 题证据在 M/L 档；
- 旧 80 题证据在 L 档全部存在。

## 40 题人工复核结果

- 抽样种子：`20261104`；
- 来源配额：旧 80 抽 20、新 50 抽 12、补 33 抽 8；
- 类别分布：A17 / B10 / C6 / D5 / E2；
- 预期分布：S 答9/拒31，M 答26/拒14，L 答38/拒2；
- 复核结果：**38/40 完全一致（95.0%）**；含 0.5 微瑕可接受 **39/40（97.5%）**。

| 题号 | 结论 | 处理 |
|---|---|---|
| q366 | 参考答案数据错误 | 联创光电归母净利润由 1.16 亿元改为 **4.80 亿元（480,172,675.11 元）**；原值是 Q1 单季值；模型三条回答均为 4.80 亿元，用户确认清理 recheck 标记 |
| q372 | 表述微瑕 | 用户确认不改题 |
| 其余 38 题 | 题目、答案、证据完全一致 | 无需修改 |

- q366 仍在 `questions_all163.jsonl` 中保留 `official`，但增加 `recheck_needed=true`；
- 新题中被抽到的 20 题有人工复核；未抽到的 63 题为 AI 起草 + 脚本机械校验，当前也统一标记 `official`；
- 详细结果见 `human_review_40_result.md` 和 `human_review_40_result.json`。

## 使用方式

```powershell
# 正式实验：core20 固定样本，20 题 ×3 次；判分时按 scale_expectations.json 区分 answer / refuse
python code/runner/batch.py --questions <repo-root>\questions_core20.jsonl `
  --corpus <repo-root>\S --groups G1 --scale S --repeats 3
```

判分：

- `expected=answer`：走原 `grade.py` 规则；
- `expected=refuse`：用独立薄层，只判“是否拒答 / 是否编造”，不改原 `grade.py`。

## 来源披露

- 新增 83 题由 AI 从原文抽取事实后起草；
- 答案数值、页码、证据文件由脚本机械校验；
- 尚未逐题人工复核，`origin=doc_extract+ai_draft`、`status=candidate`；
- 40 题复核通过后，再按复核结论批量修订并标 `approved_by=user`。
