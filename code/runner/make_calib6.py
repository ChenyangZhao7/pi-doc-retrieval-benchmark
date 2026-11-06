"""抽取 20 题复核中 6 条新补题的运行，用于判分校准。"""

import json
from pathlib import Path

ROOT = Path(r"<repo-root>\code")
IDS = ["q431", "q432", "q441", "q442", "q451", "q463"]


def main():
    rows = [json.loads(l) for l in open(ROOT / "runs" / "metrics_M_clean.jsonl", encoding="utf-8") if l.strip()]
    out = [r for r in rows if r["qid"] in IDS and r.get("repeat") == 1]
    p = ROOT / "runs" / "metrics_M_calib6.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(p, len(out), [r["qid"] for r in out])


if __name__ == "__main__":
    main()
