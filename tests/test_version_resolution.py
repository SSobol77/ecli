# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/test_version_resolution.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for source-tree and installed-package version resolution."""

from __future__ import annotations

import shutil
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Iterator

import pytest

import ecli


@pytest.fixture
def version_workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    logs_root = Path.cwd() / "logs" / "test-version-resolution"
    test_root = logs_root / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def package_file_under(root: Path) -> Path:
    package_dir = root / "src" / "ecli"
    package_dir.mkdir(parents=True)
    package_file = package_dir / "__init__.py"
    package_file.write_text("# test package marker\n", encoding="utf-8")
    return package_file


def test_source_tree_version_resolves_from_pyproject(version_workspace: Path) -> None:
    package_file = package_file_under(version_workspace)
    (version_workspace / "pyproject.toml").write_text(
        '[project]\nversion = "9.8.7"\n',
        encoding="utf-8",
    )

    assert ecli._source_tree_version(package_file) == "9.8.7"


def test_source_tree_version_returns_none_when_pyproject_is_missing(
    version_workspace: Path,
) -> None:
    package_file = package_file_under(version_workspace)

    assert ecli._source_tree_version(package_file) is None


def test_source_tree_version_returns_none_for_malformed_pyproject(
    version_workspace: Path,
) -> None:
    package_file = package_file_under(version_workspace)
    (version_workspace / "pyproject.toml").write_text(
        "[project\nversion = broken\n",
        encoding="utf-8",
    )

    assert ecli._source_tree_version(package_file) is None


def test_source_tree_version_returns_none_when_project_version_is_missing(
    version_workspace: Path,
) -> None:
    package_file = package_file_under(version_workspace)
    (version_workspace / "pyproject.toml").write_text(
        '[project]\nname = "ecli-editor"\n',
        encoding="utf-8",
    )

    assert ecli._source_tree_version(package_file) is None


def test_source_tree_version_returns_none_for_non_string_version(
    version_workspace: Path,
) -> None:
    package_file = package_file_under(version_workspace)
    (version_workspace / "pyproject.toml").write_text(
        "[project]\nversion = 123\n",
        encoding="utf-8",
    )

    assert ecli._source_tree_version(package_file) is None


def test_resolve_version_falls_back_to_installed_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ecli, "_source_tree_version", lambda: None)
    monkeypatch.setattr(ecli, "_bundled_version", lambda: None)
    monkeypatch.setattr(ecli, "_installed_package_version", lambda: "1.2.3")

    assert ecli._resolve_version() == "1.2.3"


def test_resolve_version_uses_pyinstaller_bundle_metadata(
    version_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (version_workspace / "pyproject.toml").write_text(
        '[project]\nversion = "7.6.5"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ecli, "_source_tree_version", lambda: None)
    monkeypatch.setattr(ecli.sys, "_MEIPASS", str(version_workspace), raising=False)

    assert ecli._resolve_version() == "7.6.5"


def test_installed_package_version_returns_none_when_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_distribution(_: str) -> str:
        raise PackageNotFoundError("ecli-editor")

    monkeypatch.setattr(ecli, "version", missing_distribution)

    assert ecli._installed_package_version() is None


def test_resolve_version_falls_back_to_local_when_metadata_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ecli, "_source_tree_version", lambda: None)
    monkeypatch.setattr(ecli, "_bundled_version", lambda: None)
    monkeypatch.setattr(ecli, "_installed_package_version", lambda: None)

    assert ecli._resolve_version() == "0.0.0+local"


def test_version_workspace_stays_under_logs(version_workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert version_workspace.resolve(strict=False).is_relative_to(logs_root)
