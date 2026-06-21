# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/theme_bridge.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic TextMate scope -> ECLI style-category bridge (#102).

This maps TextMate scope names (for example ``keyword.control.flow.python`` or
``string.quoted.double.json``) onto a small, stable set of ECLI style categories
that correspond to existing ECLI/curses colour names (``keyword``, ``string``,
``comment``, ``number`` …). It also flattens overlapping/nested TextMate tokens
into non-overlapping per-line spans, resolving overlaps by scope specificity so
the most specific scope wins.

It is data-only and deterministic: no theme files are executed, no VS Code theme
is activated, and the same input always yields the same spans.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


# The default category renders as plain text (the editor's default colour).
DEFAULT_CATEGORY = "default"

# ECLI style categories produced by this bridge. Each name matches an existing
# ECLI colour key (see Ecli._SYNTAX_COLOR_STRUCTURE), so the editor can map a
# category straight onto a curses attribute.
CATEGORIES: frozenset[str] = frozenset(
    {
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
        DEFAULT_CATEGORY,
    }
)

# Ordered, most-specific-first scope-prefix -> category rules. The first rule
# whose prefix equals the scope or is a dotted prefix of it wins. ``None`` means
# "render as default" (used for structural ``meta``/``source`` scopes and generic
# punctuation, so they do not over-colour the line).
_SCOPE_RULES: tuple[tuple[str, str | None], ...] = (
    ("comment", "comment"),
    ("punctuation.definition.comment", "comment"),
    ("punctuation.definition.string", "string"),
    ("string.regexp", "string"),
    ("string", "string"),
    ("constant.numeric", "number"),
    ("constant.character.escape", "string"),
    ("constant.language", "constant"),
    ("constant.other.color", "constant"),
    ("constant", "constant"),
    ("keyword.operator", "operator"),
    ("keyword.control", "keyword"),
    ("keyword", "keyword"),
    ("storage.type", "type"),
    ("storage.modifier", "keyword"),
    ("storage", "keyword"),
    ("support.function", "function"),
    ("support.class", "type"),
    ("support.type", "type"),
    ("support.constant", "constant"),
    ("support.variable", "variable"),
    ("support", "builtin"),
    ("entity.name.function", "function"),
    ("entity.name.type", "type"),
    ("entity.name.class", "type"),
    ("entity.name.tag", "tag"),
    ("entity.name.section", "function"),
    ("entity.other.attribute-name", "attribute"),
    ("entity.other.inherited-class", "type"),
    ("entity.name", "function"),
    ("variable.parameter", "variable"),
    ("variable.language", "keyword"),
    ("variable.function", "function"),
    ("variable", "variable"),
    ("markup.heading", "function"),
    ("markup.bold", "type"),
    ("markup.italic", "type"),
    ("markup.raw.block", "string"),
    ("markup.inline.raw", "string"),
    ("markup.fenced_code", "string"),
    ("markup.underline.link", "function"),
    ("markup.quote", "comment"),
    ("markup.list", "operator"),
    ("invalid.deprecated", "error"),
    ("invalid", "error"),
    ("keyword.other.unit", "number"),
    ("punctuation.section.embedded", "operator"),
    ("meta", None),
    ("source", None),
    ("text", None),
    ("punctuation", "punctuation"),
)

# Protected ranges (e.g. the Python string/docstring guard) are authoritative:
# inside a string nothing else — not even ``invalid``/``error`` scopes the engine
# emits for keywords-in-strings — may override the string category. This priority
# sits above every entry in ``_CATEGORY_PRIORITY`` so a protected range always wins.
_PROTECTED_PRIORITY = -1

_CATEGORY_PRIORITY: dict[str, int] = {
    "error": 0,
    "comment": 1,
    "string": 2,
    "keyword": 4,
    "constant": 5,
    "number": 5,
    "function": 6,
    "builtin": 6,
    "decorator": 6,
    "type": 7,
    "tag": 7,
    "attribute": 8,
    "variable": 8,
    "operator": 9,
    "punctuation": 9,
    DEFAULT_CATEGORY: 99,
}


