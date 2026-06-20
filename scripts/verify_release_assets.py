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
Public asset names are clean: they carry no numeric ordering prefix. Any
top-level file matching ``^[0-9]{2}_..*__`` (the historical v0.2.3 staging
mistake) is rejected. Internal ordering is represented only by the position of
each template in ``ASSET_TEMPLATES``, never by the public filename.

Checksum sidecars may be used during CI validation under
``releases/<version>/.checksums/``, but top-level ``.sha256`` files are not
GitHub Release assets and therefore make this verifier fail.

The script is read-only: it never builds, publishes, uploads, tags, pushes, or
modifies release files.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_RELEASE_DIR_MISSING = 2
EXIT_ASSET_MISMATCH = 3


# Clean public GitHub Release asset names, in canonical internal order
# (positions 1..21). The order encodes internal ordering only; it must never be
# rendered as a numeric filename prefix. Numeric prefixes such as
# ``01_pypi_wheel__`` were a v0.2.3-only staging mistake and are rejected by
# ``verify_release_assets`` via ``PREFIXED_ASSET_RE``.
ASSET_TEMPLATES: tuple[str, ...] = (
    "ecli_editor-{version}-py3-none-any.whl",
    "ecli_editor-{version}.tar.gz",
    "ecli_{version}_linux_x86_64.bin",
    "ecli_{version}_linux_x86_64.tar.gz",
    "ecli_{version}_linux_x86_64.deb",
    "ecli_{version}_linux_x86_64.rpm",
    "ecli_{version}_opensuse_x86_64.rpm",
    "ecli_{version}_arch_x86_64.pkg.tar.zst",
    "ecli_{version}_slackware_x86_64.txz",
    "ecli_{version}_linux_x86_64.AppImage",
    "ecli_{version}_freebsd_x86_64.pkg",
    "ecli_{version}_freebsd_ports_chroot_evidence.tar.gz",
    "ecli_{version}_macos_universal2_app_evidence.tar.gz",
    "ecli_{version}_macos_universal2.dmg",
    "ecli_{version}_win_x86_64.exe",
    "ecli_{version}_win_x86_64_setup.exe",
    "ecli_{version}_nix_flake_evidence.tar.gz",
    "ecli_{version}_nixos_package_evidence.tar.gz",
    "ecli_{version}_docker_deb_helper_evidence.tar.gz",
    "ecli_{version}_docker_rpm_helper_evidence.tar.gz",
    "ecli_{version}_workflow_contract_evidence.tar.gz",
)


# Forbidden public filename shape: a two-digit ordering prefix followed by a
# ``label__`` segment (e.g. ``16_windows_nsis__ecli_...``). Public release asset
# names must never carry this prefix.
PREFIXED_ASSET_RE = re.compile(r"^[0-9]{2}_.*__")


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

    # Public asset names are clean. Numeric-prefixed names and top-level
    # ``.sha256`` sidecars are contract violations even though they would also be
    # caught by the generic "extra" set below; report them explicitly so the
    # failure reason is unambiguous.
    prefixed = sorted(name for name in actual if PREFIXED_ASSET_RE.match(name))
    sidecars = sorted(name for name in actual if name.endswith(".sha256"))

    missing = sorted(expected - actual)
    extra = sorted((actual - expected) | unexpected_dirs)

    if prefixed:
        print("PREFIXED:")
        for name in prefixed:
            print(f"  {name}")
        print("ERROR: numeric-prefixed names are not public release asset names")
    if sidecars:
        print("SIDECAR:")
        for name in sidecars:
            print(f"  {name}")
        print("ERROR: top-level .sha256 sidecars must live under .checksums/")
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
    if missing or extra or prefixed or sidecars or len(actual) != 21:
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
