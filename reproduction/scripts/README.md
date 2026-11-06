# 复现 core20（S 档 G1）

修订任务书要求：提供 core20 ×3 的复现脚本，**由第二人独立执行**。作者不参与操作；当前待安排第二人。执行需要 Token/API 配额或本地大模型权限，协议与记录表见 `report/reproduction.md`。

## 前置

- 安装 pi（`pi -v` 应为 1.4.0）；
- 设置 `DEEPSEEK_API_KEY`；
- 语料不入库，先把 `S/` 放回仓库根目录（见 `corpus/README.md`）。

## 一条命令（获得权限后）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
```

默认跑 `questions_core20.jsonl`（20 题 ×3 次）。要跑 163 题全量：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1 -Full
```

注意：全量 163 题会消耗更多 token；按最终决定不跑全量，且当前待第二人复现。

## 结果

- `code/runs/repro_core20_S_G1.jsonl`：运行指标；
- `code/runs/repro_core20_scores_S_G1.jsonl`：判分明细；
- `code/runs/G1/S/`：逐题 JSONL 轨迹。

## 说明

- **当前待安排第二人**：执行需要 Token/API 配额或本地大模型权限；
- 语料、索引、runs 原始 JSONL 都在 `.gitignore` 里；
- 全新目录复跑前，先确认 `S` 目录存在；
- 如果 `pi` 不在 PATH，先执行 `npm install -g @earendil-works/pi-coding-agent`（版本锁定 1.4.0）。
