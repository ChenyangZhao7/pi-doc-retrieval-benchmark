# 汇总结果

本目录包含可以机读的汇总结果和审计证据；逐题原始 JSONL 未包含在公开仓库中。

## 内容

- `metrics_*.jsonl`：各格运行指标；
- `scores_*.jsonl`：各格判分结果；
- `matrix_core20.json`、`matrix_hybrid.json`：17 格汇总；
- `audit_*.json`：G2/G4 越界审计；
- `_g3/`：recall、切块消融、E 类人工校正；
- `_grep_cn/`：中文 grep 探针与真实统计；
- `_compact/`：压缩对照；
- `_g0/`：G0 汇总；
- `_guard/`、`_ollama/`、`_smoke/`、`_calib/`：辅助实验记录；
- `human_review/`：人工复核表与结果；
- `comparison_core20.csv`、`hybrid_core20.csv`、`scale_curve.csv`：报告用表。

## 不包含

- `code/runs/G0/`、`G1/`、`G1+/`、`G2/`、`G3/`、`G4/`、`G3h/`、`G4h/` 等逐题轨迹目录；
- `code/runs/_g3` 以外的超大可重建数据。

需要逐题轨迹时，请从原始运行环境中导出；公开仓库只保留汇总与判分结果。
