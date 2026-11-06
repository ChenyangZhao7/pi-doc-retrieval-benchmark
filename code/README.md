# Code

Runner, grading, aggregation, prompts, and configuration for pi-docbench.

## Layout

```text
code/
  runner/        run, parse, grade, aggregate
  config/        groups / run / judges / task paths
  prompts/       researcher.md
  extensions/    search_docs and guards
  runs/          generated at runtime (ignored by git)
```

## Corpus and questions

The public repository includes the corpus under `../corpus/` and questions under `../questions/`.

| Scale | Corpus | Questions |
|---|---|---:|
| S | `../corpus/S` (10 docs) | 163 |
| M | `../corpus/M` (50 docs) | 163 |
| L | `../corpus/L` (100 docs) | 163 |

Question files are at the repository root:

- `../questions_all163.jsonl`
- `../questions_core20.jsonl`
- `../questions_g0_22.jsonl`
- `../scale_expectations.json`

## Commands

Run from the repository root:

```powershell
# Dry run: print the command without calling the model
python code/runner/run_one.py --question "测试" --qid q301 --group G1 `
  --corpus corpus/S --dry-run

# Single question
python code/runner/run_one.py --question "..." --qid q301 --group G1 `
  --scale S --repeat 1 --corpus corpus/S

# Batch
python code/runner/batch.py --questions questions_all163.jsonl `
  --corpus corpus/S --groups G1 --scale S --repeats 3

# Grade
python code/runner/grade_scaled.py --scale S `
  --questions questions_all163.jsonl `
  --expectations scale_expectations.json `
  --runs results/metrics_G1_S_core20.jsonl `
  --corpus corpus/S
```

## Refusal rules

`expected=refuse` does not call the cloud model; it is graded by fixed rules:

| Case | Score |
|---|---:|
| Clear refusal with no specific number | 1 |
| Refusal wording but a specific number is still given | 0.5 |
| No refusal and a specific number is given | 0 (fabrication) |
| No refusal and no verifiable number | 0.5 (vague) |
| Empty answer | 0 |
