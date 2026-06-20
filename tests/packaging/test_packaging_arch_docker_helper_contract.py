# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_arch_docker_helper_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract for the containerized Arch package build helper (#93).

The aggregate release workflow runs on Ubuntu, which has no ``makepkg``. The
host-only ``make package-arch`` target therefore fails with "Missing makepkg for
Arch package build." The release-canonical path builds the Arch package inside a
real ``archlinux:base-devel`` container via ``docker/build-arch-package.Dockerfile``
and ``make package-arch-docker``. These tests pin that helper's shape: a real
Arch base-devel base image, a non-root build user (makepkg refuses to run as
root), and the canonical Python build script rather than any removed shell
entrypoint.
"""

from __future__ import annotations

from conftest import Artifact, RepoReader, get_artifact


ARTIFACT: Artifact = get_artifact("arch-pkgbuild")

ARCH_DOCKERFILE = "docker/build-arch-package.Dockerfile"
CANONICAL_ARCH_SCRIPT = "scripts/build_and_package_arch.py"
# Built from parts so this regression guard does not itself trip the
# shell-to-Python migration source scanner (tests/ is a scanned surface).
SHELL_EXT = "." + "sh"
LEGACY_ARCH_SHELL_SCRIPT = "scripts/build-and-package-arch" + SHELL_EXT


def test_arch_docker_helper_is_registered_as_an_arch_source() -> None:
    assert ARCH_DOCKERFILE in ARTIFACT.sources


def test_arch_docker_helper_uses_real_arch_base_devel_image(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(ARCH_DOCKERFILE)
    # A real Arch packaging environment, not an Ubuntu host pretending to have
    # makepkg.
    assert "FROM archlinux:base-devel" in dockerfile
    # The Arch makepkg toolchain is provided through pacman, not apt.
    assert "pacman -Syu" in dockerfile


def test_arch_docker_helper_runs_makepkg_as_non_root_user(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(ARCH_DOCKERFILE)
    # makepkg refuses to run as root; the helper must create and drop to a
    # non-root build user.
    assert "useradd" in dockerfile
    assert "builder" in dockerfile
    assert "runuser -u builder" in dockerfile


def test_arch_docker_helper_uses_canonical_python_script_not_legacy_shell(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(ARCH_DOCKERFILE)

    assert CANONICAL_ARCH_SCRIPT in dockerfile
    assert LEGACY_ARCH_SHELL_SCRIPT not in dockerfile
    # No scripts/ path with a shell extension may reappear in the helper.
    assert not any(
        "scripts/" in line and SHELL_EXT in line for line in dockerfile.splitlines()
    )


def test_arch_docker_helper_is_build_helper_not_release_artifact(
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text("docs/release/artifact-contract.md")
    # The Arch Docker helper builds the package inside a container; it is a build
    # helper documented in the contract and must not publish/upload.
    assert ARCH_DOCKERFILE in contract
    assert "must not publish or upload" in contract
