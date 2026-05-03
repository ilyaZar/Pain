"""Runtime tests that exercise Pain inside Sublime Text."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import sublime
from unittesting import DeferrableTestCase

from ..Pain import WindowCommandSettings


class PainWindowRuntimeTest(DeferrableTestCase):
    """Smoke-test the real Sublime window command surface."""

    def setUp(self) -> None:
        self.window = sublime.active_window()
        self.original_layout = deepcopy(self.window.layout())
        self.original_group = self.window.active_group()
        self.settings = sublime.load_settings(
            WindowCommandSettings.SETTINGS_FILE
        )
        self.original_settings = {
            WindowCommandSettings.RESIZE_MODE: self.settings.get(
                WindowCommandSettings.RESIZE_MODE
            ),
            WindowCommandSettings.GREEDY_PANE: self.settings.get(
                WindowCommandSettings.GREEDY_PANE
            ),
            WindowCommandSettings.RESIZE_AMOUNT: self.settings.get(
                WindowCommandSettings.RESIZE_AMOUNT
            ),
        }

        self.settings.set(WindowCommandSettings.RESIZE_MODE, "directional")
        self.settings.set(WindowCommandSettings.GREEDY_PANE, False)
        self.settings.set(WindowCommandSettings.RESIZE_AMOUNT, 10)

    def tearDown(self) -> None:
        self.window.set_layout(self.original_layout)
        self.window.focus_group(self.original_group)
        for key, value in self.original_settings.items():
            self.settings.set(key, value)

    def test_width_increase_moves_separator_right(self):
        self.window.set_layout(two_column_layout(0.5))
        self.window.focus_group(0)

        yield 100

        self.window.run_command(
            "pain_resize",
            {"dimension": "width", "resize": "increase"},
        )

        yield 100

        self.assertGreater(self.window.layout()["cols"][1], 0.5)
        self.assertEqual(self.window.active_group(), 0)

    def test_equalize_restores_focused_group(self):
        self.window.set_layout(two_column_layout(0.8))
        self.window.focus_group(1)

        yield 100

        self.window.run_command(
            "pain_resize",
            {"dimension": "width", "resize": "equal"},
        )

        yield 100

        self.assertEqual(self.window.layout()["cols"], [0.0, 0.5, 1.0])
        self.assertEqual(self.window.active_group(), 1)

    def test_greedy_width_resize_pushes_adjacent_separator(self):
        self.window.set_layout(squeezed_four_column_layout())
        self.window.focus_group(0)
        self.settings.set(WindowCommandSettings.GREEDY_PANE, True)

        yield 100

        self.window.run_command(
            "pain_resize",
            {"dimension": "width", "resize": "increase"},
        )

        yield 100

        self.assertEqual(
            self.window.layout()["cols"],
            [0.0, 0.35, 0.45, 0.90, 1.0],
        )
        self.assertEqual(self.window.active_group(), 0)


def two_column_layout(split: float) -> dict[str, Any]:
    return {
        "cols": [0.0, split, 1.0],
        "rows": [0.0, 1.0],
        "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
    }


def squeezed_four_column_layout() -> dict[str, Any]:
    return {
        "cols": [0.0, 0.25, 0.30, 0.90, 1.0],
        "rows": [0.0, 1.0],
        "cells": [
            [0, 0, 1, 1],
            [1, 0, 2, 1],
            [2, 0, 3, 1],
            [3, 0, 4, 1],
        ],
    }
