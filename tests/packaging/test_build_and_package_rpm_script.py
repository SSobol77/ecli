# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_rpm_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_rpm.py command construction."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def rpm(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_rpm.py", "rpm_build"
    )


def test_env_defaults(rpm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RPM_DEPENDS", raising=False)
    assert rpm.env("RPM_DEPENDS", "ncurses-libs;libyaml") == "ncurses-libs;libyaml"
    monkeypatch.setenv("RPM_PLATFORM_LABEL", "opensuse")
    assert rpm.env("RPM_PLATFORM_LABEL", "linux") == "opensuse"


def test_fpm_rpm_command(rpm: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "ecli-1.0.0.rpm"
    cmd = rpm.build_fpm_command(
        tmp_path / "stage",
        "ecli",
        "1.0.0",
        "M <m@e>",
        "https://ecli.io",
        "GPL-2.0-only",
        "editors",
        ["ncurses-libs", "libyaml"],
        out,
    )
    assert cmd[:5] == ["fpm", "-s", "dir", "-t", "rpm"]
    assert "--rpm-os" in cmd and cmd[cmd.index("--rpm-os") + 1] == "linux"
    assert "--package" in cmd and cmd[cmd.index("--package") + 1] == str(out)
    assert cmd.count("--depends") == 2
    assert cmd[-1] == "usr"


def test_releases_dir_mismatch_returns_error(
    rpm: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RELEASES_DIR", "releases/does-not-match")
    assert rpm.main([]) == rpm.EXIT_ERROR


def test_normalized_arch(rpm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr(
        rpm.os, "uname", lambda: os.uname_result(("Linux", "h", "r", "v", "x86_64"))
    )
    assert rpm.normalized_arch() == "x86_64"
