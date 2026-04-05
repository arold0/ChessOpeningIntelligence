"""
Chess Opening Intelligence — Data Validators

Data quality assertion functions used by pipeline scripts to validate
data at each layer boundary (DESIGN.md §9.1).

Each validator returns True if the check passes, False otherwise.
All validators also log their results using the pipeline logger.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from pipeline.config import (
    CP_LOSS_BLUNDER_THRESHOLD,
    ELO_MAX,
    ELO_MIN,
    MAX_PUZZLE_RATING,
    MIN_PUZZLE_RATING,
)
from pipeline.logger import get_logger, log_quality_check

if TYPE_CHECKING:
    import duckdb

logger = get_logger("quality")


# ── L1 Ingest validators ─────────────────────────────────────────────────────


def validate_schema(df: pl.DataFrame, required_columns: list[str]) -> bool:
    """Check that a DataFrame contains all required columns.

    Args:
        df: Polars DataFrame to validate.
        required_columns: List of column names that must be present.

    Returns:
        True if all required columns exist.
    """
    missing = set(required_columns) - set(df.columns)
    passed = len(missing) == 0
    detail = f"missing={missing}" if not passed else f"columns={len(df.columns)}"
    log_quality_check(logger, "schema", passed, detail)
    return passed


def validate_row_count(df: pl.DataFrame, min_rows: int = 1) -> bool:
    """Check that a DataFrame has at least `min_rows` rows.

    Args:
        df: Polars DataFrame to validate.
        min_rows: Minimum expected row count.

    Returns:
        True if the DataFrame meets the minimum row count.
    """
    count = df.height
    passed = count >= min_rows
    detail = f"rows={count}  min={min_rows}"
    log_quality_check(logger, "row_count", passed, detail)
    return passed


# ── L2 Clean validators ──────────────────────────────────────────────────────


def validate_elo_range(df: pl.DataFrame, elo_column: str = "white_elo") -> bool:
    """Check that all Elo values fall within the valid range.

    Args:
        df: Polars DataFrame containing Elo data.
        elo_column: Name of the Elo column to validate.

    Returns:
        True if all Elo values are in [ELO_MIN, ELO_MAX].
    """
    stats = df.select(
        pl.col(elo_column).min().alias("min_elo"),
        pl.col(elo_column).max().alias("max_elo"),
        pl.col(elo_column).null_count().alias("null_count"),
    ).row(0)

    min_elo, max_elo, null_count = stats

    if null_count > 0:
        log_quality_check(logger, "elo_range", False, f"null_count={null_count}")
        return False

    passed = min_elo >= ELO_MIN and max_elo <= ELO_MAX
    detail = f"range=[{min_elo}, {max_elo}]  expected=[{ELO_MIN}, {ELO_MAX}]"
    log_quality_check(logger, "elo_range", passed, detail)
    return passed


def validate_no_duplicates(df: pl.DataFrame, id_column: str = "game_id") -> bool:
    """Check that there are no duplicate values in an ID column.

    Args:
        df: Polars DataFrame to validate.
        id_column: Name of the column that should be unique.

    Returns:
        True if no duplicates exist.
    """
    total = df.height
    unique = df.select(pl.col(id_column).n_unique()).item()
    duplicates = total - unique
    passed = duplicates == 0
    detail = f"total={total}  unique={unique}  duplicates={duplicates}"
    log_quality_check(logger, "duplicates", passed, detail)
    return passed


def validate_null_rate(
    df: pl.DataFrame,
    column: str,
    max_null_rate: float = 0.05,
) -> bool:
    """Check that the null rate for a column is below a threshold.

    Args:
        df: Polars DataFrame to validate.
        column: Column name to check.
        max_null_rate: Maximum acceptable null rate (0.0 to 1.0).

    Returns:
        True if the null rate is acceptable.
    """
    total = df.height
    if total == 0:
        log_quality_check(logger, f"null_rate_{column}", False, "empty_df")
        return False

    null_count = df.select(pl.col(column).null_count()).item()
    null_rate = null_count / total
    passed = null_rate <= max_null_rate
    detail = f"nulls={null_count}  rate={null_rate:.2%}  max={max_null_rate:.2%}"
    log_quality_check(logger, f"null_rate_{column}", passed, detail)
    return passed


# ── L3 Load validators ───────────────────────────────────────────────────────


def validate_row_count_match(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    expected_count: int,
) -> bool:
    """Check that a DuckDB table has the expected row count.

    Args:
        conn: Active DuckDB connection.
        table_name: Name of the table to check.
        expected_count: Expected number of rows.

    Returns:
        True if the row counts match.
    """
    actual = conn.sql(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]  # noqa: S608
    passed = actual == expected_count
    detail = f"table={table_name}  actual={actual}  expected={expected_count}"
    log_quality_check(logger, "row_count_match", passed, detail)
    return passed


def validate_eco_foreign_keys(conn: duckdb.DuckDBPyConnection) -> bool:
    """Check that all ECO codes in games exist in opening_lookup.

    Args:
        conn: Active DuckDB connection.

    Returns:
        True if no orphan ECO codes exist.
    """
    orphans = conn.sql("""
        SELECT COUNT(DISTINCT g.eco) AS orphan_count
        FROM games g
        LEFT JOIN opening_lookup o ON g.eco = o.eco
        WHERE o.eco IS NULL AND g.eco IS NOT NULL
    """).fetchone()[0]

    passed = orphans == 0
    detail = f"orphan_eco_codes={orphans}"
    log_quality_check(logger, "eco_fk", passed, detail)
    return passed


# ── L4 Analyse validators ────────────────────────────────────────────────────


def validate_score_rates(conn: duckdb.DuckDBPyConnection) -> bool:
    """Check that all score rates are between 0 and 1.

    Args:
        conn: Active DuckDB connection.

    Returns:
        True if all score rates are valid.
    """
    invalid = conn.sql("""
        SELECT COUNT(*) FROM opening_stats
        WHERE (wins + 0.5 * draws) / NULLIF(games_count, 0) NOT BETWEEN 0 AND 1
    """).fetchone()[0]

    passed = invalid == 0
    detail = f"invalid_score_rates={invalid}"
    log_quality_check(logger, "score_rates", passed, detail)
    return passed


def validate_puzzle_ratings(df: pl.DataFrame) -> bool:
    """Check that puzzle ratings fall within expected bounds.

    Args:
        df: Polars DataFrame with a puzzle_rating column.

    Returns:
        True if all ratings are in [MIN_PUZZLE_RATING, MAX_PUZZLE_RATING].
    """
    stats = df.select(
        pl.col("puzzle_rating").min().alias("min_rating"),
        pl.col("puzzle_rating").max().alias("max_rating"),
    ).row(0)

    min_rating, max_rating = stats
    passed = min_rating >= MIN_PUZZLE_RATING and max_rating <= MAX_PUZZLE_RATING
    detail = (
        f"range=[{min_rating}, {max_rating}]  "
        f"expected=[{MIN_PUZZLE_RATING}, {MAX_PUZZLE_RATING}]"
    )
    log_quality_check(logger, "puzzle_ratings", passed, detail)
    return passed
