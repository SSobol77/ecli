# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/textmate_tokenizer.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Real, time-bounded TextMate tokenization over imported grammars (#102).

This wraps the third-party ``python-textmate`` engine (which uses Oniguruma via
``onigurumacffi``) to tokenize a single line of text into ``(scope, start, end)``
records using the **actual** imported TextMate grammars under
``src/ecli/extensions/``. It produces genuine TextMate scope names — not a
regex approximation.

Hard safety contract for the UI hot path (issue #102 freeze):

* **Bounded tokenization.** Every ``parse`` call runs under a deterministic
  wall-clock budget. Some imported grammars (notably ``make``) drive this
  per-line engine into catastrophic Oniguruma backtracking that never returns
  (for example on ``ifeq ($(VAR),x)``). A plain ``try/except`` cannot catch a
  non-terminating native loop, so we additionally arm a wall-clock alarm and
  treat budget overruns as a failure that degrades that line to the legacy
  highlighter. The caller negatively caches the result, so each distinct slow
  line is paid at most once — never repeatedly per frame.
* **Adaptive grammar quarantine.** Quarantine is driven by *real* per-line
  timeouts, never by synthetic probes: a synthetic adversarial line (such as a
  make ``ifeq``) is not valid input for, say, C, so probing would wrongly disable
  perfectly good grammars. Instead, once a grammar exceeds the budget on enough
  distinct real lines in a session it is disabled wholesale so scrolling a file
  it cannot handle never accumulates repeated hitches.
* **Bounded diagnostics.** Slow/failed/quarantined grammars are reported at most
  once per key, never per line and never per frame.

It executes no extension code, runs no ``activationEvents`` or ``package.json``
scripts, starts no Node runtime, and suppresses all engine stdout/stderr so it
can never corrupt the curses UI.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import signal
import threading
from collections.abc import Callable, Iterator
from functools import lru_cache
from pathlib import Path
from typing import TypeVar


logger = logging.getLogger(__name__)

# Token record: (scope_name, start_column, end_column) for a single line.
TextMateToken = tuple[str, int, int]

_T = TypeVar("_T")


def _budget_seconds(env_name: str, default_ms: int) -> float:
    """Read a millisecond budget from the environment, clamped to a sane range."""
    raw = os.environ.get(env_name)
    if raw is None:
        return default_ms / 1000.0
    try:
        value_ms = int(raw)
    except ValueError:
        return default_ms / 1000.0
    # Clamp to [1ms, 30s] so a misconfigured value can never disable the bound
    # or stall the UI for an unbounded time.
    value_ms = max(1, min(value_ms, 30_000))
    return value_ms / 1000.0


# Per-line budget on the render hot path. Must comfortably exceed the cost of a
# legitimately slow-but-valid line (real Python ``def`` lines measured ~80ms via
# the engine) while still bounding pathological backtracking (seconds).
_LINE_BUDGET_SECONDS = _budget_seconds("ECLI_TM_LINE_BUDGET_MS", 250)

# Cold-start warm-up budget. The engine compiles its Oniguruma patterns *lazily*
# on the first ``parse`` call; for large grammars (notably TypeScript) that
# first-use compilation can far exceed the per-line budget. Paying it on the
# first rendered line would wrongly mark that line as "slow" and degrade it to
# the legacy highlighter. Instead we pay it once at load time, under this
# separate, generous budget, so the per-line budget only ever measures
# steady-state tokenization. It is still bounded so a pathological grammar can
# never hang grammar loading.
_WARMUP_BUDGET_SECONDS = _budget_seconds("ECLI_TM_WARMUP_BUDGET_MS", 5000)

# Benign, non-pathological lines used to force first-use pattern compilation at
# load time. A block-comment line compiles the (very common) comment machinery
# plus, by attempting every root alternative at column 0, the bulk of the root
# patterns; a plain identifier line covers grammars without C-style comments.
# These are deliberately innocuous so they never trigger the catastrophic
# backtracking that some grammars (e.g. ``make`` on ``ifeq``) exhibit.
_WARMUP_LINES: tuple[str, ...] = ("/* ecli */", "ecli")

# After a grammar exceeds the budget on this many *distinct* real lines in a
# session, it is quarantined (disabled wholesale) so scrolling a file it cannot
# handle never accumulates more than a bounded number of one-time hitches. A
# well-behaved grammar with a single odd line never reaches the threshold and
# keeps highlighting everything else.
_GRAMMAR_QUARANTINE_THRESHOLD = max(
    1, int(os.environ.get("ECLI_TM_QUARANTINE_THRESHOLD", "8") or "8")
)

_HAS_WALL_CLOCK_ALARM = hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM")

# Bounded one-time diagnostics. We never log per line or per frame.
_WARNED_KEYS: set[str] = set()
_MAX_WARNINGS = 64

# Runtime adaptive quarantine state (keyed by grammar id == grammar path).
_GRAMMAR_TIMEOUT_LINES: dict[str, set[str]] = {}
_QUARANTINED_GRAMMARS: set[str] = set()


def is_grammar_quarantined(grammar_id: str) -> bool:
    """Return ``True`` if ``grammar_id`` was disabled after repeated timeouts."""
    return grammar_id in _QUARANTINED_GRAMMARS


def reset_quarantine_state() -> None:
    """Clear adaptive quarantine state. Intended for tests only."""
    _GRAMMAR_TIMEOUT_LINES.clear()
    _QUARANTINED_GRAMMARS.clear()
    _WARNED_KEYS.clear()


def _warn_once(key: str, message: str, *args: object) -> None:
    """Emit a single bounded diagnostic per ``key`` (never per line/frame)."""
    if key in _WARNED_KEYS or len(_WARNED_KEYS) >= _MAX_WARNINGS:
        return
    _WARNED_KEYS.add(key)
    logger.warning(message, *args)


class _TokenizeBudgetExceededError(Exception):
    """Raised when a tokenization call exceeds its wall-clock budget."""


def _load_engine() -> object | None:
    """Import the optional ``python-textmate`` engine, or ``None`` if absent."""
    try:
        import textmate  # noqa: PLC0415
    except Exception:  # pragma: no cover - exercised only without the optional dep
        return None
    engine: object = textmate
    return engine


_ENGINE = _load_engine()
TEXTMATE_AVAILABLE = _ENGINE is not None


@contextlib.contextmanager
def _silenced() -> Iterator[None]:
    """Suppress stdout/stderr so the engine can never corrupt the curses UI."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


def _can_arm_alarm() -> bool:
    """Return ``True`` if a SIGALRM wall-clock budget can be armed right now.

    ``signal.setitimer``/SIGALRM only work on the main thread of the process. The
    curses render loop runs on the main thread, so this is the common case; off
    the main thread (or on platforms without ``setitimer``) we skip the alarm and
    rely on the load-time grammar quarantine plus negative caching.
    """
    return (
        _HAS_WALL_CLOCK_ALARM and threading.current_thread() is threading.main_thread()
    )


def _call_with_budget(fn: Callable[[], _T], seconds: float) -> _T:
    """Run ``fn`` under a wall-clock budget, raising on overrun.

    Uses a SIGALRM interval timer (proven to interrupt the Oniguruma engine) and
    restores any previously installed handler. When no alarm can be armed the
    call runs unbounded (best effort) and relies on the grammar quarantine.
    """
    if not _can_arm_alarm():
        return fn()

    def _on_alarm(_signum: int, _frame: object) -> None:
        raise _TokenizeBudgetExceededError()

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class TextMateTokenizer:
    """Line-oriented, time-bounded TextMate tokenizer for one grammar.

    The underlying engine tokenizes each line independently (stateless), which
    fits ECLI's per-line render path and is cached by line content. Multi-line
    constructs are therefore scoped per line, which is an accepted limitation of
    this engine until a stateful tokenizer is available.
    """

    def __init__(self, grammar: object, grammar_id: str = "") -> None:
        """Wrap a compiled engine grammar object for per-line tokenization."""
        self._grammar = grammar
        self._grammar_id = grammar_id
        # Set once the cold-start pattern compilation has been amortized (see
        # ``warm_up``). Construction itself never warms, so directly-constructed
        # tokenizers (tests, fakes) stay cheap and side-effect free.
        self.warmed = False

    def warm_up(self) -> None:
        """Amortize first-use pattern compilation off the per-line hot path.

        Runs a couple of benign representative parses under the dedicated
        warm-up budget so the engine compiles its lazily-built Oniguruma
        patterns now, at load time, instead of on the first rendered line. This
        keeps cold-start work out of the per-line budget so a normal first line
        (e.g. inside a multiline comment) is never wrongly degraded to the
        legacy highlighter.

        Warm-up is best effort: any failure or warm-up-budget overrun is
        swallowed and is **never** recorded as a per-line timeout or counted
        toward grammar quarantine. The tokenizer is always usable afterward;
        genuinely slow steady-state lines are still bounded by
        :meth:`tokenize_line`.
        """
        for line in _WARMUP_LINES:
            if not self._warmup_parse(line):
                break
        self.warmed = True

    def _warmup_parse(self, line: str) -> bool:
        """Parse one warm-up ``line`` under the warm-up budget; never raise.

        Returns ``False`` if the parse hit the warm-up budget (cold start is
        itself pathological), so the caller stops warming and lets the per-line
        path bound real input; ``True`` otherwise.
        """
        try:
            with _silenced():
                _call_with_budget(
                    lambda: self._grammar.parse(line),  # type: ignore[attr-defined]
                    _WARMUP_BUDGET_SECONDS,
                )
        except _TokenizeBudgetExceededError:
            return False
        except Exception:
            # The engine cannot handle this grammar/line; tokenize_line will
            # return None per line. Warm-up stays silent and non-fatal.
            return True
        return True

    def tokenize_line(self, line: str) -> list[TextMateToken] | None:
        """Return ``(scope, start, end)`` records for ``line``, or ``None``.

        Returns ``None`` (caller falls back to legacy for this line) when the
        grammar is quarantined, the engine raises, **or** tokenization exceeds the
        per-line wall-clock budget. A non-terminating native loop is not an
        exception, so the budget is the only thing that can stop it; the caller
        negatively caches the ``None`` so the budget is paid at most once per
        distinct line.
        """
        if self._grammar_id in _QUARANTINED_GRAMMARS:
            return None
        try:
            with _silenced():
                raw = _call_with_budget(
                    lambda: self._grammar.parse(line),  # type: ignore[attr-defined]
                    _LINE_BUDGET_SECONDS,
                )
        except _TokenizeBudgetExceededError:
            self._record_timeout(line)
            return None
        except Exception:
            # Includes RecursionError on grammars the engine cannot handle.
            return None
        tokens: list[TextMateToken] = []
        for entry in raw:
            try:
                scope, (start, end) = entry
            except (ValueError, TypeError):
                continue
            if (
                isinstance(scope, str)
                and isinstance(start, int)
                and isinstance(end, int)
            ):
                tokens.append((scope, start, end))
        return tokens

    def _record_timeout(self, line: str) -> None:
        """Record a real per-line timeout and quarantine the grammar if persistent."""
        grammar_id = self._grammar_id or "<unknown>"
        if grammar_id in _QUARANTINED_GRAMMARS:
            return
        seen = _GRAMMAR_TIMEOUT_LINES.setdefault(grammar_id, set())
        seen.add(line)
        if len(seen) >= _GRAMMAR_QUARANTINE_THRESHOLD:
            _QUARANTINED_GRAMMARS.add(grammar_id)
            _warn_once(
                f"quarantine:{grammar_id}",
                "TextMate grammar %s quarantined after %d slow lines (catastrophic "
                "backtracking in the per-line engine); using the legacy highlighter",
                grammar_id,
                len(seen),
            )
        else:
            _warn_once(
                f"line-budget:{grammar_id}",
                "TextMate tokenization exceeded %.0fms budget for grammar %s; "
                "falling back to legacy highlighting for slow lines",
                _LINE_BUDGET_SECONDS * 1000,
                grammar_id,
            )


@lru_cache(maxsize=64)
def load_tokenizer(grammar_path: Path) -> TextMateTokenizer | None:
    """Build a :class:`TextMateTokenizer` for a ``.tmLanguage.json`` file.

    Returns ``None`` when the engine is unavailable or the grammar cannot be
    loaded/compiled (so the caller falls back to the legacy highlighter). Results
    are cached per grammar path, so the scan/compile cost is paid once per grammar
    process-wide and never on the render hot path. The returned tokenizer is
    **warmed** here (see :meth:`TextMateTokenizer.warm_up`) so first-use Oniguruma
    pattern compilation is amortized at load time, outside the per-line budget,
    rather than being charged to the first rendered line. Runtime quarantine
    (after repeated real-line timeouts) is enforced in
    :meth:`TextMateTokenizer.tokenize_line` and re-checked by the caller via
    :func:`is_grammar_quarantined`.
    """
    if _ENGINE is None:
        return None
    grammar_id = str(grammar_path)
    try:
        grammar_dict = json.loads(Path(grammar_path).read_text(encoding="utf-8"))
        with _silenced():
            repository = _ENGINE.TextMateGrammarRepository([grammar_dict])  # type: ignore[attr-defined]
            grammar = _ENGINE.TextMateGrammar(grammar_dict, repository)  # type: ignore[attr-defined]
    except Exception as error:
        # Includes RecursionError on grammars the engine cannot compile.
        logger.debug("TextMate grammar load failed for %s: %s", grammar_path, error)
        return None
    tokenizer = TextMateTokenizer(grammar, grammar_id=grammar_id)
    # Pay first-use pattern compilation here, once per grammar (this function is
    # cached), so it is never charged to the first rendered line's per-line
    # budget. This is the fix for cold-start lines (e.g. TypeScript multiline
    # comments) being wrongly degraded to the legacy highlighter.
    tokenizer.warm_up()
    return tokenizer
