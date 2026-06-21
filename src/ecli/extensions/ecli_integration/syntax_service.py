# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/syntax_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Extension-backed syntax service boundary (#102).

This deterministic, data-only service bridges the #101 grammar catalog and
language detection to the editor. Given a file name and the ``[extensions]``
configuration, it resolves the language id, TextMate scope name, and grammar
path, selects the configured syntax engine, and reports whether rendering must
fall back to the legacy highlighter.

It is a deterministic adapter over data-only extension assets. When the optional
``python-textmate`` tokenizer is importable and a grammar can be loaded, the
service returns a line highlighter that produces TextMate scope-derived spans.
Missing tokenizer, missing grammars, and tokenizer failures always fall back to
the legacy regex/Pygments highlighter. The service never executes extension code,
never parses ``activationEvents`` as runtime instructions, never invokes
Node/npm, and starts no background workers.
"""

from __future__ import annotations

import io
import token
import tokenize
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import paths
from .config import ExtensionLayerConfig, SyntaxEngine
from .grammar_catalog import GrammarCatalog, TextMateGrammar, build_grammar_catalog
from .language_detection import (
    LanguageDetectionResult,
    LanguageDetector,
    build_language_detector,
)
from .manifest import RegistryDiagnostic
from .registry import build_registry
from .textmate_tokenizer import (
    TEXTMATE_AVAILABLE,
    TextMateTokenizer,
    is_grammar_quarantined,
    load_tokenizer,
)
from .theme_bridge import tokens_to_spans


SYNTAX_ENGINE_LEGACY = SyntaxEngine.LEGACY.value
SYNTAX_ENGINE_EXTENSION = SyntaxEngine.EXTENSION.value

# Real TextMate tokenization is available when the optional ``python-textmate``
# engine (Oniguruma-backed) is importable. When it is missing, the extension
# engine degrades to the legacy highlighter. Individual grammars the engine
# cannot compile (for example the imported Markdown/C grammars) also fall back
# per file via ``build_line_highlighter`` returning ``None``.
EXTENSION_TOKENIZATION_AVAILABLE = TEXTMATE_AVAILABLE

_SERVICE_SOURCE = "syntax_service"

_REQUIRED_MISSING_GRAMMAR_ASSETS: dict[str, str] = {
    "toml": "src/ecli/extensions/toml/syntaxes/toml.tmLanguage.json",
    "asm": "src/ecli/extensions/asm/syntaxes/asm.tmLanguage.json",
    "ada": "src/ecli/extensions/ada/syntaxes/ada.tmLanguage.json",
    "fortran": "src/ecli/extensions/fortran/syntaxes/fortran.tmLanguage.json",
}

# A line span carries the rendered text and its ECLI style category name.
LineSpan = tuple[str, str]

# Upper bound on the per-line span cache so scrolling a very large file can never
# grow it without limit. It comfortably covers many viewports of scrollback; once
# exceeded the least-recently-used line is evicted.
_SPAN_CACHE_MAX = 8192

# Protected-range map type: per buffer-line index -> immutable ranges.
_RangeMap = dict[int, tuple[tuple[int, int, str], ...]]


@dataclass(frozen=True)
class SyntaxResolution:
    """Immutable, deterministic result of resolving syntax data for a file."""

    filename: str | None
    language_id: str | None
    scope_name: str | None
    grammar_path: str | None
    syntax_engine: str
    used_extension_metadata: bool
    fallback_to_legacy: bool
    matched_by: str | None = None
    is_ambiguous: bool = False
    diagnostics: tuple[RegistryDiagnostic, ...] = ()

    @property
    def has_grammar(self) -> bool:
        """Return ``True`` if an extension grammar scope was resolved."""
        return self.scope_name is not None


@dataclass
class LineHighlighter:
    """Viewport-first, bounded-cache TextMate highlighter for one file's grammar.

    ``highlight`` returns ``(text, category)`` spans that tile the line exactly,
    where ``category`` is an ECLI style/colour name. It returns ``None`` only when
    the tokenizer fails (or times out) for that line, so the editor can fall back
    to legacy.

    Two deterministic caches keep scrolling cheap:

    * a bounded LRU of per-line spans keyed by line content (so identical lines —
      and repeated viewports — never re-tokenize, and the cache cannot grow
      without limit); a cached ``None`` is a negative cache so a slow/failed line
      is paid at most once;
    * a single protected-range map keyed by the editor's buffer revision, so
      deterministic multiline guards are computed once per edit and reused across
      every scroll frame instead of re-scanning comments/strings per frame.
    """

    tokenizer: TextMateTokenizer
    scope_name: str | None = None
    _cache: OrderedDict[
        tuple[str, tuple[tuple[int, int, str], ...]], tuple[LineSpan, ...] | None
    ] = field(
        default_factory=OrderedDict
    )
    _ranges_cache: tuple[object, _RangeMap] | None = field(default=None)

    def highlight(self, line: str) -> list[LineSpan] | None:
        """Return cached ``(text, category)`` spans for ``line`` or ``None``."""
        protected = tuple(_protected_ranges_for_scope(self.scope_name, [line]).get(0, ()))
        return self._highlight_line(line, protected)

    def highlight_lines(
        self,
        lines: list[str],
        line_indices: list[int] | None = None,
        full_text: list[str] | None = None,
        text_revision: object | None = None,
    ) -> list[list[LineSpan] | None]:
        """Highlight a viewport of ``lines``, preserving deterministic string guards.

        Only the supplied ``lines`` are tokenized (viewport-first). Multiline
        comment/string guards need buffer context; they are computed from
        ``full_text`` but cached against ``text_revision`` so they run once per
        edit, never per scroll. When ``text_revision`` is ``None`` the guard is
        recomputed (used by tests/single calls); the editor always supplies a
        revision.
        """
        protected_by_line: _RangeMap = {}
        if self._has_protected_ranges:
            source = full_text if full_text is not None else lines
            all_ranges = self._protected_ranges(source, text_revision)
            if full_text is not None and line_indices is not None:
                protected_by_line = {
                    offset: tuple(all_ranges.get(line_index, ()))
                    for offset, line_index in enumerate(line_indices)
                }
            else:
                protected_by_line = {
                    line_index: tuple(ranges)
                    for line_index, ranges in all_ranges.items()
                    if line_index < len(lines)
                }
        return [
            self._highlight_line(line, protected_by_line.get(index, ()))
            for index, line in enumerate(lines)
        ]

    @property
    def _has_protected_ranges(self) -> bool:
        return _scope_supports_protection(self.scope_name)

    def _protected_ranges(
        self, source: list[str], revision: object | None
    ) -> _RangeMap:
        """Return protected ranges, reusing them across frames per revision."""
        if (
            revision is not None
            and self._ranges_cache is not None
            and self._ranges_cache[0] == revision
        ):
            return self._ranges_cache[1]
        ranges = _protected_ranges_for_scope(self.scope_name, source)
        if revision is not None:
            self._ranges_cache = (revision, ranges)
        return ranges

    def _highlight_line(
        self, line: str, protected: tuple[tuple[int, int, str], ...]
    ) -> list[LineSpan] | None:
        cache_key = (line, protected)
        cache = self._cache
        if cache_key in cache:
            # A present key may map to ``None`` (negative cache for a slow/failed
            # line); ``in`` distinguishes that from an absent key.
            cache.move_to_end(cache_key)
            spans = cache[cache_key]
            return list(spans) if spans is not None else None
        tokens = self.tokenizer.tokenize_line(line)
        result: tuple[LineSpan, ...] | None
        if tokens is None:
            result = None
        else:
            result = tuple(tokens_to_spans(line, tokens, protected_ranges=protected))
        cache[cache_key] = result
        cache.move_to_end(cache_key)
        if len(cache) > _SPAN_CACHE_MAX:
            cache.popitem(last=False)
        return list(result) if result is not None else None


def _string_span_for_row(
    row: int,
    start: tuple[int, int],
    end: tuple[int, int],
    line: str,
) -> tuple[int, int]:
    """Return the protected ``(start, end)`` columns of a STRING token on ``row``."""
    start_row, start_col = start
    end_row, end_col = end
    if row == start_row - 1 and row == end_row - 1:
        return start_col, end_col
    if row == start_row - 1:
        # First row of a multi-line string. When everything before the opening
        # quotes is whitespace (a docstring's indentation), protect the indent too
        # so the whole docstring line renders as string. For ``x = """…`` the
        # ``x = `` prefix is real code and is left unprotected.
        protected_start = 0 if line[:start_col].strip() == "" else start_col
        return protected_start, len(line)
    if row == end_row - 1:
        return 0, end_col
    return 0, len(line)


