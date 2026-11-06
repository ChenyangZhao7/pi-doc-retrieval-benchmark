# 新任务运行目录（163 题 / S-M-L）

> 本目录只放代码与配置；语料和题集在上一级 `<repo-root>`。  
> 任务 1、2 的流程保持原样：pi 仍用 `deepseek/deepseek-flash`，判分仍用 Kimi + DeepSeek V4 Pro。

## 目录

```
code/
  runner/       运行、解析、判分、汇总（从归档复制）
  config/       groups / run / judges / task 路径清单
  prompts/      researcher.md
  extensions/   search_docs（G3/G4，未建新索引）
  runs/         运行后生成
  .cache/       预热标记、G0 上下文等
```

## 语料与题集

| 档 | 语料 | 题数 | expected |
|---|---|---:|---|
| S | `<repo-root>\S`（10 份） | 163 | 答 41 / 拒 122 |
| M | `<repo-root>\M`（50 份） | 163 | 答 103 / 拒 60 |
| L | `<repo-root>\L`（100 份） | 163 | 答 153 / 拒 10 |

题集：`<repo-root>\questions_all163.jsonl`  
分档标签：`<repo-root>\scale_expectations.json`

## 命令

```powershell
cd "<repo-root>\code"

# 只打印命令，不调用模型
python runner/run_one.py --question "测试" --qid q301 --group G1 `
  --corpus <repo-root>/S --dry-run

# 单题
python runner/run_one.py --question "..." --qid q301 --group G1 `
  --scale S --repeat 1 --corpus <repo-root>/S

# 批量
python runner/batch.py --questions <repo-root>\questions_all163.jsonl `
  --corpus <repo-root>/S --groups G1 --scale S --repeats 3

# 判分（分档薄层：answer 走原 grade.py，refuse 走规则）
python runner/grade_scaled.py --scale S `
  --questions <repo-root>\questions_all163.jsonl `
  --expectations <repo-root>\scale_expectations.json `
  --runs runs/metrics.jsonl `
  --corpus <repo-root>\S

# 只判部分题/重判
python runner/grade_scaled.py --scale S --qid q301 --rejudge `
  --runs runs/metrics.jsonl --corpus <repo-root>\S

# 汇总
python runner/summarize_scores.py `
  --scores runs/scores_scaled_S.jsonl `
  --runs runs/metrics.jsonl `
  --out runs/summary_scaled_S.json

# 题目机械校验（163 题扩语料后，B 类 probe 用证据文档口径）
python runner/check_questions.py `
  --questions <repo-root>\questions_all163.jsonl `
  --corpus <repo-root>\L --probe-scope evidence
```

## 应拒题规则

`expected=refuse` 不调用云端模型，按固定规则判：

| 情况 | 分数 |
|---|---:|
| 明确拒答，且没给具体数值 | 1 |
| 有拒答表述，但仍给出具体金额/数值 | 0.5 |
| 没拒答，且给出具体金额/数值 | 0（按编造） |
| 没拒答，也没给可核实数值 | 0.5（含糊） |
| 空回答 | 0 |

输出记录里会带：

- `expected`：answer / refuse；
- `refuse_type`：`scale_out`（规模外）或 `e_class`（E 类）；
- `judge`：`refuse_rule`；
- `judge_cost_usd`：0。

## 尚未做

- G3/G4 的 L 档（L 索引还没建；L 的 G1/G1+/G2 已完成，1 次重复）；
- 163 题全量运行与判分；新增 63 题未人工复核；
- G3/G4 人工抽检（E 类已人工核对并校正）；
- compaction 对照与最终报告。

**交接入口**：`<repo-root>\report\handoff.md`（当前状态、费用口径、风险、下一步命令）；待办清单见 `<repo-root>\TODO.md`。

## 注意

- 不要把语料、`runs/**/*.jsonl`、`.cache` 提交到仓库；
- key 从当前进程环境变量读取，终端里设置即可；
- 旧仓库已合并到 v2；来源资产在 `<repo-root>\archive\old_source\`，不要再依赖旧目录。
