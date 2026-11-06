"""跑一道 pi 题，解析 JSONL，输出一行指标。

用法示例：
    python runner/run_one.py --question "华星科技2025年研发投入是多少？" \
        --group G1 --scale S --qid q001 --repeat 1 --corpus corpus/S

输出：
    runs/<group>/<scale>/<qid>_r<repeat>.jsonl   原始事件流
    runs/<group>/<scale>/<qid>_r<repeat>.meta.json  本次运行的元数据
    runs/metrics.jsonl                           追加一行指标

注意：本脚本用 subprocess 直接捕获 pi 的 stdout 字节，不经过 PowerShell，
因此不会出现 UTF-16 编码问题。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_jsonl import parse_events, read_events  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GROUPS = json.loads((ROOT / "config" / "groups.json").read_text(encoding="utf-8"))
RUN_CONFIG = json.loads((ROOT / "config" / "run.json").read_text(encoding="utf-8"))

# Windows 上 pi 是 npm 的 pi.CMD，直接写 "pi" 时 CreateProcess 找不到
PI = shutil.which("pi") or "pi"


def get_api_key():
    """优先环境变量；Windows 上回退到用户级环境变量（setx 写入的值）。"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                value, _ = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")
                return value
        except OSError:
            pass
    return None


def pi_version():
    try:
        out = subprocess.run([PI, "-v"], capture_output=True, timeout=60)
        return out.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return "unknown"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_sha256(root):
    """对语料做快照：路径 + 每个文件内容，排序后哈希。"""
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(path).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def config_snapshot():
    """记录影响行为的配置文件哈希。"""
    paths = [
        Path.home() / ".pi" / "agent" / "settings.json",
        Path.home() / ".pi" / "agent" / "models.json",
        ROOT / ".pi" / "settings.json",
        ROOT / "config" / "run.json",
        ROOT / "config" / "models.json",
        ROOT / "config" / "groups.json",
    ]
    return {str(p): sha256_file(p)[:16] for p in paths if p.exists()}


def pricing_period(now=None):
    now = now or datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return "off-peak"
    return "peak" if (1 <= now.hour < 4 or 6 <= now.hour < 10) else "off-peak"


def corrected_cost(tokens, model, period):
    """按官方价重算费用；pi 的 usage.cost 固定用高峰价。"""
    name = model.split("/")[-1]
    table = RUN_CONFIG.get("pricing_usd_per_million", {}).get(name)
    if not table:
        return None
    price = table["peak"] if period == "peak" else table["off_peak"]
    return round(
        tokens["input"] / 1e6 * price["input"]
        + tokens["cache_read"] / 1e6 * price["cache_read"]
        + tokens["output"] / 1e6 * price["output"],
        6,
    )


