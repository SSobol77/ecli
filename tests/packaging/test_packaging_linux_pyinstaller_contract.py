# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_linux_pyinstaller_contract.py
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


ARTIFACT: Artifact = get_artifact("linux-pyinstaller")


def test_linux_pyinstaller_sources_exist(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_linux_pyinstaller_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_linux_pyinstaller_uses_root_main_compatibility_shim(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    main_py = read_repo_text("main.py")
    spec = read_repo_text("packaging/pyinstaller/ecli.spec")
    # Canonical implementation is the Python entrypoint.
    linux_script = read_repo_text("scripts/build_pyinstaller_linux.py")

    assert_tokens_present(
        main_py, ["from ecli.__main__ import main", "SystemExit(main())"]
    )
    assert_tokens_present(
        spec, ['entry_point = project_root / "main.py"', "runtime_hooks"]
    )
    assert_tokens_present(
        linux_script,
        ['MAIN_SCRIPT = "main.py"', 'Path("packaging/pyinstaller/ecli.spec")'],
    )
