# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_opensuse_rpm_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_opensuse_rpm.py delegation."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def opensuse(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_opensuse_rpm.py", "opensuse_rpm"
    )


def test_delegates_to_rpm_with_opensuse_defaults(
    opensuse: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class _Result:
        returncode = 0

    def fake_run(cmd, env=None, check=False):  # noqa: ANN001, ANN202
        captured["cmd"] = cmd
        captured["env"] = env
        return _Result()

    monkeypatch.delenv("RPM_PLATFORM_LABEL", raising=False)
    monkeypatch.delenv("RPM_DEPENDS", raising=False)
    monkeypatch.setattr(opensuse.subprocess, "run", fake_run)

    assert opensuse.main([]) == 0
    cmd = captured["cmd"]
    assert str(cmd[-1]).endswith("build_and_package_rpm.py")
    env = captured["env"]
    assert env["RPM_PLATFORM_LABEL"] == "opensuse"
    assert env["RPM_DEPENDS"] == "libncurses6;libyaml-0-2"


def test_respects_preset_env(
    opensuse: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class _Result:
        returncode = 0

    def fake_run(cmd, env=None, check=False):  # noqa: ANN001, ANN202
        captured["env"] = env
        return _Result()

    monkeypatch.setenv("RPM_PLATFORM_LABEL", "suse-custom")
    monkeypatch.setattr(opensuse.subprocess, "run", fake_run)
    assert opensuse.main([]) == 0
    assert captured["env"]["RPM_PLATFORM_LABEL"] == "suse-custom"
