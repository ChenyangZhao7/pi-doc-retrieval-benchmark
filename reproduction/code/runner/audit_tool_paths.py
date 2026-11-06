"""审计轨迹里的工具路径：有没有读到语料目录之外。

按 args 里的 path 字段精确判断，不用正则猜（路径含空格会截断）。

用法：
    python runner/audit_tool_paths.py --root corpus/S --runs runs/G1/S
    python runner/audit_tool_paths.py --root <corpus-root>/S --runs runs/_clean
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABS_RE = re.compile(r"[A-Za-z]:[/\\][^\"'|;&]+")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="corpus/S")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    allowed = (ROOT / args.root).resolve()
    scan_root = (ROOT / args.runs)
    offenders = {}
    total = 0

    for path in scan_root.rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if '"tool_execution_start"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            a = event.get("args") or {}
            candidates = []
            if isinstance(a.get("path"), str):
                candidates.append(a["path"])
            if isinstance(a.get("command"), str):
                candidates += ABS_RE.findall(a["command"])
            for raw in candidates:
                raw = raw.strip("`\"' ")
                p = Path(raw.replace("\\", "/"))
                if not p.is_absolute():
                    p = allowed / p
                try:
                    p = p.resolve()
                except OSError:
                    continue
                if p != allowed and allowed not in p.parents:
                    offenders.setdefault(str(p), []).append(str(path))

    print(f"扫描 tool_execution_start: {total} 次")
    print(f"越界路径: {len(offenders)} 个")
    for p, files in list(offenders.items())[: args.limit]:
        print(f"  {p}")
        print(f"    <- {sorted(set(files))[:4]}")
    if offenders:
        print("\n结论：存在语料目录之外的读取，正式结果必须隔离后重跑。")
    else:
        print("结论：没有发现语料目录之外的读取。")


if __name__ == "__main__":
    main()
