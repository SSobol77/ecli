# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_freebsd_ports_chroot_contract.py
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


ARTIFACT: Artifact = get_artifact("freebsd-ports-chroot")


def test_freebsd_ports_chroot_sources_exist(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(ARTIFACT.sources)


def test_freebsd_ports_chroot_contract_is_documented(
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    assert_artifact_documented(
        ARTIFACT, read_repo_text, assert_paths_non_empty, assert_tokens_present
    )


def test_freebsd_ports_chroot_paths_and_make_targets(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    # Canonical implementation is the Python entrypoint.
    port_script = read_repo_text("scripts/build_freebsd_port.py")
    chroot_script = read_repo_text("tools/freebsd-chroot-build.sh")
    makefile = read_repo_text("Makefile")

    # Local port skeleton and chroot rootfs are distinct build paths from the CI
    # .pkg leg; both must remain present and wired into Makefile targets.
    assert "/usr/ports" in port_script
    assert "chroot" in chroot_script
    assert_tokens_present(
        makefile,
        ["package-freebsd-port:", "package-freebsd-chroot:"],
    )
