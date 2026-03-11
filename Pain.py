"""Pain — No pain to resize panes.

A Sublime Text 4 plugin for keyboard-driven pane resizing.
Forked from PanePane (inactive) with directional resize model
and modernized codebase.
"""

from __future__ import annotations

import itertools
import operator
from typing import Any

import sublime
import sublime_plugin

# --- Direction constants ---
LEFT, UP, RIGHT, DOWN = range(4)

# --- Cell coordinate indices into [x1, y1, x2, y2] ---
X_1, Y_1, X_2, Y_2 = range(4)

# --- Dimension strings ---
WIDTH = "width"
HEIGHT = "height"

# --- Layout dictionary keys ---
ACTIVE_GROUP = "active_group"
CELLS = "cells"
COLS = "cols"
ROWS = "rows"

# --- Direction opposites ---
OPPOSITE = {UP: DOWN, RIGHT: LEFT, DOWN: UP, LEFT: RIGHT}


def get_indices(dimension: str) -> tuple[int, int]:
    """Return cell coordinate indices for a dimension.

    Args:
        dimension: ``"width"`` or ``"height"``.

    Returns:
        ``(start_index, end_index)`` into cell coords.
    """
    return (X_1, X_2) if dimension == WIDTH else (Y_1, Y_2)


def is_cols(dimension: str) -> bool:
    """Check if the dimension refers to columns."""
    return dimension == WIDTH


def get_points(
    layout: dict[str, Any],
    dimension: str,
) -> list[float]:
    """Get separator positions for a dimension.

    Args:
        layout: The window layout dictionary.
        dimension: ``"width"`` or ``"height"``.

    Returns:
        List of floats from 0.0 to 1.0.
    """
    return layout[COLS] if dimension == WIDTH else layout[ROWS]


def set_points(
    layout: dict[str, Any],
    dimension: str,
    points: list[float],
) -> dict[str, Any]:
    """Set separator positions for a dimension.

    Args:
        layout: The window layout dictionary (mutated).
        dimension: ``"width"`` or ``"height"``.
        points: New separator positions.

    Returns:
        The mutated layout dictionary.
    """
    key = COLS if dimension == WIDTH else ROWS
    layout[key] = points
    return layout


# --- Resize model: sign functions ---


def get_sign_growth(
    point: int,
    points: list[float],
) -> int:
    """Determine resize sign using the growth model.

    Returns ``+1`` if the cell is in the left/top half,
    ``-1`` if in the right/bottom half.  This makes
    "increase" always grow the active pane.

    Args:
        point: Cell's left/top index in the points array.
        points: Column or row separator positions.

    Returns:
        ``+1`` for left/top half, ``-1`` for right/bottom.
    """
    return 1 if point <= (len(points) / 2) - 1 else -1


def get_sign_directional(
    point: int,
    points: list[float],
) -> int:
    """Determine resize sign using the directional model.

    Always returns ``+1`` so that "increase" means rightward
    or downward movement.

    Args:
        point: Unused; accepted for API symmetry.
        points: Unused; accepted for API symmetry.

    Returns:
        Always ``+1``.
    """
    return 1


# --- Resize model: separator selection ---


def get_point_index_growth(
    cell: list[int],
    points: list[float],
    dimension: str,
    sign: int,
) -> tuple[int, int]:
    """Pick the separator to move using the growth model.

    Selects the right/bottom boundary for left-half panes
    and the left/top boundary for right-half panes.  Flips
    the sign at window edges.

    Args:
        cell: Active cell as ``[x1, y1, x2, y2]`` indices.
        points: Separator positions for the dimension.
        dimension: ``"width"`` or ``"height"``.
        sign: Current sign (``+1`` or ``-1``).

    Returns:
        ``(separator_index, adjusted_sign)``.
        ``separator_index`` is ``-1`` when the cell spans
        the full dimension.
    """
    point1, point2 = get_indices(dimension)
    if sign > 0:
        point_index = cell[point2]
        other_index = cell[point1]
    else:
        point_index = cell[point1]
        other_index = cell[point2]

    if cell[point1] == 0 and cell[point2] == len(points) - 1:
        return -1, 0
    if point_index == 0 or point_index == len(points) - 1:
        point_index = other_index
        sign = get_sign_growth(point_index, points) * -1
    return point_index, sign


