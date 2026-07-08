# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/yamllint/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``yamllint --format parsable`` output.

Parsable format lines look like::

    file.yaml:3:1: [error] duplication of key "foo" in mapping (key-duplicates)
    file.yaml:10:80: [warning] line too long (85 > 80 characters) (line-length)
"""

from __future__ import annotations

import re

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+):\s*"
    r"\[(?P<severity>error|warning)\]\s*(?P<message>.+?)\s*"
    r"(?:\((?P<rule>[a-z0-9-]+)\))?$"
)


def _map_severity(raw: str) -> DiagnosticSeverity:
    return "error" if raw == "error" else "warning"


def parse_yamllint_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse yamllint parsable text output into normalized diagnostics."""
    diagnostics: list[Diagnostic] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
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
                severity=_map_severity(match.group("severity")),
                code=match.group("rule"),
                message=match.group("message").strip(),
                source="yamllint",
            )
        )
    return sort_diagnostics(diagnostics)
