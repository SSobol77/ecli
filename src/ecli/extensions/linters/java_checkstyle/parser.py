# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_checkstyle/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``checkstyle -f xml`` output.

Shape::

    <?xml version="1.0" encoding="UTF-8"?>
    <checkstyle version="10.12.1">
    <file name="/path/to/File.java">
    <error line="3" column="1" severity="warning" message="Missing a Javadoc comment."
           source="...MissingJavadocTypeCheck"/>
    </file>
    </checkstyle>
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

_SEVERITY_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "info": "info",
    "ignore": "hint",
}


def parse_checkstyle_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse Checkstyle XML output into normalized diagnostics.

    Returns an empty tuple, never raises, for malformed/non-XML output.
    """
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        root = ET.fromstring(stripped)
    except ET.ParseError:
        logger.debug("Checkstyle XML parse failed; ignoring output.")
        return ()

    diagnostics: list[Diagnostic] = []
    for file_elem in root.findall("file"):
        file_path = file_elem.get("name") or default_file
        for error_elem in file_elem.findall("error"):
            diagnostics.append(_to_diagnostic(error_elem, file_path))
    return sort_diagnostics(diagnostics)


def _to_diagnostic(error_elem: ET.Element, file_path: str) -> Diagnostic:
    severity = (error_elem.get("severity") or "warning").lower()
    source = error_elem.get("source")
    code = source.rsplit(".", 1)[-1] if source else None
    return Diagnostic(
        file_path=file_path,
        line=max(1, _as_int(error_elem.get("line"))),
        column=max(1, _as_int(error_elem.get("column"))),
        severity=_SEVERITY_MAP.get(severity, "warning"),
        code=code,
        message=error_elem.get("message") or "Checkstyle diagnostic",
        source="checkstyle",
    )


def _as_int(value: str | None) -> int:
    try:
        return int(value) if value is not None else 1
    except ValueError:
        return 1
