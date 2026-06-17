# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_syntax_highlighting_toggle.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests that the [editor].syntax_highlighting config key actually controls
highlighting and that highlighting never mutates the buffer.
"""

from __future__ import annotations

from typing import Any

from pygments.lexers import PythonLexer

from ecli.core.Ecli import Ecli


def make_editor(config: dict[str, Any]) -> Ecli:
    editor = Ecli.__new__(Ecli)
    editor.text = ["def main():", "    return 42"]
    editor.config = config
    editor.colors = {"default": 0, "keyword": 7, "number": 3, "comment": 1}
    editor.is_256_color_terminal = True
    editor._lexer = PythonLexer()
    editor.current_language = "python"
    editor.custom_syntax_patterns = []
    return editor


CODE = ["def main():", "    x = 42  # answer"]


def test_highlighting_enabled_by_default_preserves_line_content() -> None:
    editor = make_editor({})
    result = editor.apply_syntax_highlighting_with_pygments(CODE, [0, 1])

    # Content is reconstructable from tokens and the buffer is untouched.
    assert ["".join(tok for tok, _ in line) for line in result] == CODE
    assert editor.text == ["def main():", "    return 42"]
    # A keyword line yields more than a single flat segment when highlighting is on.
    assert len(result[0]) > 1


def test_highlighting_disabled_returns_single_default_segment() -> None:
    editor = make_editor({"editor": {"syntax_highlighting": False}})
    result = editor.apply_syntax_highlighting_with_pygments(CODE, [0, 1])

    default_attr = editor.colors["default"]
    assert result == [[(CODE[0], default_attr)], [(CODE[1], default_attr)]]


def test_highlighting_toggle_is_explicit_per_config() -> None:
    enabled = make_editor({"editor": {"syntax_highlighting": True}})
    disabled = make_editor({"editor": {"syntax_highlighting": False}})

    enabled_tokens = enabled.apply_syntax_highlighting_with_pygments(CODE, [0, 1])
    disabled_tokens = disabled.apply_syntax_highlighting_with_pygments(CODE, [0, 1])

    assert len(enabled_tokens[0]) > 1
    assert len(disabled_tokens[0]) == 1


def test_malformed_toggle_value_defaults_to_enabled() -> None:
    editor = make_editor({"editor": {"syntax_highlighting": "yes-please"}})
    result = editor.apply_syntax_highlighting_with_pygments(CODE, [0, 1])

    # Non-boolean -> highlighting stays on (never silently broken).
    assert len(result[0]) > 1
