# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/clang_tidy/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``clang-tidy`` plain text diagnostic output.

Lines look like::

    file.cpp:10:5: warning: variable 'x' is not initialized [cppcoreguidelines-init-variables]
    file.cpp:15:1: error: use of undeclared identifier 'foo' [clang-diagnostic-error]
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
    r"(?P<severity>error|warning|note):\s*(?P<message>.+?)"
    r"(?:\s*\[(?P<check>[a-zA-Z0-9_.,-]+)\])?\s*$"
)

_SEVERITY_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "note": "hint",
}


def parse_clang_tidy_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse clang-tidy text output into normalized diagnostics."""
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
                severity=_SEVERITY_MAP.get(match.group("severity"), "warning"),
                code=match.group("check"),
                message=match.group("message").strip(),
                source="clang-tidy",
            )
        )
    return sort_diagnostics(diagnostics)
