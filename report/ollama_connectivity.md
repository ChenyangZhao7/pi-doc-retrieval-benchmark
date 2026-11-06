# Ollama 连通性与工具调用冒烟（2026-11-04/05）

## 结论

**能连；`qwen3.5:4b` 也能调用工具了，但 5 题自动分 0/5，不能进 G1 正式表。**

- `qwen2.5:7b`、`deepseek-r1:7b`：基准题 **0/5 工具调用**；
- `qwen3.5:4b`：基准题 **5/5 调用了工具**（2–9 次），但答案跑偏/漏答，自动分 **0/5**；
- 所以“工具调用”这一关过了，“用工具把题答对”没过。

## 环境

| 项 | 值 |
|---|---|
| Ollama | 0.40.14，服务在 `127.0.0.1:11434` |
| 模型 1 | `qwen2.5:7b`，32k，tools |
| 模型 2 | `deepseek-r1:7b`，131k，tools/thinking |
| 模型 3 | `qwen3.5:4b`，262k，tools/thinking/vision |
| pi provider | `code/config/agent_ollama/models.json`（`ollama`，OpenAI 兼容 `/v1`） |

## 连通性测试

| 测试 | 结果 |
|---|---|
| `GET /api/tags` | OK |
| `POST /api/chat` | OK |
| `POST /v1/chat/completions` | OK |
| pi `--list-models` | 识别 3 个 `ollama/*` 模型 |
| pi 显式要求 `ls`（qwen2.5） | **成功调用** |

## 5 题 G1 冒烟（1 次重复）

题集：q322(A)、q306(B)、q359(C)、q364(D)、q319(E)，S 档 10 份，工具 `read/grep/find/ls`。

| 模型 | 工具调用 | 轮数 | 自动分 | 表现 | 耗时 |
|---|---:|---:|---:|---|---|
| `qwen2.5:7b` | **0/5** | 全部 1 轮 | **0.200** | 5 题全答“文档中未找到”；只有 q319 拒答得 1 | 0.7–17.4s |
| `deepseek-r1:7b` | **0/5** | 全部 1 轮 | **0.200** | q306 编造“15%”和假文件；只有 q319 拒答得 1 | 6.5–42.9s |
| `qwen3.5:4b` | **5/5**（2/2/3/2/9 次） | 3–4 轮 | **0.000** | 会 grep/read，但答成 Q4 财务、股东表、单公司摘要；q319 空回答 | 4.9–46.8s |

`qwen3.5:4b` 的具体问题：

- q306 问研发强度，它读了整份文件后总结“第四季度营收/净利润”；
- q322 问是否分红，它总结前十大股东；
- q359 问三家审计意见，它写倍轻松业务介绍；
- q364 要三家对比，它只整理铂力特；
- q319 应拒答，返回空字符串。

## 原因

1. **工具调用只是第一步**：会 `grep`/`read` 不等于会选段、抽取、核对；
2. 4B 模型读到长文件后注意力跑偏，容易总结错章节；
3. 多文档对比需要同时记住 3 家公司的数据，4B 容易只写一家；
4. 指令遵循弱：题目问“研发强度”，它答成“财务概况”。

## 结论

- 工具通道、provider、上下文都正常；
- `qwen3.5:4b` 证明“本地模型可以调工具”，但 5 题 **0.000**；
- `qwen2.5:7b` / `deepseek-r1:7b` 连工具都不调，**0.200**（只拿到 E 类拒答的 1 分）；
- **负结果已留档**：不进入 core20，也不进入正式表；
- 这类结果本身是结论：本地 4B/7B 在 agentic search 上不具备可用性，和“工具接口能不能通”是两件事。

## 负结果记录

| 项 | 值 |
|---|---|
| 模型 | qwen2.5:7b / deepseek-r1:7b / qwen3.5:4b |
| 题集 | q322(A)、q306(B)、q359(C)、q364(D)、q319(E) |
| 工具 | read / grep / find / ls |
| 重复 | 1 次 |
| 自动分 | 0.200 / 0.200 / 0.000 |
| 结论 | 不进入 core20 / 正式表 |

原始文件：

```
code/runs/G1oq/S/    qwen2.5:7b 轨迹
code/runs/G1od/S/    deepseek-r1:7b 轨迹
code/runs/G1o35/S/   qwen3.5:4b 轨迹
code/runs/_ollama/metrics_G1o*_S.jsonl
code/runs/_ollama/scores_G1o*_S.jsonl
```

## 复现

```powershell
$env:PI_CODING_AGENT_DIR="<repo-root>\code\config\agent_ollama"
cd <repo-root>\S
pi --mode json --no-session -nc --model ollama/qwen3.5:4b `
  --tools "read,grep,find,ls" --thinking off `
  --append-system-prompt "<repo-root>\code\prompts\researcher.md" `
  "倍轻松（688793）2025 年的研发强度是多少？"
```

原始轨迹：`code/runs/G1o35/S/`；指标/分数：`code/runs/_ollama/`。
