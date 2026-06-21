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
from conftest import expected_release_artifact, load_script_module


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
    assert macos.ONIGURUMA_HEADER == "oniguruma.h"
    assert macos.ONIGURUMA_PKG_CONFIG_NAME == "oniguruma"


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
    expected = expected_release_artifact(
        repo_root, version, f"ecli_{version}_macos_{macos.MACOS_ARCH}.dmg"
    )
    assert expected.parent == repo_root / "releases" / version
    assert expected.name == f"ecli_{version}_macos_{macos.MACOS_ARCH}.dmg"


def test_oniguruma_env_adds_include_lib_and_pkg_config_paths(
    macos: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "oniguruma"
    (prefix / "include").mkdir(parents=True)
    (prefix / "lib" / "pkgconfig").mkdir(parents=True)
    (prefix / "lib" / "pkgconfig" / "oniguruma.pc").write_text("", encoding="utf-8")
    (prefix / "include" / "oniguruma.h").write_text("", encoding="utf-8")
    (prefix / "lib" / "libonig.dylib").write_text("", encoding="utf-8")
    monkeypatch.setenv("ECLI_ONIGURUMA_PREFIX", str(prefix))
    monkeypatch.setattr(macos, "_capture_stdout", lambda _command: None)

    env = macos.macos_native_dependency_env({})

    assert f"-I{prefix / 'include'}" in env["CPPFLAGS"]
    assert f"-I{prefix / 'include'}" in env["CFLAGS"]
    assert f"-L{prefix / 'lib'}" in env["LDFLAGS"]
    assert str(prefix / "lib" / "pkgconfig") in env["PKG_CONFIG_PATH"]


def test_macos_workflows_install_oniguruma_before_build(repo_root: Path) -> None:
    for relative in (
        ".github/workflows/macos-dmg.yml",
        ".github/workflows/macos-validate.yml",
    ):
        text = (repo_root / relative).read_text(encoding="utf-8")
        assert "brew install oniguruma pkg-config" in text
