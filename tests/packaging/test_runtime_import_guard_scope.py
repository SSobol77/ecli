# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_runtime_import_guard_scope.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Scope tests for the runtime-import guard after the #100 adapter (issue #100).

The guard (`scripts/check_runtime_imports.py`) must skip the imported upstream
extension tree under ``src/ecli/extensions/`` (issue #98) but still scan the
ECLI-owned adapter package ``src/ecli/extensions/ecli_integration/`` (issue
#100). These tests prove the predicate and the file walk honour that boundary.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def guard(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/check_runtime_imports.py", "check_runtime_imports_guard"
    )


def test_predicate_skips_imported_upstream(guard: ModuleType) -> None:
    assert (
        guard._is_imported_upstream(Path("extensions/lang/python/extension.py")) is True
    )
    assert guard._is_imported_upstream(Path("extensions/lang/json/server/x.py")) is True


def test_predicate_scans_adapter_and_normal_source(guard: ModuleType) -> None:
    assert (
        guard._is_imported_upstream(Path("extensions/ecli_integration/registry.py"))
        is False
    )
    assert guard._is_imported_upstream(Path("core/Ecli.py")) is False


def test_walk_includes_adapter_and_excludes_upstream(
    guard: ModuleType, repo_root: Path
) -> None:
    source_root = repo_root / "src" / "ecli"
    scanned = guard.scanned_source_files(source_root)
    relative = {path.relative_to(source_root).as_posix() for path in scanned}

    # The ECLI-owned adapter package is scanned.
    for expected in (
        "extensions/ecli_integration/__init__.py",
        "extensions/ecli_integration/paths.py",
        "extensions/ecli_integration/manifest.py",
        "extensions/ecli_integration/registry.py",
    ):
        assert expected in relative, f"guard must scan {expected}"

    # Every scanned path under extensions/ belongs to the adapter package; no
    # imported upstream extension file is scanned.
    extension_paths = {rel for rel in relative if rel.startswith("extensions/")}
    assert extension_paths
    assert all(
        rel.startswith("extensions/ecli_integration/") for rel in extension_paths
    )

    # Normal ECLI runtime source is still scanned.
    assert any(rel.startswith("core/") for rel in relative)
