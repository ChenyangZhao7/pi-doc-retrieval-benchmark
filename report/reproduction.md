# 独立复现协议（core20 / S 档 G1）

> 目的：由**第二个人**在全新目录、只看 README 和本协议，独立复跑 core20 的 S 档 G1，确认结果可复现。  
> 原则：作者不参与操作，只提供材料；不能把“作者没跑”写成“复现已完成”，也不能把“待第二人”写成“复现失败”。  
> 当前状态：**待安排第二人，尚未执行**。

## 1. 复现包

| 材料 | 位置 |
|---|---|
| 仓库/代码 | `<repo-root>`（或打包后的仓库） |
| S 档语料 | 仓库根目录 `S/`（10 份，不入 git；需单独提供） |
| 题集 | `questions_core20.jsonl`、`questions_all163.jsonl` |
| 分档标签 | `scale_expectations.json` |
| 复现脚本 | `scripts/reproduce_core20.ps1` |
| 基线结果 | `report/final_report.md`：G1 S = **0.975**，26,738 token/次，8.6 秒/次，$0.0028/次 |
| 基线原始数据 | `archive/old_source/runs/metrics.jsonl`（旧任务汇总，仅作对照） |

## 2. 前置条件

- 全新目录，不复制作者的 `code/runs/`、`.cache/` 和历史轨迹；
- pi **1.4.0**，Node.js ≥ 22.19；
- `DEEPSEEK_API_KEY` 已设置，或已获得本地大模型使用权限并改好 `models.json`；
- 仓库根目录存在 `S/`（10 份，S ⊂ M）；
- 不要修改题集、提示词、判分规则和脚本参数。

## 3. 复现步骤

```powershell
# 1) 准备全新目录
# 2) 放入 S/ 语料（10 份）
# 3) 设置 key
$env:DEEPSEEK_API_KEY = "sk-..."

# 4) 跑 core20 ×3
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
```

脚本会：

1. 用 `questions_core20.jsonl` 跑 S 档 G1，20 题 ×3 次（60 次运行）；
2. 输出 `code/runs/repro_core20_S_G1.jsonl`；
3. 用 `grade_scaled.py` 判分，输出 `code/runs/repro_core20_scores_S_G1.jsonl`。

## 4. 验收标准

| 项 | 标准 |
|---|---|
| 运行完成 | 脚本退出码 0；60 次运行；0 失败 |
| 结果文件 | metrics 与 scores 都存在，题号覆盖 core20 |
| 总分 | G1 S 与基线 **0.975** 差异 ≤ 0.05；超出则记录并排查 |
| 成本/token | 与基线同量级；token 异常需记录模型/缓存差异 |
| 引用/证据 | 抽查 3 条，确认引用带公司目录和页码 |
| 隔离 | G1 只读；不应出现越过 `S/` 的读取 |

> 说明：模型版本、API 端点和缓存命中会影响 token/费用；分数只需在合理范围，不要求逐位一致。

## 5. 复现记录（由第二人填写）

| 项 | 记录 |
|---|---|
| 复现人 |  |
| 日期 |  |
| 机器/系统 |  |
| pi 版本 |  |
| 模型/端点 |  |
| 语料 hash |  |
| 命令 | `scripts/reproduce_core20.ps1` |
| 运行次数/失败数 |  |
| G1 S 总分 |  |
| token/次、费用/次 |  |
| 与基线差异 |  |
| 遇到的问题 |  |
| 结论（通过/部分通过/不通过） |  |

## 6. 给第二人的邀约模板

> 你好，我需要一位同事按 README 在**全新目录**独立复跑一次 S 档 G1（core20，20 题 ×3 次），大约需要 20–30 分钟和少量 API 额度。你只需要按 `scripts/reproduce_core20.ps1` 操作、记录结果，不需要改代码；我提供语料、脚本和验收标准。能否帮忙？复现记录填在 `report/reproduction.md` 第 5 节即可。

## 7. 当前状态

- 脚本、语料、题集、基线材料已准备；
- 第二人尚未确定，复现尚未执行；
- 因此最终报告只写“**待第二人独立复现**”，不写“复现已通过”。
