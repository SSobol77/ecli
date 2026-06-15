# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_arch_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_arch.py naming and tool guards."""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def arch(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_arch.py", "arch_build"
    )


def test_package_name_and_exit_codes(arch: ModuleType) -> None:
    assert arch.PACKAGE_NAME == "ecli-editor"
    assert arch.EXIT_MISSING_TOOL == 5


def test_normalize_arch_uses_aarch64(
    arch: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        arch.os, "uname", lambda: os.uname_result(("Linux", "h", "r", "v", "aarch64"))
    )
    assert arch.normalize_arch() == "aarch64"
    monkeypatch.setattr(
        arch.os, "uname", lambda: os.uname_result(("Linux", "h", "r", "v", "x86_64"))
    )
    assert arch.normalize_arch() == "x86_64"


def test_artifact_name_token(arch: ModuleType, repo_root: Path) -> None:
    version = arch.read_version(repo_root)
    name = f"ecli_{version}_arch_x86_64.pkg.tar.zst"
    assert name.endswith("arch_x86_64.pkg.tar.zst")
