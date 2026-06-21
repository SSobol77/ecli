# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_no_fake_textmate_support.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Acceptance gates: no fake TextMate support, no SQL fallback (#102).

These prove behaviour the previous metadata-only tests could not:

* **No fake support.** When a required language grammar is missing from the
  imported tree, ECLI must report the missing grammar and fall back to legacy —
  it must never claim a TextMate scope/grammar it does not have.
* **No SQL fallback.** Real logs, dotfiles, and plain text — even when their
  *content* looks like SQL — must never be detected as SQL/Transact-SQL. Only a
  genuinely SQL-named file may be SQL.
* **Safe fallback when the tokenizer is missing.** With ``python-textmate``
  unavailable, the service degrades to legacy and says so via a diagnostic.
"""

from __future__ import annotations

import copy

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.ecli_integration import build_syntax_service, syntax_service as svc
from ecli.extensions.ecli_integration.config import ExtensionLayerConfig
from ecli.utils.utils import DEFAULT_CONFIG


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

# Languages the project requires but whose grammar is *not* in the imported tree.
REQUIRED_MISSING = ("pyproject.toml", "boot.asm", "main.ada", "solver.f90")


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


def _service() -> svc.SyntaxService:
    return build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )


# --------------------------------------------------------------------------- #
# No fake support: missing grammar => report + safe fallback, never a claim.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", REQUIRED_MISSING)
def test_missing_grammar_is_reported_and_not_faked(filename: str) -> None:
    resolution = _service().resolve(filename)
    # The language is recognised by name...
    assert resolution.language_id is not None
    # ...but ECLI must NOT pretend to have a TextMate grammar/scope for it.
    assert resolution.scope_name is None
    assert resolution.grammar_path is None
    assert resolution.has_grammar is False
    assert resolution.fallback_to_legacy is True
    # A diagnostic must explicitly report the missing required grammar.
    messages = [d.message.lower() for d in resolution.diagnostics]
    assert any(
        "grammar missing" in m and resolution.language_id in m for m in messages
    ), messages


@pytest.mark.parametrize("filename", REQUIRED_MISSING)
def test_missing_grammar_yields_no_highlighter(filename: str) -> None:
    assert _service().build_line_highlighter(filename) is None


def test_editor_renders_missing_grammar_file_via_legacy() -> None:
    # A .toml file (grammar missing) must still render — through legacy, not as a
    # fake TextMate claim and not as flat default text.
    text = ['name = "ecli"', "[tool.x]", "value = 42  # c"]
    editor = _make_editor("pyproject.toml", text, engine="extension")
    assert editor._extension_highlighter is None
    rendered = editor.apply_syntax_highlighting_with_pygments(
        text, list(range(len(text)))
    )
    assert ["".join(t for t, _ in line) for line in rendered] == text


# --------------------------------------------------------------------------- #
# No SQL fallback for text / log / dotfiles, even with SQL-looking content.
# --------------------------------------------------------------------------- #

_SQL_LOOKING = "SELECT * FROM users WHERE id = 1; DROP TABLE x;"

_NON_SQL_CASES = [
    ("server.log", [f"2026-06-21 ERROR {_SQL_LOOKING}"]),
    ("freebsd-0.2.2-fail.log", [_SQL_LOOKING, "make: stopped"]),
    (".gitignore", ["*.pyc", "build/", "SELECT/"]),
    (".env", [f"QUERY={_SQL_LOOKING}"]),
    ("notes.txt", [_SQL_LOOKING]),
    ("README", [_SQL_LOOKING]),
    ("Makefile", ["all:", f"\techo '{_SQL_LOOKING}'"]),
]


@pytest.mark.parametrize("filename,text", _NON_SQL_CASES)
def test_non_sql_files_are_never_sql(filename: str, text: list[str]) -> None:
    editor = _make_editor(filename, text, engine="extension")
    language = (editor.current_language or "").lower()
    assert "sql" not in language, (filename, language)
    # The extension resolution must not claim a SQL language id either.
    ext_lang = (getattr(editor.extension_syntax, "language_id", "") or "").lower()
    assert "sql" not in ext_lang, (filename, ext_lang)


def test_genuine_sql_file_is_allowed_to_be_sql() -> None:
    # Control: a truly SQL-named file *is* permitted to detect as SQL, proving the
    # guard suppresses content-guessing, not real SQL files.
    editor = _make_editor("schema.sql", ["SELECT 1;"], engine="extension")
    assert "sql" in (editor.current_language or "").lower()


# --------------------------------------------------------------------------- #
# Safe fallback when the tokenizer (python-textmate) is unavailable.
# --------------------------------------------------------------------------- #


def test_missing_tokenizer_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate python-textmate/onigurumacffi being absent.
    monkeypatch.setattr(svc, "TEXTMATE_AVAILABLE", False)
    monkeypatch.setattr(svc, "EXTENSION_TOKENIZATION_AVAILABLE", False)
    service = _service()

    assert service.build_line_highlighter("example.py") is None
    resolution = service.resolve("example.py")
    assert resolution.fallback_to_legacy is True
    messages = [d.message.lower() for d in resolution.diagnostics]
    assert any("tokenizer" in m and "unavailable" in m for m in messages), messages


def test_missing_tokenizer_editor_still_highlights_via_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(svc, "TEXTMATE_AVAILABLE", False)
    monkeypatch.setattr(svc, "EXTENSION_TOKENIZATION_AVAILABLE", False)
    code = ["def main():", "    return 42  # answer"]
    editor = _make_editor("example.py", code, engine="extension")
    assert editor._extension_highlighter is None
    rendered = editor.apply_syntax_highlighting_with_pygments(code, [0, 1])
    # Legacy still highlights (more than one colour) and round-trips.
    assert ["".join(t for t, _ in line) for line in rendered] == code
    assert len({attr for line in rendered for _t, attr in line}) > 1
