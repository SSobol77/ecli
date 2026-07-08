# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/hadolint/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``hadolint --format json`` output.

Hadolint's JSON format is a flat array of objects, e.g.::

    [{"line":1,"column":1,"level":"warning","code":"DL3006",
      "message":"Always tag the version of an image explicitly","file":"Dockerfile"}]
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

_SEVERITY_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "info": "info",
    "style": "hint",
}


def parse_hadolint_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse Hadolint JSON output into normalized diagnostics."""
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        logger.debug("Hadolint JSON parse failed; ignoring output.")
        return ()
    if not isinstance(raw, list):
        return ()

    diagnostics: list[Diagnostic] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Dropping malformed Hadolint diagnostic item: %r", item)
            continue
        level = str(item.get("level") or "warning")
        diagnostics.append(
            Diagnostic(
                file_path=str(item.get("file") or default_file),
                line=max(1, _as_int(item.get("line"))),
                column=max(1, _as_int(item.get("column"))),
                severity=_SEVERITY_MAP.get(level, "warning"),
                code=_optional_str(item.get("code")),
                message=str(item.get("message") or "Hadolint diagnostic"),
                source="hadolint",
            )
        )
    return sort_diagnostics(diagnostics)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
