"""Unit tests for pipeline.validators — data quality assertion functions."""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.validators import (
    validate_elo_range,
    validate_no_duplicates,
    validate_null_rate,
    validate_row_count,
    validate_schema,
)


class TestValidateSchema:
    """Tests for validate_schema()."""

    @pytest.mark.unit
    def test_all_columns_present(self) -> None:
        """Returns True when all required columns exist."""
        df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
        assert validate_schema(df, ["a", "b"]) is True

    @pytest.mark.unit
    def test_missing_column(self) -> None:
        """Returns False when a required column is missing."""
        df = pl.DataFrame({"a": [1], "b": [2]})
        assert validate_schema(df, ["a", "b", "missing"]) is False

    @pytest.mark.unit
    def test_empty_requirements(self) -> None:
        """Returns True when no columns are required."""
        df = pl.DataFrame({"a": [1]})
        assert validate_schema(df, []) is True


class TestValidateRowCount:
    """Tests for validate_row_count()."""

    @pytest.mark.unit
    def test_sufficient_rows(self) -> None:
        """Returns True when row count meets minimum."""
        df = pl.DataFrame({"a": [1, 2, 3]})
        assert validate_row_count(df, min_rows=2) is True

    @pytest.mark.unit
    def test_insufficient_rows(self) -> None:
        """Returns False when row count is below minimum."""
        df = pl.DataFrame({"a": [1]})
        assert validate_row_count(df, min_rows=5) is False

    @pytest.mark.unit
    def test_empty_dataframe(self) -> None:
        """Returns False for empty DataFrame with default min_rows=1."""
        df = pl.DataFrame({"a": []}).cast({"a": pl.Int64})
        assert validate_row_count(df) is False


class TestValidateEloRange:
    """Tests for validate_elo_range()."""

    @pytest.mark.unit
    def test_valid_elo_range(self) -> None:
        """Returns True when all Elo values are within bounds."""
        df = pl.DataFrame({"white_elo": [600, 1200, 2800]})
        assert validate_elo_range(df) is True

    @pytest.mark.unit
    def test_elo_below_minimum(self) -> None:
        """Returns False when Elo is below minimum."""
        df = pl.DataFrame({"white_elo": [100, 1200, 1500]})
        assert validate_elo_range(df) is False

    @pytest.mark.unit
    def test_elo_above_maximum(self) -> None:
        """Returns False when Elo is above maximum."""
        df = pl.DataFrame({"white_elo": [1200, 1500, 3500]})
        assert validate_elo_range(df) is False

    @pytest.mark.unit
    def test_elo_with_nulls(self) -> None:
        """Returns False when Elo column contains nulls."""
        df = pl.DataFrame({"white_elo": [1200, None, 1500]})
        assert validate_elo_range(df) is False


class TestValidateNoDuplicates:
    """Tests for validate_no_duplicates()."""

    @pytest.mark.unit
    def test_no_duplicates(self) -> None:
        """Returns True when all IDs are unique."""
        df = pl.DataFrame({"game_id": ["a", "b", "c"]})
        assert validate_no_duplicates(df) is True

    @pytest.mark.unit
    def test_with_duplicates(self) -> None:
        """Returns False when duplicates exist."""
        df = pl.DataFrame({"game_id": ["a", "b", "a"]})
        assert validate_no_duplicates(df) is False


class TestValidateNullRate:
    """Tests for validate_null_rate()."""

    @pytest.mark.unit
    def test_below_threshold(self) -> None:
        """Returns True when null rate is below max."""
        df = pl.DataFrame({"eco": ["B30", "C65", None, "A00", "B20"]})
        assert validate_null_rate(df, "eco", max_null_rate=0.25) is True

    @pytest.mark.unit
    def test_above_threshold(self) -> None:
        """Returns False when null rate exceeds max."""
        df = pl.DataFrame({"eco": [None, None, None, "A00", "B20"]})
        assert validate_null_rate(df, "eco", max_null_rate=0.5) is False

    @pytest.mark.unit
    def test_no_nulls(self) -> None:
        """Returns True when there are zero nulls."""
        df = pl.DataFrame({"eco": ["B30", "C65", "A00"]})
        assert validate_null_rate(df, "eco", max_null_rate=0.0) is True

    @pytest.mark.unit
    def test_empty_dataframe(self) -> None:
        """Returns False for empty DataFrame."""
        df = pl.DataFrame({"eco": []}).cast({"eco": pl.Utf8})
        assert validate_null_rate(df, "eco") is False
