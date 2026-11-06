"""批量跑题：读 questions.jsonl，按题目 × 组别 × 重复次数调用 run_one.py。

用法：
    python runner/batch.py --questions questions/questions.jsonl \
        --corpus corpus/dev_redacted --groups G1 --scale M --repeats 3
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = json.loads((ROOT / "config" / "groups.json").read_text(encoding="utf-8"))


def http_health(base, timeout=2):
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def ensure_sidecar(args, groups):
    """G3/G4 需要 search_docs sidecar；模型只加载一次。"""
    needs = any(
        any("search_docs" in ext for ext in GROUPS[g].get("extensions", []))
        for g in groups
    )
    if not needs:
        return None
    health = http_health(args.server)
    if health:
        print(f"[sidecar] 复用已有实例：{health['chunks']} chunks")
        return None
    node = shutil.which("node")
    if not node:
        raise SystemExit("未找到 node，无法启动 search_docs sidecar")
    log = ROOT / ".cache" / "search_docs" / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    port = args.server.rsplit(":", 1)[-1]
    f = open(log, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [
            node,
            str(ROOT / "extensions" / "search_docs" / "server.mjs"),
            "--index", str(Path(args.index).resolve()),
            "--model", str(Path(args.embed_model).resolve()),
            "--port", port,
        ],
        cwd=str(ROOT),
        stdout=f,
        stderr=f,
    )
    deadline = time.time() + 180
    while time.time() < deadline:
        health = http_health(args.server)
        if health:
            print(f"[sidecar] 已启动：{health['chunks']} chunks，pid={proc.pid}")
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    proc.terminate()
    raise SystemExit(f"sidecar 启动失败，见 {log}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "questions" / "questions.jsonl"))
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--groups", default="G1", help="逗号分隔，如 G1,G2")
    ap.add_argument("--scale", default="S")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--ids", default=None, help="只跑指定题号，逗号分隔")
    ap.add_argument("--model", default="deepseek/deepseek-flash")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--context-docs", default=None,
                    help='G0 用：逗号分隔的语料相对路径，或 "all" 表示语料目录下全部文件')
    ap.add_argument("--metrics", default=str(ROOT / "runs" / "metrics.jsonl"))
    ap.add_argument("--force", action="store_true", help="已存在轨迹也重跑")
    ap.add_argument("--server", default="http://127.0.0.1:8765", help="search_docs sidecar 地址")
    ap.add_argument("--index", default=str(ROOT / ".cache" / "search_docs" / "S"))
    ap.add_argument("--embed-model", default=str(ROOT / ".cache" / "models" / "bge-small-zh-v1.5"))
    ap.add_argument("--no-sidecar", action="store_true", help="不自动启动 search_docs sidecar")
    args = ap.parse_args()

    context_docs = args.context_docs
    if context_docs == "all":
        corpus = Path(args.corpus).resolve()
        rels = sorted(
            p.relative_to(corpus).as_posix()
            for p in corpus.rglob("*") if p.is_file()
        )
        context_docs = ",".join(rels)
        print(f"[G0] 注入全部 {len(rels)} 份语料")

    questions = []
    with open(args.questions, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    wanted = set(args.ids.split(",")) if args.ids else None
    if wanted:
        questions = [q for q in questions if q["id"] in wanted]

    groups = args.groups.split(",")
    total = len(questions) * len(groups) * args.repeats
    done = 0
    rows = []

    sidecar = None if args.no_sidecar else ensure_sidecar(args, groups)
    try:
        for group in groups:
            for q in questions:
                for repeat in range(1, args.repeats + 1):
                    out = ROOT / "runs" / group / args.scale / f"{q['id']}_r{repeat}.jsonl"
                    done += 1
                    prefix = f"[{done}/{total}] {group} {q['id']} r{repeat}"
                    if out.exists() and not args.force:
                        print(f"{prefix} 跳过（已存在）")
                        continue

                    cmd = [
                        sys.executable, str(ROOT / "runner" / "run_one.py"),
                        "--question", q["question"],
                        "--qid", q["id"],
                        "--group", group,
                        "--model", args.model,
                        "--scale", args.scale,
                        "--repeat", str(repeat),
                        "--corpus", args.corpus,
                        "--timeout", str(args.timeout),
                        "--out", str(out),
                        "--metrics", args.metrics,
                    ]
                    if context_docs:
                        cmd += ["--context-docs", context_docs]
                    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
                    if proc.returncode != 0:
                        print(f"{prefix} 失败: {proc.stderr[-300:]}")
                        continue
                    try:
                        summary = json.loads(proc.stdout)
                    except json.JSONDecodeError:
                        print(f"{prefix} 输出无法解析")
                        continue
                    rows.append(summary)
                    print(
                        f"{prefix} {summary['wall_ms']}ms "
                        f"turns={summary['turns']} tools={summary['tool_calls_total']} "
                        f"tok={summary['tokens']['total']} ${summary['cost_usd']}"
                    )
    finally:
        if sidecar is not None:
            sidecar.terminate()
            try:
                sidecar.wait(timeout=10)
            except subprocess.TimeoutExpired:
                sidecar.kill()
            print("[sidecar] 已停止")

    print("\n完成。汇总：")
    for r in rows:
        print(
            f"{r['run_id']}: {r['wall_ms']}ms {r['turns']}轮 "
            f"{r['tool_calls_total']}次工具 {r['tokens']['total']}token ${r['cost_usd']}"
        )


if __name__ == "__main__":
    main()
