# ♟️ Chess Opening Intelligence

> 🇪🇸 [Leer en español](README_ES.md)

> **Which chess opening actually gives you the best results for your rating?**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![DuckDB](https://img.shields.io/badge/DuckDB-analytical_engine-yellow.svg)](https://duckdb.org)

---

## The Problem

Every chess platform shows you opening win rates.
The issue is — those numbers lie. If a 1500-rated player beats a 1100-rated opponent with the London System, that "win" inflates the London's win rate at the 1500 bracket. Raw win rates don't account for *who* you're beating or *how hard* the resulting positions actually are.

This project fixes that.

---

## The Metric: Opening Intelligence Index (OII)

The **OII** is a composite metric that answers: *"For my Elo rating, which openings give me the best return on investment?"*

It adjusts for three biases that raw win rates ignore:

| Component | What it captures |
|-----------|-----------------|
| **Adjusted Score Rate (ASR)** | Your actual performance minus what the Elo formula *expects* you to score. Removes the advantage of playing weaker opponents. |
| **Tactical Complexity (TC)** | Median difficulty of puzzles that arise from this opening. A "safe" opening that avoids tactics gets weighted differently than a sharp Sicilian. |
| **Sample Size** | Logarithmic scaling prevents openings with 50 games from ranking above openings with 50,000 games. |

**Formula:** `OII = ASR / Normalised(TC) × log₁₀(games_count)`

### Example

| Opening | Win Rate (1200–1400) | ASR | OII |
|---------|---------------------|-----|-----|
| London System | 58% | +0.02 | 0.31 |
| Italian Game | 54% | +0.08 | 0.87 |

The London *looks* better by raw win rate. But once you remove the Elo advantage and factor in tactical complexity, the Italian Game delivers nearly **3× the ROI** at the 1200–1400 bracket.

> **Note:** Example values are illustrative. Real numbers will be published after the full analysis pipeline runs on 12 months of Lichess data.

---

## The Blunder Zone

For every opening and Elo bracket, we calculate the **median move number where the first serious blunder happens** (centipawn loss > 200).

This tells you *when* you typically lose the thread — and whether some openings help you stay solid longer than others.

---

## Architecture

End-to-end pipeline processing **1 billion+ games** on a single machine.

```
[Lichess .zst Dumps]     [Puzzle CSV]
        │                      │
        ▼                      ▼
   L1 · Ingest ──────────────────────► data/raw/ (parquet)
        │
        ▼
   L2 · Clean ───────────────────────► data/clean/ (partitioned parquet)
        │
        ▼
   L3 · Load ────────────────────────► DuckDB (analytical tables)
        │
        ▼
   L4 · Analyse ─────────────────────► Views + OII + Blunder Zone
        │
        ├──► Streamlit Dashboard (hosted, public)
        └──► Power BI Reports (local, deep-dive)
```

---

## Tech Stack

| Tool | Role | Why |
|------|------|-----|
| **Python 3.11** | Pipeline orchestration | PGN streaming with `python-chess` and `zstandard` |
| **Polars** | Data transformation | Lazy API handles 1B+ rows with < 4GB RAM |
| **DuckDB** | Analytical SQL engine | Runs complex analytics locally without a server |
| **SQL** | Business logic | All metrics computed in CTEs and views |
| **Streamlit** | Public dashboard | Interactive hosted visualization |
| **Power BI** | Deep-dive reports | Multi-page interactive analysis with slicers |

---

## Key Findings

> 🚧 *Results will be populated after the analysis pipeline completes on the full Lichess dataset. Stay tuned.*

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/arold0/ChessOpeningIntelligence.git
cd ChessOpeningIntelligence

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Run the puzzle pipeline
python pipeline/02_ingest_puzzles.py

# 4. Run the games pipeline
python pipeline/01_ingest_games.py
```

For all available development commands, run `make help`.

---

## Data Sources

| Source | Format | License |
|--------|--------|---------|
| [Lichess Game Database](https://database.lichess.org) | PGN `.zst` (12 months) | CC0 |
| [Lichess Puzzles](https://database.lichess.org/#puzzles) | CSV (5.88M puzzles) | CC0 |

---

## Project Structure

```
chess-opening-intelligence/
├── data/
│   ├── source/       ← .zst downloads (git-ignored)
│   ├── raw/          ← L1 output: raw parquet
│   ├── clean/        ← L2 output: partitioned parquet
│   └── sample/       ← 10K rows for dev/testing
├── pipeline/         ← Python ingestion + transformation
├── sql/              ← DDL, macros, views, and OII metrics
├── notebooks/        ← EDA and OII validation
├── dashboard/        ← Streamlit app + Power BI reports
└── tests/            ← Unit, integration, and SQL tests
```

---

## Project Status

- [x] Project design and documentation
- [x] Pipeline infrastructure (config, logging, validators)
- [x] SQL foundation (schema, macros, views, OII formula)
- [x] Test infrastructure (unit, integration, SQL tests)
- [ ] Puzzle pipeline (L1–L3)
- [ ] Games pipeline (L1–L3)
- [ ] Notebooks (EDA + OII validation)
- [ ] Streamlit dashboard
- [ ] Power BI reports
- [ ] Full analysis on 12-month dataset

---

## Contributing & Links

- 📖 [Contributing Guide](CONTRIBUTING.md) — branch strategy, code style, how to run tests
- 📄 [License (MIT)](LICENSE)
- 🗂️ [SQL Documentation](sql/README.md) — schema, macros, views, execution order

---

*Built by [Aroldo](https://github.com/arold0).*
