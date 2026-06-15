# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_package_appimage_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/package_appimage.py naming and version guard."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import expected_release_artifact, load_script_module


@pytest.fixture
def appimage(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/package_appimage.py", "appimage_build"
    )


def test_normalize_arch(appimage: ModuleType) -> None:
    assert appimage.normalize_arch("amd64") == "x86_64"
    assert appimage.normalize_arch("arm64") == "arm64"
    assert appimage.normalize_arch("aarch64") == "arm64"


def test_version_mismatch_returns_two(appimage: ModuleType) -> None:
    # A version that cannot match pyproject.toml triggers the strict guard.
    assert appimage.main(["0.0.0-never-matches"]) == appimage.EXIT_VERSION_MISMATCH


def test_find_executable_missing(appimage: ModuleType, tmp_path: Path) -> None:
    assert appimage.find_executable(tmp_path) is None


def test_artifact_token(appimage: ModuleType, repo_root: Path) -> None:
    version = appimage.read_version(repo_root)
    arch = appimage.normalize_arch("x86_64")
    expected = expected_release_artifact(
        repo_root, version, f"ecli_{version}_linux_{arch}.AppImage"
    )
    assert expected.parent == repo_root / "releases" / version
    assert expected.name == f"ecli_{version}_linux_{arch}.AppImage"
