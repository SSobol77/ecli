# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_scroll_regression.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Scroll performance regression gates on real repository files (#102).

These simulate the real interaction that froze ECLI — repeated PageDown/PageUp
over large files — through the editor's actual render data path, and assert:

* no viewport repaint hangs (bounded wall-clock per frame) on the ``Makefile``
  and the large ``logs/freebsd-0.2.2-fail.log``;
* repeated scrolling over the same regions never grows the per-line span cache
  without bound;
* opening files and rendering never triggers a repeated full extension-tree
  registry scan (the catalog/detector are scanned once and reused).
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.ecli_integration import (
    syntax_service as svc,
    textmate_tokenizer as tokenizer_module,
)
from ecli.extensions.ecli_integration.syntax_service import _SPAN_CACHE_MAX
from ecli.utils.utils import DEFAULT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWPORT = 40
FRAME_BUDGET_SECONDS = 2.0

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


def _read_lines(relative: str) -> list[str]:
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"required real artifact missing: {relative}")
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _render_viewport(editor: Ecli, text: list[str], top: int) -> float:
    top = max(0, min(top, max(0, len(text) - 1)))
    lines = text[top : top + VIEWPORT]
    indices = list(range(top, top + len(lines)))
    start = time.perf_counter()
    editor.apply_syntax_highlighting_with_pygments(lines, indices)
    return time.perf_counter() - start


def _page_tops(line_count: int) -> list[int]:
    """PageDown to the bottom, then PageUp back to the top."""
    downs = list(range(0, line_count, VIEWPORT))
    ups = list(reversed(downs))
    return downs + ups


@pytest.fixture(autouse=True)
def _fresh_quarantine_state() -> None:
    tokenizer_module.reset_quarantine_state()


@pytest.mark.parametrize("relative", ["Makefile", "logs/freebsd-0.2.2-fail.log"])
def test_pagedown_pageup_cycles_do_not_hang(relative: str) -> None:
    text = _read_lines(relative)
    editor = _make_editor(relative, text)
    worst = 0.0
    for _cycle in range(3):  # repeated PgDn/PgUp, the reported interaction
        for top in _page_tops(len(text)):
            worst = max(worst, _render_viewport(editor, text, top))
    assert worst < FRAME_BUDGET_SECONDS, (
        f"{relative}: slowest PgDn/PgUp repaint {worst * 1000:.0f}ms exceeded budget"
    )


def test_repeated_scroll_does_not_grow_cache_unbounded() -> None:
    text = _read_lines("scripts/build_pyinstaller_linux.py")
    editor = _make_editor("scripts/build_pyinstaller_linux.py", text)
    assert editor._extension_highlighter is not None
    highlighter = editor._extension_highlighter

    # First full PgDn/PgUp pass populates the cache.
    for top in _page_tops(len(text)):
        _render_viewport(editor, text, top)
    size_after_first = len(highlighter._cache)

    # Repeating the identical scroll must not grow the cache further (same lines).
    for _ in range(5):
        for top in _page_tops(len(text)):
            _render_viewport(editor, text, top)
    assert len(highlighter._cache) == size_after_first
    assert len(highlighter._cache) <= _SPAN_CACHE_MAX


def test_scrolling_does_not_rescan_extension_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The full extension-tree scan must happen at most once, regardless of how
    # many files are opened or how much they are scrolled.
    svc._cached_real_parts.cache_clear()
    calls = {"n": 0}
    real_build_registry = svc.build_registry

    def _counting(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real_build_registry(*args, **kwargs)

    monkeypatch.setattr(svc, "build_registry", _counting)

    for name, text in (
        ("a.py", ["import os", "def f():", "    return 1"]),
        ("b.py", ["x = 1"]),
        ("Makefile", ["all:", "\techo hi"]),
        ("c.py", ["y = 2"]),
    ):
        editor = _make_editor(name, text)
        for top in _page_tops(len(text)):
            _render_viewport(editor, text, top)

    assert calls["n"] <= 1, f"extension registry scanned {calls['n']}x (expected once)"