def _category_for_single_scope(scope: str) -> tuple[str | None, int]:
    best_category: str | None = None
    best_length = -1
    for prefix, category in _SCOPE_RULES:
        matches = scope == prefix or scope.startswith(prefix + ".")
        if matches and len(prefix) > best_length:
            best_category = category
            best_length = len(prefix)
    return best_category, best_length


def scope_to_category(scope: str) -> str | None:
    """Return the ECLI style category for a TextMate scope, or ``None``.

    ``None`` means the scope should render as default text. A scope value may be a
    space-separated stack (for example ``meta.definition.variable.ts
    variable.other.constant.ts``); each sub-scope is evaluated and the most
    specific (longest matching dotted prefix) decision wins. Within a single
    scope, ``constant.numeric.integer`` maps to ``number`` rather than the generic
    ``constant`` rule.
    """
    best_category: str | None = None
    best_priority = _CATEGORY_PRIORITY[DEFAULT_CATEGORY]
    best_length = -1
    for sub_scope in scope.split():
        category, length = _category_for_single_scope(sub_scope)
        if category is None:
            continue
        priority = _CATEGORY_PRIORITY.get(
            category, _CATEGORY_PRIORITY[DEFAULT_CATEGORY]
        )
        if priority < best_priority or (
            priority == best_priority and length > best_length
        ):
            best_category = category
            best_priority = priority
            best_length = length
    return best_category


def _specificity(scope: str) -> int:
    return scope.count(".")


@dataclass
class _PaintBuffers:
    categories: list[str]
    priorities: list[int]
    specificities: list[int]


def _paint_range(
    buffers: _PaintBuffers,
    start: int,
    end: int,
    category: str,
    strength: tuple[int, int],
) -> None:
    priority, specificity = strength
    length = len(buffers.categories)
    clamped_start = max(0, start)
    clamped_end = min(length, end)
    for index in range(clamped_start, clamped_end):
        if priority < buffers.priorities[index] or (
            priority == buffers.priorities[index]
            and specificity >= buffers.specificities[index]
        ):
            buffers.categories[index] = category
            buffers.priorities[index] = priority
            buffers.specificities[index] = specificity


def tokens_to_spans(
    line: str,
    tokens: Iterable[tuple[str, int, int]],
    protected_ranges: Iterable[tuple[int, int, str]] = (),
) -> list[tuple[str, str]]:
    """Flatten overlapping TextMate tokens into ``(text, category)`` spans.

    Every character starts as :data:`DEFAULT_CATEGORY`. Tokens are painted from
    broadest to narrowest (ties broken so the more specific scope paints last), so
    the most specific visible scope wins per character. The returned spans tile
    the whole line exactly (including untokenized gaps), so the editor can render
    them without any out-of-bounds slicing.
    """
    length = len(line)
    if length == 0:
        return []

    categories = [DEFAULT_CATEGORY] * length
    priorities = [_CATEGORY_PRIORITY[DEFAULT_CATEGORY]] * length
    specificities = [-1] * length
    buffers = _PaintBuffers(categories, priorities, specificities)
    # Broadest first; among equal width, less specific first -> specific wins.
    ordered = sorted(
        tokens,
        key=lambda token: (-(token[2] - token[1]), _specificity(token[0])),
    )
    for scope, start, end in ordered:
        category = scope_to_category(scope)
        if category is None or category == DEFAULT_CATEGORY:
            continue
        priority = _CATEGORY_PRIORITY.get(
            category, _CATEGORY_PRIORITY[DEFAULT_CATEGORY]
        )
        specificity = _specificity(scope)
        _paint_range(
            buffers,
            start,
            end,
            category,
            (priority, specificity),
        )

    for start, end, protected_category in protected_ranges:
        resolved_category = (
            protected_category if protected_category in CATEGORIES else DEFAULT_CATEGORY
        )
        if resolved_category == DEFAULT_CATEGORY:
            continue
        _paint_range(
            buffers,
            start,
            end,
            resolved_category,
            (_PROTECTED_PRIORITY, 10_000),
        )

    spans: list[tuple[str, str]] = []
    current_text: list[str] = [line[0]]
    current_category = categories[0]
    for index in range(1, length):
        if categories[index] == current_category:
            current_text.append(line[index])
        else:
            spans.append(("".join(current_text), current_category))
            current_text = [line[index]]
            current_category = categories[index]
    spans.append(("".join(current_text), current_category))
    return spans
