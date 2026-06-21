# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_macos_dmg_contract.py
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


ARTIFACT: Artifact = get_artifact("macos-dmg")


def test_macos_dmg_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_macos_dmg_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_macos_dmg_naming_and_validation_workflow(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    # Canonical implementation is the Python entrypoint.
    macos_script = read_repo_text("scripts/build_and_package_macos.py")
    validate = read_repo_text(".github/workflows/macos-validate.yml")

    assert_tokens_present(macos_script, ["ecli_<version>_macos_universal2.dmg"])
    assert_tokens_present(
        macos_script,
        [
            "ONIGURUMA_HEADER",
            "macos_native_dependency_env",
            "check_oniguruma_prerequisites",
            "CPPFLAGS",
            "LDFLAGS",
            "PKG_CONFIG_PATH",
        ],
    )
    assert "macOS Contract Validate" in validate
    assert "brew install oniguruma pkg-config" in validate
