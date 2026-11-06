# 复现脚本：S 档 G1，core20，20 题 x3 次
#
# 当前状态：由第二人独立执行；当前待安排。
# 原因：复现应由独立的人验证，作者不参与操作；执行需要 Token/API 配额，
#       或先申请本地大模型使用权限。
# 本阶段只交付脚本、复现协议与说明，不伪造复现结果。
# 协议与记录表：report/reproduction.md
#
# 用法（获得权限后）：
#   powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\reproduce_core20.ps1 -Full
#
# 产物：
#   code/runs/repro_core20_S_G1.jsonl
#   code/runs/repro_core20_scores_S_G1.jsonl

param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Warning "本脚本用于第二人独立复现；运行前请确认已获得 Token/API 配额或本地大模型使用权限。"

if (-not (Test-Path "S")) {
    throw "找不到 S 语料。语料不入库，请先按 corpus/README.md 重建 S 档。"
}
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Warning "DEEPSEEK_API_KEY 未设置；如果已用 setx 写入用户环境变量，请重开终端。"
}

$questions = if ($Full) { "questions_all163.jsonl" } else { "questions_core20.jsonl" }
$metrics = "code/runs/repro_core20_S_G1.jsonl"
$scores = "code/runs/repro_core20_scores_S_G1.jsonl"
New-Item -ItemType Directory -Force "code/runs" | Out-Null

Write-Host "[1/2] 跑 S 档 G1：$questions，3 次重复"
python -X utf8 code/runner/batch.py `
    --questions $questions `
    --corpus "S" `
    --groups G1 `
    --scale S `
    --repeats 3 `
    --metrics $metrics

Write-Host "[2/2] 判分"
python -X utf8 code/runner/grade_scaled.py `
    --scale S `
    --questions "questions_all163.jsonl" `
    --expectations "scale_expectations.json" `
    --runs $metrics `
    --corpus "S" `
    --out $scores

Write-Host "完成：$scores"
