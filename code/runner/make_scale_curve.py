#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 matrix_core20.json 生成 S/M/L 规模曲线（SVG + CSV）。"""

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = json.loads((ROOT / "runs" / "matrix_core20.json").read_text(encoding="utf-8"))
OUT = ROOT.parent / "report"
SCALES = [("S", 10), ("M", 50), ("L", 100)]
GROUPS = ["G1", "G3", "G4"]
COLORS = {"G1": "#1f77b4", "G3": "#d62728", "G4": "#2ca02c"}


def points(metric):
    out = []
    for s, docs in SCALES:
        r = M.get(f"{metric}_{s}")
        if r:
            out.append((docs, r))
    return out


def xmap(docs, left, width):
    lo, hi = math.log10(10), math.log10(100)
    return left + (math.log10(docs) - lo) / (hi - lo) * width


def panel(title, series, ymin, ymax, yfmt, top, field):
    left, width = 90, 760
    height = 250
    svg = [f'<text x="{left}" y="{top-28}" font-size="18" font-weight="bold">{title}</text>']
    # axes
    svg.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+height}" stroke="#333"/>')
    svg.append(f'<line x1="{left}" y1="{top+height}" x2="{left+width}" y2="{top+height}" stroke="#333"/>')
    # y grid
    for i in range(5):
        val = ymin + (ymax - ymin) * i / 4
        y = top + height - (val - ymin) / (ymax - ymin) * height
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+width}" y2="{y:.1f}" stroke="#eee"/>')
        svg.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="12">{yfmt(val)}</text>')
    # x labels
    for s, docs in SCALES:
        x = xmap(docs, left, width)
        svg.append(f'<line x1="{x:.1f}" y1="{top+height}" x2="{x:.1f}" y2="{top+height+6}" stroke="#333"/>')
        svg.append(f'<text x="{x:.1f}" y="{top+height+24}" text-anchor="middle" font-size="12">{docs} 份</text>')
    # series
    for name, key in series:
        pts = []
        for docs, r in points(key):
            val = r[field]
            y = top + height - (val - ymin) / (ymax - ymin) * height
            pts.append((xmap(docs, left, width), y, val))
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y, v) in enumerate(pts))
        svg.append(f'<path d="{d}" fill="none" stroke="{COLORS[name]}" stroke-width="2.5"/>')
        for x, y, v in pts:
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{COLORS[name]}"/>')
            svg.append(f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" font-size="11">{v if isinstance(v,str) else (f"{v:.3f}" if ymax<=1.01 else f"{v/1000:.1f}k")}</text>')
    # legend
    lx = left + 20
    for name, _ in series:
        svg.append(f'<line x1="{lx}" y1="{top+10}" x2="{lx+24}" y2="{top+10}" stroke="{COLORS[name]}" stroke-width="2.5"/>')
        svg.append(f'<text x="{lx+30}" y="{top+14}" font-size="13">{name}</text>')
        lx += 70
    return "\n".join(svg)


def main():
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="940" height="760" '
        'font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="40" y="36" font-size="22" font-weight="bold">S/M/L 规模曲线（core20，20 题）</text>',
        '<text x="40" y="58" font-size="12" fill="#666">S/M 每格 3 次；L 每格 1 次；G3/G4 为原始分，E 校正后见报告</text>',
        panel("准确率（总分）", [("G1", "G1"), ("G3", "G3"), ("G4", "G4")], 0.88, 1.0, lambda v: f"{v:.2f}", 110, "score"),
        panel("token / 次", [("G1", "G1"), ("G3", "G3"), ("G4", "G4")], 0, 36000, lambda v: f"{v/1000:.0f}k", 430, "tokens"),
        '</svg>',
    ]
    (OUT / "scale_curve.svg").write_text("\n".join(svg), encoding="utf-8")

    with open(OUT / "scale_curve.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "docs", "score", "tokens", "seconds", "cost_mean"])
        for g in GROUPS:
            for s, docs in SCALES:
                r = M.get(f"{g}_{s}")
                if r:
                    w.writerow([g, docs, r["score"], r["tokens"], r["seconds"], r["cost_mean"]])
    print("wrote", OUT / "scale_curve.svg", OUT / "scale_curve.csv")


if __name__ == "__main__":
    main()
