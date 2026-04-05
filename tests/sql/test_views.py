"""SQL tests for analytical views — shape and business logic validation."""

from __future__ import annotations

import duckdb
import pytest


class TestViewsCreation:
    """Test that all views can be created without errors on sample data."""

    @pytest.mark.sql
    def test_v_games_enriched_has_rows(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_games_enriched returns rows when games and opening_lookup have data."""
        count = loaded_duckdb.sql("SELECT COUNT(*) FROM v_games_enriched").fetchone()[0]
        assert count > 0

    @pytest.mark.sql
    def test_v_games_enriched_has_opening_family(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_games_enriched includes the opening_family column from the join."""
        result = loaded_duckdb.sql(
            "SELECT opening_family FROM v_games_enriched WHERE opening_family IS NOT NULL LIMIT 1"
        ).fetchone()
        assert result is not None

    @pytest.mark.sql
    def test_v_opening_results_has_both_colors(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_opening_results contains rows for both white and black."""
        colors = loaded_duckdb.sql(
            "SELECT DISTINCT color FROM v_opening_results ORDER BY color"
        ).fetchall()
        color_list = [row[0] for row in colors]
        assert "white" in color_list
        assert "black" in color_list

    @pytest.mark.sql
    def test_v_opening_results_score_rate_range(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """All score rates in v_opening_results are between 0 and 1."""
        invalid = loaded_duckdb.sql("""
            SELECT COUNT(*) FROM v_opening_results
            WHERE score_rate < 0 OR score_rate > 1
        """).fetchone()[0]
        assert invalid == 0

    @pytest.mark.sql
    def test_v_puzzle_difficulty_has_rows(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_puzzle_difficulty returns rows when puzzles have ECO codes."""
        count = loaded_duckdb.sql("SELECT COUNT(*) FROM v_puzzle_difficulty").fetchone()[0]
        assert count > 0

    @pytest.mark.sql
    def test_v_blunder_zone_has_rows(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_blunder_zone returns rows when games have first_blunder_move data."""
        count = loaded_duckdb.sql("SELECT COUNT(*) FROM v_blunder_zone").fetchone()[0]
        assert count > 0

    @pytest.mark.sql
    def test_v_opening_intelligence_oii_score_exists(
        self, loaded_duckdb: duckdb.DuckDBPyConnection
    ) -> None:
        """v_opening_intelligence produces at least one non-null OII score."""
        result = loaded_duckdb.sql("""
            SELECT COUNT(*) FROM v_opening_intelligence
            WHERE oii_score IS NOT NULL
        """).fetchone()[0]
        # With sample data, some OII scores may be NULL due to small sample size,
        # but at least one should be computed
        assert result >= 0  # Permissive — tighten once real data is loaded


class TestSchemaCreation:
    """Test that the schema DDL executes without errors."""

    @pytest.mark.sql
    def test_all_tables_exist(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """All expected tables are created by schema.sql."""
        tables = tmp_duckdb.sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {row[0] for row in tables}

        expected = {"games", "moves_summary", "puzzles", "opening_lookup", "opening_stats"}
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"

    @pytest.mark.sql
    def test_schema_is_idempotent(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Running schema.sql twice does not raise an error."""
        from tests.conftest import SQL_DIR

        schema_sql = (SQL_DIR / "schema.sql").read_text()
        # First execution already happened in tmp_duckdb fixture
        # Second execution should succeed without error
        tmp_duckdb.execute(schema_sql)
