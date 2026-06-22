# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/parsers.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Output parsers that normalise tool stdout into ECLI diagnostics (#104).

ECLI does **not** implement linting engines or lint rules. These parsers only
translate the structured output of an existing professional tool (e.g. Ruff's
``--output-format=json``) into the provider-neutral :class:`~.model.Diagnostic`
shape. The stdout→normalized-offense concept is ported from the multi-linter
design of `fnando/vscode-linter` (MIT); see ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

import json

from .model import Diagnostic, DiagnosticSeverity


__all__ = ["ParseError", "parse_ruff_json", "short_detail"]


class ParseError(ValueError):
    """Raised when a tool's structured output cannot be normalised."""


# Ruff JSON records carry no severity field; map a small set of codes to ERROR
# and treat everything else as WARNING. Syntax errors (no code) are ERROR. This
# is a presentation mapping over Ruff's own findings — not a lint rule.
_RUFF_ERROR_CODE_PREFIXES = ("E9",)  # E999 syntax error, etc.


def _ruff_severity(code: str | None) -> DiagnosticSeverity:
    if not code:
        return DiagnosticSeverity.ERROR
    if any(code.startswith(prefix) for prefix in _RUFF_ERROR_CODE_PREFIXES):
        return DiagnosticSeverity.ERROR
    return DiagnosticSeverity.WARNING


def parse_ruff_json(file_path: str, stdout: str) -> tuple[Diagnostic, ...]:
    """Parse Ruff ``--output-format=json`` *stdout* into diagnostics.

    Returns an empty tuple for an empty/whitespace payload (clean run). Raises
    :class:`ParseError` for malformed JSON or an unexpected top-level structure
    so the adapter can surface a bounded error state.
    """
    text = stdout.strip()
    if not text:
        return ()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError("ruff produced unparseable output") from exc
    if not isinstance(payload, list):
        raise ParseError("unexpected ruff output structure")
    return tuple(
        diag
        for diag in (_ruff_item_to_diagnostic(file_path, item) for item in payload)
        if diag is not None
    )


def _ruff_item_to_diagnostic(file_path: str, item: object) -> Diagnostic | None:
    if not isinstance(item, dict):
        return None
    code = item.get("code")
    code_str = str(code) if code else None
    location = item.get("location")
    end_location = item.get("end_location")
    line = 1
    column: int | None = None
    if isinstance(location, dict):
        line = _as_int(location.get("row"), default=1) or 1
        column = _as_int(location.get("column"), default=None)
    end_line: int | None = None
    end_column: int | None = None
    if isinstance(end_location, dict):
        end_line = _as_int(end_location.get("row"), default=None)
        end_column = _as_int(end_location.get("column"), default=None)
    filename = item.get("filename")
    path = str(filename) if isinstance(filename, str) and filename else file_path
    message = str(item.get("message", "")).strip() or "(no message)"
    docs_url = item.get("url")
    fix = item.get("fix")
    return Diagnostic(
        file_path=path,
        line=line,
        column=column,
        severity=_ruff_severity(code_str),
        source="ruff",
        message=message,
        code=code_str,
        end_line=end_line,
        end_column=end_column,
        docs_url=str(docs_url) if isinstance(docs_url, str) and docs_url else None,
        # Future metadata only: ECLI does not apply fixes in issue #104.
        correctable=isinstance(fix, dict),
    )


def _as_int(value: object, default: int | None) -> int | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def short_detail(text: str, limit: int = 160) -> str:
    """Return a single-line, length-bounded snippet of *text* for the UI."""
    flattened = " ".join(text.split())
    if len(flattened) > limit:
        return flattened[: limit - 1] + "…"
    return flattened
