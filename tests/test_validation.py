"""Tests for input validation.

Verifies that Pain shows an error dialog for invalid
resize_mode values, returns early without modifying the
layout, debounces repeated errors, and handles invalid
resize_amount values gracefully.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import sublime

from Pain import PainResizeCommand, WindowCommandSettings

# -- Helpers --


def _make_command(
    mode: str = "directional",
    amount: Any = None,
    minimum: Any = None,
) -> PainResizeCommand:
    """Build a PainResizeCommand with a mocked window.

    Args:
        mode: The resize_mode value to return from
            get_setting.
        amount: The resize_amount value.  ``None`` means
            the setting is absent (falls back to default).
        minimum: The minimum_pane_size value. ``None`` means
            the setting is absent (falls back to default).

    Returns:
        A command instance ready for ``resize()`` calls.
    """
    overrides = {WindowCommandSettings.RESIZE_MODE: mode}
    if amount is not None:
        overrides[WindowCommandSettings.RESIZE_AMOUNT] = amount
    if minimum is not None:
        overrides[WindowCommandSettings.MINIMUM_PANE_SIZE] = minimum

    cmd = PainResizeCommand.__new__(PainResizeCommand)
    cmd.window = MagicMock()
    cmd.window.layout.return_value = {
        "cols": [0.0, 0.5, 1.0],
        "rows": [0.0, 1.0],
        "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
    }
    cmd.window.active_group.return_value = 0
    cmd.window.views_in_group.return_value = []
    cmd.window.active_view_in_group.return_value = MagicMock()

    settings = MagicMock()
    settings.get.side_effect = lambda key, default=None: overrides.get(
        key, default
    )
    with patch.object(
        WindowCommandSettings, "settings", return_value=settings
    ):
        pass
    # Bind get_setting to use our controlled settings mock.
    cmd.settings = MagicMock(return_value=settings)  # type: ignore[method-assign]
    return cmd


def _reset_debounce() -> None:
    """Clear the debounce state between tests."""
    PainResizeCommand._last_invalid_mode = None


# -- Tests: invalid mode triggers error --


class TestInvalidResizeMode:
    """Error dialog on invalid resize_mode values."""

    def setup_method(self) -> None:
        """Reset debounce before each test."""
        _reset_debounce()

    @patch.object(sublime, "error_message")
    def test_typo_growht_shows_error(
        self,
        mock_err: MagicMock,
    ) -> None:
        """A common typo like 'growht' triggers error."""
        cmd = _make_command("growht")
        cmd.resize("width", 3)
        mock_err.assert_called_once()
        msg = mock_err.call_args[0][0]
        assert "growht" in msg

    @patch.object(sublime, "error_message")
    def test_arbitrary_string_shows_error(
        self,
        mock_err: MagicMock,
    ) -> None:
        """Any unrecognised string triggers error."""
        cmd = _make_command("zoom")
        cmd.resize("width", 3)
        mock_err.assert_called_once()
        msg = mock_err.call_args[0][0]
        assert "zoom" in msg

    @patch.object(sublime, "error_message")
    def test_invalid_mode_no_resize(
        self,
        mock_err: MagicMock,
    ) -> None:
        """Invalid mode returns early; cols unchanged."""
        cmd = _make_command("growht")
        cmd.resize("width", 3)
        # sort_and_get_layout calls set_layout once (to
        # normalize). If a resize happened, set_layout would
        # be called a second time with modified cols.
        assert cmd.window.set_layout.call_count == 1
        applied = cmd.window.set_layout.call_args[0][0]
        assert applied["cols"] == [0.0, 0.5, 1.0]


# -- Tests: debounce behaviour --


class TestErrorDebounce:
    """Error dialog is debounced on repeated keypresses."""

    def setup_method(self) -> None:
        """Reset debounce before each test."""
        _reset_debounce()

    @patch.object(sublime, "error_message")
    def test_same_invalid_shown_once(
        self,
        mock_err: MagicMock,
    ) -> None:
        """Repeated calls with same typo show dialog once."""
        cmd = _make_command("growht")
        cmd.resize("width", 3)
        cmd.resize("width", 3)
        cmd.resize("width", 3)
        mock_err.assert_called_once()

    @patch.object(sublime, "error_message")
    def test_different_invalid_shows_again(
        self,
        mock_err: MagicMock,
    ) -> None:
        """A new typo triggers a fresh dialog."""
        cmd_a = _make_command("growht")
        cmd_a.resize("width", 3)
        assert mock_err.call_count == 1

        cmd_b = _make_command("direchtional")
        cmd_b.resize("width", 3)
        assert mock_err.call_count == 2

    @patch.object(sublime, "error_message")
    def test_valid_resets_debounce(
        self,
        mock_err: MagicMock,
    ) -> None:
        """A valid resize clears the debounce flag."""
        cmd_bad = _make_command("growht")
        cmd_bad.resize("width", 3)
        assert mock_err.call_count == 1

        cmd_good = _make_command("directional")
        cmd_good.resize("width", 3)
        # Valid mode should reset the debounce.
        assert PainResizeCommand._last_invalid_mode is None

        cmd_bad2 = _make_command("growht")
        cmd_bad2.resize("width", 3)
        assert mock_err.call_count == 2


# -- Tests: valid modes do not trigger error --


class TestValidResizeMode:
    """Valid modes proceed without error."""

    def setup_method(self) -> None:
        """Reset debounce before each test."""
        _reset_debounce()

    @patch.object(sublime, "error_message")
    def test_directional_no_error(
        self,
        mock_err: MagicMock,
    ) -> None:
        """'directional' does not trigger error_message."""
        cmd = _make_command("directional")
        cmd.resize("width", 3)
        mock_err.assert_not_called()

    @patch.object(sublime, "error_message")
    def test_growth_no_error(
        self,
        mock_err: MagicMock,
    ) -> None:
        """'growth' does not trigger error_message."""
        cmd = _make_command("growth")
        cmd.resize("width", 3)
        mock_err.assert_not_called()


# -- Tests: resize_amount validation --


class TestGetResizeAmount:
    """Validate and clamp resize_amount setting."""

    def test_normal_value(self) -> None:
        cmd = _make_command(amount=3)
        assert cmd.get_resize_amount() == 3

    def test_string_returns_default(self) -> None:
        cmd = _make_command(amount="fast")
        assert cmd.get_resize_amount() == 3

    def test_none_returns_default(self) -> None:
        cmd = _make_command(amount=None)
        # amount=None means setting absent -> default (3)
        assert cmd.get_resize_amount() == 3

    def test_float_truncates(self) -> None:
        cmd = _make_command(amount=2.9)
        assert cmd.get_resize_amount() == 2

    def test_negative_clamps_to_one(self) -> None:
        cmd = _make_command(amount=-5)
        assert cmd.get_resize_amount() == 1

    def test_zero_clamps_to_one(self) -> None:
        cmd = _make_command(amount=0)
        assert cmd.get_resize_amount() == 1

    def test_one_is_minimum(self) -> None:
        cmd = _make_command(amount=1)
        assert cmd.get_resize_amount() == 1

    def test_hundred_is_maximum(self) -> None:
        cmd = _make_command(amount=100)
        assert cmd.get_resize_amount() == 100

    def test_over_hundred_clamps(self) -> None:
        cmd = _make_command(amount=101)
        assert cmd.get_resize_amount() == 100


class TestGetMinimumPaneSize:
    """Validate and clamp minimum_pane_size setting."""

    def test_normal_value(self) -> None:
        cmd = _make_command(minimum=10)
        assert cmd.get_minimum_pane_size() == 10

    def test_string_returns_default(self) -> None:
        cmd = _make_command(minimum="small")
        assert cmd.get_minimum_pane_size() == 10

    def test_none_returns_default(self) -> None:
        cmd = _make_command(minimum=None)
        assert cmd.get_minimum_pane_size() == 10

    def test_float_truncates(self) -> None:
        cmd = _make_command(minimum=10.9)
        assert cmd.get_minimum_pane_size() == 10

    def test_negative_clamps_to_zero(self) -> None:
        cmd = _make_command(minimum=-5)
        assert cmd.get_minimum_pane_size() == 0

    def test_zero_is_allowed(self) -> None:
        cmd = _make_command(minimum=0)
        assert cmd.get_minimum_pane_size() == 0

    def test_hundred_is_maximum(self) -> None:
        cmd = _make_command(minimum=100)
        assert cmd.get_minimum_pane_size() == 100

    def test_over_hundred_clamps(self) -> None:
        cmd = _make_command(minimum=101)
        assert cmd.get_minimum_pane_size() == 100
