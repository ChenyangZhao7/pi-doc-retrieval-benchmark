# G2/G4 隔离边界说明

> 结论先说：**当前不是容器隔离，是“专用目录 + 两个启发式 guard + 事后审计”。**  
> 它能防住常规越界，但不能当成安全沙箱；报告里不能写“容器隔离”。

## 1. 为什么没用容器

本机是 Windows 11，没有 Docker Desktop，WSL2 未确认可用。修订任务书允许带 bash 的组在容器或专用目录里跑；在不具备容器的条件下，实际退到“专用目录 + 启发式防护 + 事后审计”，并把残余风险写清楚。

## 2. 实际做了什么

| 层 | 做法 | 位置 |
|---|---|---|
| 目录隔离 | 把语料复制到 `<isolated-corpus>/S` / `<isolated-corpus>/M` / `<isolated-corpus>/L`，与项目目录、索引目录分开；agent 的 cwd 只在这里 | `<isolated-corpus>/{S,M,L}` |
| 只读工具 guard | `corpus_guard` 拦截 cwd 外的绝对路径、`..`、跨目录读取 | `extensions/corpus_guard` |
| bash guard | `bash_guard` 拦截 `pi-docbench`、`powershell`、`pwsh`、`cmd.exe`、`wsl`、`python`、`node`、`..`、cwd 外绝对路径、Git Bash 的 `/c/` `/z/` 路径、`cd` 到 cwd 外 | `extensions/bash_guard` |
| 工具限制 | 关闭 `edit` / `write`，避免直接改语料 | `config/groups.json` |
| 事后审计 | `audit_g2.py` 扫描每次工具调用的参数和最终回答，统计“成功越界 / 被拦截 / 引用外部路径” | `code/runs/audit_G4_*.json` |

已跑结果：G4 S/M/L 与 G2 L 的成功越界 **0**、被拦截 **0**、答案引用外部路径 **0**。

## 3. 为什么“0 越界”不等于“安全”

- guard 是字符串/路径启发式，**不是系统调用级隔离**；base64、变量拼接、`eval`、别名等可以绕过；
- 没有 OS 级只读挂载：bash 仍可在 `bench_iso_*` 内写文件、改语料；
- 没有网络隔离：guard 没拦 `curl` / `wget`，理论上可以把公开语料发出去（本轮公开语料不涉密，但报告要披露）；
- 没有进程/资源隔离：死循环、超大输出仍可能拖慢机器；
- 审计是事后扫描，不能阻止第一次越界，只能发现。

## 4. 残余风险与适用边界

**适用**：公开语料、短时间、有人值守的对照实验；出现越界也只影响一份可重建的副本。

**不适用**：内部文档、密钥、需要严格隔离的无人值守运行。那种场景必须上容器（Docker/WSL2/Windows Sandbox）或只读挂载 + 网络白名单。

## 5. 报告写法

建议原文：

> G2/G4 由于本机没有可用容器，采用专用目录 + `corpus_guard` / `bash_guard` + 事后审计的折中方案；所有运行的成功越界为 0，但该方案是启发式防护，不是安全沙箱，残余风险包括 guard 绕过、目录内写入和未限制的网络访问。
