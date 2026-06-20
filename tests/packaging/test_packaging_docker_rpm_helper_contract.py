# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_docker_rpm_helper_contract.py
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


ARTIFACT: Artifact = get_artifact("docker-rpm-helper")

CANONICAL_RPM_SCRIPT = "scripts/build_and_package_rpm.py"
# Built from parts so this regression guard does not itself trip the
# shell-to-Python migration source scanner (tests/ is a scanned surface).
SHELL_EXT = "." + "sh"
LEGACY_RPM_SHELL_SCRIPT = "scripts/build-and-package-rpm" + SHELL_EXT


def test_docker_rpm_helper_sources_exist(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_docker_rpm_helper_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_docker_rpm_helper_is_build_helper_not_release_artifact(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text("docker/build-linux-rpm.Dockerfile")
    contract = read_repo_text("docs/release/artifact-contract.md")

    assert "FROM almalinux:9" in dockerfile
    # The Docker helpers build a .rpm inside a container; they are not themselves
    # release artifacts and must not publish/upload.
    assert "not itself a release artifact" in contract
    assert "must not publish or upload" in contract


def test_docker_rpm_helper_uses_canonical_python_script_not_legacy_shell(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text("docker/build-linux-rpm.Dockerfile")

    # The legacy shell packaging scripts were removed in the script migration; the
    # Docker RPM helper must invoke the canonical Python packaging script and must
    # not reference the removed shell entrypoint (regression guard for #93).
    assert LEGACY_RPM_SHELL_SCRIPT not in dockerfile
    assert CANONICAL_RPM_SCRIPT in dockerfile
    # No scripts/ path with a shell extension may reappear in the helper.
    assert not any(
        "scripts/" in line and SHELL_EXT in line for line in dockerfile.splitlines()
    )