def get_point_index_directional(
    cell: list[int],
    points: list[float],
    dimension: str,
    sign: int,
) -> tuple[int, int]:
    """Pick the separator to move using directional model.

    Always prefers the right/bottom boundary.  Falls back to
    the left/top boundary when the preferred one is the
    window edge.  Never flips the sign.

    Args:
        cell: Active cell as ``[x1, y1, x2, y2]`` indices.
        points: Separator positions for the dimension.
        dimension: ``"width"`` or ``"height"``.
        sign: Current sign (always ``+1``).

    Returns:
        ``(separator_index, sign)``.
        ``separator_index`` is ``-1`` when the cell spans
        the full dimension.
    """
    point1, point2 = get_indices(dimension)
    point_index = cell[point2]

    if cell[point1] == 0 and cell[point2] == len(points) - 1:
        return -1, 0
    if point_index == len(points) - 1:
        point_index = cell[point1]
    return point_index, sign


# --- Adjacency and boundary helpers ---


def get_adjacent_direction(
    dimension: str,
    sign: int,
) -> int:
    """Map dimension and sign to a direction constant.

    Args:
        dimension: ``"width"`` or ``"height"``.
        sign: ``+1`` or ``-1``.

    Returns:
        One of ``LEFT``, ``UP``, ``RIGHT``, ``DOWN``.
    """
    if is_cols(dimension):
        return RIGHT if sign > 0 else LEFT
    return DOWN if sign > 0 else UP


def get_active_cell(
    layout: dict[str, Any],
) -> list[int]:
    """Get cell coordinates of the active group.

    Args:
        layout: Layout dict with ``active_group`` and
            ``cells`` keys.

    Returns:
        Cell as ``[x1, y1, x2, y2]`` indices.
    """
    return layout[CELLS][layout[ACTIVE_GROUP]]


def get_adjacent_cells(
    point_index: int,
    cells: list[list[int]],
    signs: list[int],
) -> list[list[int]]:
    """Find cells adjacent to a separator.

    Args:
        point_index: Index of the separator in cols/rows.
        cells: All cells in the layout.
        signs: Direction constants to search.

    Returns:
        List of cells touching the separator.
    """
    coordinate_map = {
        LEFT: (X_1, X_2),
        UP: (Y_1, Y_2),
        RIGHT: (X_2, X_1),
        DOWN: (Y_2, Y_1),
    }
    adjacent: list[list[int]] = []
    for cell in cells:
        for sign in signs:
            _, point = coordinate_map[sign]
            if point_index == cell[point]:
                adjacent.append(cell)
    return adjacent


def get_point_min_max(
    cell: list[int],
    cells: list[list[int]],
    point_index: int,
    dimension: str,
    sign: int,
) -> tuple[int, int]:
    """Compute boundary indices for separator movement.

    Used by the growth model to determine how far a
    separator can move without crossing adjacent panes.

    Args:
        cell: Active cell coordinates.
        cells: All cells in the layout.
        point_index: Index of the separator to move.
        dimension: ``"width"`` or ``"height"``.
        sign: Direction sign (``+1`` or ``-1``).

    Returns:
        ``(min_index, max_index)`` into the points array.
    """
    point1, point2 = get_indices(dimension)
    direction = get_adjacent_direction(dimension, sign)

    if sign > 0:
        max_adj = get_adjacent_cells(point_index, cells, [direction])
        point_max = (
            min(c[point2] for c in max_adj) if max_adj else cell[point2]
        )
        opposite = OPPOSITE[direction]
        min_adj = get_adjacent_cells(cell[point2], cells, [opposite])
        point_min = (
            max(c[point1] for c in min_adj) if min_adj else cell[point1]
        )
    else:
        min_adj = get_adjacent_cells(point_index, cells, [direction])
        point_min = (
            max(c[point1] for c in min_adj) if min_adj else cell[point1]
        )
        opposite = OPPOSITE[direction]
        max_adj = get_adjacent_cells(cell[point2], cells, [opposite])
        if max_adj:
            point_max = min(c[point1] for c in max_adj)
        else:
            max_adj = get_adjacent_cells(cell[point1], cells, [opposite])
            point_max = min(c[point2] for c in max_adj)

    return point_min, point_max


