# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_layout_geometry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the deterministic split-layout geometry."""

from __future__ import annotations

import pytest

from ecli.ui.geometry import (
    EDITOR_FRACTION,
    MIN_EDITOR_WIDTH,
    MIN_PANEL_WIDTH,
    centered_modal_rect,
    compute_layout,
)


def test_no_panel_editor_uses_full_width() -> None:
    geo = compute_layout(120, 40, active_panel=False)
    assert geo.split is False
    assert geo.panel is None
    assert geo.editor.x == 0
    assert geo.editor.width == 120


@pytest.mark.parametrize("width", [100, 120, 160, 200])
def test_active_panel_splits_60_40(width: int) -> None:
    geo = compute_layout(width, 40, active_panel=True)
    assert geo.split is True
    assert geo.panel is not None
    assert geo.editor.x == 0
    assert geo.editor.width == int(width * EDITOR_FRACTION)
    # Panel starts exactly where the editor ends and runs to the right edge.
    assert geo.panel.x == geo.editor.right
    assert geo.panel.right == width


def test_work_area_rows_and_chrome_separation() -> None:
    geo = compute_layout(120, 40, active_panel=True)
    # Header is row 0, status is H-2, footer is H-1.
    assert geo.header.y == 0 and geo.header.height == 1
    assert geo.status.y == 40 - 2
    assert geo.footer.y == 40 - 1
    # Editor and panel both live in the work area: rows 1 .. H-3.
    assert geo.editor.y == 1 and geo.panel.y == 1
    assert geo.editor.bottom == 40 - 2  # ends before the status row
    assert geo.panel.bottom == 40 - 2
    # The panel must NOT extend into the global status/footer rows.
    assert geo.panel.bottom <= geo.status.y
    assert geo.panel.bottom <= geo.footer.y


def test_narrow_terminal_refuses_split() -> None:
    # Too narrow to honour both minimum widths -> no split, panel is None.
    geo = compute_layout(MIN_EDITOR_WIDTH + MIN_PANEL_WIDTH - 1, 40, active_panel=True)
    assert geo.split is False
    assert geo.panel is None
    assert geo.editor.width == MIN_EDITOR_WIDTH + MIN_PANEL_WIDTH - 1


def test_minimum_widths_respected_when_split() -> None:
    geo = compute_layout(MIN_EDITOR_WIDTH + MIN_PANEL_WIDTH, 40, active_panel=True)
    if geo.split:
        assert geo.editor.width >= MIN_EDITOR_WIDTH
        assert geo.panel.width >= MIN_PANEL_WIDTH


def test_small_height_collapses_chrome_but_keeps_status() -> None:
    geo = compute_layout(120, 6, active_panel=True)
    # Below the full-chrome threshold: no header/footer, status only.
    assert geo.header.height == 0
    assert geo.footer.height == 0
    assert geo.status.height == 1


def test_centered_modal_stays_inside_and_above_footer() -> None:
    rect = centered_modal_rect(120, 40, want_width=80, want_height=20)
    assert rect.x >= 0 and rect.right <= 120
    assert rect.y >= 1  # below the header
    assert rect.bottom <= 40 - 2  # above the global status/footer
