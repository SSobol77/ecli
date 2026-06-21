# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_multiline_protection.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Multiline TextMate protection regression tests for issue #102."""

from __future__ import annotations

import copy

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.ecli_integration import (
    EXTENSION_TOKENIZATION_AVAILABLE,
    ExtensionLayerConfig,
    SyntaxService,
    build_syntax_service,
)
from ecli.extensions.ecli_integration.syntax_service import (
    _protected_ranges_for_scope,
)
from ecli.utils.utils import DEFAULT_CONFIG


pytestmark = pytest.mark.skipif(
    not EXTENSION_TOKENIZATION_AVAILABLE,
    reason="python-textmate tokenizer is not installed",
)

STYLE_COLORS = {
    name: index
    for index, name in enumerate(
        [
            "default",
            "keyword",
            "string",
            "comment",
            "number",
            "constant",
            "type",
            "function",
            "variable",
            "tag",
            "attribute",
            "builtin",
            "operator",
            "decorator",
            "error",
            "punctuation",
            "class",
        ]
    )
}


@pytest.fixture(scope="module")
def service() -> SyntaxService:
    return build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )


def _make_editor(filename: str, text: list[str]) -> Ecli:
    editor = Ecli.__new__(Ecli)
    config = copy.deepcopy(DEFAULT_CONFIG)
    extensions = config.setdefault("extensions", {})
    extensions["syntax_engine"] = "extension"
    extensions["enabled"] = True
    editor.config = config
    editor.filename = filename
    editor.text = text
    editor.colors = STYLE_COLORS
    editor.is_256_color_terminal = True
    editor._lexer = None
    editor.current_language = None
    editor.custom_syntax_patterns = []
    editor.extension_syntax = None
    editor._extension_highlighter = None
    editor._modified = False
    editor._buffer_edit_revision = 0
    editor.detect_language()
    return editor


def _char_categories(spans: list[tuple[str, str]]) -> list[str]:
    return [category for text, category in spans for _char in text]


def _attr_categories(rendered_line: list[tuple[str, int]]) -> list[int]:
    return [attr for text, attr in rendered_line for _char in text]


def _assert_range_category(
    spans: list[tuple[str, str]], line: str, needle: str, category: str
) -> None:
    start = line.index(needle)
    end = start + len(needle)
    categories = _char_categories(spans)
    assert set(categories[start:end]) == {category}, spans


def _assert_editor_range_attr(
    rendered_line: list[tuple[str, int]], line: str, needle: str, attr: int
) -> None:
    start = line.index(needle)
    end = start + len(needle)
    attrs = _attr_categories(rendered_line)
    assert set(attrs[start:end]) == {attr}, rendered_line


def test_protected_range_detection_for_required_languages() -> None:
    js_body = 'class Test { return 123; const x = "<div>"; }'
    ts_body = "interface User { id: number; }"
    html_body = '<div class="x"> return 123 </div>'
    css_body = "color: red; display: block; margin: 10px;"
    py_body = "def class return import for while 123 == -> <tag>"
    cases = [
        (
            "source.js",
            ["/*", js_body, "*/"],
            {
                0: ((0, 2, "comment"),),
                1: ((0, len(js_body), "comment"),),
                2: ((0, 2, "comment"),),
            },
        ),
        (
            "source.ts",
            ["/*", ts_body, "*/"],
            {
                0: ((0, 2, "comment"),),
                1: ((0, len(ts_body), "comment"),),
                2: ((0, 2, "comment"),),
            },
        ),
        (
            "text.html.derivative",
            ["<!--", html_body, "-->"],
            {
                0: ((0, 4, "comment"),),
                1: ((0, len(html_body), "comment"),),
                2: ((0, 3, "comment"),),
            },
        ),
        (
            "source.css",
            ["/*", css_body, "*/"],
            {
                0: ((0, 2, "comment"),),
                1: ((0, len(css_body), "comment"),),
                2: ((0, 2, "comment"),),
            },
        ),
        (
            "source.python",
            ["'''", py_body, "'''"],
            {
                0: ((0, 3, "string"),),
                1: ((0, len(py_body), "string"),),
                2: ((0, 3, "string"),),
            },
        ),
    ]
    for scope_name, lines, expected in cases:
        assert _protected_ranges_for_scope(scope_name, lines) == expected


