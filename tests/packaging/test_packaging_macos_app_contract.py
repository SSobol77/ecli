# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_macos_app_contract.py
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


ARTIFACT: Artifact = get_artifact("macos-app")


def test_macos_app_sources_exist(assert_paths_non_empty: PathAssertion) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_macos_app_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_macos_app_uses_root_main_shim_and_app_bundle(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    # macOS .app still builds through the shared PyInstaller spec and the root
    # main.py compatibility shim — not a package-only entry point.
    main_py = read_repo_text("main.py")
    # Canonical implementation is the Python entrypoint.
    macos_script = read_repo_text("scripts/build_and_package_macos.py")
    spec = read_repo_text("packaging/pyinstaller/ecli.spec")

    assert "from ecli.__main__ import main" in main_py
    assert 'APP_NAME = "ECLI"' in macos_script
    assert_tokens_present(spec, ['entry_point = project_root / "main.py"'])
