# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_release_asset_count_gate.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Exact 21 GitHub Release asset gate tests."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, load_script_module


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


def _write_assets(directory: Path, names: tuple[str, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(f"{name}\n", encoding="utf-8")


def test_expected_canonical_list_has_exactly_twenty_one_versioned_assets(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names("7.6.5")

    assert len(names) == 21
    assert len(set(names)) == 21
    assert all("7.6.5" in name for name in names)
    assert names == tuple(sorted(names))


@pytest.mark.parametrize(
    "token",
    [
        "10_appimage__ecli_7.6.5_linux_x86_64.AppImage",
        "07_opensuse__ecli_7.6.5_opensuse_x86_64.rpm",
        "08_arch__ecli_7.6.5_arch_x86_64.pkg.tar.zst",
        "09_slackware__ecli_7.6.5_slackware_x86_64.txz",
        "11_freebsd_pkg__ecli_7.6.5_freebsd_x86_64.pkg",
        "12_freebsd_ports_chroot__ecli_7.6.5_freebsd_ports_chroot_evidence.tar.gz",
        "13_macos_app__ecli_7.6.5_macos_universal2_app_evidence.tar.gz",
        "14_macos_dmg__ecli_7.6.5_macos_universal2.dmg",
        "15_windows_portable__ecli_7.6.5_win_x86_64.exe",
        "16_windows_nsis__ecli_7.6.5_win_x86_64_setup.exe",
        "17_nix_flake__ecli_7.6.5_nix_flake_evidence.tar.gz",
        "18_nixos_package__ecli_7.6.5_nixos_package_evidence.tar.gz",
        "19_docker_deb_helper__ecli_7.6.5_docker_deb_helper_evidence.tar.gz",
        "20_docker_rpm_helper__ecli_7.6.5_docker_rpm_helper_evidence.tar.gz",
        "21_workflow_contract__ecli_7.6.5_workflow_contract_evidence.tar.gz",
    ],
)
def test_expected_list_includes_every_mandatory_surface(
    release_assets: ModuleType,
    token: str,
) -> None:
    assert token in release_assets.expected_asset_names("7.6.5")


def test_valid_temp_release_dir_with_exact_assets_passes(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    (tmp_path / ".checksums").mkdir()

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_OK
    )


@pytest.mark.parametrize(
    "missing_token",
    [
        "01_pypi_wheel__",
        "02_pypi_sdist__",
        "03_linux_pyinstaller__",
        "04_linux_tarball__",
        "05_debian__",
        "06_rpm__",
        "07_opensuse__",
        "08_arch__",
        "09_slackware__",
        "10_appimage__",
        "11_freebsd_pkg__",
        "12_freebsd_ports_chroot__",
        "13_macos_app__",
        "14_macos_dmg__",
        "15_windows_portable__",
        "16_windows_nsis__",
        "17_nix_flake__",
        "18_nixos_package__",
        "19_docker_deb_helper__",
        "20_docker_rpm_helper__",
        "21_workflow_contract__",
    ],
)
def test_missing_mandatory_surface_fails(
    release_assets: ModuleType,
    tmp_path: Path,
    missing_token: str,
) -> None:
    names = tuple(
        name
        for name in release_assets.expected_asset_names("1.2.3")
        if not name.startswith(missing_token)
    )
    _write_assets(tmp_path, names)

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_extra_file_fails(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "unexpected.txt").write_text("extra\n", encoding="utf-8")

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_unexpected_top_level_directory_fails(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "unexpected-directory").mkdir()

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_twenty_files_fail(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3")[:-1])

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_twenty_two_files_fail(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "22_extra__ecli_1.2.3_extra.tar.gz").write_text(
        "extra\n", encoding="utf-8"
    )

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_top_level_sha256_sidecar_fails_as_extra_asset(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    (tmp_path / f"{names[0]}.sha256").write_text("0" * 64 + f"  {names[0]}\n")

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_checksums_directory_is_allowed(release_assets: ModuleType, tmp_path: Path) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    checksums = tmp_path / ".checksums"
    checksums.mkdir()
    (checksums / f"{names[0]}.sha256").write_text(
        "0" * 64 + f"  {names[0]}\n",
        encoding="utf-8",
    )

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_OK
    )


def test_makefile_and_release_workflow_call_exact_asset_verifier(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    release_workflow = read_repo_text(".github/workflows/release.yml")

    assert "validate-release-assets" in makefile
    assert "scripts/verify_release_assets.py" in release_workflow
    assert "files: releases/${{ steps.release_meta.outputs.version }}/[0-9][0-9]_*" in (
        release_workflow
    )
    assert "fail_on_unmatched_files: true" in release_workflow


def test_release_workflow_does_not_allow_official_freebsd_deferral(
    read_repo_text: RepoReader,
) -> None:
    release_workflow = read_repo_text(".github/workflows/release.yml")
    freebsd_workflow = read_repo_text(".github/workflows/freebsd-pkg.yml")

    forbidden_tokens = (
        "continue-on-error" + ": true",
        "freebsd" + "_note",
        "fail_on_unmatched_files" + ": false",
        "release" + "_tag",
    )
    for token in forbidden_tokens:
        assert token not in release_workflow
        assert token not in freebsd_workflow

    assert "gh release upload" not in freebsd_workflow
    assert "validation evidence only" in freebsd_workflow


def test_release_docs_state_exact_physical_asset_rule(
    read_repo_text: RepoReader,
) -> None:
    release_docs = "\n".join(
        read_repo_text(path)
        for path in (
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
            "docs/release/release-checklist.md",
            "docs/release/build-matrix.md",
            "docs/release/packaging-flows.md",
            "docs/release/v0.2.3.md",
        )
    )

    assert "exactly 21 physical GitHub Release assets" in release_docs
    assert "scripts/verify_release_assets.py" in release_docs
    assert ".checksums/" in release_docs
    assert "12_freebsd_ports_chroot__ecli_<version>" in release_docs
    assert "21_workflow_contract__ecli_<version>" in release_docs
