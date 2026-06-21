# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_tokenizer_budget.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Bounded-tokenization / freeze regression for the TextMate engine (#102).

The imported ``make`` grammar drives the per-line Oniguruma engine into
catastrophic, non-terminating backtracking on lines such as
``ifeq ($(ARCH),x86_64)`` — the exact cause of the reported UI freeze. These
tests use the **real** grammars (no mocks) and a hard wall-clock bound to prove:

* tokenizing any line of the real repository ``Makefile`` terminates within a
  per-line budget (it used to run forever);
* the specific ``ifeq ($(...))`` line returns within budget (legacy fallback is
  acceptable; hanging is not);
* a grammar that keeps timing out is quarantined after a bounded number of
  distinct slow lines, after which the editor uses the legacy highlighter.
"""

from __future__ import annotations

import signal
import time
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import textmate_tokenizer as tok
from ecli.extensions.ecli_integration.config import ExtensionLayerConfig
from ecli.extensions.ecli_integration.syntax_service import build_syntax_service


pytestmark = pytest.mark.skipif(
    not tok.TEXTMATE_AVAILABLE,
    reason="python-textmate tokenizer is not installed",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKE_GRAMMAR = REPO_ROOT / "src/ecli/extensions/make/syntaxes/make.tmLanguage.json"

# A hard ceiling, well above the in-engine per-line budget but far below the
# unbounded freeze. If a single tokenize_line call ever exceeds this, the freeze
# has regressed.
HARD_LINE_CEILING_SECONDS = 2.0


@pytest.fixture(autouse=True)
def _fresh_state() -> None:
    tok.reset_quarantine_state()


def _alarm_guard(seconds: float):
    """A SIGALRM watchdog that converts a true hang into a test failure."""

    class _Guard:
        def __enter__(self) -> None:
            def _fire(_s: int, _f: object) -> None:
                raise AssertionError(
                    f"tokenization did not terminate within {seconds}s (freeze)"
                )

            self._prev = signal.signal(signal.SIGALRM, _fire)
            signal.setitimer(signal.ITIMER_REAL, seconds)

        def __exit__(self, *_exc: object) -> None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self._prev)

    return _Guard()


@pytest.fixture(scope="module")
def make_highlighter():
    service = build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )
    highlighter = service.build_line_highlighter("Makefile")
    assert highlighter is not None, "expected a TextMate highlighter for Makefile"
    return highlighter


def test_every_makefile_line_tokenizes_within_budget(make_highlighter) -> None:
    lines = (REPO_ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1000, "expected a large real Makefile"
    for number, line in enumerate(lines, start=1):
        start = time.perf_counter()
        make_highlighter.tokenizer.tokenize_line(line)
        elapsed = time.perf_counter() - start
        assert elapsed < HARD_LINE_CEILING_SECONDS, (
            f"Makefile line {number} took {elapsed:.2f}s "
            f"(>{HARD_LINE_CEILING_SECONDS}s): {line[:60]!r}"
        )


def test_ifeq_line_terminates(make_highlighter) -> None:
    # The exact catastrophic line. It must return within budget; None (legacy
    # fallback) is a fine result — a hang is not.
    with _alarm_guard(HARD_LINE_CEILING_SECONDS):
        result = make_highlighter.tokenizer.tokenize_line("ifeq ($(ARCH),x86_64)")
    # Either bounded tokens or a safe None fallback; never a freeze.
    assert result is None or isinstance(result, list)


def test_grammar_quarantined_after_repeated_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Lower the threshold so the two naturally-catastrophic make lines trip it.
    monkeypatch.setattr(tok, "_GRAMMAR_QUARANTINE_THRESHOLD", 2)
    service = build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )
    highlighter = service.build_line_highlighter("Makefile")
    assert highlighter is not None

    grammar_id = highlighter.tokenizer._grammar_id
    with _alarm_guard(HARD_LINE_CEILING_SECONDS * 3):
        highlighter.tokenizer.tokenize_line("ifeq ($(ARCH),x86_64)")
        highlighter.tokenizer.tokenize_line("ifeq ($(MACOS_ASSERT_MODE),native)")

    assert tok.is_grammar_quarantined(grammar_id)
    # Once quarantined, a freshly built highlighter for the same file is None,
    # so the editor renders the whole file with the legacy highlighter.
    assert service.build_line_highlighter("Makefile") is None


def test_quarantine_bookkeeping_is_deterministic() -> None:
    # Unit-level proof of the threshold logic, independent of engine timing.
    tokenizer = tok.TextMateTokenizer(grammar=object(), grammar_id="grammar://x")
    threshold = tok._GRAMMAR_QUARANTINE_THRESHOLD
    for i in range(threshold - 1):
        tokenizer._record_timeout(f"line-{i}")
        assert not tok.is_grammar_quarantined("grammar://x")
    tokenizer._record_timeout(f"line-{threshold}")
    assert tok.is_grammar_quarantined("grammar://x")
    # A quarantined grammar short-circuits to None without touching the engine.
    assert tokenizer.tokenize_line("anything") is None


def test_repeated_timeout_on_same_line_counts_once() -> None:
    tokenizer = tok.TextMateTokenizer(grammar=object(), grammar_id="grammar://y")
    for _ in range(tok._GRAMMAR_QUARANTINE_THRESHOLD + 5):
        tokenizer._record_timeout("the same slow line")
    # Distinct lines drive quarantine; the same line repeated must not.
    assert not tok.is_grammar_quarantined("grammar://y")


def test_wall_clock_budget_available_on_main_thread() -> None:
    # The render loop runs on the main thread, where SIGALRM can bound the engine.
    assert tok._can_arm_alarm() is True
