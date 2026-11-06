"""为 G1+ 建 S_index / M_index：复制语料 + INDEX.md + AGENTS.md。"""

import json
import shutil
from pathlib import Path

ROOT = Path(r"<repo-root>")
OUT = ROOT / "code" / "runs" / "_g1plus"


def summary_of(path, company):
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    title = next((l.strip("# ").strip() for l in text.split("\n") if l.strip().startswith("# ")), company)
    # 取标题后的第一段非空文本，截断
    lines = [
        l.strip()
        for l in text.split("\n")
        if l.strip()
        and not l.strip().startswith("#")
        and not l.strip().startswith("<!--")
        and not l.strip().startswith("- 来源")
        and not l.strip().startswith("- 抓取时间")
        and not l.strip().startswith("- 页数")
        and not l.strip().startswith("- 字符")
        and "http" not in l
    ]
    snippet = lines[0] if lines else ""
    snippet = snippet[:80]
    return title, snippet


def build(scale, src):
    dst = Path(rf"<repo-root>\{scale}_index")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    rows = []
    for company_dir in sorted(p for p in dst.iterdir() if p.is_dir()):
        for md in sorted(company_dir.rglob("*.md")):
            title, snippet = summary_of(md, company_dir.name)
            rel = md.relative_to(dst).as_posix()
            rows.append(f"- `{rel}` — {title}；{snippet}")
    index = [
        f"# {scale} 语料目录索引",
        "",
        f"本目录共 {len(rows)} 份文档。每行：文件路径 — 标题；首句。",
        "",
    ] + rows + [""]
    (dst / "INDEX.md").write_text("\n".join(index), encoding="utf-8")
    agents = [
        "# 目录索引",
        "",
        "本目录根下有 `INDEX.md`，列出每份文档的路径、标题和首句。",
        "需要定位文档时，先读 `INDEX.md`，再读具体文件。",
        "",
    ]
    (dst / "AGENTS.md").write_text("\n".join(agents), encoding="utf-8")
    print(scale, "docs", len(rows), "->", dst)
    return dst


def main():
    for scale in ("S", "M", "L"):
        build(scale, ROOT / scale)


if __name__ == "__main__":
    main()
