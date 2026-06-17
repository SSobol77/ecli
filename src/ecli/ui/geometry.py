# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/geometry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic terminal split-layout geometry (Midnight Commander discipline).

A single source of truth for *where* the editor, a side panel, and the global
header/status/footer live, so panels stop being ad-hoc overlays that collide
with the bottom command/status rows.

Vertical contract (full chrome):

    row 0          global app header / menu bar
    rows 1..H-3    main work area (editor left, side panel right)
    row H-2        global status bar
    row H-1        global command/footer strip

A side panel occupies **only** the work-area rows (``1..H-3``) on the right; it
never draws into row 0, ``H-2`` or ``H-1``. Horizontally the editor takes ~60%
and the panel the remaining ~40%. When the terminal is too narrow to honour the
minimum editor/panel widths, ``split`` is ``False`` and ``panel`` is ``None`` —
the caller should fall back to a centered modal (or hide the panel with a
warning).

These constants intentionally mirror ``DrawScreen`` chrome heights so the editor
and panels agree on the work-area rows.
"""

from __future__ import annotations

from dataclasses import dataclass


#: Fraction of the width given to the editor when a side panel is open.
EDITOR_FRACTION = 0.60
#: Minimum usable widths before the split is refused (fall back to modal/hide).
MIN_EDITOR_WIDTH = 30
MIN_PANEL_WIDTH = 24
#: Below this height the header/footer collapse (status line only) — matches
#: ``DrawScreen.MIN_HEIGHT_FOR_FULL_CHROME``.
MIN_HEIGHT_FOR_FULL_CHROME = 8
HEADER_HEIGHT = 1
STATUS_HEIGHT = 1
FOOTER_HEIGHT = 1


@dataclass(frozen=True)
class Rect:
    """A terminal rectangle: top-left ``(x, y)`` with ``width`` x ``height``."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Exclusive right edge (``x + width``)."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Exclusive bottom edge (``y + height``)."""
        return self.y + self.height

    def contains_cols(self, x0: int, x1: int) -> bool:
        """True when the column span ``[x0, x1)`` fits inside this rect."""
        return self.x <= x0 and x1 <= self.right

    def contains(self, x: int, y: int) -> bool:
        """True when the point ``(x, y)`` lies inside this rectangle."""
        return self.x <= x < self.right and self.y <= y < self.bottom


@dataclass(frozen=True)
class LayoutGeometry:
    """Resolved regions for a frame: header, editor, optional panel, chrome."""

    terminal: Rect
    header: Rect
    editor: Rect
    status: Rect
    footer: Rect
    panel: Rect | None
    split: bool  # True when a real left/right split was produced


def chrome_heights(height: int) -> tuple[int, int, int]:
    """Return ``(header_h, status_h, footer_h)`` for a window height."""
    if height < MIN_HEIGHT_FOR_FULL_CHROME:
        return 0, STATUS_HEIGHT, 0
    return HEADER_HEIGHT, STATUS_HEIGHT, FOOTER_HEIGHT


def compute_layout(
    width: int, height: int, active_panel: bool = False
) -> LayoutGeometry:
    """Compute the editor/panel/chrome rectangles for a terminal of ``W``x``H``.

    With ``active_panel`` and enough width, the work area splits ~60/40 into an
    editor region (left) and a panel region (right), both confined to the
    work-area rows. If the terminal is too narrow, ``split`` is ``False`` and
    ``panel`` is ``None`` (caller falls back to a modal or hides the panel).
    """
    width = max(0, width)
    height = max(1, height)
    header_h, status_h, footer_h = chrome_heights(height)
    top = header_h
    work_h = max(1, height - header_h - status_h - footer_h)

    terminal = Rect(0, 0, width, height)
    header = Rect(0, 0, width, header_h)
    status = Rect(0, height - footer_h - status_h, width, status_h)
    footer = Rect(0, height - footer_h, width, footer_h)
    full_editor = Rect(0, top, width, work_h)

    if not active_panel:
        return LayoutGeometry(
            terminal, header, full_editor, status, footer, panel=None, split=False
        )

    editor_w = int(width * EDITOR_FRACTION)
    panel_w = width - editor_w
    if (
        editor_w < MIN_EDITOR_WIDTH
        or panel_w < MIN_PANEL_WIDTH
        or width < MIN_EDITOR_WIDTH + MIN_PANEL_WIDTH
    ):
        # Too narrow for a usable split: keep the editor full-width and let the
        # caller present the panel as a centered modal (or hide it).
        return LayoutGeometry(
            terminal, header, full_editor, status, footer, panel=None, split=False
        )

    editor = Rect(0, top, editor_w, work_h)
    panel = Rect(editor_w, top, panel_w, work_h)
    return LayoutGeometry(
        terminal, header, editor, status, footer, panel=panel, split=True
    )


def centered_modal_rect(
    width: int, height: int, want_width: int, want_height: int
) -> Rect:
    """A centered modal rectangle clamped to fit inside the terminal chrome.

    The modal never covers the global footer row (``H-1``) unless the terminal
    is too small to leave room.
    """
    header_h, status_h, footer_h = chrome_heights(height)
    avail_w = max(1, width - 2)
    avail_h = max(1, height - header_h - status_h - footer_h)
    w = max(1, min(want_width, avail_w))
    h = max(1, min(want_height, avail_h))
    x = max(0, (width - w) // 2)
    y = max(header_h, (height - h) // 2)
    # Keep the modal above the global status/footer when possible.
    max_y = max(header_h, height - footer_h - status_h - h)
    if max_y >= header_h:
        y = min(y, max_y)
    return Rect(x, y, w, h)
