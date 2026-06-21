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
# Imported, read-only VS Code / TextMate extension assets (issue #98) are not
# ECLI runtime source. The upstream tree must remain unchanged and contains
# foreign-language code and intentionally-malformed Python fixtures, so this
# guard must not parse it. See docs/architecture/extensions-layer.md.
#
# Exception (issue #100): ``src/ecli/extensions/ecli_integration/`` is ECLI-owned
# deterministic adapter code, not imported upstream, so it MUST be scanned. Every
# other direct child of ``src/ecli/extensions/`` stays an imported upstream asset
# tree and remains skipped.
IMPORTED_EXTENSIONS_DIR = "extensions"
ECLI_OWNED_EXTENSIONS_SUBDIR = "ecli_integration"


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


def _is_imported_upstream(relative: Path) -> bool:
    """Return ``True`` if ``relative`` (under ``src/ecli``) is an imported asset.

    The imported VS Code extension tree lives under ``extensions/`` and is read
    only (issue #98). The single ECLI-owned exception is the deterministic
    adapter package ``extensions/ecli_integration/`` (issue #100), which is
    scanned like any other ECLI source.
    """
    parts = relative.parts
    if not parts or parts[0] != IMPORTED_EXTENSIONS_DIR:
        return False
    return len(parts) < 2 or parts[1] != ECLI_OWNED_EXTENSIONS_SUBDIR


def scanned_source_files(root: Path | None = None) -> list[Path]:
    """Return ECLI-owned ``*.py`` files under ``root``, skipping imported assets.

    ``root`` defaults to the module-level ``SOURCE_ROOT`` resolved at call time,
    so tests that monkeypatch ``SOURCE_ROOT`` are honoured.
    """
    base = SOURCE_ROOT if root is None else root
    files: list[Path] = []
    for path in sorted(base.rglob("*.py")):
        if _is_imported_upstream(path.relative_to(base)):
            continue
        files.append(path)
    return files


def main() -> int:
    """Validate production runtime import policy."""
    violations: list[str] = []
    for path in scanned_source_files():
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
