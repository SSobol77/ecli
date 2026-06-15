# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_macos_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_macos.py (no real build)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def macos(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_macos.py", "macos_build"
    )


def test_constants(macos: ModuleType) -> None:
    assert macos.APP_NAME == "ECLI"
    assert macos.MACOS_ARCH == "universal2"
    assert macos.EXIT_DMG_MISSING == 2
    assert macos.EXIT_SHA_MISSING == 3
    assert macos.EXIT_MISSING_TOOL == 5


def test_non_darwin_returns_error(
    macos: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(macos.platform, "system", lambda: "Linux")
    assert macos.main([]) == macos.EXIT_ERROR


def test_info_plist_embeds_version(macos: ModuleType) -> None:
    plist = macos.info_plist("3.1.4", "")
    assert "<string>3.1.4</string>" in plist
    assert "io.ecli.editor" in plist


def test_dmg_artifact_token(macos: ModuleType, repo_root: Path) -> None:
    version = macos.read_version(repo_root)
    assert f"ecli_{version}_macos_universal2.dmg".endswith("macos_universal2.dmg")
