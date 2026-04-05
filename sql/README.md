# SQL Layer — Chess Opening Intelligence

## Execution Order

The SQL files must be executed in this exact order against the DuckDB database:

| Order | File | Purpose |
|-------|------|---------|
| 1 | `schema.sql` | Create all tables (DDL) |
| 2 | `macros.sql` | Register DuckDB macros (`expected_score`, `elo_bracket`, etc.) |
| 3 | `views.sql` | Create analytical views (`v_games_enriched`, `v_opening_results`, etc.) |
| 4 | `metrics.sql` | Create the OII computation view and materialise `opening_stats` |

## Quick Start

Using DuckDB CLI:

```bash
duckdb data/chess_oi.duckdb < sql/schema.sql
duckdb data/chess_oi.duckdb < sql/macros.sql
duckdb data/chess_oi.duckdb < sql/views.sql
duckdb data/chess_oi.duckdb < sql/metrics.sql
```

Or via DBeaver: open each file and execute in order against your DuckDB connection.

## Tables

| Table | Rows (est.) | Description |
|-------|-------------|-------------|
| `games` | 1.5M – 10M | One row per game (grain: `game_id`) |
| `moves_summary` | 1.5M – 10M | Aggregated move stats per game × color |
| `puzzles` | 5.88M | One row per Lichess puzzle |
| `opening_lookup` | ~3,500 | ECO code → opening family mapping |
| `opening_stats` | ~500K | Pre-aggregated OII metrics |

## Views

| View | Dependencies | Description |
|------|-------------|-------------|
| `v_games_enriched` | `games`, `opening_lookup` | Base view with opening family and Elo brackets |
| `v_opening_results` | `v_games_enriched` | Win/draw/loss + ASR by ECO × color × bracket × time class |
| `v_puzzle_difficulty` | `puzzles` | Median puzzle rating by ECO |
| `v_blunder_zone` | `v_games_enriched` | Median first blunder move by ECO × bracket |
| `v_opening_intelligence` | `v_opening_results`, `v_puzzle_difficulty` | Final OII score |
| `v_termination_analysis` | `v_games_enriched` | Termination type breakdown |
| `v_time_pressure` | `games`, `moves_summary` | Time trouble rates |

## Macros

| Macro | Signature | Description |
|-------|-----------|-------------|
| `expected_score` | `(elo_diff)` | Elo expected score formula |
| `elo_bracket` | `(elo)` | Classify Elo into bracket label |
| `score_rate` | `(wins, draws, total)` | Calculate score rate |
| `adjusted_score_rate` | `(wins, draws, total, avg_elo_diff)` | ASR = score_rate - expected_score |
| `confidence_flag` | `(games_count)` | Returns 'low' or 'normal' |
