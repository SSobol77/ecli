# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_project_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for Phase 1 ProjectService workspace discovery."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from ecli.services.config_service import ConfigService
from ecli.services.project_service import ProjectService, UnsafeProjectPathError


PYPROJECT_CONTENT = '[project]\nname = "demo"\n'


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-project-service"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def snapshot_tree(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def test_discovers_root_from_git_marker(workspace: Path) -> None:
    project = workspace / "repo"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    (project / ".git").mkdir()

    discovery = ProjectService.discover(nested)

    assert discovery.discovered is True
    assert discovery.root == project.resolve(strict=False)
    assert discovery.metadata.vcs == "git"
    assert discovery.metadata.markers == (".git",)


def test_discovers_root_from_pyproject_marker(workspace: Path) -> None:
    project = workspace / "python-repo"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")

    discovery = ProjectService.discover(nested)

    assert discovery.discovered is True
    assert discovery.root == project.resolve(strict=False)
    assert discovery.metadata.markers == ("pyproject.toml",)
    assert "python" in discovery.metadata.primary_language_hints


def test_falls_back_to_start_directory_when_no_marker_exists(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = workspace / "plain"
    start.mkdir()
    monkeypatch.setattr("ecli.services.project_service.PROJECT_MARKERS", ())

    discovery = ProjectService.discover(start)

    assert discovery.discovered is False
    assert discovery.root == start.resolve(strict=False)
    assert discovery.metadata.markers == ()


def test_start_path_file_uses_parent_directory(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = workspace / "standalone"
    directory.mkdir()
    source_file = directory / "main.py"
    source_file.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr("ecli.services.project_service.PROJECT_MARKERS", ())

    discovery = ProjectService.discover(source_file)

    assert discovery.discovered is False
    assert discovery.root == directory.resolve(strict=False)


def test_project_local_ecli_toml_is_detected(workspace: Path) -> None:
    project = workspace / "repo"
    project.mkdir()
    project_config = project / ".ecli.toml"
    project_config.write_text("[editor]\ntab_size = 2\n", encoding="utf-8")

    discovery = ProjectService.discover(project)
    service = ProjectService.from_discovery(discovery)

    assert discovery.discovered is True
    assert discovery.metadata.markers == (".ecli.toml",)
    assert service.get_project_config_path() == project_config.resolve(strict=False)


def test_resolve_path_resolves_relative_path_against_project_root(
    workspace: Path,
) -> None:
    project = workspace / "repo"
    project.mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    service = ProjectService.from_discovery(ProjectService.discover(project))

    resolved = service.resolve_path("src/main.py")

    assert resolved == (project / "src" / "main.py").resolve(strict=False)


def test_resolve_path_safe_allows_paths_inside_root(workspace: Path) -> None:
    project = workspace / "repo"
    inside = project / "src"
    inside.mkdir(parents=True)
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    service = ProjectService.from_discovery(ProjectService.discover(project))

    resolved = service.resolve_path_safe("src/module.py")

    assert resolved == (project / "src" / "module.py").resolve(strict=False)


def test_resolve_path_safe_rejects_parent_escape(workspace: Path) -> None:
    project = workspace / "repo"
    project.mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    service = ProjectService.from_discovery(ProjectService.discover(project))

    with pytest.raises(UnsafeProjectPathError):
        service.resolve_path_safe("../outside.txt")


@pytest.mark.parametrize(
    "unsafe_path",
    ["~/secret", "$HOME/secret", "${HOME}/secret", "$(pwd)/secret", "`pwd`/secret"],
)
def test_resolve_path_safe_rejects_shell_expansion(
    workspace: Path,
    unsafe_path: str,
) -> None:
    project = workspace / "repo"
    project.mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    service = ProjectService.from_discovery(ProjectService.discover(project))

    with pytest.raises(UnsafeProjectPathError):
        service.resolve_path_safe(unsafe_path)


def test_symlink_escape_is_rejected_when_supported(workspace: Path) -> None:
    project = workspace / "repo"
    outside = workspace / "outside"
    project.mkdir()
    outside.mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    link = project / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation is not supported: {exc}")

    service = ProjectService.from_discovery(ProjectService.discover(project))

    with pytest.raises(UnsafeProjectPathError):
        service.resolve_path_safe("link/secret.txt")


def test_metadata_includes_name_root_markers_vcs_and_language_hints(
    workspace: Path,
) -> None:
    project = workspace / "metadata-repo"
    project.mkdir()
    (project / ".git").mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT_CONTENT, encoding="utf-8")
    (project / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (project / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")

    discovery = ProjectService.discover(project)

    assert discovery.metadata.name == "metadata-repo"
    assert discovery.metadata.root == project.resolve(strict=False)
    assert discovery.metadata.markers == ("pyproject.toml", ".git")
    assert discovery.metadata.vcs == "git"
    assert discovery.metadata.primary_language_hints == ("python", "make", "docker")


def test_discovery_does_not_mutate_filesystem(workspace: Path) -> None:
    project = workspace / "repo"
    nested = project / "src"
    nested.mkdir(parents=True)
    (project / ".git").mkdir()
    before = snapshot_tree(workspace)

    ProjectService.discover(nested)

    assert snapshot_tree(workspace) == before
    assert not (project / ".ecli").exists()


def test_test_workspaces_are_under_logs(workspace: Path) -> None:
    logs_dir = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_dir)


def test_get_effective_config_is_conservative_until_registry_integration(
    workspace: Path,
) -> None:
    project = workspace / "repo"
    project.mkdir()
    (project / ".ecli.toml").write_text("[editor]\ntab_size = 2\n", encoding="utf-8")
    user_config = ConfigService(ConfigService.load(env={}).config)
    service = ProjectService.from_discovery(ProjectService.discover(project))

    effective = service.get_effective_config(user_config)

    assert effective is user_config
    assert any(
        diagnostic.code == "project.config.integration_deferred"
        for diagnostic in service.diagnostics
    )
