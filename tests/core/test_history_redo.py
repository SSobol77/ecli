# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_history_redo.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Regression tests for real History redo behavior."""

from __future__ import annotations

from threading import RLock
from typing import Any, cast

from ecli.core.History import History


class MinimalEditor:
    """Minimal editor surface required by History block-operation redo."""

    def __init__(self) -> None:
        """Initialize editor state matching a completed block indent action."""
        self._state_lock = RLock()
        self.status_message = ""
        self.text = ["    alpha"]
        self.cursor_y = 0
        self.cursor_x = 9
        self.scroll_top = 0
        self.scroll_left = 0
        self.is_selecting = True
        self.selection_start: tuple[int, int] | None = (0, 0)
        self.selection_end: tuple[int, int] | None = (0, 9)
        self.modified = True

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def _ensure_cursor_in_bounds(self) -> None:
        self.cursor_y = max(0, min(self.cursor_y, len(self.text) - 1))
        self.cursor_x = max(0, min(self.cursor_x, len(self.text[self.cursor_y])))

    def _clamp_scroll_and_check_change(
        self, previous_scroll: tuple[int, int]
    ) -> bool:
        return (self.scroll_top, self.scroll_left) != previous_scroll


def test_redo_block_operation_restores_selection_on_editor() -> None:
    editor = MinimalEditor()
    history = History(cast(Any, editor))
    action: dict[str, Any] = {
        "type": "block_indent",
        "changes": [
            {
                "line_index": 0,
                "original_text": "alpha",
                "new_text": "    alpha",
            }
        ],
        "selection_before": ((0, 0), (0, 5)),
        "selection_after": (True, (0, 0), (0, 9)),
    }

    history.add_action(action)

    assert history.undo() is True
    assert editor.text == ["alpha"]
    assert editor.selection_start == (0, 0)
    assert editor.selection_end == (0, 5)

    assert history.redo() is True

    assert editor.text == ["    alpha"]
    assert editor.is_selecting is True
    assert editor.selection_start == (0, 0)
    assert editor.selection_end == (0, 9)
    assert (editor.cursor_y, editor.cursor_x) == (0, 9)
    assert editor.status_message == "Action redone"
    assert history._action_history == [action]
    assert history._undone_actions == []
