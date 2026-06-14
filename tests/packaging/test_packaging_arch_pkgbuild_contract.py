# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_arch_pkgbuild_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

from pathlib import Path

from conftest import (
    Artifact,
    PathAssertion,
    RepoReader,
    TokenAssertion,
    assert_artifact_documented,
    get_artifact,
)


ARTIFACT: Artifact = get_artifact("arch-pkgbuild")


def test_arch_pkgbuild_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_arch_pkgbuild_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_arch_pkgbuild_is_under_packaging_not_repo_root(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    # The Arch contract must check packaging/arch/PKGBUILD, never a root PKGBUILD.
    assert not (repo_root / "PKGBUILD").exists()
    assert (repo_root / "packaging/arch/PKGBUILD").is_file()
    assert "pkgname=ecli-editor" in read_repo_text("packaging/arch/PKGBUILD")
