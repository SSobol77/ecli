# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/cargo_clippy/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``cargo clippy --message-format=json`` newline-delimited JSON.

Only ``"reason": "compiler-message"`` records carry diagnostics; every
other record (``"build-script-executed"``, ``"compiler-artifact"``, ...)
is ignored. Each compiler message nests a ``spans`` list; the primary span
(``"is_primary": true``) supplies the file/line/column.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


logger = logging.getLogger(__name__)

_LEVEL_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "note": "hint",
    "help": "hint",
    "failure-note": "hint",
}


def parse_cargo_clippy_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse Cargo's newline-delimited JSON message stream into diagnostics."""
    diagnostics: list[Diagnostic] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("reason") != "compiler-message":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        diagnostic = _message_to_diagnostic(message, default_file=default_file)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return sort_diagnostics(diagnostics)


def _message_to_diagnostic(
    message: dict[str, Any], *, default_file: str
) -> Diagnostic | None:
    spans = message.get("spans")
    span = _primary_span(spans) if isinstance(spans, list) else None
    if span is None:
        # No location to anchor a diagnostic row on; drop rather than guess.
        return None

    level = str(message.get("level") or "warning")
    code_obj = message.get("code")
    code = None
    if isinstance(code_obj, dict) and isinstance(code_obj.get("code"), str):
        code = code_obj["code"]

    text = message.get("message")
    text = text.strip() if isinstance(text, str) and text.strip() else "Clippy diagnostic"

    return Diagnostic(
        file_path=str(span.get("file_name") or default_file),
        line=max(1, _as_int(span.get("line_start"))),
        column=max(1, _as_int(span.get("column_start"))),
        severity=_LEVEL_MAP.get(level, "warning"),
        code=code,
        message=text,
        source="cargo-clippy",
    )


def _primary_span(spans: list[Any]) -> dict[str, Any] | None:
    for span in spans:
        if isinstance(span, dict) and span.get("is_primary"):
            return span
    for span in spans:
        if isinstance(span, dict):
            return span
    return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1
