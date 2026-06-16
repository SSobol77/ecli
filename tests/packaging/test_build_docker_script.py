# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_docker_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_docker.py command construction and guards."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def build_docker(repo_root: Path) -> ModuleType:
    return load_script_module(repo_root, "scripts/build_docker.py", "build_docker")


def test_build_image_command(build_docker: ModuleType) -> None:
    cmd = build_docker.build_image_command(no_cache=False, verbose=False)
    assert cmd[:2] == ["docker", "build"]
    assert "-t" in cmd and build_docker.IMAGE_NAME in cmd
    assert "-f" in cmd and build_docker.DOCKERFILE in cmd
    assert cmd[-1] == "--quiet"  # non-verbose appends --quiet
    assert "--no-cache" not in cmd


def test_build_image_command_no_cache_verbose(build_docker: ModuleType) -> None:
    cmd = build_docker.build_image_command(no_cache=True, verbose=True)
    assert "--no-cache" in cmd
    assert "--quiet" not in cmd


def test_docker_run_command_mounts(build_docker: ModuleType) -> None:
    cmd = build_docker.docker_run_command(Path("/work"))
    assert cmd[:2] == ["docker", "run"]
    assert "--rm" in cmd
    assert "/work:/app:rw" in cmd
    assert "/work/releases:/app/releases:rw" in cmd
    assert cmd[-1] == build_docker.IMAGE_NAME


def test_usage_error_exits_one(build_docker: ModuleType) -> None:
    with pytest.raises(SystemExit) as exc:
        build_docker.main(["--bogus-flag"])
    assert exc.value.code == build_docker.EXIT_ERROR


def test_missing_docker_returns_error(
    build_docker: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_docker.shutil, "which", lambda name: None)
    assert build_docker.main([]) == build_docker.EXIT_ERROR
