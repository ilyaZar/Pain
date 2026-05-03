from __future__ import annotations

import pytest

from Pain import (
    calc_point_value,
    calc_point_value_in_boundaries,
    calc_point_value_in_range,
    is_valid_point_value,
)


class TestCalcPointValue:
    """Basic separator position calculation."""

    def test_increase_by_one(self) -> None:
        assert calc_point_value(0.5, 1) == 0.51

    def test_decrease_by_one(self) -> None:
        assert calc_point_value(0.5, -1) == 0.49

    def test_increase_by_five(self) -> None:
        assert calc_point_value(0.5, 5) == 0.55

    def test_at_zero(self) -> None:
        assert calc_point_value(0.0, 3) == 0.03

    def test_rounding(self) -> None:
        result = calc_point_value(0.33, 1)
        assert result == 0.34


class TestCalcPointValueInBoundaries:
    """Clamped separator position calculation."""

    def test_within_bounds(self) -> None:
        result = calc_point_value_in_boundaries(0.5, 1, 0.0, 1.0)
        assert result == 0.51

    def test_clamp_at_max(self) -> None:
        result = calc_point_value_in_boundaries(0.99, 5, 0.0, 1.0)
        assert result == pytest.approx(0.99)

    def test_clamp_at_min(self) -> None:
        result = calc_point_value_in_boundaries(0.01, -5, 0.0, 1.0)
        assert result == pytest.approx(0.01)

    def test_exact_max_snaps_inside(self) -> None:
        result = calc_point_value_in_boundaries(0.5, 50, 0.0, 1.0)
        assert result == pytest.approx(0.99)

    def test_exact_min_snaps_inside(self) -> None:
        result = calc_point_value_in_boundaries(0.5, -50, 0.0, 1.0)
        assert result == pytest.approx(0.01)


class TestCalcPointValueInRange:
    """Inclusive separator position calculation."""

    def test_no_available_range_keeps_value(self) -> None:
        assert calc_point_value_in_range(0.5, 10, 0.8, 0.2) == 0.5

    def test_positive_move_at_max_keeps_value(self) -> None:
        assert calc_point_value_in_range(0.9, 5, 0.1, 0.9) == 0.9

    def test_negative_move_at_min_keeps_value(self) -> None:
        assert calc_point_value_in_range(0.1, -5, 0.1, 0.9) == 0.1

    def test_zero_move_keeps_value(self) -> None:
        assert calc_point_value_in_range(0.5, 0, 0.1, 0.9) == 0.5


class TestIsValidPointValue:
    """Point value validation."""

    def test_valid_middle(self) -> None:
        assert is_valid_point_value(0.5, 0.0, 1.0) is True

    def test_at_min_invalid(self) -> None:
        assert is_valid_point_value(0.0, 0.0, 1.0) is False

    def test_at_max_invalid(self) -> None:
        assert is_valid_point_value(1.0, 0.0, 1.0) is False

    def test_below_min_invalid(self) -> None:
        assert is_valid_point_value(-0.1, 0.0, 1.0) is False

    def test_above_max_invalid(self) -> None:
        assert is_valid_point_value(1.1, 0.0, 1.0) is False

    def test_barely_inside(self) -> None:
        assert is_valid_point_value(0.01, 0.0, 1.0) is True
