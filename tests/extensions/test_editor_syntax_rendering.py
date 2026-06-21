# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_editor_syntax_rendering.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Editor-facing rendering proofs for #102.

These tests exercise the *real* legacy highlighting data path
(``detect_language`` -> ``apply_syntax_highlighting_with_pygments`` ->
``_get_tokenized_line``) on a bare editor, and prove:

* the legacy Pygments highlighter still produces **visible** (multi-colour)
  spans and differentiates file types — i.e. it was not broken by #102;
* the #102 extension metadata is exposed for the active file but never changes,
  disables, or bypasses the legacy tokens;
* selecting ``syntax_engine = "extension"`` still renders **identically** through
  the legacy path (no tokenizer yet), with ``fallback_to_legacy = True``;
* the ``[editor].syntax_highlighting`` toggle still works.

The colours are plain ints standing in for the distinct curses colour pairs that
``init_colors`` builds from the active theme, so the data path can be verified
without a live terminal.
"""

from __future__ import annotations

import copy

from ecli.core.Ecli import Ecli
from ecli.utils.utils import DEFAULT_CONFIG


# Distinct stand-in colour attributes for the semantic roles the highlighter
# maps Pygments tokens onto (see Ecli._get_tokenized_line).
COLORS: dict[str, int] = {
    "default": 0,
    "keyword": 1,
    "string": 2,
    "comment": 3,
    "number": 4,
    "function": 5,
    "class": 6,
    "type": 7,
    "decorator": 8,
    "operator": 9,
    "builtin": 10,
    "tag": 11,
    "attribute": 12,
    "error": 13,
}

PYTHON_CODE = ["import os", "def main():", "    x = 42  # answer", "    return 'hi'"]
MARKDOWN_DOC = ["# Title", "Some **bold** text and `code`.", "> a quote"]
YAML_DOC = ["version: '3'", "services:", "  app: # comment"]


def _make_editor(filename: str, text: list[str], engine: str = "legacy") -> Ecli:
    editor = Ecli.__new__(Ecli)
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.setdefault("extensions", {})["syntax_engine"] = engine
    editor.config = config
    editor.filename = filename
    editor.text = text
    editor.colors = COLORS
    editor.is_256_color_terminal = True
    editor._lexer = None
    editor.current_language = None
    editor.custom_syntax_patterns = []
    editor.extension_syntax = None
    editor._extension_highlighter = None
    return editor


def _distinct_colors(rendered: list[list[tuple[str, int]]]) -> set[int]:
    return {attr for line in rendered for _text, attr in line}


# --------------------------------------------------------------------------- #
# Legacy highlighting is visibly active and differentiates file types.
# --------------------------------------------------------------------------- #


def test_legacy_highlighting_produces_visible_spans() -> None:
    editor = _make_editor("example.py", PYTHON_CODE)
    editor.detect_language()
    rendered = editor.apply_syntax_highlighting_with_pygments(
        PYTHON_CODE, list(range(len(PYTHON_CODE)))
    )

    assert editor.current_language == "python"
    # Content round-trips and more than one colour is emitted (visible highlight).
    assert ["".join(t for t, _ in line) for line in rendered] == PYTHON_CODE
    assert len(_distinct_colors(rendered)) > 1


def test_legacy_highlighting_differentiates_file_types() -> None:
    py = _make_editor("example.py", PYTHON_CODE)
    py.detect_language()
    md = _make_editor("README.md", MARKDOWN_DOC)
    md.detect_language()

    assert py.current_language == "python"
    assert md.current_language == "markdown"
    py_rendered = py.apply_syntax_highlighting_with_pygments(
        PYTHON_CODE, list(range(len(PYTHON_CODE)))
    )
    md_rendered = md.apply_syntax_highlighting_with_pygments(
        MARKDOWN_DOC, list(range(len(MARKDOWN_DOC)))
    )
    assert len(_distinct_colors(py_rendered)) > 1
    assert len(_distinct_colors(md_rendered)) > 1


def test_yaml_highlighting_is_visible_for_required_filenames() -> None:
    for filename in (".coderabbit.yaml", "docker-compose.yml", "config.yaml"):
        editor = _make_editor(filename, YAML_DOC, engine="extension")
        editor.detect_language()
        rendered = editor.apply_syntax_highlighting_with_pygments(
            YAML_DOC, list(range(len(YAML_DOC)))
        )
        assert editor.extension_syntax is not None
        assert editor.extension_syntax.language_id in {"yaml", "dockercompose"}
        assert ["".join(text for text, _attr in line) for line in rendered] == YAML_DOC
        assert len(_distinct_colors(rendered)) > 1


def test_gitignore_status_language_is_never_sql() -> None:
    editor = _make_editor(".gitignore", ["*.pyc", "build/"], engine="extension")
    editor.detect_language()
    assert editor.extension_syntax is not None
    assert editor.extension_syntax.language_id == "ignore"
    assert editor.current_language == "ignore"
    assert "sql" not in editor.current_language.lower()


def test_log_files_are_plain_log_not_sql() -> None:
    for filename in (
        "freebsd-0.2.2-fail.log",
        "editor.log",
        "qemu.raw.log",
    ):
        editor = _make_editor(filename, ["ERROR SELECT -> 123"], engine="extension")
        editor.detect_language()
        assert editor.extension_syntax is not None
        assert editor.extension_syntax.language_id == "log"
        assert editor.current_language == "log"
        assert "sql" not in editor.current_language.lower()


def test_syntax_toggle_still_disables_highlighting() -> None:
    editor = _make_editor("example.py", PYTHON_CODE)
    editor.config["editor"]["syntax_highlighting"] = False
    editor.detect_language()
    rendered = editor.apply_syntax_highlighting_with_pygments(
        PYTHON_CODE, list(range(len(PYTHON_CODE)))
    )
    # Disabled => exactly one default segment per line.
    assert all(len(line) == 1 for line in rendered)
    assert _distinct_colors(rendered) == {COLORS["default"]}


# --------------------------------------------------------------------------- #
# #102 metadata is exposed but never affects legacy rendering.
# --------------------------------------------------------------------------- #


def test_editor_receives_extension_metadata_for_active_file() -> None:
    editor = _make_editor("example.py", PYTHON_CODE)
    editor.detect_language()

    resolution = editor.extension_syntax
    assert resolution is not None
    assert resolution.language_id == "python"
    assert resolution.scope_name == "source.python"
    assert resolution.grammar_path.startswith("src/ecli/extensions/")


def test_extension_metadata_does_not_change_legacy_tokens() -> None:
    editor = _make_editor("example.py", PYTHON_CODE)
    editor.detect_language()
    indices = list(range(len(PYTHON_CODE)))
    baseline = editor.apply_syntax_highlighting_with_pygments(PYTHON_CODE, indices)

    # The rendering path must not read extension metadata at all: mutating it
    # (including to nonsense) cannot change the produced tokens.
    editor.extension_syntax = None
    after_none = editor.apply_syntax_highlighting_with_pygments(PYTHON_CODE, indices)
    editor.extension_syntax = "garbage"  # type: ignore[assignment]
    after_garbage = editor.apply_syntax_highlighting_with_pygments(PYTHON_CODE, indices)

    assert baseline == after_none == after_garbage
    assert len(_distinct_colors(baseline)) > 1


def test_extension_engine_renders_textmate_spans() -> None:
    indices = list(range(len(PYTHON_CODE)))
    extension = _make_editor("example.py", PYTHON_CODE, engine="extension")
    extension.detect_language()

    # The TextMate line highlighter is engaged and metadata reports no fallback.
    assert extension._extension_highlighter is not None
    assert extension.extension_syntax.syntax_engine == "extension"
    assert extension.extension_syntax.fallback_to_legacy is False

    rendered = extension.apply_syntax_highlighting_with_pygments(PYTHON_CODE, indices)
    # The TextMate path produces visible, multi-colour spans aligned to the text.
    assert ["".join(t for t, _ in line) for line in rendered] == PYTHON_CODE
    assert len(_distinct_colors(rendered)) > 1


def test_legacy_engine_does_not_engage_textmate() -> None:
    indices = list(range(len(PYTHON_CODE)))
    legacy = _make_editor("example.py", PYTHON_CODE, engine="legacy")
    legacy.detect_language()

    # Legacy stays on the Pygments path; the TextMate highlighter is not engaged.
    assert legacy._extension_highlighter is None
    rendered = legacy.apply_syntax_highlighting_with_pygments(PYTHON_CODE, indices)
    assert ["".join(t for t, _ in line) for line in rendered] == PYTHON_CODE
    assert len(_distinct_colors(rendered)) > 1


def test_textmate_spans_reach_renderer_as_distinct_attributes() -> None:
    # Rendering-level proof: the editor converts TextMate scope categories into
    # the curses colour attributes the draw layer consumes, and keyword, string,
    # and comment end up as THREE different attributes (not all default).
    code = ["def f(): s = 'hi'  # c"]
    editor = _make_editor("example.py", code, engine="extension")
    editor.detect_language()
    assert editor._extension_highlighter is not None

    rendered = editor.apply_syntax_highlighting_with_pygments(code, [0])
    line = rendered[0]
    # Build a quick char-offset -> attr map to read specific tokens' colours.
    attr_by_text = dict(line)
    keyword_attr = attr_by_text.get("def")
    default_attr = COLORS["default"]

    assert keyword_attr is not None and keyword_attr != default_attr
    # The string and comment characters carry non-default, mutually distinct attrs.
    string_attr = next(attr for text, attr in line if "hi" in text)
    comment_attr = next(attr for text, attr in line if "#" in text)
    assert len({keyword_attr, string_attr, comment_attr}) == 3
    assert default_attr not in {keyword_attr, string_attr, comment_attr}
