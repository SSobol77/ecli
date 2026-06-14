# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_windows_nsis_installer_contract.py
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


ARTIFACT: Artifact = get_artifact("windows-nsis-installer")


def test_windows_nsis_installer_sources_exist(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_windows_nsis_installer_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_windows_nsis_installer_descriptor_and_validation(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    nsi = read_repo_text("packaging/windows/nsis/ecli.nsi")
    validate = read_repo_text(".github/workflows/windows-validate.yml")

    assert_tokens_present(nsi, ["ecli_${VERSION}_win_x86_64_setup.exe", "OutFile"])
    assert "Windows Contract Validate" in validate
