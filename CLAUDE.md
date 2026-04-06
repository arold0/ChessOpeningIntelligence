# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chess Opening Intelligence computes the **Opening Intelligence Index (OII)** — a composite metric that identifies optimal chess openings per Elo rating bracket. Raw win rates are misleading because they ignore Elo advantage and position complexity; OII corrects this via adjusted score rate, tactical complexity, and sample size scaling.

## Commands

```bash
# Install
make install-dev       # Core + dev (pytest, ruff, pre-commit)
make install-all       # Core + dev + notebook + dashboard

# Test
make test              # All tests
make test-unit         # Fast pure-function tests (no I/O)
make test-integration  # Pipeline step tests (temp files/DuckDB)
make test-sql          # SQL logic tests (temp DuckDB)
make test-cov          # Tests + HTML coverage report

# Lint & format
make lint              # Check with ruff
make format            # Auto-fix with ruff

# Pipeline
make pipeline          # Run all steps (L1 → L5)
make sample            # Generate sample data (2015-01 only)
make clean             # Remove generated data (keeps data/sample/)
```

**Run a single test:**
```bash
pytest tests/unit/test_config.py::TestEloBracket::test_boundaries_lower -v
pytest tests/sql/test_macros.py -v
```

**Test markers:** `unit`, `integration`, `sql`, `slow` (slow = real data files, excluded from default run).

## Architecture: Four-Layer Pipeline

```
Lichess .zst dumps / Puzzle CSV
    │
    ▼ L1 INGEST  — Parse PGN (python-chess), decompress .zst → data/raw/*.parquet
    ▼ L2 CLEAN   — Filter, normalize, Hive-partition by year/month → data/clean/*.parquet
    ▼ L3 LOAD    — Copy parquet → DuckDB tables (data/chess_oi.duckdb)
    ▼ L4 ANALYSE — SQL views + OII computation → opening_stats table
```

- **Python (L1–L3):** Uses Polars lazy API — never pandas — to handle 1B+ rows within ~4 GB RAM.
- **SQL (L4):** DuckDB views and macros. **SQL files must be executed in order:** `schema.sql` → `macros.sql` → `views.sql` → `metrics.sql`.

### SQL View Hierarchy

1. `v_games_enriched` — games + opening family (LEFT JOIN opening_lookup)
2. `v_opening_results` — unpivots into white/black perspectives; aggregates by ECO × color × elo_bracket × time_class
3. `v_puzzle_difficulty` — median puzzle rating by ECO (proxy for Tactical Complexity)
4. `v_blunder_zone` — median first-blunder move by opening × bracket
5. `v_opening_intelligence` — joins (2), (3); computes OII
6. `opening_stats` — materialized table from metrics.sql

### OII Formula

```
OII = ASR / Normalised(TC) × log₁₀(games_count)
```

- **ASR** = Adjusted Score Rate = `score_rate − expected_score(avg_elo_diff)` (removes Elo-advantage bias)
- **TC** = Tactical Complexity = min-max scaled median puzzle rating for the opening's ECO
- **Sample size scaling** = `log₁₀(games_count)` suppresses low-sample openings

## Key Design Conventions

**Python:**
- All shared constants live in `pipeline/config.py` (single source of truth — Elo brackets defined here must match SQL macros exactly)
- Use `pipeline/logger.py` structured logging; never bare `print()`
- Use `pathlib.Path` for all file paths
- Pipeline scripts follow `01_`, `02_`, … naming; `run_pipeline.py` orchestrates them

**SQL:**
- All identifiers `snake_case`; named CTEs (no nested subqueries)
- Reusable formulas go in `macros.sql`, not inline

**Testing:**
- `tests/conftest.py` provides shared fixtures: `sample_games_df`, `tmp_duckdb` (schema + macros loaded), `loaded_duckdb` (sample data + views loaded)
- Unit tests: pure functions, no I/O. Integration tests: temp files/DuckDB. SQL tests: `tmp_duckdb`/`loaded_duckdb` fixtures.

**Branching:** `feat/xxx → dev → main`. Never push directly to `main`. Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).

## Environment

Copy `.env.example` to `.env`:
```
LICHESS_DUMP_DIR=/path/to/zst/files
DUCKDB_PATH=./data/chess_oi.duckdb
LOG_LEVEL=INFO
CHUNK_SIZE=100000
```

## Current Status

Pipeline scripts (`01_ingest_games.py` through `05_load_duckdb.py`) are **stubs** — infrastructure (config, logging, validators, SQL layer, tests) is complete and ready for implementation. `data/sample/` contains 10K rows committed for dev/testing.
