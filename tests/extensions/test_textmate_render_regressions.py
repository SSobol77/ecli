# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_render_regressions.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Render-correctness regression locks for #102.

These pin the syntax-correctness behaviours that must survive the viewport-first
rendering work: log/gitignore are never mis-detected as SQL, YAML stays visible,
Python docstrings keep absolute string priority, invalid theme numbers keep the
current theme with a warning, old theme ids migrate, and the shipped
``config.toml`` stays clean.
"""

from __future__ import annotations

import copy
import logging
import tomllib
from pathlib import Path

from ecli.core.Ecli import Ecli
from ecli.utils.themes import DEFAULT_THEME_ID, get_theme, resolve_theme
from ecli.utils.utils import DEFAULT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[2]

_STYLE_COLORS = {
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


def _make_editor(filename: str, text: list[str], engine: str = "extension") -> Ecli:
    editor = Ecli.__new__(Ecli)
    config = copy.deepcopy(DEFAULT_CONFIG)
    extensions = config.setdefault("extensions", {})
    extensions["syntax_engine"] = engine
    extensions["enabled"] = True
    editor.config = config
    editor.filename = filename
    editor.text = text
    editor.colors = _STYLE_COLORS
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


def _categories(rendered: list[list[tuple[str, int]]]) -> set[int]:
    return {attr for line in rendered for _text, attr in line}


# --------------------------------------------------------------------------- #
# Language detection: .log / .gitignore are never Transact-SQL.
# --------------------------------------------------------------------------- #


def test_log_file_is_not_transact_sql() -> None:
    for filename in ("freebsd-0.2.2-fail.log", "editor.log", "qemu.raw.log"):
        editor = _make_editor(filename, ["ERROR SELECT * FROM x WHERE id = 1"])
        assert editor.current_language == "log"
        assert "sql" not in (editor.current_language or "").lower()


def test_gitignore_is_not_transact_sql() -> None:
    editor = _make_editor(".gitignore", ["*.pyc", "build/", "SELECT/"])
    assert editor.current_language == "ignore"
    assert "sql" not in (editor.current_language or "").lower()


# --------------------------------------------------------------------------- #
# YAML stays visibly highlighted (legacy fallback when the engine yields nothing).
# --------------------------------------------------------------------------- #


def test_yaml_renders_with_visible_colours() -> None:
    yaml_doc = ["version: '3'", "services:", "  app:  # comment"]
    editor = _make_editor(".coderabbit.yaml", yaml_doc, engine="extension")
    rendered = editor.apply_syntax_highlighting_with_pygments(
        yaml_doc, list(range(len(yaml_doc)))
    )
    assert ["".join(t for t, _ in line) for line in rendered] == yaml_doc
    assert len(_categories(rendered)) > 1, "YAML must not render as flat default text"


# --------------------------------------------------------------------------- #
# Python multiline docstring keeps absolute string priority.
# --------------------------------------------------------------------------- #


def test_python_docstring_is_uniformly_string() -> None:
    code = [
        "def f():",
        '    """class def return 123 ==',
        "    import while -> + -",
        '    """',
        "    return 1",
    ]
    editor = _make_editor("example.py", code, engine="extension")
    if editor._extension_highlighter is None:
        import pytest

        pytest.skip("python-textmate engine unavailable")
    string_attr = _STYLE_COLORS["string"]
    default_attr = _STYLE_COLORS["default"]
    rendered = editor.apply_syntax_highlighting_with_pygments(
        code, list(range(len(code)))
    )
    # Lines fully inside the docstring carry only the string colour — no keyword,
    # number, operator or error colour leaks through the guard.
    for index in (1, 2, 3):
        attrs = {attr for _text, attr in rendered[index]}
        assert attrs <= {string_attr, default_attr}, (index, rendered[index])
        assert string_attr in attrs
    # The real statement after the docstring still highlights its keyword.
    assert _STYLE_COLORS["keyword"] in {attr for _text, attr in rendered[4]}


# --------------------------------------------------------------------------- #
# Theme: invalid number keeps current theme + warns; old ids migrate.
# --------------------------------------------------------------------------- #


def test_invalid_theme_number_keeps_current_and_warns(
    caplog: logging.LogCaptureFixture,
) -> None:
    current = get_theme(208)  # Monokai
    with caplog.at_level(logging.WARNING):
        result = resolve_theme({"theme": 9999}, current_theme=current)
    assert result.theme_id == current.theme_id
    assert result.name == current.name
    assert result.diagnostics, "a diagnostic must record the rejected theme"
    assert any("invalid theme" in record.message.lower() for record in caplog.records)


def test_old_theme_id_is_migrated() -> None:
    # Legacy pre-extension configs used a [theme] table with ids 1-8.
    assert resolve_theme({"theme": {"id": 3}}).theme_id == 381
    assert resolve_theme({"theme": {"name": "dark"}}).theme_id != DEFAULT_THEME_ID


# --------------------------------------------------------------------------- #
# Shipped config.toml is clean.
# --------------------------------------------------------------------------- #


def test_shipped_config_toml_is_clean() -> None:
    config_path = REPO_ROOT / "config.toml"
    raw = config_path.read_text(encoding="utf-8")
    # The obsolete empty keybindings table was removed during cleanup.
    assert "keybindings = {}" not in raw
    parsed = tomllib.loads(raw)
    # The configured theme is a real, resolvable theme number.
    theme = parsed.get("theme")
    assert isinstance(theme, int) and not isinstance(theme, bool)
    assert resolve_theme({"theme": theme}).theme_id == theme