def prewarm(model, timeout=180):
    """预热：第一次调用 pi/grep 会拉起 rg 并被杀毒扫描，耗时可达 27 秒。

    预热本身不计入实验指标。用缓存标记避免每道题都重复付费。
    """
    cache_dir = ROOT / ".cache"
    cache_dir.mkdir(exist_ok=True)
    marker = cache_dir / "prewarm.flag"
    if marker.exists() and time.time() - marker.stat().st_mtime < 6 * 3600:
        return {"skipped": True}

    info = {}
    if shutil.which("rg"):
        try:
            subprocess.run(["rg", "--version"], capture_output=True, timeout=60)
            info["rg"] = "ok"
        except Exception as exc:  # noqa: BLE001
            info["rg"] = str(exc)

    # 一次极小的模型调用，确保 pi 与工具链已就绪
    cmd = [
        PI, "-p", "--no-session", "--no-tools",
        "--model", model, "预热，请只回复 ok",
    ]
    env = dict(os.environ)
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        info["pi"] = "ok"
    except Exception as exc:  # noqa: BLE001
        info["pi"] = str(exc)
    marker.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def build_command(args, group):
    cmd = [PI, "--mode", "json", "--no-session"]
    if not group.get("context_files"):
        cmd.append("-nc")
    cmd += ["--model", args.model]
    if not group.get("tools"):
        cmd.append("--no-tools")
    else:
        # 必须作为一个整体参数传入；在 PowerShell 里不加引号会被逗号拆开
        cmd += ["--tools", ",".join(group["tools"])]
    for rel in group.get("extensions", []):
        cmd += ["--extension", str((ROOT / rel).resolve())]
    if args.append_prompt:
        cmd += ["--append-system-prompt", str(Path(args.append_prompt).resolve())]
    if args.thinking:
        cmd += ["--thinking", args.thinking]
    cmd.append(args.question)
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True)
    ap.add_argument("--qid", default="q000", help="题号，如 q001")
    ap.add_argument("--group", default="G1", choices=sorted(GROUPS))
    ap.add_argument("--model", default="deepseek/deepseek-flash")
    ap.add_argument("--scale", default="S", choices=["S", "M", "L"])
    ap.add_argument("--repeat", type=int, default=1, help="第几次重复（1..3）")
    ap.add_argument("--corpus", default="corpus/S", help="语料目录，作为 pi 的工作目录")
    ap.add_argument("--append-prompt", default=str(ROOT / "prompts" / "researcher.md"))
    ap.add_argument("--thinking", default=RUN_CONFIG.get("thinking"))
    ap.add_argument("--timeout", type=int, default=900, help="秒")
    ap.add_argument("--out", default=None)
    ap.add_argument("--metrics", default=str(ROOT / "runs" / "metrics.jsonl"))
    ap.add_argument("--no-prewarm", action="store_true")
    ap.add_argument("--no-corpus-hash", action="store_true")
    ap.add_argument("--allow-legacy", action="store_true",
                    help="允许使用 corpus/clean 或 corpus/dev_redacted（非公开语料，仅限复现旧结果）")
    ap.add_argument("--context-docs", default=None,
                    help="逗号分隔的语料相对路径；给出时把这些文件全文注入 system prompt（G0）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    group = GROUPS[args.group]
    corpus_dir = Path(args.corpus).resolve()
    if not corpus_dir.is_dir() and not args.dry_run:
        raise SystemExit(f"语料目录不存在: {corpus_dir}")

    normalized = str(corpus_dir).replace("\\", "/").lower()
    forbidden = ("/corpus/clean", "/corpus/dev_redacted")
    if any(x in normalized for x in forbidden) and not args.allow_legacy:
        raise SystemExit(
            "拒绝使用非公开语料 corpus/clean 或 corpus/dev_redacted。"
            "正式实验只能用 corpus/S、corpus/M、corpus/L；"
            "如确需复现旧结果，加 --allow-legacy。"
        )

    if args.context_docs:
        if group.get("tools"):
            raise SystemExit("--context-docs 只用于无工具组（G0）")
        rels = [x.strip() for x in args.context_docs.split(",") if x.strip()]
        prompt = Path(args.append_prompt).read_text(encoding="utf-8")
        parts = [prompt, "\n\n# 完整语料（按文件拼接，未做改写）\n"]
        total_chars = 0
        for rel in rels:
            path = corpus_dir / rel
            if not path.exists():
                raise SystemExit(f"语料文件不存在: {path}")
            text = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"\n<!-- file: {rel} -->\n{text}")
            total_chars += len(text)
        cache_dir = ROOT / ".cache"
        cache_dir.mkdir(exist_ok=True)
        tag = hashlib.sha256(("\n".join(rels) + str(total_chars)).encode()).hexdigest()[:12]
        context_path = cache_dir / f"g0_context_{tag}.md"
        context_path.write_text("\n".join(parts), encoding="utf-8")
        args.append_prompt = str(context_path)
        print(f"[G0] 注入 {len(rels)} 份 / {total_chars} 字符 -> {context_path}", file=sys.stderr)

    out_path = Path(args.out) if args.out else (
        ROOT / "runs" / args.group / args.scale / f"{args.qid}_r{args.repeat}.jsonl"
    )
    cmd = build_command(args, group)

    corpus_sha = None
    config_hashes = {}
    period = pricing_period()
    if not args.dry_run:
        config_hashes = config_snapshot()
        # 扩展代码也进配置快照：G3/G4 的检索行为由这些文件决定
        for rel in group.get("extensions", []):
            for name in ("index.ts", "server.mjs", "build_index.mjs", "package.json"):
                p = ROOT / rel / name
                if p.exists():
                    config_hashes[str(p)] = sha256_file(p)[:16]
        if not args.no_corpus_hash:
            corpus_sha = corpus_sha256(corpus_dir)

    if args.dry_run:
        print(json.dumps({"cwd": str(corpus_dir), "cmd": cmd}, ensure_ascii=False, indent=2))
        return

    key = get_api_key()
    if not key:
        raise SystemExit("未找到 DEEPSEEK_API_KEY（环境变量或用户环境变量）")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    args.metrics = str(Path(args.metrics))
    Path(args.metrics).parent.mkdir(parents=True, exist_ok=True)

    if not args.no_prewarm:
        prewarm(args.model)

    env = dict(os.environ)
    env["DEEPSEEK_API_KEY"] = key
    if "bash" in group.get("tools", []):
        git_bin = r"C:\Program Files\Git\bin"
        if Path(git_bin).is_dir():
            env["PATH"] = git_bin + os.pathsep + env.get("PATH", "")

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.perf_counter()
    timed_out = False
    proc = subprocess.Popen(
        cmd,
        cwd=str(corpus_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        timed_out = True
    wall_ms = round((time.perf_counter() - t0) * 1000)

    # 原样写字节，避免任何转码
    out_path.write_bytes(stdout)
    stderr_text = stderr.decode("utf-8", "replace")

    metrics = {
        "run_id": f"{args.group}_{args.scale}_{args.qid}_r{args.repeat}",
        "qid": args.qid,
        "group": args.group,
        "model": args.model,
        "scale": args.scale,
        "repeat": args.repeat,
        "started_at": started,
        "wall_ms": wall_ms,
        "timed_out": timed_out,
        "exit_code": proc.returncode,
        "pi_version": pi_version(),
        "question": args.question,
        "corpus": str(corpus_dir),
        "raw_file": str(out_path),
        "stderr_tail": stderr_text[-1000:],
    }
    metrics.update(parse_events(read_events(out_path)))
    metrics.update({
        "thinking": args.thinking,
        "temperature": RUN_CONFIG.get("temperature"),
        "model_snapshot": RUN_CONFIG.get("model_versions", {}).get(args.model),
        "pricing_period": period,
        "cost_usd_corrected": corrected_cost(metrics["tokens"], args.model, period),
        "corpus_sha256": corpus_sha,
        "config_hashes": config_hashes,
        "extensions": group.get("extensions", []),
    })

    meta = {
        "cmd": cmd,
        "cwd": str(corpus_dir),
        "model": args.model,
        "group": args.group,
        "started_at": started,
        "wall_ms": wall_ms,
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "pi_version": metrics["pi_version"],
        "thinking": args.thinking,
        "temperature": RUN_CONFIG.get("temperature"),
        "model_snapshot": metrics["model_snapshot"],
        "pricing_period": period,
        "corpus_sha256": corpus_sha,
        "config_hashes": config_hashes,
        "extensions": group.get("extensions", []),
    }
    out_path.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with open(args.metrics, "a", encoding="utf-8") as f:
        f.write(json.dumps(metrics, ensure_ascii=False) + "\n")

    summary = {k: metrics[k] for k in (
        "run_id", "group", "wall_ms", "turns", "tool_calls_total",
        "tool_calls_by_name", "tokens", "cost_usd", "cost_usd_corrected",
        "pricing_period", "thinking", "compactions",
        "pseudo_tool_call", "answer_chars", "exit_code", "timed_out",
    ) if k in metrics}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
