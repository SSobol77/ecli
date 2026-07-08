# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/zig/parser.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Best-effort parser for ``zig fmt --check --ast-check`` text output.

Two distinct shapes are handled:

* AST/syntax errors, compiler-style: ``file:line:column: error: message``.
* Formatting drift only: ``zig fmt --check`` prints just the bare filename
  of any file that would be reformatted, with no line/column -- this
  becomes a single line-1/column-1 "not formatted" diagnostic.
"""

from __future__ import annotations

import re

from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticSeverity,
    sort_diagnostics,
)


_COMPILER_DIAGNOSTIC_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+):\s*"
    r"(?P<severity>error|warning|note):\s*(?P<message>.+)$"
)

_SEVERITY_MAP: dict[str, DiagnosticSeverity] = {
    "error": "error",
    "warning": "warning",
    "note": "hint",
}


def parse_zig_output(
    text: str, *, default_file: str = ""
) -> tuple[Diagnostic, ...]:
    """Parse ``zig fmt --check --ast-check`` output into normalized diagnostics."""
    diagnostics: list[Diagnostic] = []
    formatting_only_files: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _COMPILER_DIAGNOSTIC_RE.match(line)
        if match:
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
                    severity=_SEVERITY_MAP.get(match.group("severity"), "error"),
                    code=None,
                    message=match.group("message").strip(),
                    source="zig",
                )
            )
            continue
        # `zig fmt --check` without a matched compiler-diagnostic line: if
        # the bare line looks like a plain file path, treat it as "needs
        # formatting" rather than discarding it silently.
        if line.endswith(".zig"):
            formatting_only_files.append(line)

    for file_path in formatting_only_files:
        diagnostics.append(
            Diagnostic(
                file_path=file_path or default_file,
                line=1,
                column=1,
                severity="warning",
                code=None,
                message="File is not formatted per `zig fmt`.",
                source="zig",
            )
        )

    return sort_diagnostics(diagnostics)
