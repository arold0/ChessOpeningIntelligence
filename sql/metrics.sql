-- ============================================================================
-- Chess Opening Intelligence — OII Metrics
-- ============================================================================
-- Execution order: 4 of 4 (schema.sql → macros.sql → views.sql → metrics.sql)
--
-- Computes the Opening Intelligence Index (OII) by joining opening results
-- with puzzle difficulty data. This is the analytical centrepiece of the
-- project.
--
-- OII = ASR / Normalised(TC) × log10(games_count)
--
-- Where:
--   ASR = Adjusted Score Rate (actual score - expected score)
--   TC  = Tactical Complexity (bracket-aware median puzzle rating)
--
-- Dependencies:
--   views: v_opening_results, v_puzzle_difficulty
--   macros: confidence_flag()
-- ============================================================================


-- ── v_opening_intelligence ───────────────────────────────────────────────────
-- The final OII view. Joins opening results with puzzle difficulty to
-- compute the composite OII score.
--
-- Normalisation: TC is normalised within each Elo bracket using min-max
-- scaling so that TC values are comparable across brackets.

CREATE OR REPLACE VIEW v_opening_intelligence AS
WITH tc_stats AS (
    -- Get min/max puzzle difficulty for normalisation
    SELECT
        MIN(median_puzzle_rating) AS min_tc,
        MAX(median_puzzle_rating) AS max_tc
    FROM v_puzzle_difficulty
    WHERE median_puzzle_rating IS NOT NULL
),

oii_raw AS (
    SELECT
        r.eco,
        r.opening_family,
        r.color,
        r.elo_bracket,
        r.time_class,
        r.games_count,
        r.wins,
        r.draws,
        r.losses,
        r.score_rate,
        r.asr,
        r.median_blunder,
        p.median_puzzle_rating  AS tc_raw,
        p.puzzle_count,

        -- Normalise TC to [0, 1] range using min-max scaling
        CASE
            WHEN tc_stats.max_tc = tc_stats.min_tc THEN 0.5
            ELSE (p.median_puzzle_rating - tc_stats.min_tc)::DOUBLE
                 / (tc_stats.max_tc - tc_stats.min_tc)::DOUBLE
        END                     AS tc_normalised,

        r.confidence

    FROM v_opening_results r
    LEFT JOIN v_puzzle_difficulty p ON r.eco = p.eco
    CROSS JOIN tc_stats
)

SELECT
    eco,
    opening_family,
    color,
    elo_bracket,
    time_class,
    games_count,
    wins,
    draws,
    losses,
    score_rate,
    asr,
    tc_raw,
    tc_normalised,
    median_blunder,
    puzzle_count,

    -- OII Formula: ASR / normalised(TC) × log10(games_count)
    -- Guard against division by zero and log(0)
    CASE
        WHEN tc_normalised IS NULL OR tc_normalised = 0 THEN NULL
        WHEN games_count < 2 THEN NULL
        ELSE ROUND(
            (asr / tc_normalised) * LOG10(games_count::DOUBLE),
            4
        )
    END                         AS oii_score,

    confidence

FROM oii_raw;


-- ── Populate opening_stats table ─────────────────────────────────────────────
-- Materialise the OII results into the opening_stats table for dashboard
-- consumption. This uses INSERT OR REPLACE for idempotent re-runs.
--
-- Run this as a separate step after views are validated.

-- DELETE FROM opening_stats;
--
-- INSERT INTO opening_stats (
--     eco, color, elo_bracket, time_class,
--     games_count, wins, draws, losses,
--     avg_asr, avg_tc, oii_score, median_blunder, confidence
-- )
-- SELECT
--     eco, color, elo_bracket, time_class,
--     games_count, wins, draws, losses,
--     asr           AS avg_asr,
--     tc_raw        AS avg_tc,
--     oii_score,
--     median_blunder,
--     confidence
-- FROM v_opening_intelligence
-- WHERE eco IS NOT NULL;
