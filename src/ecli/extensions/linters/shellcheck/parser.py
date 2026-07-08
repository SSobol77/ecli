# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/shellcheck/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``shellcheck --format=json`` output.

ShellCheck's JSON format is a flat array of objects, e.g.::

    [{"file":"a.sh","line":3,"endLine":3,"column":1,"endColumn":5,
      "level":"warning","code":2086,"message":"Double quote to prevent globbing."}]
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


def parse_shellcheck_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse ShellCheck JSON output into normalized diagnostics.

    Returns an empty tuple, never raises, for malformed/non-JSON output.
    """
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        logger.debug("ShellCheck JSON parse failed; ignoring output.")
        return ()
    if not isinstance(raw, list):
        return ()

    diagnostics: list[Diagnostic] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Dropping malformed ShellCheck diagnostic item: %r", item)
            continue
        diagnostics.append(_to_diagnostic(item, default_file=default_file))
    return sort_diagnostics(diagnostics)


def _to_diagnostic(item: dict[str, Any], *, default_file: str) -> Diagnostic:
    code_raw = item.get("code")
    code = f"SC{code_raw}" if code_raw is not None else None
    level = str(item.get("level") or "warning")
    return Diagnostic(
        file_path=str(item.get("file") or default_file),
        line=max(1, _as_int(item.get("line"))),
        column=max(1, _as_int(item.get("column"))),
        severity=_SEVERITY_MAP.get(level, "warning"),
        code=code,
        message=str(item.get("message") or "ShellCheck diagnostic"),
        source="shellcheck",
    )


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1
