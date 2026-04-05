"""
Chess Opening Intelligence — Shared Test Fixtures

Pytest fixtures used across all test categories (unit, integration, sql).
Provides:
    - Sample DataFrames with deterministic test data
    - Temporary DuckDB connections with schema/macros pre-loaded
    - Path helpers for test data files
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest

# ── Path constants ────────────────────────────────────────────────────────────
TESTS_DIR = Path(__file__).resolve().parent
TESTS_DATA_DIR = TESTS_DIR / "data"
SQL_DIR = TESTS_DIR.parent / "sql"


# ── Sample game data ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_games_df() -> pl.DataFrame:
    """Create a small deterministic DataFrame of chess games for testing.

    Contains 10 games covering various Elo ranges, time controls,
    results, and edge cases (missing eval, low Elo, high Elo).
    """
    return pl.DataFrame({
        "game_id": [f"game_{i:03d}" for i in range(1, 11)],
        "played_at": [f"2024-01-{i:02d}T12:00:00Z" for i in range(1, 11)],
        "year": [2024] * 10,
        "month": [1] * 10,
        "eco": ["B30", "C65", "A00", "D35", "B20", "C50", "E60", "A45", "B30", "C65"],
        "opening_name": [
            "Sicilian Defense", "Ruy Lopez", "Irregular", "Queen's Gambit Declined",
            "Sicilian Defense", "Italian Game", "King's Indian", "Trompowsky Attack",
            "Sicilian Defense", "Ruy Lopez",
        ],
        "result": ["white", "black", "draw", "white", "black",
                   "white", "draw", "white", "black", "white"],
        "white_elo": [1200, 1500, 800, 1800, 2100, 1000, 1400, 1600, 700, 2200],
        "black_elo": [1150, 1520, 820, 1750, 2050, 1100, 1380, 1650, 750, 2180],
        "elo_diff": [50, -20, -20, 50, 50, -100, 20, -50, -50, 20],
        "time_class": [
            "blitz", "rapid", "bullet", "classical", "blitz",
            "rapid", "blitz", "rapid", "bullet", "classical",
        ],
        "time_control": [
            "180+0", "600+0", "60+0", "1800+0", "180+2",
            "600+0", "180+0", "600+5", "60+0", "1800+0",
        ],
        "termination": [
            "resign", "checkmate", "timeout", "resign", "checkmate",
            "resign", "draw_agreement", "resign", "timeout", "checkmate",
        ],
        "has_eval": [True, True, False, True, True, False, True, True, False, True],
        "first_blunder_move": [15, 22, None, 30, 12, None, 25, 18, None, 35],
        "platform": ["lichess"] * 10,
    })


@pytest.fixture
def sample_puzzles_df() -> pl.DataFrame:
    """Create a small deterministic DataFrame of chess puzzles for testing."""
    return pl.DataFrame({
        "puzzle_id": [f"puz_{i:03d}" for i in range(1, 8)],
        "fen": ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"] * 7,
        "eco": ["B30", "C65", "A00", "D35", "B20", "C50", "E60"],
        "puzzle_rating": [1200, 1800, 900, 1500, 1400, 1100, 1600],
        "rating_dev": [75.0, 80.0, 100.0, 70.0, 85.0, 90.0, 78.0],
        "popularity": [85, 92, 60, 78, 88, 72, 80],
        "nb_plays": [50000, 80000, 20000, 45000, 60000, 30000, 55000],
        "themes": ["fork", "pin", "skewer", "discovery", "fork,pin", "mate", "deflection"],
        "opening_tags": [
            "Sicilian_Defense", "Ruy_Lopez", "Irregular", "QGD",
            "Sicilian", "Italian_Game", "Kings_Indian",
        ],
    })


@pytest.fixture
def sample_moves_summary_df() -> pl.DataFrame:
    """Create a small deterministic DataFrame of move summaries for testing."""
    rows = []
    for i in range(1, 8):  # 7 games with eval data
        for color in ["white", "black"]:
            rows.append({
                "game_id": f"game_{i:03d}",
                "color": color,
                "avg_cp_loss": 30.0 + i * 5,
                "max_cp_loss": 150.0 + i * 20,
                "blunder_count": i % 3,
                "mistake_count": i % 4,
                "time_trouble_moves": i % 2,
                "move_count": 30 + i * 2,
            })
    return pl.DataFrame(rows)


@pytest.fixture
def sample_opening_lookup_df() -> pl.DataFrame:
    """Create a small ECO → opening family lookup for testing."""
    return pl.DataFrame({
        "eco": ["A00", "A45", "B20", "B30", "C50", "C65", "D35", "E60"],
        "name": [
            "Irregular Opening", "Trompowsky Attack",
            "Sicilian Defense", "Sicilian, Najdorf",
            "Italian Game", "Ruy Lopez, Berlin",
            "Queen's Gambit Declined", "King's Indian Defense",
        ],
        "pgn": ["1. a3", "1. d4 Nf6 2. Bg5", "1. e4 c5", "1. e4 c5 2. Nf3 Nc6",
                 "1. e4 e5 2. Nf3 Nc6 3. Bc4", "1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6",
                 "1. d4 d5 2. c4 e6", "1. d4 Nf6 2. c4 g6"],
        "uci": [None] * 8,
        "family": [
            "Irregular", "Trompowsky", "Sicilian", "Sicilian",
            "Italian", "Ruy Lopez", "Queen's Gambit", "King's Indian",
        ],
    })


# ── DuckDB fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_duckdb() -> duckdb.DuckDBPyConnection:
    """Create a temporary in-memory DuckDB connection with schema and macros loaded.

    The connection has all tables created (empty) and all macros registered.
    Tests can insert sample data as needed.
    """
    conn = duckdb.connect(":memory:")

    # Load schema
    schema_sql = (SQL_DIR / "schema.sql").read_text()
    conn.execute(schema_sql)

    # Load macros
    macros_sql = (SQL_DIR / "macros.sql").read_text()
    conn.execute(macros_sql)

    yield conn
    conn.close()


@pytest.fixture
def loaded_duckdb(
    tmp_duckdb: duckdb.DuckDBPyConnection,
    sample_games_df: pl.DataFrame,
    sample_puzzles_df: pl.DataFrame,
    sample_moves_summary_df: pl.DataFrame,
    sample_opening_lookup_df: pl.DataFrame,
) -> duckdb.DuckDBPyConnection:
    """DuckDB connection with sample data loaded into all tables.

    Includes schema, macros, AND views so that downstream analytics
    can be tested end-to-end.
    """
    conn = tmp_duckdb

    # Insert sample data
    conn.execute("INSERT INTO games SELECT * FROM sample_games_df")
    conn.execute("INSERT INTO puzzles SELECT * FROM sample_puzzles_df")
    conn.execute("INSERT INTO moves_summary SELECT * FROM sample_moves_summary_df")
    conn.execute("INSERT INTO opening_lookup SELECT * FROM sample_opening_lookup_df")

    # Load views (depends on data being present)
    views_sql = (SQL_DIR / "views.sql").read_text()
    conn.execute(views_sql)

    # Load metrics views
    metrics_sql = (SQL_DIR / "metrics.sql").read_text()
    conn.execute(metrics_sql)

    return conn
