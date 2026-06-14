# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_freebsd_pkg_contract.py
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


ARTIFACT: Artifact = get_artifact("freebsd-pkg")


def test_freebsd_pkg_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_freebsd_pkg_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_freebsd_pkg_script_and_workflow_declare_pkg_artifact(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    script = read_repo_text("scripts/build-and-package-freebsd.sh")
    workflow = read_repo_text(".github/workflows/freebsd-pkg.yml")

    assert_tokens_present(script, ["ecli_<version>_freebsd_<arch>.pkg"])
    assert "FreeBSD" in workflow
    assert ".pkg" in workflow