def test_python_triple_single_and_double_strings_are_protected(
    service: SyntaxService,
) -> None:
    highlighter = service.build_line_highlighter("example.py")
    assert highlighter is not None
    lines = [
        "'''",
        "def class return import for while 123 == -> <tag>",
        "'''",
        '"""',
        "def class return import for while 123 == -> <tag>",
        '"""',
        "def real_function():",
        "    return 1",
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    for index in (0, 1, 2, 3, 4, 5):
        assert highlighted[index] is not None
        assert {category for _text, category in highlighted[index]} == {"string"}
    assert highlighted[6] is not None
    assert any(
        text == "def" and category == "keyword" for text, category in highlighted[6]
    )


def test_javascript_multiline_comments_win_over_code_scopes(
    service: SyntaxService,
) -> None:
    highlighter = service.build_line_highlighter("fixture.js")
    assert highlighter is not None
    lines = [
        "/*",
        'class Test { return 123; const x = "<div>"; }',
        "*/",
        "/**",
        "function return import export let const 123 == =>",
        "*/",
        "const real = 123;",
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    assert highlighted[1] is not None
    _assert_range_category(highlighted[1], lines[1], "class Test", "comment")
    _assert_range_category(highlighted[1], lines[1], "123", "comment")
    _assert_range_category(highlighted[1], lines[1], "<div>", "comment")
    assert highlighted[4] is not None
    _assert_range_category(highlighted[4], lines[4], "function", "comment")
    _assert_range_category(highlighted[4], lines[4], "=>", "comment")
    assert highlighted[6] is not None
    assert any(
        text == "const" and category in {"keyword", "type"}
        for text, category in highlighted[6]
    )


def test_typescript_multiline_comments_win_over_code_scopes(
    service: SyntaxService,
) -> None:
    highlighter = service.build_line_highlighter("fixture.ts")
    assert highlighter is not None
    lines = [
        "/*",
        'class Test { return 123; const x = "<div>"; }',
        "interface User { id: number; }",
        "*/",
        "const real: number = 123;",
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    assert highlighted[1] is not None
    _assert_range_category(highlighted[1], lines[1], "return", "comment")
    _assert_range_category(highlighted[1], lines[1], "123", "comment")
    assert highlighted[2] is not None
    _assert_range_category(highlighted[2], lines[2], "interface", "comment")
    _assert_range_category(highlighted[2], lines[2], "number", "comment")
    assert highlighted[4] is not None
    assert any(
        text == "const" and category in {"keyword", "type"}
        for text, category in highlighted[4]
    )


def test_html_multiline_comments_win_over_tag_scopes(service: SyntaxService) -> None:
    highlighter = service.build_line_highlighter("fixture.html")
    assert highlighter is not None
    lines = [
        "<!--",
        '<div class="x"> return 123 </div>',
        "-->",
        '<section class="real">content</section>',
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    assert highlighted[1] is not None
    _assert_range_category(highlighted[1], lines[1], "<div", "comment")
    _assert_range_category(highlighted[1], lines[1], "return", "comment")
    _assert_range_category(highlighted[1], lines[1], "123", "comment")
    assert highlighted[3] is not None
    assert any(category == "tag" for _text, category in highlighted[3])


def test_css_multiline_comments_win_over_property_scopes(
    service: SyntaxService,
) -> None:
    highlighter = service.build_line_highlighter("fixture.css")
    assert highlighter is not None
    lines = [
        "/*",
        "color: red; display: block; margin: 10px;",
        "*/",
        "body { color: red; }",
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    assert highlighted[1] is not None
    _assert_range_category(highlighted[1], lines[1], "color", "comment")
    _assert_range_category(highlighted[1], lines[1], "10px", "comment")
    assert highlighted[3] is not None
    assert any(category != "comment" for _text, category in highlighted[3])
    assert any(category != "default" for _text, category in highlighted[3])


@pytest.mark.parametrize(
    ("filename", "lines", "line_index", "needle", "expected_attr"),
    [
        (
            "fixture.js",
            [
                "/*",
                'class Test { return 123; const x = "<div>"; }',
                "*/",
                "const real = 1;",
            ],
            1,
            "return 123",
            STYLE_COLORS["comment"],
        ),
        (
            "fixture.ts",
            ["/*", "interface User { id: number; }", "*/", "const real: number = 1;"],
            1,
            "interface User",
            STYLE_COLORS["comment"],
        ),
        (
            "fixture.html",
            ["<!--", '<div class="x"> return 123 </div>', "-->", "<p>real</p>"],
            1,
            "<div",
            STYLE_COLORS["comment"],
        ),
        (
            "fixture.css",
            [
                "/*",
                "color: red; display: block; margin: 10px;",
                "*/",
                "body { color: red; }",
            ],
            1,
            "display: block",
            STYLE_COLORS["comment"],
        ),
        (
            "fixture.py",
            [
                "'''",
                "def class return import for while 123 == -> <tag>",
                "'''",
                "return_value = 1",
            ],
            1,
            "return import",
            STYLE_COLORS["string"],
        ),
    ],
)
def test_editor_rendering_applies_multiline_protection(
    filename: str,
    lines: list[str],
    line_index: int,
    needle: str,
    expected_attr: int,
) -> None:
    editor = _make_editor(filename, lines)
    if editor._extension_highlighter is None:
        pytest.skip(f"no extension highlighter for {filename}")
    rendered = editor.apply_syntax_highlighting_with_pygments(
        lines, list(range(len(lines)))
    )
    _assert_editor_range_attr(
        rendered[line_index], lines[line_index], needle, expected_attr
    )
    assert ["".join(text for text, _attr in line) for line in rendered] == lines
