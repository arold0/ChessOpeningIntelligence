"""Unit tests for pipeline.config — Elo brackets and time classification."""

from __future__ import annotations

import pytest

from pipeline.config import (
    ELO_BRACKETS,
    ELO_MAX,
    ELO_MIN,
    classify_time_control,
    elo_bracket,
)


class TestEloBracket:
    """Tests for the elo_bracket() function."""

    @pytest.mark.unit
    def test_boundaries_lower(self) -> None:
        """Each bracket's lower bound maps to that bracket."""
        assert elo_bracket(0) == "<800"
        assert elo_bracket(800) == "800-999"
        assert elo_bracket(1000) == "1000-1199"
        assert elo_bracket(1200) == "1200-1399"
        assert elo_bracket(1400) == "1400-1599"
        assert elo_bracket(1600) == "1600-1799"
        assert elo_bracket(1800) == "1800-1999"
        assert elo_bracket(2000) == "2000-2199"
        assert elo_bracket(2200) == "2200+"

    @pytest.mark.unit
    def test_boundaries_upper(self) -> None:
        """Each bracket's upper bound - 1 maps to that bracket."""
        assert elo_bracket(799) == "<800"
        assert elo_bracket(999) == "800-999"
        assert elo_bracket(1199) == "1000-1199"
        assert elo_bracket(1399) == "1200-1399"
        assert elo_bracket(1599) == "1400-1599"
        assert elo_bracket(1799) == "1600-1799"
        assert elo_bracket(1999) == "1800-1999"
        assert elo_bracket(2199) == "2000-2199"
        assert elo_bracket(2800) == "2200+"

    @pytest.mark.unit
    def test_full_valid_range_has_no_none(self) -> None:
        """Every Elo in the valid range [ELO_MIN, ELO_MAX] maps to a bracket."""
        for elo in range(ELO_MIN, ELO_MAX + 1):
            result = elo_bracket(elo)
            assert result is not None, f"elo_bracket({elo}) returned None"
            assert isinstance(result, str)

    @pytest.mark.unit
    def test_extreme_high_elo(self) -> None:
        """Very high Elo still maps to 2200+."""
        assert elo_bracket(3000) == "2200+"
        assert elo_bracket(9999) == "2200+"

    @pytest.mark.unit
    def test_brackets_are_contiguous(self) -> None:
        """Bracket definitions cover the full range without gaps."""
        for i in range(len(ELO_BRACKETS) - 1):
            current_upper = ELO_BRACKETS[i][1]
            next_lower = ELO_BRACKETS[i + 1][0]
            assert current_upper == next_lower, (
                f"Gap between brackets: {ELO_BRACKETS[i]} and {ELO_BRACKETS[i + 1]}"
            )


class TestTimeControlClassification:
    """Tests for the classify_time_control() function."""

    @pytest.mark.unit
    def test_bullet(self) -> None:
        """Short time controls classify as bullet."""
        assert classify_time_control("60+0") == "bullet"
        assert classify_time_control("120+0") == "bullet"
        assert classify_time_control("30+0") == "bullet"

    @pytest.mark.unit
    def test_blitz(self) -> None:
        """Medium time controls classify as blitz."""
        assert classify_time_control("180+0") == "blitz"
        assert classify_time_control("180+2") == "blitz"
        assert classify_time_control("300+0") == "blitz"

    @pytest.mark.unit
    def test_rapid(self) -> None:
        """Longer time controls classify as rapid."""
        assert classify_time_control("600+0") == "rapid"
        assert classify_time_control("600+5") == "rapid"
        assert classify_time_control("900+0") == "rapid"

    @pytest.mark.unit
    def test_classical(self) -> None:
        """Very long time controls classify as classical."""
        assert classify_time_control("1800+0") == "classical"
        assert classify_time_control("3600+0") == "classical"

    @pytest.mark.unit
    def test_ultrabullet(self) -> None:
        """Very short time controls classify as ultrabullet."""
        assert classify_time_control("15+0") == "ultrabullet"
        assert classify_time_control("25+0") == "ultrabullet"

    @pytest.mark.unit
    def test_invalid_input(self) -> None:
        """Invalid inputs return 'unknown'."""
        assert classify_time_control("") == "unknown"
        assert classify_time_control("abc") == "unknown"
        assert classify_time_control("-") == "unknown"

    @pytest.mark.unit
    def test_increment_ignored(self) -> None:
        """Only base time matters — increment is ignored for classification."""
        assert classify_time_control("180+0") == classify_time_control("180+10")
