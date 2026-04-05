-- ============================================================================
-- Chess Opening Intelligence — Schema Definition (DDL)
-- ============================================================================
-- Execution order: 1 of 4 (schema.sql → macros.sql → views.sql → metrics.sql)
--
-- This file creates all base tables used by the pipeline. All tables use
-- CREATE OR REPLACE to support idempotent re-runs.
-- ============================================================================

-- ── games ────────────────────────────────────────────────────────────────────
-- One row per game. Grain: game_id.
-- Source: Lichess PGN dump (L1 ingest → L2 clean → L3 load).

CREATE TABLE IF NOT EXISTS games (
    game_id             TEXT PRIMARY KEY,
    played_at           TIMESTAMPTZ,
    year                INTEGER,                -- extracted for Hive partitioning
    month               INTEGER,                -- extracted for Hive partitioning
    eco                 TEXT,                    -- ECO code, e.g. B30, C65
    opening_name        TEXT,
    result              TEXT,                    -- 'white' / 'black' / 'draw'
    white_elo           INTEGER,
    black_elo           INTEGER,
    elo_diff            INTEGER,                -- white_elo - black_elo
    time_class          TEXT,                    -- bullet / blitz / rapid / classical
    time_control        TEXT,                    -- raw string e.g. "600+0"
    termination         TEXT,                    -- checkmate / resign / timeout / draw_agreement
    has_eval            BOOLEAN,                -- whether %eval annotations are present
    first_blunder_move  INTEGER,                -- move number where cp_loss > 200 (Blunder Zone)
    platform            TEXT DEFAULT 'lichess'
);

-- ── moves_summary ────────────────────────────────────────────────────────────
-- Aggregated move statistics per game and color (not individual moves).
-- Source: PGN parsing during L1 ingest.

CREATE TABLE IF NOT EXISTS moves_summary (
    game_id             TEXT REFERENCES games(game_id),
    color               TEXT,                    -- 'white' / 'black'
    avg_cp_loss         NUMERIC(7,2),            -- only when has_eval = true
    max_cp_loss         NUMERIC(7,2),
    blunder_count       INTEGER,                 -- moves with cp_loss > 200
    mistake_count       INTEGER,                 -- moves with cp_loss > 100
    time_trouble_moves  INTEGER,                 -- moves with < 15% clock remaining
    move_count          INTEGER,
    PRIMARY KEY (game_id, color)
);

-- ── puzzles ──────────────────────────────────────────────────────────────────
-- One row per puzzle. Source: Lichess puzzle CSV (5.88M rows).

CREATE TABLE IF NOT EXISTS puzzles (
    puzzle_id           TEXT PRIMARY KEY,
    fen                 TEXT,
    eco                 TEXT,                    -- populated when opening < move 20
    puzzle_rating       INTEGER,
    rating_dev          NUMERIC(6,2),
    popularity          INTEGER,                 -- -100 to 100
    nb_plays            INTEGER,
    themes              TEXT,                    -- comma-separated: fork, pin, skewer, etc.
    opening_tags        TEXT
);

-- ── opening_lookup ───────────────────────────────────────────────────────────
-- ECO code → opening family mapping (~3,500 rows).
-- Source: https://github.com/lichess-org/chess-openings

CREATE TABLE IF NOT EXISTS opening_lookup (
    eco                 TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    pgn                 TEXT,
    uci                 TEXT,
    family              TEXT NOT NULL            -- e.g. "Sicilian", "Italian", "Queen's Gambit"
);

-- ── opening_stats ────────────────────────────────────────────────────────────
-- Pre-aggregated metrics by ECO × Elo bracket × color × time class.
-- Populated by SQL aggregation in L4 (metrics.sql).

CREATE TABLE IF NOT EXISTS opening_stats (
    eco                 TEXT NOT NULL,
    color               TEXT NOT NULL,           -- 'white' / 'black'
    elo_bracket         TEXT NOT NULL,
    time_class          TEXT NOT NULL,
    games_count         INTEGER NOT NULL,
    wins                INTEGER NOT NULL,
    draws               INTEGER NOT NULL,
    losses              INTEGER NOT NULL,
    avg_asr             NUMERIC(8,4),
    avg_tc              NUMERIC(8,2),
    oii_score           NUMERIC(8,4),
    median_blunder      INTEGER,                 -- median move of first blunder
    confidence          TEXT DEFAULT 'normal',   -- 'low' if games_count < 500
    PRIMARY KEY (eco, color, elo_bracket, time_class)
);
