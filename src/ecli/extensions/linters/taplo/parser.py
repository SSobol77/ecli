# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/taplo/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

r"""Best-effort parser for ``taplo lint`` text output.

Taplo renders diagnostics using a multi-line ``codespan-reporting`` style
diagram, e.g.::

    Error: invalid escape sequence
       ╭─[config.toml:3:10]
       │
     3 │ foo = "\q"
       │          ─
       │

This parser pairs each ``Error:``/``Warning:`` message line with the
following ``file:line:column`` location line, ignoring the ASCII-art
framing in between.
"""

from __future__ import annotations

import re

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


_LEVEL_RE = re.compile(r"^(?P<level>Error|Warning|error|warning):\s*(?P<message>.+)$")
_LOCATION_RE = re.compile(r"(?P<file>[^\s\[\]:]+):(?P<line>\d+):(?P<column>\d+)")


def parse_taplo_output(text: str, *, default_file: str = "") -> tuple[Diagnostic, ...]:
    """Parse Taplo's diagnostic-report text output into normalized diagnostics."""
    diagnostics: list[Diagnostic] = []
    pending_message: str | None = None
    pending_severity: DiagnosticSeverity = "error"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        level_match = _LEVEL_RE.match(line)
        if level_match:
            pending_message = level_match.group("message").strip()
            pending_severity = (
                "error" if level_match.group("level").lower() == "error" else "warning"
            )
            continue
        if pending_message is None:
            continue
        location_match = _LOCATION_RE.search(line)
        if not location_match:
            continue
        try:
            line_no = max(1, int(location_match.group("line")))
            column = max(1, int(location_match.group("column")))
        except ValueError:
            continue
        diagnostics.append(
            Diagnostic(
                file_path=location_match.group("file") or default_file,
                line=line_no,
                column=column,
                severity=pending_severity,
                code=None,
                message=pending_message,
                source="taplo",
            )
        )
        pending_message = None

    return sort_diagnostics(diagnostics)
