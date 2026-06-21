# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_theme_bridge_priority.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Scope-priority tests for TextMate-to-renderer spans."""

from __future__ import annotations

from ecli.extensions.ecli_integration.theme_bridge import (
    scope_to_category,
    tokens_to_spans,
)


def test_string_scope_beats_nested_keyword_scope() -> None:
    scope = "source.python string.quoted.docstring.python keyword.control.flow.python"
    assert scope_to_category(scope) == "string"
    assert tokens_to_spans("return", [(scope, 0, 6)]) == [("return", "string")]


def test_comment_scope_beats_nested_keyword_scope() -> None:
    scope = (
        "source.python comment.line.number-sign.python keyword.control.import.python"
    )
    assert scope_to_category(scope) == "comment"
    assert tokens_to_spans("import", [(scope, 0, 6)]) == [("import", "comment")]


def test_invalid_scope_has_highest_priority() -> None:
    scope = "source.python string.quoted.python invalid.illegal.python"
    assert scope_to_category(scope) == "error"
    assert tokens_to_spans("bad", [(scope, 0, 3)]) == [("bad", "error")]


def test_protected_string_range_blocks_keyword_overpaint() -> None:
    spans = tokens_to_spans(
        "class def return 123 == ->",
        [
            ("keyword.control.python", 0, 16),
            ("constant.numeric.python", 17, 20),
            ("keyword.operator.python", 21, 26),
        ],
        protected_ranges=[(0, 16, "string")],
    )
    assert spans == [
        ("class def return", "string"),
        (" ", "default"),
        ("123", "number"),
        (" ", "default"),
        ("== ->", "operator"),
    ]


def test_protected_docstring_range_blocks_code_like_tokens() -> None:
    spans = tokens_to_spans(
        "class def return 123 == ->",
        [
            ("keyword.control.python", 0, 16),
            ("constant.numeric.python", 17, 20),
            ("keyword.operator.python", 21, 26),
        ],
        protected_ranges=[(0, 26, "string")],
    )
    assert spans == [("class def return 123 == ->", "string")]


def test_markdown_scopes_do_not_collapse_to_one_category() -> None:
    assert scope_to_category("text.html.markdown markup.heading.markdown") == "function"
    assert scope_to_category("text.html.markdown markup.bold.markdown") == "type"
    assert (
        scope_to_category("text.html.markdown markup.inline.raw.markdown") == "string"
    )
    assert scope_to_category("text.html.markdown markup.quote.markdown") == "comment"
