# 复现包（给第二人）

> 目标：由第二个人在**全新目录**独立复跑 core20 的 S 档 G1。作者不参与操作。  
> 当前状态：待安排第二人，尚未执行。

## 目录

```text
reproduction/
  reproduction.md           # 复现协议、验收标准、记录表
  scripts/reproduce_core20.ps1  # 复现脚本
  questions_core20.jsonl    # 20 题固定样本
  questions_all163.jsonl    # 163 题题库（判分需要）
  scale_expectations.json   # answer/refuse 标签
  baseline.md               # 基线结果
  S/                        # 10 份 S 档语料
  code/runner/              # 运行、判分脚本
  code/config/              # 模型/组别/判分配置
  code/prompts/             # 共用提示词
```

## 快速开始

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
```

执行前请确认：

- pi 1.4.0；
- 有 Token/API 配额，或已配置本地大模型权限；
- 不复制作者的 `code/runs/` 和历史轨迹。

## 验收

- 60 次运行（20 题 ×3），0 失败；
- G1 S 总分与基线 **0.975** 差异 ≤ 0.05；
- 结果文件：`code/runs/repro_core20_S_G1.jsonl`、`code/runs/repro_core20_scores_S_G1.jsonl`；
- 在 `reproduction.md` 第 5 节填写记录表。

> 说明：本包已包含 `code/runner/`、`code/config/`、`code/prompts/`、`S/` 和题集；在 `reproduction/` 根目录运行即可，结果写到 `reproduction/code/runs/`。
