# Chess Opening Intelligence — Design Document

> **v1.1 · Data Engineering + Data Analytics Portfolio Project**

| Field | Value |
|-------|-------|
| Scope | Data Engineering + Data Analytics |
| Primary dataset | Lichess Open Database (last 12 months) |
| Stack | Python · Polars · DuckDB · DBeaver · Streamlit · Power BI |
| Target output | Pipeline + Streamlit Hosted Dashboard + Power BI Reports |
| MVP timeline | 5 weeks |
| Unique metric | Opening Intelligence Index (OII) |

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Data Sources](#2-data-sources)
3. [Architecture](#3-architecture)
4. [Data Model](#4-data-model)
5. [The Opening Intelligence Index](#5-the-opening-intelligence-index-oii)
6. [SQL Layer](#6-sql-layer)
7. [Jupyter Notebooks](#7-jupyter-notebooks)
8. [Power BI Dashboard](#8-power-bi-dashboard)
9. [Data Quality & Pipeline Checks](#9-data-quality--pipeline-checks)
10. [MVP Roadmap](#10-mvp-roadmap)
11. [README Structure](#11-readme-structure)

---

## 1. Project Overview

This project builds an end-to-end data pipeline and analytics layer on top of the Lichess Open Database. The goal is twofold: demonstrate production-grade data engineering skills (ingestion, transformation, schema design, data quality) and deliver actionable analytics insights for chess players through a Power BI dashboard.

### 1.1 The problem

Existing chess analytics tools answer descriptive questions: *what is the win rate of the Sicilian Defense?*

This project answers a prescriptive question:

> **Given a player's Elo rating, which opening maximises results relative to the tactical difficulty it generates — i.e., what is the best opening ROI for my level?**

### 1.2 Why this is different

- **OII (Opening Intelligence Index):** A composite metric that adjusts win rates for Elo difference and tactical complexity.
- **Scalable Architecture:** Designed to process **1 billion+ games** (12-month historical window) on a single laptop using Polars and DuckDB.
- **The Blunder Zone:** Identification of the average move number where players at specific Elo levels typically lose the thread in each opening.

### 1.3 Skills demonstrated

| Skill area | What the project shows |
|------------|----------------------|
| Data Engineering | Pipeline design, multi-source ingestion, schema modelling, data quality checks |
| Data Analytics | Metric definition, statistical adjustment, EDA, storytelling, actionable dashboard |
| SQL | CTEs, window functions, aggregations, cross-source joins, view design |
| Python | PGN parsing, transformation with Polars, DuckDB integration, data quality |
| BI / Visualisation | Hybrid approach: Streamlit (hosted) + Power BI (deep-dive) |

---

## 2. Data Sources

### 2.1 Source inventory

| Source | Format | Key fields |
|--------|--------|-----------|
| [Lichess game dump](https://database.lichess.org) | PGN `.zst` (12 months) | ECO, opening name, result, Elo, termination, `%eval` Stockfish (~6%) |
| [Lichess puzzle DB](https://database.lichess.org/#puzzles) | CSV · 5.88M puzzles | PuzzleId, rating, themes, OpeningTags |
| [Lichess API](https://lichess.org/api) | NDJSON / REST | User rating history, per-user game stats |

### 2.2 Scalability Strategy

- **Stream-First:** Use `zstandard` for on-the-fly decompression. Never uncompress full months to disk.
- **Chunked Processing:** Process games in chunks (e.g., 50k–100k) using Polars `LazyFrame` to keep memory usage low.
- **Hive Partitioning:** Store clean data as Parquet files partitioned by `year/month/`.

### 2.3 Recommended starting point

> **Start with the puzzle CSV** — no parsing needed, ~200 MB, loads in seconds. Then for games start with `2015-01` (286 MB compressed). Enough to build and test the full pipeline before scaling up to recent months.

### 2.3 Filters to apply

| Filter | Rule |
|--------|------|
| Variant | Keep `standard` only. Exclude Chess960, Antichess, Atomic. |
| Bots | Exclude games where `WhiteTitle = BOT` or `BlackTitle = BOT` |
| Short games | Drop games under 5 moves (abandoned / disconnections) |
| Elo range | Keep 600–2800. Outside range = likely test accounts. |
| Time control | Drop games under 30 seconds base time |

---

## 3. Architecture

### 3.1 Pipeline layers

| Layer | Input | Output |
|-------|-------|--------|
| **L1 — Ingest** | PGN `.zst` / puzzle CSV | Raw parquet chunks in `data/raw/` |
| **L2 — Clean** | Raw parquet | Partitioned parquet in `data/clean/` (Polars) |
| **L3 — Load** | Partitioned parquet | DuckDB tables: `games`, `puzzles`, `opening_stats` |
| **L4 — Analyse** | DuckDB views | Aggregated metrics + Streamlit / Power BI datasets |

### 3.2 Technology choices

| Tool | Role and reason |
|------|----------------|
| **Polars** | High-performance, multithreaded data processing. Used for L2 transformation. |
| **DuckDB** | Analytical SQL engine. The "Engine" for processing 1B+ rows with minimal resources. |
| **DBeaver** | The "Management Tool" (GUI). Used to connect to DuckDB, write SQL, and manage the schema. |
| **Streamlit** | Hosted, interactive dashboard for free portfolio visualization (Streamlit Cloud). |
| **Power BI** | Local, high-detail visual analysis and report generation. |

### 3.3 Folder structure

```
chess-opening-intelligence/
├── data/
│   ├── source/           ← .zst download files (git-ignored, L1 input)
│   ├── raw/              ← L1 output: raw parquet from ingestion (git-ignored)
│   ├── clean/            ← L2 output: normalised partitioned parquet (git-ignored)
│   └── sample/           ← 10K row samples for dev/testing (committed)
├── pipeline/
│   ├── __init__.py
│   ├── config.py         ← shared constants, paths, brackets
│   ├── logger.py         ← structured pipeline logging
│   ├── validators.py     ← data quality assertion functions
│   ├── run_pipeline.py   ← orchestrator (CLI entry point)
│   ├── 01_ingest_games.py
│   ├── 02_ingest_puzzles.py
│   ├── 03_clean_games.py
│   ├── 04_clean_puzzles.py
│   └── 05_load_duckdb.py
├── sql/
│   ├── schema.sql        ← table definitions (DDL)
│   ├── macros.sql        ← DuckDB macros (expected_score, elo_bracket)
│   ├── views.sql         ← analytical views
│   └── metrics.sql       ← OII and derived metrics
├── notebooks/
│   ├── 01_eda_games.ipynb
│   ├── 02_eda_puzzles.ipynb
│   └── 03_opening_intelligence.ipynb
├── dashboard/
│   ├── app.py            ← Streamlit entry point
│   └── chess_oi.pbix     ← Power BI report
├── tests/
│   ├── conftest.py       ← shared fixtures
│   ├── unit/             ← pure function tests
│   ├── integration/      ← pipeline step tests
│   └── sql/              ← SQL logic tests
├── .gitignore
├── .env.example
├── pyproject.toml
├── Makefile
├── LICENSE
├── CONTRIBUTING.md
├── DESIGN.md             ← this document
├── GEMINI.md             ← AI context (private)
└── README.md
```

### 3.4 `.gitignore` essentials

```
data/source/
data/raw/
data/clean/
*.zst
*.pgn
*.duckdb
*.duckdb.wal
.env
__pycache__/
.ipynb_checkpoints/
logs/
.ruff_cache/
.pytest_cache/
dist/
*.egg-info/
htmlcov/
```

---

## 4. Data Model

Minimal schema. Five tables cover all analytical needs for the MVP.

### 4.1 Table inventory

| Table | Estimated rows | Purpose |
|-------|---------------|---------|
| `games` | 1.5M – 10M | One row per game. Grain: `game_id`. Source: PGN dump. |
| `moves_summary` | 1.5M – 10M | Aggregated move stats per game and color (not individual moves). Source: PGN parsing. |
| `puzzles` | 5.88M | One row per puzzle. Source: Lichess puzzle CSV. |
| `opening_lookup` | ~3,500 | ECO code → opening family mapping. Source: [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings). |
| `opening_stats` | ~500K | Pre-aggregated metrics by ECO × Elo bracket × color × time class. Source: SQL aggregation. |

### 4.2 `games` table

```sql
CREATE TABLE games (
    game_id             TEXT PRIMARY KEY,
    played_at           TIMESTAMPTZ,
    year                INTEGER,            -- extracted for partitioning
    month               INTEGER,            -- extracted for partitioning
    eco                 TEXT,               -- e.g. B30, C65
    opening_name        TEXT,
    result              TEXT,               -- white / black / draw
    white_elo           INTEGER,
    black_elo           INTEGER,
    elo_diff            INTEGER,            -- white_elo - black_elo
    time_class          TEXT,               -- bullet / blitz / rapid / classical
    time_control        TEXT,               -- raw string e.g. "600+0"
    termination         TEXT,               -- checkmate / resign / timeout / draw_agreement
    has_eval            BOOLEAN,            -- whether %eval is present in moves
    first_blunder_move  INTEGER,            -- move number where cp_loss > 200 (Blunder Zone)
    platform            TEXT DEFAULT 'lichess'
);
```

### 4.3 `moves_summary` table

```sql
CREATE TABLE moves_summary (
    game_id             TEXT REFERENCES games(game_id),
    color               TEXT,           -- white / black
    avg_cp_loss         NUMERIC(7,2),   -- only populated when has_eval = true
    max_cp_loss         NUMERIC(7,2),
    blunder_count       INTEGER,        -- moves with cp_loss > 200
    mistake_count       INTEGER,        -- moves with cp_loss > 100
    time_trouble_moves  INTEGER,        -- moves played with < 15% clock remaining
    move_count          INTEGER,
    PRIMARY KEY (game_id, color)
);
```

### 4.4 `puzzles` table

```sql
CREATE TABLE puzzles (
    puzzle_id       TEXT PRIMARY KEY,
    fen             TEXT,
    eco             TEXT,               -- populated when opening starts before move 20
    puzzle_rating   INTEGER,
    rating_dev      NUMERIC(6,2),
    popularity      INTEGER,            -- -100 to 100
    nb_plays        INTEGER,
    themes          TEXT,               -- comma-separated: fork, pin, skewer, etc.
    opening_tags    TEXT
);
```

### 4.5 Elo bracket definition

Used consistently across all views and the dashboard.

```sql
-- Standard brackets used throughout the project
CASE
    WHEN elo < 800  THEN '<800'
    WHEN elo < 1000 THEN '800-999'
    WHEN elo < 1200 THEN '1000-1199'
    WHEN elo < 1400 THEN '1200-1399'
    WHEN elo < 1600 THEN '1400-1599'
    WHEN elo < 1800 THEN '1600-1799'
    WHEN elo < 2000 THEN '1800-1999'
    WHEN elo < 2200 THEN '2000-2199'
    ELSE '2200+'
END AS elo_bracket
```

### 4.6 `opening_stats` table

Pre-aggregated metrics by ECO × Elo bracket × color × time class. Populated by SQL aggregation in L4.

```sql
CREATE TABLE opening_stats (
    eco             TEXT NOT NULL,
    color           TEXT NOT NULL,          -- white / black
    elo_bracket     TEXT NOT NULL,
    time_class      TEXT NOT NULL,
    games_count     INTEGER NOT NULL,
    wins            INTEGER NOT NULL,
    draws           INTEGER NOT NULL,
    losses          INTEGER NOT NULL,
    avg_asr         NUMERIC(8,4),
    avg_tc          NUMERIC(8,2),
    oii_score       NUMERIC(8,4),
    median_blunder  INTEGER,                -- median move of first blunder
    confidence      TEXT DEFAULT 'normal',  -- 'low' if games_count < 500
    PRIMARY KEY (eco, color, elo_bracket, time_class)
);
```

---

## 5. The Opening Intelligence Index (OII)

### 5.1 Components

- **Adjusted Score Rate (ASR):** Actual performance minus expected score based on average Elo difference.
- **Tactical Complexity (TC):** Bracket-aware median puzzle rating for each opening family.
- **OII:** `ASR / Bracket_Normalised(TC) × log10(games_count)`.

### 5.2 The Blunder Zone (Utility Enhancement)

A new analytical view to calculate the **median move of first blunder** (`cp_loss > 200`) per opening and Elo bracket. This helps players understand when they typically "lose control" of an opening.

### 5.3 Interpretation

- **High OII** → opening performs above expectation and generates tactically manageable positions for your level.
- **Low OII despite high win rate** → you are winning because opponents are weaker, not because of the opening.
- Always filter by Elo bracket — the OII for 1200–1400 is a different number to the OII for 1800–2000.
- Compare OII for white vs black separately.

### 5.4 Limitations to document

These must appear in Notebook 03 and on the dashboard:

1. Correlation is not causation — switching openings does not guarantee the shown OII score.
2. Puzzle difficulty is a proxy for tactical complexity, not a direct measure.
3. Results vary significantly by time control — always filter by blitz/rapid/classical separately.
4. Brackets with fewer than 500 games are flagged as **low confidence**.

---

## 6. SQL Layer

All metric calculations live in SQL. Python only handles parsing and loading. This maximises the SQL signal for a data analyst role.

### 6.1 File execution order

| File | Purpose | Run order |
|------|---------|-----------|
| `schema.sql` | Table definitions (DDL) | 1st |
| `macros.sql` | DuckDB macros (`expected_score`, `elo_bracket`) | 2nd |
| `views.sql` | Analytical views | 3rd |
| `metrics.sql` | OII formula and derived metrics | 4th |

### 6.2 Views to build (`views.sql`)

| View | Description |
|------|-------------|
| `v_games_enriched` | `games JOIN opening_lookup`. Adds `opening_family`, `elo_bracket`. |
| `v_opening_results` | Win/draw/loss counts + ASR by `eco × color × elo_bracket × time_class`. |
| `v_puzzle_difficulty` | Median puzzle rating + theme frequency by `eco`. |
| `v_opening_intelligence` | Final OII. Joins `v_opening_results` and `v_puzzle_difficulty`. Includes `confidence` flag. |
| `v_blunder_zone` | Median move of first blunder by `eco × elo_bracket`. |
| `v_termination_analysis` | Termination type breakdown by Elo bracket. Supports dashboard page 3. |
| `v_time_pressure` | From `moves_summary`: share of games where time trouble occurred by Elo bracket. |

### 6.3 SQL patterns to demonstrate

- **Window functions** — `RANK() OVER`, `NTILE()` for Elo bucketing, running totals
- **CTEs** — multi-step metric calculations without nested subqueries
- **Conditional aggregation** — `SUM(CASE WHEN result = 'white' THEN 1 ELSE 0 END)` for win/draw/loss in one pass
- **Statistical formula in SQL** — expected score calculation as a SQL expression
- **DuckDB macros** — reusable formulas (`expected_score`, `elo_bracket`) defined once in `macros.sql`
- **Cross-source join** — `games` ECO joined to `puzzles` ECO for the OII
- **Quality assertions** — `ASSERT` / inline checks that fail loudly when data is unexpected

---

## 7. Jupyter Notebooks

Three notebooks form the analytical layer. Each notebook has a clear question, clean code, and narrative Markdown between every block of code.

### Notebook 01 — EDA: Games (`01_eda_games.ipynb`)

- Distribution of Elo ratings — shape, mean, median, outliers
- Games per time control — how has blitz vs rapid grown over years
- Termination breakdown — what % ends by resign vs timeout vs checkmate
- Most played openings by Elo bracket — top 20 by frequency
- **Data quality report**: null rates, out-of-range values, duplicates found and handled

### Notebook 02 — EDA: Puzzles (`02_eda_puzzles.ipynb`)

- Puzzle rating distribution by opening family
- Most common tactical themes overall and per opening
- Popularity score distribution — are hard puzzles less popular?
- Opening coverage — which ECO codes have the most puzzles, which have few

### Notebook 03 — Opening Intelligence (`03_opening_intelligence.ipynb`)

- Show the bias in raw win rate with a concrete example
- Calculate ASR and demonstrate the correction changes rankings
- Calculate TC from puzzle data
- Build and validate the OII
- Top 10 / bottom 10 openings by OII for each Elo bracket
- Case study: Italian Game vs Sicilian across 1000–1800 Elo
- **Key findings** — 3 paragraphs written for a non-chess audience

> **Portfolio note:** Notebook 03 is the centrepiece deliverable. Write it so that someone who does not play chess can read it and understand the problem, the methodology and the findings. This is what you present in interviews.

---

## 8. Dashboard Strategy

### 8.1 Hybrid Approach

1. **Streamlit (Public Portfolio):** A live, hosted dashboard showing OII rankings and Blunder Zone insights. Connects to a light version of the DuckDB file.
2. **Power BI (Deep Dive):** Comprehensive local reports exported as PDFs/Screenshots for the GitHub README, focusing on multi-month trends and statistical confidence.

### 8.2 Required DAX measures

| Measure | Purpose |
|---------|---------|
| `Score Rate` | `(wins + 0.5 * draws) / total_games` |
| `Adjusted Score Rate` | Score Rate minus expected score based on average Elo diff |
| `OII Score` | Composite metric as defined in Section 5 |
| `Confidence Flag` | Returns `"Low confidence"` if sample < 500 games in selected filter |
| `Avg Puzzle Difficulty` | Weighted median puzzle rating for selected opening |

### 8.3 Design rules

- Maximum **6 visuals per page** — clarity over completeness
- Every chart title states the **finding**, not just the metric name (e.g. *"Italian Game outperforms at 1200–1600 Elo"* not *"Win rate by opening"*)
- Elo bracket slicer affects **all pages** via a shared filter
- Colour encodes meaning consistently: green = high OII, amber = medium, red = low
- A non-chess-player must understand what they are looking at within **5 seconds**

---

## 9. Data Quality & Pipeline Checks

Quality gates are where DE skills are demonstrated. Each pipeline step validates its output before the next step runs.

### 9.1 Checks per layer

| Layer | Checks |
|-------|--------|
| **L1 Ingest** | File SHA256 matches published checksum. Row count logged. Schema of first 100 rows validated. |
| **L2 Clean** | Null rate per column logged. Elo in 600–2800. ECO codes match known list. Duplicates detected by `game_id`. |
| **L3 Load** | Row counts match between clean parquet and DuckDB table. All ECOs in `games` exist in `opening_lookup`. |
| **L4 Analyse** | OII has no nulls for openings with > 500 games. Score rates between 0 and 1. Puzzle ratings between 400 and 3000. |

### 9.2 What to log per pipeline run

```
[INGEST]  source=lichess_2015-01.pgn.zst  rows_raw=1497237  runtime=142s
[CLEAN]   rows_in=1497237  rows_out=1441089  dropped=56148  reason=filters
[LOAD]    table=games  rows_loaded=1441089  matches_clean=True
[QUALITY] elo_range=PASS  eco_fk=PASS  null_rate_eco=0.3%=PASS  duplicate_ids=0=PASS
```

---

## 10. MVP Roadmap

| Week | Focus | Deliverable |
|------|-------|-------------|
| **1** | Setup + puzzle pipeline | Repo structure, puzzle CSV loaded into DuckDB, Notebook 02 complete |
| **2** | Games pipeline | `01_ingest_games.py` working on `2015-01` file, `games` table loaded, data quality report |
| **3** | SQL metrics layer | All views built and tested, OII calculated, Notebook 03 draft |
| **4** | Scale + validate | Pipeline runs on `2024-01` (larger file), OII stability validated, notebooks finalised |
| **5** | Power BI + README | Dashboard 3 pages complete, README with findings, repo portfolio-ready |

### What is explicitly out of scope for MVP

| Item | Reason cut |
|------|-----------|
| FastAPI / web backend | Adds engineering complexity, zero analytical signal |
| Stockfish execution | Use the ~6% of games with existing `%eval` — sufficient for MVP |
| Individual move analysis | `moves_summary` aggregates provide enough signal |
| ML models | The OII is a formula, not a model. Models are v2. |
| Multi-user system | Single-analyst pipeline only |
| Next.js / frontend | Power BI covers the visualisation deliverable |

> Every item removed from scope was cut because it adds complexity without adding analytical signal. The goal is to demonstrate DE + DA skills clearly, not to build a production SaaS.

---

## 11. README Structure

The README is what a hiring manager reads first. It must communicate project value in under 60 seconds.

| Section | Content |
|---------|---------|
| One-line description | What the project does and for whom (non-technical language) |
| The metric | What is the OII, why it is better than raw win rate, one example with real numbers |
| Key findings | 3 bullet points with concrete numbers from the analysis |
| Stack | Python · DuckDB · SQL · Power BI — with one-line justification per tool |
| How to run | Maximum 4 commands to reproduce the pipeline from scratch |
| Dashboard preview | Screenshot of page 1 of the Power BI dashboard |
| Data sources | Links to Lichess dump and puzzle CSV with licence (CC0) |

---

*Chess Opening Intelligence · Design Document v1.1*