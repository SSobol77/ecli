#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/check_runtime_imports.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Fail if production ECLI runtime source imports test-only modules."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = frozenset({"mock", "pytest", "test", "tests", "unittest"})
FORBIDDEN_IMPORT_PARTS = frozenset(
    {"conftest", "mock", "pytest", "test_helpers", "testing", "unittest"}
)
SOURCE_ROOT = Path("src/ecli")


def _forbidden_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_module(alias.name):
                    findings.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden_module(module):
                findings.append((node.lineno, f"from {module} import ..."))
    return findings


def _is_forbidden_module(module_name: str) -> bool:
    parts = tuple(part for part in module_name.split(".") if part)
    if not parts:
        return False
    if parts[0] in FORBIDDEN_IMPORT_ROOTS:
        return True
    return any(part in FORBIDDEN_IMPORT_PARTS for part in parts)


def main() -> int:
    """Validate production runtime import policy."""
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        for lineno, import_text in _forbidden_imports(path):
            violations.append(
                f"{path}:{lineno}: forbidden runtime import: {import_text}"
            )

    if violations:
        print(
            "Production runtime source must not import test-only modules.",
            file=sys.stderr,
        )
        print("\n".join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