# --- Layout sorting and cell swapping ---


def swap_cell(
    cell: list[int],
    swap: list[int],
    indices: list[int],
) -> list[int]:
    """Swap coordinate indices within a cell.

    Args:
        cell: Cell coordinates to modify (mutated).
        swap: Pair of indices to exchange.
        indices: Which cell positions to check.

    Returns:
        The modified cell.
    """
    for i in indices:
        if cell[i] == swap[0]:
            cell[i] = swap[1]
        elif cell[i] == swap[1]:
            cell[i] = swap[0]
    return cell


def swap_cells(
    swap_pos: list[float],
    pos: list[float],
    cells: list[list[int]],
    active_cell: list[int],
    points: list[int],
) -> tuple[list[list[int]], list[int]]:
    """Reorder cells to match sorted separator positions.

    Args:
        swap_pos: Sorted separator positions.
        pos: Original separator positions.
        cells: All cells in the layout.
        active_cell: The currently active cell.
        points: Cell coordinate indices to swap.

    Returns:
        Tuple of (updated_cells, updated_active_cell).
    """
    raw_swaps: list[list[int]] = []
    for i, position in enumerate(pos):
        if position != swap_pos[i]:
            sorted_index = swap_pos.index(position)
            raw_swaps.append(sorted([i, sorted_index]))
    unique_swaps = list(s for s, _ in itertools.groupby(raw_swaps))
    for cell in cells:
        for swap in unique_swaps:
            is_active = active_cell == cell
            cell = swap_cell(cell, swap, points)
            if is_active:
                active_cell = cell
    return cells, active_cell


