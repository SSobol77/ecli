# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_linux_tarball_contract.py
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


ARTIFACT: Artifact = get_artifact("linux-tarball")


def test_linux_tarball_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_linux_tarball_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_linux_tarball_makefile_naming_and_targets(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    makefile = read_repo_text("Makefile")
    assert_tokens_present(
        makefile,
        [
            "package-tar-linux:",
            "package-tar-linux-assert",
            "ecli_$(TAR_VERSION)_linux_$(LINUX_ARCH).tar.gz",
            "scripts/build_pyinstaller_linux.py",
            "verify_runtime.py",
        ],
    )
