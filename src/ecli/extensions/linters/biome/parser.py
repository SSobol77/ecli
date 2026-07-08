# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/biome/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Best-effort parser for ``biome lint --reporter=json`` output.

Biome's JSON reporter schema has changed across releases and encodes
positions as byte-code spans rather than plain line/column pairs, so this
parser is deliberately conservative: it extracts what it reliably can
(severity, rule category, message, file) and falls back to line 1 / column
1 when a structured line/column is not present in a recognized shape,
rather than guessing. A line-oriented text fallback handles Biome's
non-JSON CLI output shape (``file:line:column message``).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


logger = logging.getLogger(__name__)

_SEVERITY_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "information": "info",
    "info": "info",
    "hint": "hint",
}

_TEXT_LINE_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+)\s+(?P<rest>.+)$")


def parse_biome_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse Biome JSON reporter output into normalized diagnostics."""
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        return _parse_text_fallback(text, default_file=default_file)

    if not isinstance(raw, dict):
        return ()
    entries = raw.get("diagnostics")
    if not isinstance(entries, list):
        return ()

    diagnostics: list[Diagnostic] = []
    for item in entries:
        if not isinstance(item, dict):
            logger.warning("Dropping malformed Biome diagnostic item: %r", item)
            continue
        diagnostics.append(_item_to_diagnostic(item, default_file=default_file))
    return sort_diagnostics(diagnostics)


def _item_to_diagnostic(item: dict[str, Any], *, default_file: str) -> Diagnostic:
    severity_raw = str(item.get("severity") or "warning").lower()
    location = item.get("location")
    location = location if isinstance(location, dict) else {}
    path = location.get("path")
    file_path = default_file
    if isinstance(path, dict) and isinstance(path.get("file"), str):
        file_path = path["file"]
    elif isinstance(path, str):
        file_path = path

    line, column = _best_effort_position(location)
    return Diagnostic(
        file_path=file_path or default_file,
        line=line,
        column=column,
        severity=_SEVERITY_MAP.get(severity_raw, "warning"),
        code=_optional_str(item.get("category")),
        message=_extract_message(item),
        source="biome",
    )


def _best_effort_position(location: dict[str, Any]) -> tuple[int, int]:
    """Return (line, column), defaulting to (1, 1) when unavailable.

    Biome's ``span`` is a byte-offset pair, not a line/column pair; some
    reporter versions additionally provide a nested line/column-shaped
    field. Only the latter is trusted here.
    """
    for key in ("start", "position"):
        candidate = location.get(key)
        if isinstance(candidate, dict):
            line = candidate.get("line")
            column = candidate.get("column")
            if isinstance(line, int) and isinstance(column, int):
                return max(1, line), max(1, column)
    return 1, 1


def _extract_message(item: dict[str, Any]) -> str:
    description = item.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    message = item.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    if isinstance(message, list):
        parts: list[str] = []
        for node in message:
            if isinstance(node, str):
                parts.append(node)
            elif isinstance(node, dict) and isinstance(node.get("content"), str):
                parts.append(node["content"])
        joined = "".join(parts).strip()
        if joined:
            return joined
    return "Biome diagnostic"


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_text_fallback(text: str, *, default_file: str) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _TEXT_LINE_RE.match(line)
        if not match:
            continue
        try:
            line_no = max(1, int(match.group("line")))
            column = max(1, int(match.group("column")))
        except ValueError:
            continue
        diagnostics.append(
            Diagnostic(
                file_path=match.group("file") or default_file,
                line=line_no,
                column=column,
                severity="warning",
                code=None,
                message=match.group("rest").strip(),
                source="biome",
            )
        )
    return sort_diagnostics(diagnostics)