def sort_layout(
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Sort layout separators and reorder cells.

    Args:
        layout: Layout dictionary to sort.

    Returns:
        New sorted layout dictionary.
    """
    cols, rows, cells, active_cell = _sort_layout_and_swap_cells(layout)
    cells = sorted(cells)
    active_group = cells.index(active_cell)
    return create_layout(active_group, cols, rows, cells)


def create_layout(
    active_group: int,
    cols: list[float],
    rows: list[float],
    cells: list[list[int]],
) -> dict[str, Any]:
    """Create a layout dictionary from components.

    Args:
        active_group: Index of the active group.
        cols: Column separator positions.
        rows: Row separator positions.
        cells: Cell coordinate list.

    Returns:
        Layout dictionary.
    """
    return {
        ACTIVE_GROUP: active_group,
        COLS: cols,
        ROWS: rows,
        CELLS: cells,
    }


def _sort_points_and_swap_cells(
    points: list[float],
    cells: list[list[int]],
    active_cell: list[int],
    indices: list[int],
) -> tuple[list[float], list[list[int]], list[int]]:
    """Sort separator positions and adjust cells.

    Args:
        points: Separator positions to sort.
        cells: All cells in the layout.
        active_cell: The currently active cell.
        indices: Cell coordinate indices to adjust.

    Returns:
        Tuple of (sorted_points, cells, active_cell).
    """
    sorted_points = sorted(points)
    cells, active_cell = swap_cells(
        sorted_points, points, cells, active_cell, indices
    )
    return sorted_points, cells, active_cell


def _get_layout_tuple(
    layout: dict[str, Any],
) -> tuple[
    list[int],
    int,
    list[float],
    list[float],
    list[list[int]],
]:
    """Unpack a layout dictionary into components.

    Args:
        layout: The layout dictionary.

    Returns:
        Tuple of (active_cell, active_group, cols, rows,
        cells).
    """
    return (
        get_active_cell(layout),
        layout[ACTIVE_GROUP],
        layout[COLS],
        layout[ROWS],
        layout[CELLS],
    )


def _sort_layout_and_swap_cells(
    layout: dict[str, Any],
) -> tuple[
    list[float],
    list[float],
    list[list[int]],
    list[int],
]:
    """Sort all separators and adjust cells accordingly.

    Args:
        layout: The layout dictionary.

    Returns:
        Tuple of (sorted_cols, sorted_rows, cells,
        active_cell).
    """
    active_cell, _, cols, rows, cells = _get_layout_tuple(layout)
    sorted_cols, cells, active_cell = _sort_points_and_swap_cells(
        cols, cells, active_cell, [X_1, X_2]
    )
    sorted_rows, cells, active_cell = _sort_points_and_swap_cells(
        rows, cells, active_cell, [Y_1, Y_2]
    )
    return sorted_cols, sorted_rows, cells, active_cell


# --- Value calculation ---


def calc_point_value(
    point_value: float,
    amount: float,
) -> float:
    """Calculate a new separator position.

    Args:
        point_value: Current position (0.0 to 1.0).
        amount: Resize amount (divided by 100).

    Returns:
        New position, rounded to 2 decimal places.
    """
    return round(float(point_value) + (amount / 100), 2)


def calc_point_value_in_boundaries(
    point_value: float,
    amount: float,
    point_min: float,
    point_max: float,
) -> float:
    """Calculate a new separator position within bounds.

    Clamps the result to ``[point_min + 0.01,
    point_max - 0.01]``.

    Args:
        point_value: Current position.
        amount: Resize amount.
        point_min: Minimum allowed position.
        point_max: Maximum allowed position.

    Returns:
        Clamped new position.
    """
    new_value = calc_point_value(point_value, amount)
    if new_value >= point_max:
        new_value = point_max - 0.01
    if new_value <= point_min:
        new_value = point_min + 0.01
    return new_value


def is_valid_point_value(
    value: float,
    min_value: float,
    max_value: float,
) -> bool:
    """Check if a position is strictly within bounds.

    Args:
        value: Position to check.
        min_value: Minimum bound (exclusive).
        max_value: Maximum bound (exclusive).

    Returns:
        ``True`` if ``min_value < value < max_value``.
    """
    return min_value < value < max_value


def get_greedy_points(
    point_index: int,
    points: list[float],
    new_point_value: float,
    amount: float,
) -> list[float]:
    """Move a separator, pushing neighbors if needed.

    In greedy mode, if moving a separator would overlap a
    neighbor, the neighbor is pushed by the same amount.

    Args:
        point_index: Index of the separator to move.
        points: Current separator positions.
        new_point_value: Desired new position.
        amount: Resize amount for cascading pushes.

    Returns:
        Updated positions, or the original list if the
        cascade cannot complete.
    """
    greedy_points = list(points)
    greedy_points[point_index] = new_point_value

    if points[point_index] < new_point_value:
        step = 1
        stop = len(greedy_points)
        compare = operator.le
    else:
        step = -1
        stop = -1
        compare = operator.ge

    for i in range(point_index + step, stop, step):
        index = i + (step * -1)
        if compare(greedy_points[i], greedy_points[index]):
            new_val = calc_point_value(greedy_points[index], amount)
            if (
                is_valid_point_value(new_val, 0, 1)
                and new_val != greedy_points[index]
            ):
                greedy_points[i] = new_val
            else:
                return points

    return greedy_points


# --- Sublime Text command classes ---


class WindowCommandSettings:
    """Base class providing settings access for commands."""

    RESIZE_MODE = "resize_mode"
    GREEDY_PANE = "greedy_pane"
    RESIZE_AMOUNT = "resize_amount"
    SETTINGS_FILE = "Pain.sublime-settings"
    _VALID_RESIZE_MODES = ("directional", "growth")

    def get_setting(
        self,
        setting: str,
        default: Any = None,
    ) -> Any:
        """Read a setting value.

        Args:
            setting: Setting key name.
            default: Fallback if the key is missing.

        Returns:
            The setting value.
        """
        return self.settings().get(setting, default)

    def set_setting(
        self,
        setting: str,
        value: Any,
    ) -> None:
        """Write a setting value.

        Args:
            setting: Setting key name.
            value: Value to store.
        """
        self.settings().set(setting, value)

    def toggle_boolean_setting(
        self,
        setting: str,
    ) -> None:
        """Toggle a boolean setting.

        Args:
            setting: Setting key name.
        """
        self.set_setting(setting, not self.get_setting(setting, False))

    def cycle_resize_mode(self) -> None:
        """Cycle resize_mode between directional and growth."""
        current = self.get_setting(
            WindowCommandSettings.RESIZE_MODE,
            "directional",
        )
        new_mode = "growth" if current == "directional" else "directional"
        self.set_setting(WindowCommandSettings.RESIZE_MODE, new_mode)

    @classmethod
    def save_settings(cls) -> None:
        """Persist settings to disk."""
        sublime.save_settings(WindowCommandSettings.SETTINGS_FILE)

    @classmethod
    def settings(cls) -> sublime.Settings:
        """Load the Pain settings object.

        Returns:
            Sublime ``Settings`` instance.
        """
        return sublime.load_settings(WindowCommandSettings.SETTINGS_FILE)


class PainResizeCommand(sublime_plugin.WindowCommand, WindowCommandSettings):
    """Resize editor panes via keyboard shortcuts."""

    _last_invalid_mode: str | None = None

    def get_resize_amount(self) -> int:
        """Read and clamp the resize_amount setting.

        Returns:
            Integer in range ``[1, 100]``.
        """
        raw = self.get_setting(WindowCommandSettings.RESIZE_AMOUNT, 3)
        try:
            resize_amount = int(raw)
        except (ValueError, TypeError):
            return 3
        if resize_amount <= 0:
            return 1
        if resize_amount > 100:
            return 100
        return resize_amount

    def run(
        self,
        dimension: str,
        resize: str,
    ) -> None:
        """Entry point called by Sublime Text.

        Args:
            dimension: ``"width"``, ``"height"``,
                or ``"all"`` (equalize only).
            resize: ``"increase"``, ``"decrease"``,
                or ``"equal"``.
        """
        amount = self.get_resize_amount()
        if resize == "decrease":
            self.resize(dimension, -amount)
        elif resize == "increase":
            self.resize(dimension, amount)
        elif resize == "equal":
            self.equalize(dimension)

    def equalize(self, dimension: str) -> None:
        """Distribute separators evenly.

        Args:
            dimension: ``"width"``, ``"height"``, or
                ``"all"`` (both dimensions).
        """
        layout, _ = self.sort_and_get_layout()
        dims = [WIDTH, HEIGHT] if dimension == "all" else [dimension]
        for dim in dims:
            points = get_points(layout, dim)
            length = len(points)
            points = [i * (1 / (length - 1)) for i in range(length)]
            layout = set_points(layout, dim, points)
        self.set_layout(layout)

    def resize(self, dimension: str, amount: int) -> None:
        """Move a separator to resize the active pane.

        Args:
            dimension: ``"width"`` or ``"height"``.
            amount: Signed resize amount (positive means
                increase, negative means decrease).
        """
        layout, orig_layout = self.sort_and_get_layout()
        cells = orig_layout[CELLS]
        active_cell = get_active_cell(orig_layout)
        points = get_points(layout, dimension)
        point, _ = get_indices(dimension)

        mode = self.get_setting(
            WindowCommandSettings.RESIZE_MODE,
            "directional",
        )
        valid = WindowCommandSettings._VALID_RESIZE_MODES
        if mode not in valid:
            if mode != PainResizeCommand._last_invalid_mode:
                PainResizeCommand._last_invalid_mode = mode
                sublime.error_message(
                    "Pain: Invalid resize_mode "
                    '"' + str(mode) + '".\n'
                    'Expected "directional" or '
                    '"growth".\n'
                    "Check Preferences > Package "
                    "Settings > Pain > Settings."
                )
            return
        PainResizeCommand._last_invalid_mode = None

        if mode == "directional":
            sign = get_sign_directional(active_cell[point], points)
            point_index, sign = get_point_index_directional(
                active_cell, points, dimension, sign
            )
        else:
            sign = get_sign_growth(active_cell[point], points)
            point_index, sign = get_point_index_growth(
                active_cell, points, dimension, sign
            )

        if point_index >= 0:
            amount *= sign
            if mode == "directional":
                point_min = points[point_index - 1]
                point_max = points[point_index + 1]
            elif self.get_setting(WindowCommandSettings.GREEDY_PANE):
                point_min = 0.0
                point_max = 1.0
            else:
                min_idx, max_idx = get_point_min_max(
                    active_cell,
                    cells,
                    point_index,
                    dimension,
                    sign,
                )
                point_min = points[min_idx]
                point_max = points[max_idx]

            new_value = calc_point_value_in_boundaries(
                points[point_index],
                amount,
                point_min,
                point_max,
            )
            if is_valid_point_value(new_value, point_min, point_max):
                if self.get_setting(WindowCommandSettings.GREEDY_PANE):
                    points = get_greedy_points(
                        point_index,
                        points,
                        new_value,
                        amount,
                    )
                else:
                    points[point_index] = new_value
                layout = sort_layout(set_points(layout, dimension, points))

        self.swap_views(cells, layout[CELLS])
        self.set_layout(layout)

    def get_layout(self) -> dict[str, Any]:
        """Read the window layout with active group.

        Returns:
            Layout dict augmented with ``active_group``.
        """
        window = self.window
        layout = window.layout()
        layout[ACTIVE_GROUP] = window.active_group()
        return layout

    def set_layout(
        self,
        layout: dict[str, Any],
    ) -> None:
        """Apply a layout and restore group focus.

        Args:
            layout: Layout dict with ``active_group``.
        """
        window = self.window
        window.set_layout(layout)
        window.focus_group(layout[ACTIVE_GROUP])

    def sort_and_get_layout(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Sort current layout and return both versions.

        Returns:
            ``(sorted_layout, original_layout)``.
        """
        layout = self.get_layout()
        sorted_layout = sort_layout(layout)
        self.set_layout(sorted_layout)
        return sorted_layout, layout

    def swap_views(
        self,
        cells: list[list[int]],
        sorted_cells: list[list[int]],
    ) -> None:
        """Move views to match reordered cells.

        Args:
            cells: Original cell order.
            sorted_cells: New cell order after sorting.
        """
        window = self.window
        swaps: list[dict[str, Any]] = []
        for i, cell in enumerate(cells):
            if cell != sorted_cells[i]:
                swaps.append(
                    {
                        "group": sorted_cells.index(cell),
                        "views": window.views_in_group(i),
                        "active_view": (window.active_view_in_group(i)),
                    }
                )
        for swap in swaps:
            for index, view in enumerate(swap["views"]):
                window.set_view_index(view, swap["group"], index)
            window.focus_view(swap["active_view"])


class PainToggleSettingCommand(
    sublime_plugin.WindowCommand, WindowCommandSettings
):
    """Toggle a Pain setting via the command palette.

    Cycles ``resize_mode`` between ``"directional"`` and
    ``"growth"``.  All other settings are toggled as booleans.
    """

    def run(self, setting: str) -> None:
        """Toggle or cycle a setting, then persist.

        Args:
            setting: The setting key to toggle/cycle.
        """
        if setting == WindowCommandSettings.RESIZE_MODE:
            self.cycle_resize_mode()
        else:
            self.toggle_boolean_setting(setting)
        self.save_settings()
