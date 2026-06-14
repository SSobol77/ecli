# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_windows_portable_exe_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

from conftest import (
    Artifact,
    PathAssertion,
    RepoReader,
    TokenAssertion,
    assert_artifact_documented,
    get_artifact,
)


ARTIFACT: Artifact = get_artifact("windows-portable-exe")


def test_windows_portable_exe_sources_exist(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_windows_portable_exe_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_windows_portable_exe_uses_root_main_shim_and_naming(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    # Windows portable .exe still builds through the shared PyInstaller spec and
    # the root main.py compatibility shim.
    main_py = read_repo_text("main.py")
    ps1 = read_repo_text("scripts/build-and-package-windows.ps1")

    assert "from ecli.__main__ import main" in main_py
    assert_tokens_present(ps1, ["ecli_${version}_win_${winArch}.exe"])
