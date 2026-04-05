"""SQL tests for DuckDB macros — expected_score, elo_bracket, score_rate."""

from __future__ import annotations

import duckdb
import pytest


class TestExpectedScoreMacro:
    """Tests for the expected_score() DuckDB macro."""

    @pytest.mark.sql
    def test_equal_elos(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Expected score is 0.5 when Elo difference is 0."""
        result = tmp_duckdb.sql("SELECT expected_score(0)").fetchone()[0]
        assert abs(result - 0.5) < 0.001

    @pytest.mark.sql
    def test_positive_diff(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Stronger player (positive diff) has expected score > 0.5."""
        result = tmp_duckdb.sql("SELECT expected_score(200)").fetchone()[0]
        assert result > 0.5
        assert abs(result - 0.7597) < 0.01  # Known value for +200 diff

    @pytest.mark.sql
    def test_negative_diff(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Weaker player (negative diff) has expected score < 0.5."""
        result = tmp_duckdb.sql("SELECT expected_score(-200)").fetchone()[0]
        assert result < 0.5
        assert abs(result - 0.2403) < 0.01

    @pytest.mark.sql
    def test_symmetry(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """E(+d) + E(-d) = 1.0 for any Elo difference."""
        pos = tmp_duckdb.sql("SELECT expected_score(300)").fetchone()[0]
        neg = tmp_duckdb.sql("SELECT expected_score(-300)").fetchone()[0]
        assert abs((pos + neg) - 1.0) < 0.001


class TestEloBracketMacro:
    """Tests for the elo_bracket() DuckDB macro."""

    @pytest.mark.sql
    def test_bracket_boundaries(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Boundary values map to correct brackets in SQL (must match Python)."""
        cases = [
            (799, "<800"),
            (800, "800-999"),
            (1000, "1000-1199"),
            (1200, "1200-1399"),
            (1400, "1400-1599"),
            (1600, "1600-1799"),
            (1800, "1800-1999"),
            (2000, "2000-2199"),
            (2200, "2200+"),
        ]
        for elo, expected in cases:
            result = tmp_duckdb.sql(f"SELECT elo_bracket({elo})").fetchone()[0]
            assert result == expected, f"elo_bracket({elo}) = {result}, expected {expected}"

    @pytest.mark.sql
    def test_matches_python(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """SQL elo_bracket matches Python elo_bracket for all test values."""
        from pipeline.config import elo_bracket as py_bracket

        test_values = [600, 799, 800, 999, 1000, 1500, 1800, 2000, 2199, 2200, 2800]
        for elo in test_values:
            sql_result = tmp_duckdb.sql(f"SELECT elo_bracket({elo})").fetchone()[0]
            py_result = py_bracket(elo)
            assert sql_result == py_result, (
                f"Mismatch at elo={elo}: SQL={sql_result}, Python={py_result}"
            )


class TestScoreRateMacro:
    """Tests for the score_rate() DuckDB macro."""

    @pytest.mark.sql
    def test_all_wins(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Score rate is 1.0 when all games are wins."""
        result = tmp_duckdb.sql("SELECT score_rate(10, 0, 10)").fetchone()[0]
        assert abs(result - 1.0) < 0.001

    @pytest.mark.sql
    def test_all_draws(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Score rate is 0.5 when all games are draws."""
        result = tmp_duckdb.sql("SELECT score_rate(0, 10, 10)").fetchone()[0]
        assert abs(result - 0.5) < 0.001

    @pytest.mark.sql
    def test_all_losses(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Score rate is 0.0 when all games are losses."""
        result = tmp_duckdb.sql("SELECT score_rate(0, 0, 10)").fetchone()[0]
        assert abs(result - 0.0) < 0.001

    @pytest.mark.sql
    def test_zero_games(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Score rate is NULL when total games is 0."""
        result = tmp_duckdb.sql("SELECT score_rate(0, 0, 0)").fetchone()[0]
        assert result is None


class TestConfidenceFlagMacro:
    """Tests for the confidence_flag() DuckDB macro."""

    @pytest.mark.sql
    def test_low_confidence(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Games count < 500 returns 'low'."""
        result = tmp_duckdb.sql("SELECT confidence_flag(499)").fetchone()[0]
        assert result == "low"

    @pytest.mark.sql
    def test_normal_confidence(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Games count >= 500 returns 'normal'."""
        result = tmp_duckdb.sql("SELECT confidence_flag(500)").fetchone()[0]
        assert result == "normal"

    @pytest.mark.sql
    def test_boundary(self, tmp_duckdb: duckdb.DuckDBPyConnection) -> None:
        """Exactly 500 games is 'normal' (not 'low')."""
        result = tmp_duckdb.sql("SELECT confidence_flag(500)").fetchone()[0]
        assert result == "normal"
