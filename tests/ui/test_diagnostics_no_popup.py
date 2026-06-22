# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_diagnostics_no_popup.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""The legacy centered "Diagnostics" popup is retired: F4 uses only the right
side panel and no centered overlay is ever drawn (#104 UX).
"""

from __future__ import annotations

from typing import Any

from ecli.ui.DrawScreen import DrawScreen


class RecordingStdscr:
    def __init__(self) -> None:
        """Record any attempt to draw onto the editor surface."""
        self.draw_calls: list[tuple[int, int, str]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (40, 120)

    def addnstr(self, y: int, x: int, text: str, *_a: Any, **_k: Any) -> None:
        self.draw_calls.append((y, x, text))

    def addstr(self, y: int, x: int, text: str, *_a: Any, **_k: Any) -> None:
        self.draw_calls.append((y, x, text))


class LegacyEditor:
    def __init__(self) -> None:
        """Editor double whose legacy lint-overlay flag is (wrongly) active."""
        self.lint_panel_active = True
        self.lint_panel_message = "a.py:1:1 W292 No newline at end of file"
        self.colors: dict[str, int] = {}


class DrawScreenDouble:
    """Minimal stand-in carrying just what `_draw_lint_panel` touches."""

    def __init__(self) -> None:
        """Build the stand-in with a legacy editor and a recording surface."""
        self.editor = LegacyEditor()
        self.stdscr = RecordingStdscr()
        self.colors: dict[str, int] = {}


def test_legacy_lint_popup_draws_nothing_even_when_flag_active() -> None:
    double = DrawScreenDouble()
    assert double.editor.lint_panel_active is True

    DrawScreen._draw_lint_panel(double)  # type: ignore[arg-type]

    # No centered overlay is ever painted, regardless of the legacy flag.
    assert double.stdscr.draw_calls == []


def test_legacy_lint_flag_is_force_cleared_every_frame() -> None:
    double = DrawScreenDouble()

    # The per-frame hide hook unconditionally retires the stale legacy overlay
    # state so it cannot swallow Esc or leave a ghost surface.
    DrawScreen._maybe_hide_lint_panel(double)  # type: ignore[arg-type]

    assert double.editor.lint_panel_active is False
    assert double.stdscr.draw_calls == []
