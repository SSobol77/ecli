# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/markdownlint/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``markdownlint-cli2`` line-oriented text output.

Typical lines look like::

    audit-report.md:12 MD013/line-length Line length [Expected: 80; Actual: 95]
    audit-report.md:34:1-34:10 MD047/single-trailing-newline Files should end with a single newline character
"""

from __future__ import annotations

import re

from ecli.extensions.linters.core.models import Diagnostic, sort_diagnostics


_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<column>\d+))?(?:-\d+:\d+)?\s+"
    r"(?P<rule>\S+)\s+(?P<message>.+)$"
)


def parse_markdownlint_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse markdownlint-cli2 text output into normalized diagnostics.

    Malformed or unrecognized lines (banner text, summary counts) are
    silently skipped rather than raising.
    """
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
            column_group = match.group("column")
            column = max(1, int(column_group)) if column_group else 1
        except ValueError:
            continue
        diagnostics.append(
            Diagnostic(
                file_path=match.group("file") or default_file,
                line=line_no,
                column=column,
                severity="warning",
                code=match.group("rule"),
                message=match.group("message").strip(),
                source="markdownlint-cli2",
            )
        )
    return sort_diagnostics(diagnostics)
