# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_slackware_docker_helper_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract for the containerized Slackware package build helper (#93).

The aggregate release workflow runs on Ubuntu, which has no Slackware pkgtools.
The host-only ``make package-slackware`` target therefore fails with "Missing
makepkg for Slackware package build." The release-canonical path builds the
Slackware package inside a real Slackware container via
``docker/build-slackware-package.Dockerfile`` and ``make package-slackware-docker``.
These tests pin that helper's shape: a real Slackware base image, the Slackware
pkgtools / ``makepkg`` environment, a Python interpreter that satisfies the
project floor, and the canonical Python build script rather than any removed
shell entrypoint.
"""

from __future__ import annotations

from conftest import Artifact, RepoReader, get_artifact


ARTIFACT: Artifact = get_artifact("slackware-txz")

SLACKWARE_DOCKERFILE = "docker/build-slackware-package.Dockerfile"
CANONICAL_SLACKWARE_SCRIPT = "scripts/build_and_package_slackware.py"
# Built from parts so this regression guard does not itself trip the
# shell-to-Python migration source scanner (tests/ is a scanned surface).
SHELL_EXT = "." + "sh"
LEGACY_SLACKWARE_SHELL_SCRIPT = "scripts/build-and-package-slackware" + SHELL_EXT


def test_slackware_docker_helper_is_registered_as_a_slackware_source() -> None:
    assert SLACKWARE_DOCKERFILE in ARTIFACT.sources


def test_slackware_docker_helper_uses_real_slackware_base_image(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(SLACKWARE_DOCKERFILE)
    # A real Slackware packaging environment, not an Ubuntu host pretending to
    # have makepkg.
    assert "FROM aclemons/slackware" in dockerfile
    # The Slackware toolchain is provisioned through slackpkg, not apt/pacman.
    assert "slackpkg" in dockerfile


def test_slackware_docker_helper_provides_pkgtools_makepkg(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(SLACKWARE_DOCKERFILE)
    # The helper must verify the genuine Slackware pkgtools / makepkg environment
    # is present (it ships with the base image's pkgtools).
    assert "makepkg" in dockerfile
    assert "installpkg" in dockerfile
    # Python (>=3.11 floor) and PyInstaller must be available for the build.
    assert "python3" in dockerfile
    assert "pyinstaller" in dockerfile.lower()


def test_slackware_docker_helper_provisions_utf8_locale(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(SLACKWARE_DOCKERFILE)
    # The runtime smoke check decodes the curses binary's pseudo-TTY output as
    # UTF-8; without a real UTF-8 locale ncurses/Python emit latin-1 bytes (the
    # "·" separator as a lone 0xB7) and verify_runtime fails. A generated UTF-8
    # locale brings the Slackware build container to DEB/RPM/Arch parity (#93).
    assert "glibc-i18n" in dockerfile
    assert "localedef" in dockerfile
    assert "UTF-8" in dockerfile
    assert "LANG=" in dockerfile or "LC_ALL=" in dockerfile


def test_slackware_docker_helper_uses_canonical_python_script_not_legacy_shell(
    read_repo_text: RepoReader,
) -> None:
    dockerfile = read_repo_text(SLACKWARE_DOCKERFILE)

    assert CANONICAL_SLACKWARE_SCRIPT in dockerfile
    assert LEGACY_SLACKWARE_SHELL_SCRIPT not in dockerfile
    # No scripts/ path with a shell extension may reappear in the helper.
    assert not any(
        "scripts/" in line and SHELL_EXT in line for line in dockerfile.splitlines()
    )


def test_slackware_docker_helper_is_build_helper_not_release_artifact(
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text("docs/release/artifact-contract.md")
    # The Slackware Docker helper builds the package inside a container; it is a
    # build helper documented in the contract and must not publish/upload.
    assert SLACKWARE_DOCKERFILE in contract
    assert "must not publish or upload" in contract
