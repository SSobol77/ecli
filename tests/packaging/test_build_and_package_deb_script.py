# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_deb_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_deb.py command construction."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def deb(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_deb.py", "deb_build"
    )


def test_filename_arch(deb: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr(
        deb.filename_arch.__globals__["os"],
        "uname",
        lambda: os.uname_result(("Linux", "h", "r", "v", "aarch64")),
    )
    assert deb.filename_arch() == "arm64"


def test_fpm_command_naming_and_deps(deb: ModuleType, tmp_path: Path) -> None:
    final = tmp_path / "releases" / "1.2.3" / "ecli_1.2.3_linux_x86_64.deb"
    cmd = deb.build_fpm_command(tmp_path / "stage", "1.2.3", final)
    assert cmd[:5] == ["fpm", "-s", "dir", "-t", "deb"]
    assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "amd64"
    assert "--package" in cmd and cmd[cmd.index("--package") + 1] == str(final)
    # Dependency set is preserved exactly.
    for dep in deb.DEB_DEPENDS:
        assert dep in cmd
    assert cmd[-1] == "usr"


def test_man_page_and_desktop(deb: ModuleType) -> None:
    man = deb.man_page("9.9.9")
    assert ".TH ECLI 1" in man
    assert "ecli 9.9.9" in man
    desktop = deb.desktop_entry()
    assert "Exec=ecli" in desktop and "Terminal=true" in desktop


def test_find_executable_missing(deb: ModuleType, tmp_path: Path) -> None:
    assert deb.find_executable(tmp_path) is None
