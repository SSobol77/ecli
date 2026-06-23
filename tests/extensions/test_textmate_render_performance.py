# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_render_performance.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Viewport-first rendering performance proofs on **real** repository files (#102).

These are not mock tests. They drive the editor's actual render data path
(``detect_language`` -> ``apply_syntax_highlighting_with_pygments`` ->
``_apply_extension_highlighting``) over real, large, dirty repository artifacts —
the ``Makefile`` (which previously froze ECLI at line ~42), the large FreeBSD
failure log, a real PR-body Markdown file, and a real packaging script — and
assert:

* every viewport repaint is bounded (the #102 freeze is gone);
* scrolling never re-tokenizes the whole file (the per-frame string guard is
  computed once per buffer revision, reused across scroll frames);
* repeated scroll over the same region is cheap (cached) and the per-line cache
  cannot grow without bound;
* the grammar catalog, language detector, theme registry, and per-grammar
  tokenizer are each built once and reused.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.ecli_integration import textmate_tokenizer as tokenizer_module
from ecli.extensions.ecli_integration.config import ExtensionLayerConfig
from ecli.extensions.ecli_integration.syntax_service import (
    _SPAN_CACHE_MAX,
    LineHighlighter,
    build_syntax_service,
)
from ecli.utils.utils import DEFAULT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[2]

# A repaint budget per viewport frame. The pre-fix bug was an unbounded freeze;
# this generous bound proves termination/responsiveness without being flaky on
# slow CI. The worst real one-time make repaint is ~250ms (the per-line budget).
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


def _read_repo_lines(relative: str) -> list[str]:
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"required real artifact missing: {relative}")
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _scroll_and_time(
    editor: Ecli, text: list[str], viewport: int = 40, step: int = 13
) -> tuple[float, list[float]]:
    """Render sliding viewports across the whole file; return (worst, all frames)."""
    frame_times: list[float] = []
    for top in range(0, max(1, len(text)), step):
        lines = text[top : top + viewport]
        indices = list(range(top, top + len(lines)))
        start = time.perf_counter()
        rendered = editor.apply_syntax_highlighting_with_pygments(lines, indices)
        frame_times.append(time.perf_counter() - start)
        # Every visible line round-trips exactly (no dropped/duplicated text).
        assert ["".join(t for t, _ in line) for line in rendered] == lines
    return (max(frame_times) if frame_times else 0.0), frame_times


@pytest.fixture(autouse=True)
def _fresh_quarantine_state() -> None:
    tokenizer_module.reset_quarantine_state()


# --------------------------------------------------------------------------- #
# Real large-file rendering is bounded (the freeze is gone).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "relative",
    [
        "Makefile",
        "logs/freebsd-0.2.2-fail.log",
        "logs/pr-46-body.md",
        "scripts/build_pyinstaller_linux.py",
    ],
)
def test_real_file_scroll_is_bounded(relative: str) -> None:
    text = _read_repo_lines(relative)
    editor = _make_editor(relative, text)
    worst, frames = _scroll_and_time(editor, text)
    assert worst < FRAME_BUDGET_SECONDS, (
        f"{relative}: slowest viewport repaint {worst * 1000:.0f}ms exceeded "
        f"{FRAME_BUDGET_SECONDS * 1000:.0f}ms budget"
    )
    assert frames, f"{relative}: no frames rendered"


def test_makefile_does_not_freeze_around_line_42() -> None:
    # The exact reported symptom: scrolling the repo Makefile to the ifeq block
    # near line 42 used to hang ECLI forever. Render that window directly.
    text = _read_repo_lines("Makefile")
    editor = _make_editor("Makefile", text)
    window = text[30:80]
    start = time.perf_counter()
    rendered = editor.apply_syntax_highlighting_with_pygments(
        window, list(range(30, 30 + len(window)))
    )
    elapsed = time.perf_counter() - start
    assert elapsed < FRAME_BUDGET_SECONDS, f"line-42 window took {elapsed:.2f}s"
    assert ["".join(t for t, _ in line) for line in rendered] == window


