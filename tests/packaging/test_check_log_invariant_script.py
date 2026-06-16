# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_check_log_invariant_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/check_log_invariant.py against a temp git repo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def check_log_invariant(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/check_log_invariant.py", "check_log_invariant"
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Isolate git config so global excludes do not perturb --exclude-standard.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "logs").mkdir()
    (repo / "logs" / ".gitkeep").write_text("", encoding="utf-8")
    monkeypatch.chdir(repo)
    return repo


def test_clean_repo_satisfies_invariant(
    check_log_invariant: ModuleType, git_repo: Path
) -> None:
    (git_repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (git_repo / "logs" / "run.log").write_text("ok\n", encoding="utf-8")
    assert check_log_invariant.main([]) == 0


def test_untracked_log_outside_logs_fails(
    check_log_invariant: ModuleType, git_repo: Path
) -> None:
    (git_repo / "debug.log").write_text("oops\n", encoding="utf-8")
    assert check_log_invariant.main([]) == 1


def test_untracked_evidence_prefix_outside_logs_fails(
    check_log_invariant: ModuleType, git_repo: Path
) -> None:
    (git_repo / "dry-run-evidence").write_text("x\n", encoding="utf-8")
    assert check_log_invariant.main([]) == 1


def test_forbidden_runtime_dir_fails(
    check_log_invariant: ModuleType, git_repo: Path
) -> None:
    (git_repo / ".ecli").mkdir()
    (git_repo / ".ecli" / "state").write_text("x\n", encoding="utf-8")
    assert check_log_invariant.main([]) == 1


def test_tracked_generated_artifact_fails(
    check_log_invariant: ModuleType, git_repo: Path
) -> None:
    pid_file = git_repo / "server.pid"
    pid_file.write_text("123\n", encoding="utf-8")
    _git(git_repo, "add", "server.pid")
    assert check_log_invariant.main([]) == 1
