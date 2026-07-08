# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_pmd/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``pmd check --format xml`` output.

Shape::

    <?xml version="1.0" encoding="UTF-8"?>
    <pmd version="7.0.0" timestamp="...">
    <file name="/path/to/File.java">
    <violation beginline="10" endline="10" begincolumn="5" endcolumn="20"
               rule="UnusedLocalVariable" ruleset="Best Practices" priority="3">
    Avoid unused local variables such as 'x'.
    </violation>
    </file>
    </pmd>
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


logger = logging.getLogger(__name__)

# PMD priority: 1 (highest) .. 5 (lowest).
_PRIORITY_SEVERITY: dict[int, DiagnosticSeverity] = {
    1: "error",
    2: "error",
    3: "warning",
    4: "info",
    5: "hint",
}


def parse_pmd_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse PMD XML output into normalized diagnostics.

    Returns an empty tuple, never raises, for malformed/non-XML output.
    """
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        root = ET.fromstring(stripped)
    except ET.ParseError:
        logger.debug("PMD XML parse failed; ignoring output.")
        return ()

    diagnostics: list[Diagnostic] = []
    for file_elem in root.findall("file"):
        file_path = file_elem.get("name") or default_file
        for violation_elem in file_elem.findall("violation"):
            diagnostics.append(_to_diagnostic(violation_elem, file_path))
    return sort_diagnostics(diagnostics)


def _to_diagnostic(violation_elem: ET.Element, file_path: str) -> Diagnostic:
    priority = _as_int(violation_elem.get("priority"), default=3)
    message = (violation_elem.text or "PMD diagnostic").strip()
    return Diagnostic(
        file_path=file_path,
        line=max(1, _as_int(violation_elem.get("beginline"))),
        column=max(1, _as_int(violation_elem.get("begincolumn"))),
        severity=_PRIORITY_SEVERITY.get(priority, "warning"),
        code=violation_elem.get("rule"),
        message=message,
        source="pmd",
    )


def _as_int(value: str | None, *, default: int = 1) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
