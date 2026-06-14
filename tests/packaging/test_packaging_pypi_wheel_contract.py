# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_pypi_wheel_contract.py
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


ARTIFACT: Artifact = get_artifact("pypi-wheel")


def test_pypi_wheel_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_pypi_wheel_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_pypi_wheel_metadata_and_force_include(read_repo_text: RepoReader) -> None:
    pyproject = tomllib.loads(read_repo_text("pyproject.toml"))

    assert pyproject["project"]["name"] == "ecli-editor"
    assert pyproject["project"]["version"]
    assert pyproject["project"]["license"] == "GPL-2.0-only"
    assert pyproject["project"]["scripts"]["ecli"] == "ecli.__main__:main"

    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/ecli"]
    assert "src/ecli/assets/ecli.png" in wheel["force-include"]


def test_pypi_wheel_validation_workflow_is_mapped(read_repo_text: RepoReader) -> None:
    workflow = read_repo_text(".github/workflows/pypi-validate.yml")
    assert "py3-none-any.whl" in workflow or "*.whl" in workflow