def _python_string_ranges(
    lines: list[str],
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return per-line string/docstring ranges using Python's tokenizer."""
    if not lines:
        return {}
    ranges: dict[int, list[tuple[int, int, str]]] = {}
    try:
        stream = io.StringIO("\n".join(lines) + "\n")
        for tok in tokenize.generate_tokens(stream.readline):
            if tok.type != token.STRING:
                continue
            start_row, _ = tok.start
            end_row, _ = tok.end
            for row in range(start_row - 1, end_row):
                if not 0 <= row < len(lines):
                    continue
                start, end = _string_span_for_row(
                    row, tok.start, tok.end, lines[row]
                )
                ranges.setdefault(row, []).append((start, end, "string"))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return {}
    return {line: tuple(spans) for line, spans in ranges.items()}


def _scope_supports_protection(scope_name: str | None) -> bool:
    """Return whether ``scope_name`` has an ECLI deterministic guard."""
    return scope_name in {
        "source.python",
        "source.js",
        "source.ts",
        "source.css",
    } or scope_name in _HTML_SCOPES


_HTML_SCOPES = frozenset(
    {
        "text.html.basic",
        "text.html.derivative",
        "text.html.markdown",
    }
)


def _protected_ranges_for_scope(
    scope_name: str | None, lines: list[str]
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return language-aware protected comment/string ranges for ``lines``.

    TextMate tokenization remains the primary token source. These guards only
    repaint known multiline comments/strings over the TextMate output when the
    current line-oriented engine cannot preserve cross-line state.
    """
    if scope_name == "source.python":
        return _python_string_ranges(lines)
    if scope_name in {"source.js", "source.ts"}:
        return _javascript_like_protected_ranges(lines)
    if scope_name == "source.css":
        return _css_protected_ranges(lines)
    if scope_name in _HTML_SCOPES:
        return _html_comment_ranges(lines)
    return {}


def _append_range(
    ranges: dict[int, list[tuple[int, int, str]]],
    row: int,
    start: int,
    end: int,
    category: str,
) -> None:
    """Append a non-empty protected range clamped to a line."""
    if end > start:
        ranges.setdefault(row, []).append((start, end, category))


def _is_escaped(line: str, index: int) -> bool:
    """Return whether ``line[index]`` is escaped by an odd number of backslashes."""
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and line[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return bool(backslashes % 2)


def _scan_quoted_string(line: str, start: int, quote: str) -> tuple[int, bool]:
    """Return ``(end, closed)`` for a JS/CSS quoted string starting at ``start``."""
    index = start + 1
    while index < len(line):
        if line[index] == quote and not _is_escaped(line, index):
            return index + 1, True
        index += 1
    return len(line), False


@dataclass(frozen=True)
class _CLikeRules:
    block_comments: bool
    line_comments: bool
    quoted_strings: bool
    template_strings: bool


def _resume_c_like_state(
    line: str,
    row: int,
    state: tuple[str, str | None] | None,
    ranges: dict[int, list[tuple[int, int, str]]],
) -> tuple[int, tuple[str, str | None] | None, bool]:
    """Resume an open multiline C-like comment/string at the start of a line."""
    if state is None:
        return 0, None, False
    state_kind, delimiter = state
    if state_kind == "block_comment":
        close = line.find("*/")
        if close == -1:
            _append_range(ranges, row, 0, len(line), "comment")
            return 0, state, True
        end = close + 2
        _append_range(ranges, row, 0, end, "comment")
        return end, None, False
    if state_kind == "string" and delimiter is not None:
        end, closed = _scan_quoted_string(line, 0, delimiter)
        _append_range(ranges, row, 0, end, "string")
        return (end, None, False) if closed else (0, state, True)
    return 0, None, False


def _scan_block_comment_start(
    line: str,
    row: int,
    index: int,
    ranges: dict[int, list[tuple[int, int, str]]],
) -> tuple[int, tuple[str, str | None] | None]:
    """Protect a C-like block comment that starts at ``index``."""
    close = line.find("*/", index + 2)
    if close == -1:
        _append_range(ranges, row, index, len(line), "comment")
        return len(line), ("block_comment", None)
    end = close + 2
    _append_range(ranges, row, index, end, "comment")
    return end, None


def _scan_string_start(
    line: str,
    row: int,
    index: int,
    quote: str,
    ranges: dict[int, list[tuple[int, int, str]]],
) -> tuple[int, tuple[str, str | None] | None]:
    """Protect a quoted/template string that starts at ``index``."""
    end, closed = _scan_quoted_string(line, index, quote)
    _append_range(ranges, row, index, end, "string")
    return (end, None) if closed else (len(line), ("string", quote))


def _scan_line_comment_start(
    line: str,
    row: int,
    index: int,
    ranges: dict[int, list[tuple[int, int, str]]],
) -> int:
    """Protect a C-like line comment that starts at ``index``."""
    _append_range(ranges, row, index, len(line), "comment")
    return len(line)


def _scan_c_like_line(
    line: str,
    row: int,
    start: int,
    rules: _CLikeRules,
    ranges: dict[int, list[tuple[int, int, str]]],
) -> tuple[str, str | None] | None:
    """Scan one normal-state C-like line and return any carried state."""
    index = start
    while index < len(line):
        two = line[index : index + 2]
        if rules.block_comments and two == "/*":
            index, state = _scan_block_comment_start(line, row, index, ranges)
            if state is not None:
                return state
            continue
        if rules.line_comments and two == "//":
            _scan_line_comment_start(line, row, index, ranges)
            return None
        if rules.quoted_strings and line[index] in {"'", '"'}:
            index, state = _scan_string_start(line, row, index, line[index], ranges)
            if state is not None:
                return state
            continue
        if rules.template_strings and line[index] == "`":
            index, state = _scan_string_start(line, row, index, "`", ranges)
            if state is not None:
                return state
            continue
        index += 1
    return None


def _c_like_protected_ranges(
    lines: list[str],
    *,
    block_comments: bool,
    line_comments: bool,
    quoted_strings: bool,
    template_strings: bool,
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return protected ranges for C-like comments and quoted strings."""
    rules = _CLikeRules(
        block_comments=block_comments,
        line_comments=line_comments,
        quoted_strings=quoted_strings,
        template_strings=template_strings,
    )
    ranges: dict[int, list[tuple[int, int, str]]] = {}
    state: tuple[str, str | None] | None = None
    for row, line in enumerate(lines):
        index, state, skip_line = _resume_c_like_state(line, row, state, ranges)
        if not skip_line:
            state = _scan_c_like_line(line, row, index, rules, ranges)
    return {line: tuple(spans) for line, spans in ranges.items()}


def _javascript_like_protected_ranges(
    lines: list[str],
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return JS/TS protected comments and strings."""
    return _c_like_protected_ranges(
        lines,
        block_comments=True,
        line_comments=True,
        quoted_strings=True,
        template_strings=True,
    )


def _css_protected_ranges(
    lines: list[str],
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return CSS protected block comments and quoted strings."""
    return _c_like_protected_ranges(
        lines,
        block_comments=True,
        line_comments=False,
        quoted_strings=True,
        template_strings=False,
    )


def _html_comment_ranges(
    lines: list[str],
) -> dict[int, tuple[tuple[int, int, str], ...]]:
    """Return protected ranges for HTML ``<!-- ... -->`` comments."""
    ranges: dict[int, list[tuple[int, int, str]]] = {}
    in_comment = False
    for row, line in enumerate(lines):
        index = 0
        if in_comment:
            close = line.find("-->")
            if close == -1:
                _append_range(ranges, row, 0, len(line), "comment")
                continue
            end = close + 3
            _append_range(ranges, row, 0, end, "comment")
            index = end
            in_comment = False

        while index < len(line):
            start = line.find("<!--", index)
            if start == -1:
                break
            close = line.find("-->", start + 4)
            if close == -1:
                _append_range(ranges, row, start, len(line), "comment")
                in_comment = True
                break
            end = close + 3
            _append_range(ranges, row, start, end, "comment")
            index = end
    return {line: tuple(spans) for line, spans in ranges.items()}


@dataclass(frozen=True)
class SyntaxService:
    """Deterministic bridge from #101 metadata to editor rendering decisions."""

    config: ExtensionLayerConfig
    catalog: GrammarCatalog
    detector: LanguageDetector
    root: Path = field(default_factory=paths.extensions_root)

    def build_line_highlighter(self, filename: str | None) -> LineHighlighter | None:
        """Build a per-line TextMate highlighter for ``filename``, or ``None``.

        Returns ``None`` (caller renders with the legacy highlighter) when the
        extension engine is not selected/enabled, the engine is unavailable, no
        grammar resolves for the file, or the grammar cannot be compiled by the
        tokenizer (for example the imported Markdown/C grammars).
        """
        if (
            not self.config.enabled
            or self.config.syntax_engine != SYNTAX_ENGINE_EXTENSION
            or not TEXTMATE_AVAILABLE
            or not filename
        ):
            return None
        resolution = self.resolve(filename)
        if resolution.grammar_path is None or resolution.scope_name is None:
            return None
        grammar_file = self._absolute_grammar_path(resolution.grammar_path)
        if grammar_file is None:
            return None
        # A grammar disabled at runtime after repeated real-line timeouts (for
        # example the imported ``make`` grammar) stays on the legacy path for the
        # rest of the session, so re-opening such a file never re-incurs hitches.
        if is_grammar_quarantined(str(grammar_file)):
            return None
        tokenizer = load_tokenizer(grammar_file)
        if tokenizer is None:
            return None
        return LineHighlighter(tokenizer=tokenizer, scope_name=resolution.scope_name)

    def _absolute_grammar_path(self, repo_relative: str) -> Path | None:
        prefix = f"{paths.REPO_RELATIVE_PREFIX}/"
        if not repo_relative.startswith(prefix):
            return None
        candidate = (self.root / repo_relative[len(prefix) :]).resolve()
        return candidate if candidate.is_file() else None

    def resolve(self, filename: str | None) -> SyntaxResolution:
        """Resolve language/grammar metadata + the rendering decision for a file."""
        engine = self.config.syntax_engine
        diagnostics: list[RegistryDiagnostic] = list(self.config.diagnostics)

        if not self.config.enabled or not filename:
            return _legacy_resolution(filename, engine, diagnostics)

        detection = (
            self.detector.detect(filename)
            if self.config.language_detection
            else LanguageDetectionResult.no_match()
        )
        if detection.language_id is None:
            return _legacy_resolution(filename, engine, diagnostics)

        scope_name, grammar_path = self._resolve_grammar(detection.language_id)
        if (
            scope_name is None
            and detection.language_id in _REQUIRED_MISSING_GRAMMAR_ASSETS
        ):
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    _SERVICE_SOURCE,
                    "required language grammar missing from imported extension tree: "
                    f"{detection.language_id}; expected "
                    f"{_REQUIRED_MISSING_GRAMMAR_ASSETS[detection.language_id]}",
                )
            )

        render_with_extension = (
            engine == SYNTAX_ENGINE_EXTENSION
            and EXTENSION_TOKENIZATION_AVAILABLE
            and scope_name is not None
        )
        if engine == SYNTAX_ENGINE_EXTENSION and not EXTENSION_TOKENIZATION_AVAILABLE:
            diagnostics.append(
                RegistryDiagnostic(
                    "info",
                    _SERVICE_SOURCE,
                    "TextMate tokenizer (python-textmate) is unavailable; "
                    "rendering uses the legacy highlighter",
                )
            )

        return SyntaxResolution(
            filename=filename,
            language_id=detection.language_id,
            scope_name=scope_name,
            grammar_path=grammar_path,
            syntax_engine=engine,
            used_extension_metadata=True,
            fallback_to_legacy=not render_with_extension,
            matched_by=detection.matched_by,
            is_ambiguous=detection.is_ambiguous,
            diagnostics=tuple(diagnostics),
        )

    def _resolve_grammar(self, language_id: str) -> tuple[str | None, str | None]:
        if not self.config.grammar_catalog:
            return None, None
        grammar = _primary_grammar(self.catalog, language_id)
        if grammar is None:
            return None, None
        return grammar.scope_name, grammar.path_repo_relative


def _primary_grammar(
    catalog: GrammarCatalog, language_id: str
) -> TextMateGrammar | None:
    """Return the primary grammar for a language, deterministically.

    A language may have several grammars (e.g. embedded/injection grammars). The
    conventional root scope ``source.<language_id>`` is preferred when present;
    otherwise the first grammar in deterministic registry order is used.
    """
    grammars = catalog.grammars_for_language(language_id)
    if not grammars:
        return None
    canonical = f"source.{language_id}"
    for grammar in grammars:
        if grammar.scope_name == canonical:
            return grammar
    return grammars[0]


def _legacy_resolution(
    filename: str | None, engine: str, diagnostics: list[RegistryDiagnostic]
) -> SyntaxResolution:
    return SyntaxResolution(
        filename=filename,
        language_id=None,
        scope_name=None,
        grammar_path=None,
        syntax_engine=engine,
        used_extension_metadata=False,
        fallback_to_legacy=True,
        diagnostics=tuple(diagnostics),
    )


@lru_cache(maxsize=1)
def _cached_real_parts() -> tuple[GrammarCatalog, LanguageDetector]:
    """Scan the imported tree once and reuse the catalog + detector process-wide."""
    registry = build_registry()
    catalog = build_grammar_catalog(registry=registry)
    detector = build_language_detector(registry=registry)
    return catalog, detector


def build_syntax_service(
    config: ExtensionLayerConfig | object | None = None,
    *,
    catalog: GrammarCatalog | None = None,
    detector: LanguageDetector | None = None,
    root: Path | None = None,
) -> SyntaxService:
    """Build a :class:`SyntaxService`.

    ``config`` may be an :class:`ExtensionLayerConfig` or a raw config mapping
    (its ``[extensions]`` table is parsed). With no ``root`` the catalog and
    detector for the imported tree are built once and cached process-wide, so the
    tree is scanned only once. Pass ``root=<temp dir>`` (or explicit ``catalog``/
    ``detector``) to exercise fixtures without touching the real cache.
    """
    layer_config = (
        config
        if isinstance(config, ExtensionLayerConfig)
        else ExtensionLayerConfig.from_config(config)  # type: ignore[arg-type]
    )
    if root is not None:
        catalog = catalog or build_grammar_catalog(root=root)
        detector = detector or build_language_detector(root=root)
    elif catalog is None or detector is None:
        real_catalog, real_detector = _cached_real_parts()
        catalog = catalog or real_catalog
        detector = detector or real_detector
    resolved_root = root if root is not None else paths.extensions_root()
    return SyntaxService(
        config=layer_config, catalog=catalog, detector=detector, root=resolved_root
    )
