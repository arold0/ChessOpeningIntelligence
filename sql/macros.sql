-- ============================================================================
-- Chess Opening Intelligence — DuckDB Macros
-- ============================================================================
-- Execution order: 2 of 4 (schema.sql → macros.sql → views.sql → metrics.sql)
--
-- Reusable formulas defined once and referenced by views and metrics.
-- These macros mirror the Python equivalents in pipeline/config.py to
-- ensure consistency between the Python and SQL layers.
-- ============================================================================

-- ── expected_score ───────────────────────────────────────────────────────────
-- Standard Elo expected score formula.
-- Given an Elo difference (white_elo - black_elo), returns the expected
-- score for White (0.0 to 1.0).
--
-- Formula: E = 1 / (1 + 10^(-elo_diff / 400))
--
-- Examples:
--   expected_score(0)    → 0.5    (equal Elo)
--   expected_score(200)  → 0.76   (White is 200 points stronger)
--   expected_score(-200) → 0.24   (White is 200 points weaker)

CREATE OR REPLACE MACRO expected_score(elo_diff) AS
    1.0 / (1.0 + POWER(10, -elo_diff::DOUBLE / 400.0));


-- ── elo_bracket ──────────────────────────────────────────────────────────────
-- Classify an Elo rating into a bracket label.
-- Must match pipeline/config.py ELO_BRACKETS exactly.
--
-- Brackets: <800, 800-999, 1000-1199, ..., 2000-2199, 2200+

CREATE OR REPLACE MACRO elo_bracket(elo) AS
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
    END;


-- ── score_rate ───────────────────────────────────────────────────────────────
-- Calculate the score rate from wins, draws, and total games.
-- Score = (wins + 0.5 * draws) / total_games
--
-- Returns NULL if total_games is 0 (avoids division by zero).

CREATE OR REPLACE MACRO score_rate(wins, draws, total_games) AS
    CASE
        WHEN total_games = 0 THEN NULL
        ELSE (wins + 0.5 * draws)::DOUBLE / total_games::DOUBLE
    END;


-- ── adjusted_score_rate ──────────────────────────────────────────────────────
-- Actual Score Rate minus Expected Score based on Elo difference.
-- Positive values mean the opening outperforms Elo expectation.
-- Negative values mean it underperforms.

CREATE OR REPLACE MACRO adjusted_score_rate(wins, draws, total_games, avg_elo_diff) AS
    score_rate(wins, draws, total_games) - expected_score(avg_elo_diff);


-- ── confidence_flag ──────────────────────────────────────────────────────────
-- Returns 'low' if sample size is below threshold (500 games),
-- 'normal' otherwise. Used throughout views and the dashboard.

CREATE OR REPLACE MACRO confidence_flag(games_count) AS
    CASE
        WHEN games_count < 500 THEN 'low'
        ELSE 'normal'
    END;
