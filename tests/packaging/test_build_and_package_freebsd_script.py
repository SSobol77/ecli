# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_freebsd_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_freebsd.py (no real build)."""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def freebsd(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_freebsd.py", "freebsd_build"
    )


def test_normalize_arch(freebsd: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        freebsd.normalize_arch.__globals__["os"],
        "uname",
        lambda: os.uname_result(("FreeBSD", "h", "r", "v", "amd64")),
    )
    assert freebsd.normalize_arch() == "x86_64"


def test_dependency_lists(freebsd: ModuleType) -> None:
    assert "python311" in freebsd.SYSTEM_PACKAGES
    assert "py311-pyinstaller" in freebsd.SYSTEM_PACKAGES
    assert "aiohttp" in freebsd.PIP_PACKAGES


def test_manifest_text(freebsd: ModuleType) -> None:
    manifest = freebsd.manifest_text("2.0.0", "FreeBSD:14:amd64")
    assert "name: ecli" in manifest
    assert "version: 2.0.0" in manifest
    assert "abi: FreeBSD:14:amd64" in manifest
    assert "categories: [editors]" in manifest
    assert "licenses: [GPL-2.0-only]" in manifest


def test_python_bin_default(
    freebsd: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON", raising=False)
    assert freebsd.python_bin() == "python3.11"
