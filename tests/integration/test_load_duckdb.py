"""
Integration tests for pipeline loading — DuckDB idempotency and data integrity.

These tests validate the L3 (Load) layer: loading clean parquet data into
DuckDB tables and verifying row counts, foreign keys, and idempotent behavior.

NOTE: These are stub tests. They will be fully implemented when the pipeline
scripts (01_ingest through 05_load) are built.
"""

from __future__ import annotations

import duckdb
import polars as pl
import pytest


class TestDuckDBIdempotentLoad:
    """Tests for idempotent loading behavior."""

    @pytest.mark.integration
    def test_double_insert_same_data(
        self,
        tmp_duckdb: duckdb.DuckDBPyConnection,
        sample_games_df: pl.DataFrame,
    ) -> None:
        """Loading the same data twice with INSERT OR REPLACE doesn't duplicate rows."""
        # First load
        tmp_duckdb.execute("INSERT OR REPLACE INTO games SELECT * FROM sample_games_df")
        count_1 = tmp_duckdb.sql("SELECT COUNT(*) FROM games").fetchone()[0]

        # Second load (same data)
        tmp_duckdb.execute("INSERT OR REPLACE INTO games SELECT * FROM sample_games_df")
        count_2 = tmp_duckdb.sql("SELECT COUNT(*) FROM games").fetchone()[0]

        assert count_1 == count_2, (
            f"Row count changed after re-load: {count_1} → {count_2}"
        )

    @pytest.mark.integration
    def test_row_count_matches_source(
        self,
        tmp_duckdb: duckdb.DuckDBPyConnection,
        sample_games_df: pl.DataFrame,
    ) -> None:
        """DuckDB row count matches the source DataFrame row count."""
        tmp_duckdb.execute("INSERT INTO games SELECT * FROM sample_games_df")

        db_count = tmp_duckdb.sql("SELECT COUNT(*) FROM games").fetchone()[0]
        df_count = sample_games_df.height

        assert db_count == df_count


class TestForeignKeyIntegrity:
    """Tests for referential integrity between tables."""

    @pytest.mark.integration
    def test_all_game_ecos_in_lookup(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """Every ECO code in games has a corresponding entry in opening_lookup."""
        orphans = loaded_duckdb.sql("""
            SELECT DISTINCT g.eco
            FROM games g
            LEFT JOIN opening_lookup o ON g.eco = o.eco
            WHERE o.eco IS NULL AND g.eco IS NOT NULL
        """).fetchall()

        assert len(orphans) == 0, f"Orphan ECO codes: {[r[0] for r in orphans]}"

    @pytest.mark.integration
    def test_moves_summary_references_valid_games(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """Every game_id in moves_summary exists in the games table."""
        orphans = loaded_duckdb.sql("""
            SELECT DISTINCT m.game_id
            FROM moves_summary m
            LEFT JOIN games g ON m.game_id = g.game_id
            WHERE g.game_id IS NULL
        """).fetchall()

        assert len(orphans) == 0, f"Orphan game_ids in moves_summary: {[r[0] for r in orphans]}"
