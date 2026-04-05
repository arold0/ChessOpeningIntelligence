# Chess Opening Intelligence — Gemini Context

## Project goal

End-to-end data pipeline (L1-L4) that ingests 12 months of Lichess data (~1B games), calculates the **Opening Intelligence Index (OII)** and **Blunder Zone** metrics, and delivers a hybrid dashboard (Streamlit + Power BI).

## Stack (Scalable v1.1)

| Tool | Role |
|------|------|
| Python 3.11 | Orchestration and PGN streaming |
| polars | **Lazy API** for all transformations (`pl.scan_parquet`) |
| DuckDB | Analytical SQL engine (Brain of the project) |
| DBeaver | SQL Client/GUI for DuckDB management |
| SQL | All business logic and metric formulas |
| Streamlit | Hosted public dashboard (Free portfolio link) |
| Power BI | Local high-detail analytical reports |

## Scalability & Performance (Mandatory)

- **Streaming:** Use `zstandard` for on-the-fly PGN decompression. NEVER uncompress to disk.
- **Lazy Evaluation:** Use `pl.scan_parquet()` or `pl.scan_csv()` in Polars to allow the query optimizer to handle 1B+ rows.
- **Chunking:** Process games in chunks (e.g., 100k) to maintain memory usage < 4GB RAM.
- **Partitioning:** Store L2 data in Parquet files using Hive-style partitioning: `data/clean/year=YYYY/month=MM/`.
- **Idempotency:** All pipeline scripts must be re-runnable without duplicating data in DuckDB.

## Folder structure

```
chess-opening-intelligence/
├── data/
│   ├── source/       ← .zst download files (git-ignored, L1 input)
│   ├── raw/          ← L1 output: raw parquet (git-ignored)
│   ├── clean/        ← L2 output: partitioned parquet (git-ignored)
│   └── sample/       ← committed (10K rows for dev/testing)
├── pipeline/
│   ├── __init__.py
│   ├── config.py     ← shared constants, paths, brackets
│   ├── logger.py     ← structured pipeline logging
│   ├── validators.py ← data quality assertion functions
│   ├── run_pipeline.py
│   ├── 01_ingest_games.py
│   ├── 02_ingest_puzzles.py
│   ├── 03_clean_games.py
│   ├── 04_clean_puzzles.py
│   └── 05_load_duckdb.py
├── sql/
│   ├── schema.sql    ← DDL
│   ├── macros.sql    ← DuckDB macros (expected_score, elo_bracket)
│   ├── views.sql     ← Analytical views
│   └── metrics.sql   ← OII formulas
├── notebooks/        ← EDA and OII validation
├── dashboard/
│   ├── app.py        ← Streamlit entry point
│   └── chess_oi.pbix ← Power BI report
├── tests/
│   ├── conftest.py   ← Shared fixtures
│   ├── unit/         ← Pure function tests
│   ├── integration/  ← Pipeline step tests
│   └── sql/          ← SQL logic tests
├── DESIGN.md         ← Blueprint (Private)
├── GEMINI.md         ← Context (Private)
└── README.md         ← Public Portfolio Page
```

## Core tables (Updated)

```sql
-- games: partitioned by year/month
game_id, played_at, year, month, eco, opening_name, result,
white_elo, black_elo, elo_diff, time_class, time_control,
termination, has_eval, first_blunder_move, platform

-- moves_summary: aggregated move stats per game and color
game_id, color, avg_cp_loss, max_cp_loss, blunder_count,
mistake_count, time_trouble_moves, move_count

-- puzzles: 5.88M rows
puzzle_id, fen, eco, puzzle_rating, rating_dev,
popularity, nb_plays, themes, opening_tags

-- opening_lookup: ~3,500 rows
eco, name, pgn, uci, family

-- opening_stats: the analytics engine
eco, color, elo_bracket, time_class, games_count, wins, draws, losses,
avg_asr, avg_tc, oii_score, median_blunder, confidence
```

## Key metrics

### 1. Opening Intelligence Index (OII)
- **ASR:** Actual performance minus expected score (Elo-adjusted).
- **TC:** **Bracket-aware** median puzzle rating for the opening family.
- **Formula:** `ASR / Normalised(TC) * log10(games_count)`.

### 2. The Blunder Zone
- **Definition:** The median move number where the first blunder occurs for a specific (Opening × Elo Bracket).
- **Goal:** Help amateur players identify where they typically "lose control".

## Python conventions

- **Pathlib:** Use `pathlib.Path` for all local path handling.
- **Environment:** Use `.env` for local configuration (Lichess dump paths).
- **Type Hints:** Required on all function signatures.
- **Polars Over Pandas:** Pandas only for EDA notebooks; Polars for all pipeline logic.
- **Import Safety:** All pipeline scripts use `if __name__ == "__main__":` guards.
- **Testing:** pytest with markers (`unit`, `integration`, `sql`).

## SQL conventions

- **CTEs:** Every complex query must use named CTEs for readability.
- **Snake_case:** All columns and table names.
- **DuckDB Macros:** Use for repetitive formulas (e.g., `expected_score`). Defined in `macros.sql`.
- **Separation:** `schema.sql` (DDL) → `macros.sql` (Macros) → `views.sql` (Logic) → `metrics.sql` (Formulas).

## Branch strategy
`feat/xxx → dev → main` (Never push to main).
