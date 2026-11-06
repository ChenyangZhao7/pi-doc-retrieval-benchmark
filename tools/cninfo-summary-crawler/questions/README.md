# 题集与工具

## 当前 80 题

- `official_80.jsonl`：80 道题，A20 / B20 / C15 / D15 / E10；
- `official_80.md`：人工审阅表；
- `official_80.validation.md`：校验报告。

题目基于 50 份 2025 年年报摘要，证据路径形如：

```text
603801_志邦家居/2025_年度报告摘要.md
```

这些摘要文件不在本仓库里；校验时用 `--corpus` 指向本地语料目录。

## 校验 / 渲染工具

```text
scripts/question_set_tool.py
scripts/run_question_tool.bat
scripts/README.md
```

常用命令：

```powershell
python -X utf8 scripts/question_set_tool.py all --strict
python -X utf8 scripts/question_set_tool.py check --strict
python -X utf8 scripts/question_set_tool.py render
```

在有语料的本机：

```powershell
python -X utf8 scripts/question_set_tool.py all --strict `
  --corpus "<old-project>\corpus\incoming\summaries"
```

没有语料时，工具只做结构校验（分类数量、字段、D 类长度/结构），并跳过 probe 和证据文件检查。

## 历史 AI 候选

`questions_s_80_candidates.jsonl`、`.md`、`.validation.md` 是生成过程中的 AI 候选版本，
保留作对比；当前以 `official_80.jsonl` 为准。
