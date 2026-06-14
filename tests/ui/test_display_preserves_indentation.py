# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_display_preserves_indentation.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Display-preparation regression coverage for leading whitespace."""

from __future__ import annotations

from ecli.ui.DrawScreen import prepare_visible_text_segment


def test_visible_text_segment_preserves_leading_spaces() -> None:
    source = "        return data"

    assert prepare_visible_text_segment(source, 0, 80) == source


def test_visible_text_segment_preserves_tab_and_mixed_spaces() -> None:
    source = "\t    mixed_indent()"

    assert prepare_visible_text_segment(source, 0, 80) == source


def test_horizontal_slicing_does_not_modify_source_buffer() -> None:
    source = "\t    mixed_indent()"
    original = source[:]

    visible = prepare_visible_text_segment(source, 1, 80, lambda _ch: 1)

    assert source == original
    assert visible == "    mixed_indent()"
