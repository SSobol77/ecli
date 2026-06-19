# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_linux_packaging_metadata.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Static checks for Linux packaging metadata added for v0.2.x."""

from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def test_linux_packaging_support_files_exist() -> None:
    required_paths = [
        "packaging/arch/PKGBUILD",
        "packaging/nix/package.nix",
        "flake.nix",
        "scripts/build_and_package_arch.py",
        "scripts/build_and_package_opensuse_rpm.py",
        "scripts/build_and_package_slackware.py",
    ]

    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_new_packaging_python_entrypoints_are_canonical() -> None:
    scripts = [
        "scripts/build_and_package_arch.py",
        "scripts/build_and_package_opensuse_rpm.py",
        "scripts/build_and_package_slackware.py",
    ]

    for relative_path in scripts:
        script = (ROOT / relative_path).read_text(encoding="utf-8")
        assert script.startswith("#!/usr/bin/env python3"), relative_path
        assert "def main(" in script, relative_path


def test_packaging_metadata_documents_expected_artifact_names() -> None:
    arch_pkgbuild = (ROOT / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    # Canonical implementations are the Python entrypoints.
    arch_script = (ROOT / "scripts/build_and_package_arch.py").read_text(
        encoding="utf-8"
    )
    slackware_script = (ROOT / "scripts/build_and_package_slackware.py").read_text(
        encoding="utf-8"
    )
    opensuse_script = (ROOT / "scripts/build_and_package_opensuse_rpm.py").read_text(
        encoding="utf-8"
    )
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

    assert "pkgname=ecli-editor" in arch_pkgbuild
    assert "ecli_{version}_arch_{arch}.pkg.tar.zst" in arch_script
    assert "{PACKAGE_NAME}_{version}_slackware_{arch}.txz" in slackware_script
    assert '"RPM_PLATFORM_LABEL", "opensuse"' in opensuse_script
    assert 'systems = [ "x86_64-linux" "aarch64-linux" ];' in flake


def test_nix_metadata_tracks_project_version_and_gpl_license() -> None:
    """Nix surfaces must not drift from the release version or the GPL-2.0-only license."""
    version = _project_version()
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    package = (ROOT / "packaging/nix/package.nix").read_text(encoding="utf-8")

    # Version pins must track [project].version, with no stale 0.2.2 drift.
    assert f'version = "{version}";' in flake, flake
    assert f'version ? "{version}"' in package, package
    assert "0.2.2" not in flake
    assert "0.2.2" not in package

    # License metadata must be GPL-2.0-only, never Apache-2.0 / asl20.
    assert "gpl2Only" in package
    assert "asl20" not in package
    assert "apache" not in package.lower()


def test_release_docs_use_normalized_linux_package_names() -> None:
    doc_paths = [
        "README.md",
        "docs/INSTALL.md",
        "docs/contributor/install.md",
        "docs/contributor/build-from-source.md",
        "docs/install/windows.md",
        "docs/release/artifact-contract.md",
    ]
    docs = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in doc_paths)

    forbidden_package_examples = [
        "ecli_0.2.0_",
        "ecli_0.2.1_",
        "ecli-editor-0.2.0-1-",
        "ecli-editor-0.2.1-1-",
    ]
    for forbidden in forbidden_package_examples:
        assert forbidden not in docs

    assert "ecli_<version>_linux_x86_64.deb" in docs
    assert "ecli_<version>_linux_x86_64.rpm" in docs
    assert "ecli_<version>_opensuse_x86_64.rpm" in docs
    assert "ecli_<version>_arch_x86_64.pkg.tar.zst" in docs
    assert "ecli_<version>_slackware_x86_64.txz" in docs
    assert "ecli_<version>_linux_x86_64.AppImage" in docs

    assert "ecli-editor-<version>-1-<arch>.pkg.tar.zst" in docs
    assert "ecli_<version>_arch_<arch>.pkg.tar.zst" in docs
    assert "ecli_<version>_slackware_<arch>.txz" in docs


def test_install_docs_cover_suse_slackware_and_windows_dependencies() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install_docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in [
            "docs/INSTALL.md",
            "docs/contributor/install.md",
            "docs/install/windows.md",
        ]
    )

    assert "**SUSE/openSUSE runtime:**" in readme
    assert "sudo zypper install ncurses6 libyaml-0-2 xclip xsel" in readme
    assert "**Slackware:**" in readme
    assert "official Slackware series or SlackBuilds" in readme
    assert "**Windows:**" in readme
    assert "Prebuilt installer and portable `.exe` artifacts do not require" in readme

    assert "### SUSE / openSUSE" in install_docs
    assert "sudo zypper install ncurses6 libyaml-0-2 xclip xsel" in install_docs
    assert "### Slackware" in install_docs
    assert "official Slackware series or SlackBuilds" in install_docs
    assert "### Windows" in install_docs
    assert "PowerShell is used for checksum examples" in install_docs
    assert "Visual Studio Build Tools only" in install_docs