# --------------------------------------------------------------------------- #
# No full-file retokenization during scroll.
# --------------------------------------------------------------------------- #


def test_no_full_file_retokenization_during_scroll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _read_repo_lines("scripts/build_pyinstaller_linux.py")
    editor = _make_editor("scripts/build_pyinstaller_linux.py", text)
    assert editor._extension_highlighter is not None
    assert editor.current_language == "python"

    calls = {"n": 0}
    import ecli.extensions.ecli_integration.syntax_service as svc

    real = svc._python_string_ranges

    def _counting(lines: list[str]):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real(lines)

    monkeypatch.setattr(svc, "_python_string_ranges", _counting)

    # Many scroll frames, no edits => the whole-file Python string guard must be
    # computed at most once (cached by buffer revision), never per frame.
    for top in range(0, len(text), 7):
        lines = text[top : top + 40]
        editor.apply_syntax_highlighting_with_pygments(
            lines, list(range(top, top + len(lines)))
        )
    assert calls["n"] <= 1, f"string guard recomputed {calls['n']}x during scroll"

    # An edit bumps the revision and recomputes exactly once more.
    editor.modified = True
    top = 10
    editor.apply_syntax_highlighting_with_pygments(
        text[top : top + 40], list(range(top, top + 40))
    )
    assert calls["n"] == 2


# --------------------------------------------------------------------------- #
# Repeated scroll is cheap (cache) and the cache is bounded.
# --------------------------------------------------------------------------- #


def test_repeated_scroll_is_cached_and_fast() -> None:
    text = _read_repo_lines("scripts/build_pyinstaller_linux.py")
    editor = _make_editor("scripts/build_pyinstaller_linux.py", text)
    window = text[:40]
    indices = list(range(40))

    first = time.perf_counter()
    editor.apply_syntax_highlighting_with_pygments(window, indices)
    first_elapsed = time.perf_counter() - first

    repeats = []
    for _ in range(5):
        start = time.perf_counter()
        editor.apply_syntax_highlighting_with_pygments(window, indices)
        repeats.append(time.perf_counter() - start)
    # Cached repaints of the same viewport are no slower than the first render.
    assert max(repeats) <= first_elapsed + 0.05


def test_span_cache_is_bounded() -> None:
    service = build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )
    highlighter = service.build_line_highlighter("example.py")
    assert isinstance(highlighter, LineHighlighter)
    # Feed many more distinct lines than the cache can hold; it must evict.
    for i in range(_SPAN_CACHE_MAX + 500):
        highlighter.highlight(f"x{i} = {i}")
    assert len(highlighter._cache) <= _SPAN_CACHE_MAX


# --------------------------------------------------------------------------- #
# Caches: build-once, reuse.
# --------------------------------------------------------------------------- #


def test_theme_registry_loaded_once() -> None:
    from ecli.extensions.ecli_integration.theme_registry import cached_theme_registry

    cached_theme_registry.cache_clear()
    first = cached_theme_registry()
    second = cached_theme_registry()
    assert first == second
    assert cached_theme_registry.cache_info().hits >= 1


def test_grammar_loaded_once_per_scope() -> None:
    from ecli.extensions.ecli_integration.textmate_tokenizer import load_tokenizer

    grammar = (
        REPO_ROOT
        / "src/ecli/extensions/lang/python/syntaxes/MagicPython.tmLanguage.json"
    ).resolve()
    first = load_tokenizer(grammar)
    second = load_tokenizer(grammar)
    assert first == second, "tokenizer must be cached per grammar path"


def test_catalog_and_detector_built_once() -> None:
    from ecli.extensions.ecli_integration.syntax_service import _cached_real_parts

    _cached_real_parts.cache_clear()
    first = _cached_real_parts()
    second = _cached_real_parts()
    assert first == second
    assert _cached_real_parts.cache_info().hits >= 1
