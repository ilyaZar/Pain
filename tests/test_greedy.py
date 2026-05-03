"""Tests for greedy and non-greedy resize behaviour."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock

from Pain import COLS, ROWS, PainResizeCommand, WindowCommandSettings


class _DictSettings:
    """Dict-backed settings mock that supports get/set."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = dict(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


def _make_resize_cmd(
    layout: dict[str, Any],
    mode: str,
    greedy: bool,
    amount: int = 10,
    minimum: int = 0,
) -> PainResizeCommand:
    cmd = PainResizeCommand.__new__(PainResizeCommand)
    cmd.window = MagicMock()
    cmd.window.layout.return_value = deepcopy(layout)
    cmd.window.active_group.return_value = layout["active_group"]
    cmd.window.views_in_group.return_value = []
    cmd.window.active_view_in_group.return_value = MagicMock()

    settings = _DictSettings(
        {
            WindowCommandSettings.RESIZE_MODE: mode,
            WindowCommandSettings.GREEDY_PANE: greedy,
            WindowCommandSettings.RESIZE_AMOUNT: amount,
            WindowCommandSettings.MINIMUM_PANE_SIZE: minimum,
        }
    )
    cmd.settings = MagicMock(return_value=settings)  # type: ignore[method-assign]
    return cmd


def _squeezed_four_column_layout(active_group: int = 0) -> dict[str, Any]:
    return {
        "active_group": active_group,
        "cols": [0.0, 0.25, 0.30, 0.90, 1.0],
        "rows": [0.0, 1.0],
        "cells": [
            [0, 0, 1, 1],
            [1, 0, 2, 1],
            [2, 0, 3, 1],
            [3, 0, 4, 1],
        ],
    }


def _applied_cols(cmd: PainResizeCommand) -> list[float]:
    return cmd.window.set_layout.call_args_list[-1][0][0][COLS]


def _applied_rows(cmd: PainResizeCommand) -> list[float]:
    return cmd.window.set_layout.call_args_list[-1][0][0][ROWS]


class TestUngreedyResize:
    def test_growth_mode_stops_at_adjacent_separator(self) -> None:
        cmd = _make_resize_cmd(
            _squeezed_four_column_layout(),
            mode="growth",
            greedy=False,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.29, 0.30, 0.90, 1.0]


class TestGreedyResize:
    def test_growth_mode_pushes_adjacent_separator(self) -> None:
        cmd = _make_resize_cmd(
            _squeezed_four_column_layout(),
            mode="growth",
            greedy=True,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.35, 0.45, 0.90, 1.0]

    def test_directional_mode_pushes_adjacent_separator(self) -> None:
        cmd = _make_resize_cmd(
            _squeezed_four_column_layout(),
            mode="directional",
            greedy=True,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.35, 0.45, 0.90, 1.0]

    def test_rolls_back_when_cascade_hits_outer_edge(self) -> None:
        cmd = _make_resize_cmd(
            _squeezed_four_column_layout(),
            mode="growth",
            greedy=True,
            amount=70,
        )

        cmd.resize("width", 70)

        assert _applied_cols(cmd) == [0.0, 0.25, 0.30, 0.90, 1.0]

    def test_directional_mode_stops_at_adjacent_separator(self) -> None:
        cmd = _make_resize_cmd(
            _squeezed_four_column_layout(),
            mode="directional",
            greedy=False,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.29, 0.30, 0.90, 1.0]


class TestMinimumPaneSize:
    def test_non_greedy_clamps_left_pane_at_minimum(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 0,
                "cols": [0.0, 0.12, 1.0],
                "rows": [0.0, 1.0],
                "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
            },
            mode="directional",
            greedy=False,
            minimum=10,
        )

        cmd.resize("width", -3)

        assert _applied_cols(cmd) == [0.0, 0.10, 1.0]

    def test_growth_mode_clamps_right_pane_at_minimum(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 1,
                "cols": [0.0, 0.88, 1.0],
                "rows": [0.0, 1.0],
                "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
            },
            mode="growth",
            greedy=False,
            minimum=10,
        )

        cmd.resize("width", -3)

        assert _applied_cols(cmd) == [0.0, 0.90, 1.0]

    def test_greedy_pushes_neighbor_to_preserve_minimum(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 0,
                "cols": [0.0, 0.25, 0.40, 0.70, 1.0],
                "rows": [0.0, 1.0],
                "cells": [
                    [0, 0, 1, 1],
                    [1, 0, 2, 1],
                    [2, 0, 3, 1],
                    [3, 0, 4, 1],
                ],
            },
            mode="directional",
            greedy=True,
            minimum=10,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.35, 0.45, 0.70, 1.0]

    def test_greedy_shrink_pushes_neighbor_to_preserve_minimum(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 2,
                "cols": [0.0, 0.30, 0.60, 0.75, 1.0],
                "rows": [0.0, 1.0],
                "cells": [
                    [0, 0, 1, 1],
                    [1, 0, 2, 1],
                    [2, 0, 3, 1],
                    [3, 0, 4, 1],
                ],
            },
            mode="directional",
            greedy=True,
            minimum=10,
        )

        cmd.resize("width", -10)

        assert _applied_cols(cmd) == [0.0, 0.30, 0.55, 0.65, 1.0]

    def test_non_greedy_height_clamps_top_pane_at_minimum(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 0,
                "cols": [0.0, 1.0],
                "rows": [0.0, 0.12, 1.0],
                "cells": [[0, 0, 1, 1], [0, 1, 1, 2]],
            },
            mode="directional",
            greedy=False,
            minimum=10,
        )

        cmd.resize("height", -3)

        assert _applied_rows(cmd) == [0.0, 0.10, 1.0]

    def test_greedy_impossible_minimum_leaves_layout_unchanged(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 0,
                "cols": [0.0, 0.25, 0.50, 0.75, 1.0],
                "rows": [0.0, 1.0],
                "cells": [
                    [0, 0, 1, 1],
                    [1, 0, 2, 1],
                    [2, 0, 3, 1],
                    [3, 0, 4, 1],
                ],
            },
            mode="directional",
            greedy=True,
            minimum=30,
        )

        cmd.resize("width", 10)

        assert _applied_cols(cmd) == [0.0, 0.25, 0.50, 0.75, 1.0]

    def test_greedy_clamps_at_outer_edge(self) -> None:
        cmd = _make_resize_cmd(
            {
                "active_group": 1,
                "cols": [0.0, 0.88, 1.0],
                "rows": [0.0, 1.0],
                "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
            },
            mode="directional",
            greedy=True,
            minimum=10,
        )

        cmd.resize("width", 5)

        assert _applied_cols(cmd) == [0.0, 0.90, 1.0]
