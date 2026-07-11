# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_release_metadata_v024.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""v0.2.4 release metadata and version-source contract."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


VERSION = "0.2.4"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pyproject_version(repo_root: Path) -> str:
    with (repo_root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


def test_authoritative_version_sources_are_current(repo_root: Path) -> None:
    assert _pyproject_version(repo_root) == VERSION
    assert f'version = "{VERSION}"' in _read(repo_root / "flake.nix")
    assert f'version ? "{VERSION}"' in _read(repo_root / "packaging/nix/package.nix")
    assert f"pkgver={VERSION}" in _read(repo_root / "packaging/arch/PKGBUILD")


def test_make_validate_version_consistency_passes(repo_root: Path) -> None:
    result = subprocess.run(
        ["make", "validate-version-consistency"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"pyproject={VERSION} ecli.__version__={VERSION}" in result.stdout


def test_runtime_version_cli_reports_current_release(repo_root: Path) -> None:
    env = os.environ.copy()
    python_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        python_path = os.pathsep.join((python_path, existing_pythonpath))
    env["PYTHONPATH"] = python_path

    result = subprocess.run(
        [sys.executable, "-m", "ecli", "--version"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"ecli {VERSION}"


def test_packaging_filenames_derive_current_version(
    repo_root: Path,
    release_assets: ModuleType,
) -> None:
    project_version = _pyproject_version(repo_root)
    names = release_assets.expected_asset_names(project_version)

    assert project_version == VERSION
    assert len(names) == 21
    assert len(set(names)) == 21
    assert all(VERSION in name for name in names)
    assert all("0.2.3" not in name for name in names)
    assert "ecli_editor-0.2.4-py3-none-any.whl" in names
    assert "ecli_0.2.4_linux_x86_64.deb" in names
    assert "ecli_0.2.4_workflow_contract_evidence.tar.gz" in names


def test_exact_twenty_one_release_asset_semantics_remain_unchanged(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names(VERSION)

    assert len(names) == 21
    assert "Source code (zip)" not in names
    assert "Source code (tar.gz)" not in names
    assert not any(name.endswith(".sha256") for name in names)


def test_release_workflow_has_no_hard_coded_v024_path(repo_root: Path) -> None:
    release_workflow = _read(repo_root / ".github/workflows/release.yml")

    assert f"releases/{VERSION}" not in release_workflow
    assert f"releases\\{VERSION}" not in release_workflow
    assert f"v{VERSION}" not in release_workflow
