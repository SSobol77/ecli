# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_pyinstaller_linux_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_pyinstaller_linux.py (no real build)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def builder(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_pyinstaller_linux.py", "build_pyinstaller_linux"
    )


def test_build_pyi_args_includes_present_data(
    builder: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "config.toml").write_text("x", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("x", encoding="utf-8")
    args = builder.build_pyi_args(tmp_path)
    assert args[:4] == ["--onefile", "--clean", "--noconfirm", "--strip"]
    assert "config.toml:." in args
    assert "pyproject.toml:." in args


def test_build_pyi_args_skips_absent_data(builder: ModuleType, tmp_path: Path) -> None:
    args = builder.build_pyi_args(tmp_path)
    assert "config.toml:." not in args
    assert args == ["--onefile", "--clean", "--noconfirm", "--strip"]


def test_find_executable_onedir(builder: ModuleType, tmp_path: Path) -> None:
    onedir = tmp_path / "dist" / "ecli" / "ecli"
    onedir.parent.mkdir(parents=True)
    onedir.write_text("bin", encoding="utf-8")
    assert builder.find_executable(tmp_path) == onedir


def test_find_executable_missing(builder: ModuleType, tmp_path: Path) -> None:
    assert builder.find_executable(tmp_path) is None


def test_require_tool_and_module(
    builder: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(builder.shutil, "which", lambda name: None)
    assert builder.require_tool("pyinstaller") is False
    assert builder.require_python_module("definitely_not_a_real_module_xyz") is False
