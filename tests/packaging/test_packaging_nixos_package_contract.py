# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_nixos_package_contract.py
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


ARTIFACT: Artifact = get_artifact("nixos-package")


def test_nixos_package_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_nixos_package_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_nixos_package_expression_builds_ecli_main_program(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    package = read_repo_text("packaging/nix/package.nix")
    assert_tokens_present(
        package,
        [
            'pname = "ecli-editor";',
            'mainProgram = "ecli";',
            'platforms = [ "x86_64-linux" "aarch64-linux" ];',
        ],
    )
