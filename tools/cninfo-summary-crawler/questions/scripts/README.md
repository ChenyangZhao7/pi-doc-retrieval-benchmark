# 80 道题工具

校验和渲染 `questions/official_80.jsonl`，不调用 LLM，不修改题目内容。

## 用法

在项目根目录：

```powershell
python -X utf8 questions/scripts/question_set_tool.py all
python -X utf8 questions/scripts/question_set_tool.py check --strict
python -X utf8 questions/scripts/question_set_tool.py render
```

Windows 下也可以直接双击或用 PowerShell 调：

```powershell
questions\scripts\run_question_tool.bat
```

## 默认路径

| 项 | 默认 |
|---|---|
| 输入 | `questions/official_80.jsonl` |
| 语料 | `corpus/incoming/summaries` |
| 审阅表 | `questions/official_80.md` |
| 校验报告 | `questions/official_80.validation.md` |

输出路径都可以用参数覆盖：

```powershell
python -X utf8 questions/scripts/question_set_tool.py all `
  --input questions/official_80.jsonl `
  --corpus corpus/incoming/summaries `
  --md questions/official_80.md `
  --validation questions/official_80.validation.md
```

## 检查内容

- 总数 80，A20 / B20 / C15 / D15 / E10；
- 每行有 `id`、`category`、`question`、`answer`、`evidence`；
- A 类 `probe` 在语料中命中 > 0；
- B / E 类 `probe` 在语料中命中 = 0；
- C 类证据 ≥ 2 份，D 类证据 ≥ 3 份；
- 证据文件真实存在；
- D 类题面含 `1200–1500 字` 之类的长度要求；
- `q362` 之后的 D 类还必须含“结构”要求；
- 完全重复的题面会警告；A/B 同答案是允许的。

如果语料目录不存在，工具只做结构校验，并提示跳过 probe/证据检查。

`--strict` 时有错误会返回退出码 1。

## 修改题目

直接编辑 `questions/official_80.jsonl`，然后重跑：

```powershell
python -X utf8 questions/scripts/question_set_tool.py all --strict
```

工具会重新生成 `official_80.md` 和 `official_80.validation.md`，但**不会改 JSONL 本身**。
