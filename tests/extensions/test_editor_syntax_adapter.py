# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_editor_syntax_adapter.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the narrow, read-only editor syntax adapter (#102).

The editor exposes extension-backed syntax metadata via
``Ecli._resolve_extension_syntax_metadata`` without changing the legacy
highlighter. These tests build a bare editor (the established
``Ecli.__new__`` pattern) and verify the adapter records metadata, fails safe,
and never disturbs the authoritative legacy highlighting path.
"""

from __future__ import annotations

from typing import Any

from pygments.lexers import PythonLexer

from ecli.core.Ecli import Ecli


def _make_editor(config: dict[str, Any], filename: str | None) -> Ecli:
    editor = Ecli.__new__(Ecli)
    editor.config = config
    editor.filename = filename
    editor.extension_syntax = None
    return editor


def test_adapter_records_metadata_for_known_file() -> None:
    editor = _make_editor({}, "example.py")
    editor._resolve_extension_syntax_metadata()

    resolution = editor.extension_syntax
    assert resolution is not None
    assert resolution.language_id == "python"
    assert resolution.scope_name == "source.python"
    assert resolution.used_extension_metadata is True
    # Legacy rendering stays authoritative.
    assert resolution.fallback_to_legacy is True


def test_adapter_falls_back_for_unknown_file() -> None:
    editor = _make_editor({}, "mystery.zzz")
    editor._resolve_extension_syntax_metadata()

    resolution = editor.extension_syntax
    assert resolution is not None
    assert resolution.language_id is None
    assert resolution.fallback_to_legacy is True


def test_adapter_disabled_extensions_layer_clears_metadata() -> None:
    editor = _make_editor({"extensions": {"enabled": False}}, "example.py")
    editor._resolve_extension_syntax_metadata()
    assert editor.extension_syntax is None


def test_adapter_never_raises_on_bad_config() -> None:
    editor = _make_editor({"extensions": "not-a-table"}, "example.py")
    # Must not raise; degrades to a safe resolution or None.
    editor._resolve_extension_syntax_metadata()


def test_adapter_does_not_disturb_legacy_highlighting() -> None:
    editor = _make_editor({}, "example.py")
    editor.text = ["def main():", "    return 42"]
    editor.colors = {"default": 0, "keyword": 7, "number": 3, "comment": 1}
    editor.is_256_color_terminal = True
    editor._lexer = PythonLexer()
    editor.current_language = "python"
    editor.custom_syntax_patterns = []

    editor._resolve_extension_syntax_metadata()
    code = ["def main():", "    x = 42  # answer"]
    result = editor.apply_syntax_highlighting_with_pygments(code, [0, 1])

    # Legacy highlighting is unaffected: content round-trips and tokens are split.
    assert ["".join(tok for tok, _ in line) for line in result] == code
    assert len(result[0]) > 1
    # Metadata is exposed alongside the unchanged legacy path.
    assert editor.extension_syntax is not None
    assert editor.extension_syntax.fallback_to_legacy is True
