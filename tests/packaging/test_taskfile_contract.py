# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_taskfile_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import re
from pathlib import Path

from conftest import CANONICAL_ARTIFACTS, RepoReader


REQUIRED_TASKS = (
    "help",
    "install",
    "run",
    "validate",
    "validate-fast",
    "validate-full",
    "validate-packaging",
    "doctor",
    "show-artifacts",
    "clean",
    "package-pypi",
    "package-linux",
    "package-freebsd",
    "package-macos",
    "package-windows",
    "package-nix",
    "publish-pypi",
    "publish-all",
    "release-linux",
    "release-freebsd",
    "release-macos",
    "release-windows",
    "release-pypi",
)

EXPECTED_MAKE_WRAPPERS = {
    "help": ("make help",),
    "install": ("make install",),
    "run": ("make run",),
    "validate": ("make validate",),
    "validate-fast": ("make validate-fast",),
    "validate-full": ("make validate-full",),
    "validate-packaging": ("make validate-packaging",),
    "doctor": ("make doctor",),
    "show-artifacts": ("make show-artifacts",),
    "clean": ("make clean",),
    "package-pypi": ("make package-pypi",),
    "package-linux": ("make package-linux",),
    "package-freebsd": ("make package-freebsd",),
    "package-macos": ("make package-macos",),
    "package-windows": ("make package-windows",),
    "package-nix": ("make package-nix",),
    "publish-pypi": ("make publish-pypi",),
    "publish-all": ("make publish-all",),
    "release-linux": (
        "make release-deb",
        "make release-rpm",
        "make release-appimage",
    ),
    "release-freebsd": ("make release-freebsd",),
    "release-macos": ("make release-macos",),
    "release-windows": ("make release-windows",),
    "release-pypi": ("make publish-pypi",),
}

FORBIDDEN_DIRECT_RELEASE_TOKENS = (
    "gh release",
    "gh workflow",
    "git push",
    "git tag",
    "twine upload",
    "uv publish",
    "python -m twine upload",
)


def _task_block(taskfile: str, task_name: str) -> str:
    pattern = re.compile(
        rf"^  {re.escape(task_name)}:\n"
        rf"(?P<body>(?:    .*(?:\n|$)|\n)+)",
        re.MULTILINE,
    )
    match = pattern.search(taskfile)
    assert match is not None, f"missing task: {task_name}"
    return match.group("body")


def test_taskfile_exists(repo_root: Path) -> None:
    taskfile = repo_root / "Taskfile.yml"

    assert taskfile.is_file()
    assert taskfile.stat().st_size > 0


def test_taskfile_declares_makefile_as_authoritative(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")

    assert "Makefile remains the authoritative build/release contract" in taskfile
    assert 'version: "3"' in taskfile


def test_taskfile_contains_required_developer_tasks(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")

    for task_name in REQUIRED_TASKS:
        _task_block(taskfile, task_name)


def test_taskfile_references_canonical_make_targets(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")
    makefile = read_repo_text("Makefile")

    for task_name, commands in EXPECTED_MAKE_WRAPPERS.items():
        task = _task_block(taskfile, task_name)
        for command in commands:
            assert command in task
            target = command.removeprefix("make ")
            assert re.search(rf"^\.PHONY: .*{re.escape(target)}", makefile, re.M)
            assert re.search(rf"^{re.escape(target)}:", makefile, re.M)


def test_taskfile_does_not_reference_shell_wrappers_or_scripts_sh(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")

    assert "scripts/" not in taskfile
    assert ".sh" not in taskfile


def test_taskfile_does_not_bypass_guarded_release_or_publish_targets(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")

    for token in FORBIDDEN_DIRECT_RELEASE_TOKENS:
        assert token not in taskfile

    release_tasks = (
        "release-linux",
        "release-freebsd",
        "release-macos",
        "release-windows",
        "publish-all",
    )
    for task_name in release_tasks:
        task = _task_block(taskfile, task_name)
        assert "make release-" in task or "make publish-all" in task

    assert "make publish-pypi" in _task_block(taskfile, "publish-pypi")
    assert "make publish-pypi" in _task_block(taskfile, "release-pypi")


def test_taskfile_does_not_redefine_artifact_names(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")

    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.artifact_token not in taskfile
    assert "ecli_<version>" not in taskfile
    assert "releases/<version>" not in taskfile


def test_taskfile_does_not_become_sole_release_contract(
    read_repo_text: RepoReader,
) -> None:
    taskfile = read_repo_text("Taskfile.yml")
    docs = "\n".join(
        read_repo_text(path)
        for path in (
            "README.md",
            "docs/contributor/development-setup.md",
            "docs/contributor/local-validation.md",
            "docs/release/release-process.md",
            "docs/release/packaging-flows.md",
        )
    )

    assert "Makefile.yml" not in taskfile
    assert "Makefile remains the authoritative" in docs
    assert "Taskfile.yml" in docs
    assert "optional developer convenience" in docs
