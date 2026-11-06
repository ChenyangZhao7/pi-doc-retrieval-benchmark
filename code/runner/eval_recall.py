"""计算 search_docs 的 recall@k（文件级 / 页码级）。

不调用 LLM，不产生运行费用。默认自动拉起本地 sidecar。

用法：
    python runner/eval_recall.py --questions questions/official_80.jsonl
    python runner/eval_recall.py --start-server 0   # 已有 sidecar 时

指标口径：
- file@k  : top-k 段落中，有任意一段来自标注的证据文件；
- page@k  : top-k 段落中，有任意一段同时命中证据文件与标注页码；
- 多证据题：命中任意一条证据即算该题命中；另给出按证据条目统计的 micro 值。

E 类（无答案）没有证据，不参与 recall。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER = Path(ROOT / "extensions" / "search_docs" / "server.mjs")
DEFAULT_INDEX = Path(ROOT / ".cache" / "search_docs" / "S")
DEFAULT_MODEL = Path(ROOT / ".cache" / "models" / "bge-small-zh-v1.5")
PAGE_RE = re.compile(r"第\s*(\d+)\s*页")


def http_json(url, payload=None, timeout=60):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json; charset=utf-8"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def wait_health(base, seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return http_json(f"{base}/health", timeout=2)
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return None


def ensure_server(base, index, model):
    """返回 (health, 自己启动的进程或 None)。"""
    health = None
    try:
        health = http_json(f"{base}/health", timeout=2)
    except Exception:  # noqa: BLE001
        pass
    if health:
        return health, None

    node = shutil.which("node")
    if not node:
        raise SystemExit("未找到 node，无法启动 search_docs sidecar")
    log = ROOT / ".cache" / "search_docs" / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log, "a", encoding="utf-8")
    port = base.rsplit(":", 1)[-1]
    proc = subprocess.Popen(
        [node, str(DEFAULT_SERVER), "--index", str(index), "--model", str(model), "--port", str(port)],
        cwd=str(ROOT),
        stdout=log_f,
        stderr=log_f,
    )
    health = wait_health(base)
    if not health:
        proc.terminate()
        raise SystemExit(f"sidecar 启动失败，见 {log}")
    return health, proc


def evidence_pages(locator):
    return [int(x) for x in PAGE_RE.findall(locator or "")]


def norm_file(value):
    return str(value or "").replace("\\", "/").strip("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "questions" / "official_80.jsonl"))
    ap.add_argument("--server", default="http://127.0.0.1:8765")
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--start-server", type=int, default=1, help="1 自动拉起 sidecar，0 不拉起")
    ap.add_argument("--k", default="1,3,5,10")
    ap.add_argument("--mode", default="hybrid", choices=["dense", "hybrid"])
    ap.add_argument("--out", default=str(ROOT / "runs" / "_g3" / "recall_at_k.json"))
    args = ap.parse_args()

    ks = sorted({int(x) for x in args.k.split(",") if x.strip()})
    kmax = max(ks)

    health = None
    proc = None
    if args.start_server:
        health, proc = ensure_server(args.server, Path(args.index), Path(args.model))
    else:
        health = wait_health(args.server, seconds=5)
    if not health:
        raise SystemExit("search_docs sidecar 不可用")
    print(f"[recall] sidecar: {health['chunks']} chunks, {health['dim']}d, model={health['model']}, mode={args.mode}")

    questions = []
    with open(args.questions, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    per_question = []
    try:
        for q in questions:
            evidences = q.get("evidence") or []
            if not evidences:
                continue
            out = http_json(f"{args.server}/search", {"query": q["question"], "k": kmax, "mode": args.mode}, timeout=120)
            results = out.get("results") or []
            files = [norm_file(r["file"]) for r in results]
            pages = [int(r["page"]) for r in results]

            file_ranks, page_ranks = [], []
            for ev in evidences:
                target = norm_file(ev.get("file"))
                ev_pages = evidence_pages(ev.get("locator"))
                f_rank = next((i + 1 for i, f in enumerate(files) if f == target), None)
                p_rank = next(
                    (
                        i + 1
                        for i, (f, p) in enumerate(zip(files, pages))
                        if f == target and (not ev_pages or p in ev_pages)
                    ),
                    None,
                )
                file_ranks.append(f_rank)
                page_ranks.append(p_rank)

            def hit(ranks, k):
                return any(r is not None and r <= k for r in ranks)

            per_question.append(
                {
                    "id": q["id"],
                    "category": q.get("category"),
                    "question": q["question"],
                    "evidence": [
                        {"file": norm_file(e.get("file")), "pages": evidence_pages(e.get("locator"))}
                        for e in evidences
                    ],
                    "asked_k": kmax,
                    "file_ranks": file_ranks,
                    "page_ranks": page_ranks,
                    "top": [
                        {"rank": i + 1, "file": files[i], "page": pages[i], "score": results[i]["score"]}
                        for i in range(len(results))
                    ],
                    **{f"file_hit@{k}": hit(file_ranks, k) for k in ks},
                    **{f"page_hit@{k}": hit(page_ranks, k) for k in ks},
                }
            )
    finally:
        if proc is not None:
            proc.terminate()

    # 汇总：题目级 + 证据条目级
    summary = {"n_questions": len(per_question), "ks": ks, "mode": args.mode, "overall": {}, "by_category": {}}
    for k in ks:
        fq = sum(1 for r in per_question if r[f"file_hit@{k}"])
        pq = sum(1 for r in per_question if r[f"page_hit@{k}"])
        f_items = [x for r in per_question for x in r["file_ranks"]]
        p_items = [x for r in per_question for x in r["page_ranks"]]
        summary["overall"][f"@{k}"] = {
            "file_question": round(fq / len(per_question), 4),
            "page_question": round(pq / len(per_question), 4),
            "file_evidence": round(
                sum(1 for x in f_items if x is not None and x <= k) / max(1, len(f_items)), 4
            ),
            "page_evidence": round(
                sum(1 for x in p_items if x is not None and x <= k) / max(1, len(p_items)), 4
            ),
            "file_question_n": f"{fq}/{len(per_question)}",
            "page_question_n": f"{pq}/{len(per_question)}",
        }

    by_cat = defaultdict(list)
    for r in per_question:
        by_cat[r["category"]].append(r)
    for cat, rows in sorted(by_cat.items()):
        summary["by_category"][cat] = {
            "n": len(rows),
            **{
                f"@{k}": {
                    "file": round(sum(1 for r in rows if r[f"file_hit@{k}"]) / len(rows), 4),
                    "page": round(sum(1 for r in rows if r[f"page_hit@{k}"]) / len(rows), 4),
                }
                for k in ks
            },
        }

    misses = [
        r
        for r in per_question
        if not r.get(f"page_hit@{max(ks)}") and not r.get(f"file_hit@{max(ks)}")
    ]
    summary["misses"] = [
        {"id": r["id"], "category": r["category"], "evidence": r["evidence"], "top": r["top"][:5]}
        for r in misses
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"summary": summary, "questions": per_question}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\n[recall] questions with evidence: {summary['n_questions']}")
    for k in ks:
        o = summary["overall"][f"@{k}"]
        print(
            f"  @{k:<2} file {o['file_question']:.3f} ({o['file_question_n']})  "
            f"page {o['page_question']:.3f} ({o['page_question_n']})  "
            f"evidence-micro file {o['file_evidence']:.3f} / page {o['page_evidence']:.3f}"
        )
    for cat, s in summary["by_category"].items():
        print(
            f"  {cat}: n={s['n']:<2} "
            + "  ".join(f"@{k} f{s[f'@{k}']['file']:.2f}/p{s[f'@{k}']['page']:.2f}" for k in ks)
        )
    print(f"\n[recall] wrote {out_path}")
    if misses:
        print(f"[recall] {len(misses)} 题在 @{max(ks)} 完全未命中：")
        for m in misses:
            print(f"  {m['id']} {m['category']} top1={m['top'][0]['file'] if m['top'] else 'n/a'}")


if __name__ == "__main__":
    main()
