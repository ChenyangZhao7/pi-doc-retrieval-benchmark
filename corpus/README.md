# Corpus (S / M / L)

| Scale | Docs | Bytes | Notes |
|---|---:|---:|---|
| S | 10 | 382,966 | 10 docs selected from M to maximize coverage of the original 80 questions |
| M | 50 | 1,722,556 | 50 docs from the earlier task |
| L | 100 | 3,036,077 | M + 50 new docs (seed 20261104) |

- Source: public 2025 annual-report summaries from CNINFO (巨潮资讯);
- Format: Markdown, with `<!-- page: -->` markers preserved;
- `S_index/`, `M_index/`, and `L_index/` are corpus copies with `INDEX.md` and `AGENTS.md` for G1+; they are not additional documents;
- Do not edit corpus content; hashes and company lists are in `../MANIFEST.json`.

## Rebuild scripts

The crawler and packaging scripts are under `scripts/` and `../tools/cninfo-summary-crawler/`.

1. Use `scripts/cninfo_summary_crawler.py` to download 2025 annual-report summaries from CNINFO;
2. Use `scripts/make_bundles.py` to split the bundle by document count;
3. The S/M/L scales in this repository were constructed as above.

The scripts were copied from an archived task and may default to old paths; change `--out` / `--summaries` before running.
