# tests/stubs.py
"""Test stubs for ECLI editor tests.

This module provides stub implementations of editor components
for testing purposes, particularly for the History functionality.
"""

import threading


class StubEditor:
    """Minimal subset of the ECLI editor required for History testing."""

    def __init__(self) -> None:
        """Initialize a stub editor with default values."""
        self.text: list[str] = [""]
        self.cursor_y: int = 0
        self.cursor_x: int = 0
        self.scroll_top: int = 0
        self.scroll_left: int = 0
        self.is_selecting: bool = False
        self.selection_start: tuple[int, int] | None = None
        self.selection_end: tuple[int, int] | None = None
        self.modified: bool = False
        self.status_message: str = "Ready"
        self._state_lock: threading.RLock = threading.RLock()

    # ---- methods invoked by History ----
    def _set_status_message(self, msg: str) -> None:
        """Update the editor status message.

        Args:
            msg: The new status message string.
        """
        self.status_message = str(msg)

    def _ensure_cursor_in_bounds(self) -> None:
        """Clamp cursor coordinates to remain within valid text bounds."""
        self.cursor_y = min(max(self.cursor_y, 0), len(self.text) - 1)
        self.cursor_x = min(max(self.cursor_x, 0), len(self.text[self.cursor_y]))

    def _clamp_scroll_and_check_change(self, _old: bool) -> bool:
        """Stub implementation of scroll clamping.

        Args:
            _old: Placeholder argument (not used in stub).

        Returns:
            Always False, as scrolling is not simulated in the stub.
        """
        return False

    # ---- text insertion (used by redo(insert) and undo(delete_selection)) ----
    def insert_text_at_position(self, txt: str, row: int, col: int) -> bool:
        """Insert text at a given position.

        Args:
            txt: The text to insert.
            row: Row (line index) at which to insert.
            col: Column index at which to insert.

        Returns:
            bool: True if the text was successfully inserted.
        """
        lines = txt.split("\n")
        if row >= len(self.text):
            self.text.extend([""] * (row - len(self.text) + 1))
        first, rest = lines[0], lines[1:]
        self.text[row] = self.text[row][:col] + first + self.text[row][col:]
        for i, ln in enumerate(rest, 1):
            self.text.insert(row + i, ln)
        self.cursor_y, self.cursor_x = (
            row + len(rest),
            (col + len(rest[-1]) if rest else col + len(first)),
        )
        self.modified = True
        return True

    # ---- deletion of a range (used by redo(delete_selection)) ----
    def delete_selected_text_internal(self, sy: int, sx: int, ey: int, ex: int) -> str:
        """Delete text from the specified range.

        Args:
            sy: Start row (y-coordinate).
            sx: Start column (x-coordinate).
            ey: End row (y-coordinate).
            ex: End column (x-coordinate).

        Returns:
            str: The removed text.
        """
        # For testing purposes, simplified deletion logic is sufficient
        if sy == ey:
            removed = self.text[sy][sx:ex]
            self.text[sy] = self.text[sy][:sx] + self.text[sy][ex:]
        else:
            removed = "\n".join(
                [
                    self.text[sy][sx:],
                    *self.text[sy + 1 : ey],
                    self.text[ey][:ex],
                ]
            )
            self.text[sy] = self.text[sy][:sx] + self.text[ey][ex:]
            del self.text[sy + 1 : ey + 1]
        self.cursor_y, self.cursor_x = sy, sx
        self.modified = True
        return removed
