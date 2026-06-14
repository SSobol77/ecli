# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_appimage_contract.py
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


ARTIFACT: Artifact = get_artifact("appimage")


def test_appimage_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_appimage_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_appimage_script_uses_canonical_naming(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    script = read_repo_text("scripts/package_appimage.sh")
    assert_tokens_present(script, ["ecli_${VERSION}_linux_${ARCH}.AppImage"])

def test_appimage_generated_staging_paths_are_not_release_contract_surfaces(
    read_repo_text: RepoReader,
) -> None:
    forbidden_tokens = [
        "AppDirpackaging",
        "packaging/linux/appimage/AppDirpackaging",
    ]

    checked_files = [
        "docs/release/artifact-contract.md",
        "docs/release/build-matrix.md",
        "docs/release/packaging-flows.md",
        ".claude/commands/package-linux.md",
        ".codex/prompts/package-linux.md",
        "tests/packaging/conftest.py",
    ]

    for relative_path in checked_files:
        text = read_repo_text(relative_path)
        for token in forbidden_tokens:
            assert token not in text, f"{relative_path} must not contract generated staging path {token}"
