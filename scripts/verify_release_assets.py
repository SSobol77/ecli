#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/verify_release_assets.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Verify the official ECLI 21-asset GitHub Release contract.

This verifier is intentionally separate from checksum verification. Official
release assets are the 21 top-level files named by ``expected_asset_names()``.
Checksum sidecars may be used during CI validation under
``releases/<version>/.checksums/``, but top-level ``.sha256`` files are not
GitHub Release assets and therefore make this verifier fail as extras.

The script is read-only: it never builds, publishes, uploads, tags, pushes, or
modifies release files.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_RELEASE_DIR_MISSING = 2
EXIT_ASSET_MISMATCH = 3


ASSET_TEMPLATES: tuple[str, ...] = (
    "01_pypi_wheel__ecli_editor-{version}-py3-none-any.whl",
    "02_pypi_sdist__ecli_editor-{version}.tar.gz",
    "03_linux_pyinstaller__ecli_{version}_linux_x86_64.bin",
    "04_linux_tarball__ecli_{version}_linux_x86_64.tar.gz",
    "05_debian__ecli_{version}_linux_x86_64.deb",
    "06_rpm__ecli_{version}_linux_x86_64.rpm",
    "07_opensuse__ecli_{version}_opensuse_x86_64.rpm",
    "08_arch__ecli_{version}_arch_x86_64.pkg.tar.zst",
    "09_slackware__ecli_{version}_slackware_x86_64.txz",
    "10_appimage__ecli_{version}_linux_x86_64.AppImage",
    "11_freebsd_pkg__ecli_{version}_freebsd_x86_64.pkg",
    "12_freebsd_ports_chroot__ecli_{version}_freebsd_ports_chroot_evidence.tar.gz",
    "13_macos_app__ecli_{version}_macos_universal2_app_evidence.tar.gz",
    "14_macos_dmg__ecli_{version}_macos_universal2.dmg",
    "15_windows_portable__ecli_{version}_win_x86_64.exe",
    "16_windows_nsis__ecli_{version}_win_x86_64_setup.exe",
    "17_nix_flake__ecli_{version}_nix_flake_evidence.tar.gz",
    "18_nixos_package__ecli_{version}_nixos_package_evidence.tar.gz",
    "19_docker_deb_helper__ecli_{version}_docker_deb_helper_evidence.tar.gz",
    "20_docker_rpm_helper__ecli_{version}_docker_rpm_helper_evidence.tar.gz",
    "21_workflow_contract__ecli_{version}_workflow_contract_evidence.tar.gz",
)


class _ContractArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that maps usage errors to the release verifier contract."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)


def read_project_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    try:
        with pyproject.open("rb") as handle:
            version = tomllib.load(handle)["project"]["version"]
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR: cannot read project version from {pyproject}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID) from exc
    if not isinstance(version, str) or not version.strip():
        print(f"ERROR: invalid project version in {pyproject}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)
    return version


def expected_asset_names(version: str) -> tuple[str, ...]:
    """Return the exact 21 official GitHub Release asset filenames."""
    return tuple(template.format(version=version) for template in ASSET_TEMPLATES)


def release_dir_for(root: Path, version: str, release_dir: str | None) -> Path:
    if release_dir:
        return Path(release_dir)
    return root / "releases" / version


def top_level_entries(release_dir: Path) -> set[str]:
    return {path.name for path in release_dir.iterdir()}


def verify_release_assets(release_dir: Path, version: str) -> int:
    """Validate the exact top-level release asset set for *version*."""
    expected = set(expected_asset_names(version))

    if not release_dir.is_dir():
        print(f"ERROR: release asset directory is missing: {release_dir}")
        print("MISSING:")
        for name in sorted(expected):
            print(f"  {name}")
        return EXIT_RELEASE_DIR_MISSING

    checksums = release_dir / ".checksums"
    if checksums.exists() and not checksums.is_dir():
        print("EXTRA:")
        print(f"  {checksums.name}")
        print("ERROR: .checksums must be a directory when present")
        return EXIT_ASSET_MISMATCH

    entries = top_level_entries(release_dir)
    # The .checksums sidecar directory is the only permitted non-asset entry.
    if checksums.is_dir():
        entries.discard(".checksums")

    actual = {name for name in entries if (release_dir / name).is_file()}
    unexpected_dirs = {name for name in entries if (release_dir / name).is_dir()}

    missing = sorted(expected - actual)
    extra = sorted((actual - expected) | unexpected_dirs)

    if missing:
        print("MISSING:")
        for name in missing:
            print(f"  {name}")
    if extra:
        print("EXTRA:")
        for name in extra:
            print(f"  {name}")

    if len(actual) != 21:
        print(f"ERROR: expected exactly 21 release assets, found {len(actual)}")
    if missing or extra or len(actual) != 21:
        return EXIT_ASSET_MISMATCH

    print(f"PASS: exactly 21 release assets present for {version}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractArgumentParser(
        prog="verify_release_assets.py",
        description="Verify ECLI's exact 21-file official GitHub Release asset set.",
    )
    parser.add_argument(
        "--version",
        help="release version; defaults to [project].version in pyproject.toml",
    )
    parser.add_argument(
        "--release-dir",
        help="release asset directory; defaults to releases/<version>",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd()
    version = args.version or read_project_version(root)
    return verify_release_assets(release_dir_for(root, version, args.release_dir), version)


if __name__ == "__main__":
    raise SystemExit(main())
