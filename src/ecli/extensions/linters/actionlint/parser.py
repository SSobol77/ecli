# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/actionlint/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Parser for ``actionlint -color=never`` text output.

Lines look like::

    .github/workflows/ci.yml:10:5: character '"' is invalid for step name [syntax-check]
"""

from __future__ import annotations

import re

from ecli.extensions.linters.core.models import Diagnostic, sort_diagnostics


_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+):\s*(?P<message>.+?)"
    r"(?:\s*\[(?P<rule>[a-z0-9_-]+)\])?$"
)


def parse_actionlint_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse actionlint text output into normalized diagnostics."""
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
                severity="error",
                code=match.group("rule"),
                message=match.group("message").strip(),
                source="actionlint",
            )
        )
    return sort_diagnostics(diagnostics)
