-- ============================================================================
-- Chess Opening Intelligence — Analytical Views
-- ============================================================================
-- Execution order: 3 of 4 (schema.sql → macros.sql → views.sql → metrics.sql)
--
-- All views use macros defined in macros.sql. Each view builds on the
-- previous one to compute progressively richer analytics.
--
-- Dependencies:
--   macros: elo_bracket(), expected_score(), score_rate(),
--           adjusted_score_rate(), confidence_flag()
--   tables: games, moves_summary, puzzles, opening_lookup
-- ============================================================================


-- ── v_games_enriched ─────────────────────────────────────────────────────────
-- Enriches the base games table with opening family and Elo brackets.
-- This is the foundation view used by most downstream analytics.

CREATE OR REPLACE VIEW v_games_enriched AS
SELECT
    g.game_id,
    g.played_at,
    g.year,
    g.month,
    g.eco,
    g.opening_name,
    o.family          AS opening_family,
    g.result,
    g.white_elo,
    g.black_elo,
    g.elo_diff,
    elo_bracket(g.white_elo) AS white_elo_bracket,
    elo_bracket(g.black_elo) AS black_elo_bracket,
    g.time_class,
    g.time_control,
    g.termination,
    g.has_eval,
    g.first_blunder_move
FROM games g
LEFT JOIN opening_lookup o ON g.eco = o.eco;


-- ── v_opening_results ────────────────────────────────────────────────────────
-- Win/draw/loss counts and Adjusted Score Rate (ASR) aggregated by
-- ECO × color × Elo bracket × time class.
--
-- This view unpivots each game into two rows (one per color) so that
-- openings can be analysed from both White's and Black's perspective.

CREATE OR REPLACE VIEW v_opening_results AS
WITH game_sides AS (
    -- White's perspective
    SELECT
        eco,
        opening_family,
        'white'                             AS color,
        white_elo_bracket                   AS elo_bracket,
        time_class,
        elo_diff,
        CASE result
            WHEN 'white' THEN 1 ELSE 0
        END                                 AS is_win,
        CASE result
            WHEN 'draw' THEN 1 ELSE 0
        END                                 AS is_draw,
        CASE result
            WHEN 'black' THEN 1 ELSE 0
        END                                 AS is_loss,
        first_blunder_move
    FROM v_games_enriched

    UNION ALL

    -- Black's perspective
    SELECT
        eco,
        opening_family,
        'black'                             AS color,
        black_elo_bracket                   AS elo_bracket,
        time_class,
        -elo_diff                           AS elo_diff,   -- invert for Black
        CASE result
            WHEN 'black' THEN 1 ELSE 0
        END                                 AS is_win,
        CASE result
            WHEN 'draw' THEN 1 ELSE 0
        END                                 AS is_draw,
        CASE result
            WHEN 'white' THEN 1 ELSE 0
        END                                 AS is_loss,
        first_blunder_move
    FROM v_games_enriched
)
SELECT
    eco,
    opening_family,
    color,
    elo_bracket,
    time_class,
    COUNT(*)                                        AS games_count,
    SUM(is_win)                                     AS wins,
    SUM(is_draw)                                    AS draws,
    SUM(is_loss)                                    AS losses,
    AVG(elo_diff)                                   AS avg_elo_diff,
    score_rate(SUM(is_win), SUM(is_draw), COUNT(*)) AS score_rate,
    adjusted_score_rate(
        SUM(is_win), SUM(is_draw), COUNT(*), AVG(elo_diff)
    )                                               AS asr,
    MEDIAN(first_blunder_move)                      AS median_blunder,
    confidence_flag(COUNT(*))                        AS confidence
FROM game_sides
GROUP BY eco, opening_family, color, elo_bracket, time_class;


-- ── v_puzzle_difficulty ──────────────────────────────────────────────────────
-- Median puzzle rating and theme frequency aggregated by ECO code.
-- Represents the Tactical Complexity (TC) component of the OII.

CREATE OR REPLACE VIEW v_puzzle_difficulty AS
SELECT
    eco,
    COUNT(*)                     AS puzzle_count,
    MEDIAN(puzzle_rating)        AS median_puzzle_rating,
    AVG(puzzle_rating)           AS avg_puzzle_rating,
    MIN(puzzle_rating)           AS min_puzzle_rating,
    MAX(puzzle_rating)           AS max_puzzle_rating
FROM puzzles
WHERE eco IS NOT NULL
GROUP BY eco;


-- ── v_blunder_zone ───────────────────────────────────────────────────────────
-- Median move of first blunder per opening × Elo bracket.
-- Helps players identify where they typically "lose control".

CREATE OR REPLACE VIEW v_blunder_zone AS
WITH blunder_data AS (
    SELECT
        eco,
        opening_family,
        white_elo_bracket   AS elo_bracket,
        first_blunder_move
    FROM v_games_enriched
    WHERE first_blunder_move IS NOT NULL
)
SELECT
    eco,
    opening_family,
    elo_bracket,
    COUNT(*)                        AS games_with_blunder,
    MEDIAN(first_blunder_move)      AS median_blunder_move,
    AVG(first_blunder_move)         AS avg_blunder_move,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY first_blunder_move) AS p25_blunder_move,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY first_blunder_move) AS p75_blunder_move,
    confidence_flag(COUNT(*))       AS confidence
FROM blunder_data
GROUP BY eco, opening_family, elo_bracket;


-- ── v_termination_analysis ───────────────────────────────────────────────────
-- How games end (checkmate, resign, timeout, etc.) broken down by Elo bracket.
-- Supports dashboard page 3.

CREATE OR REPLACE VIEW v_termination_analysis AS
SELECT
    white_elo_bracket       AS elo_bracket,
    time_class,
    termination,
    COUNT(*)                AS games_count,
    COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (
        PARTITION BY white_elo_bracket, time_class
    )                       AS termination_pct
FROM v_games_enriched
GROUP BY white_elo_bracket, time_class, termination;


-- ── v_time_pressure ──────────────────────────────────────────────────────────
-- Share of games where time trouble occurred, by Elo bracket and time class.
-- Based on moves_summary aggregate data.

CREATE OR REPLACE VIEW v_time_pressure AS
WITH time_data AS (
    SELECT
        g.eco,
        elo_bracket(g.white_elo)    AS elo_bracket,
        g.time_class,
        m.color,
        m.time_trouble_moves,
        m.move_count,
        CASE
            WHEN m.time_trouble_moves > 0 THEN 1
            ELSE 0
        END                         AS had_time_trouble
    FROM games g
    JOIN moves_summary m ON g.game_id = m.game_id
)
SELECT
    elo_bracket,
    time_class,
    color,
    COUNT(*)                                    AS total_games,
    SUM(had_time_trouble)                       AS games_with_time_trouble,
    SUM(had_time_trouble)::DOUBLE / COUNT(*)    AS time_trouble_rate,
    AVG(time_trouble_moves)                     AS avg_time_trouble_moves
FROM time_data
GROUP BY elo_bracket, time_class, color;
