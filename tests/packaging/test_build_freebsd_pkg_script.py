# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_freebsd_pkg_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_freebsd_pkg.py (no real build, no sudo)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def fpkg(repo_root: Path) -> ModuleType:
    return load_script_module(repo_root, "scripts/build_freebsd_pkg.py", "freebsd_pkg")


def test_required_commands(fpkg: ModuleType) -> None:
    assert "python3.11" in fpkg.REQUIRED_COMMANDS
    assert "pkg" in fpkg.REQUIRED_COMMANDS


def test_check_dependencies_missing(
    fpkg: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fpkg.shutil, "which", lambda name: None)
    assert fpkg.check_dependencies() is False


def test_yaml_and_ucl_manifests(fpkg: ModuleType) -> None:
    yaml = fpkg.yaml_manifest("1.0.0", "FreeBSD:14:amd64")
    ucl = fpkg.ucl_manifest("1.0.0", "FreeBSD:14:amd64")
    assert 'name: "ecli"' in yaml
    assert "/usr/local/bin/ecli" in yaml
    assert 'name = "ecli";' in ucl
    assert "/usr/local/man/man1/ecli.1.gz" in ucl


def test_normalize_arch(fpkg: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr(
        fpkg.os, "uname", lambda: os.uname_result(("FreeBSD", "h", "r", "v", "arm64"))
    )
    assert fpkg.normalize_arch() == "arm64"
