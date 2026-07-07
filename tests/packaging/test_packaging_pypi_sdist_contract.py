# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_pypi_sdist_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import tomllib

from conftest import (
    Artifact,
    PathAssertion,
    RepoReader,
    TokenAssertion,
    assert_artifact_documented,
    get_artifact,
)


ARTIFACT: Artifact = get_artifact("pypi-sdist")


def test_pypi_sdist_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_pypi_sdist_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_pypi_sdist_includes_main_shim_and_sources(read_repo_text: RepoReader) -> None:
    pyproject = tomllib.loads(read_repo_text("pyproject.toml"))

    sdist_include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    # The sdist must ship the root main.py compatibility shim and the package
    # sources so the PyInstaller contract can be rebuilt from a release sdist.
    assert "/main.py" in sdist_include
    assert "/src" in sdist_include
    assert "/pyproject.toml" in sdist_include


def test_pypi_sdist_upload_stays_maintainer_owned(read_repo_text: RepoReader) -> None:
    guard = read_repo_text("scripts/publish_pypi.py")
    assert "maintainer-owned" in guard
    assert "does **not** upload anything" in guard

    release_process = read_repo_text("docs/release/release-process.md")
    assert "twine upload" in release_process
