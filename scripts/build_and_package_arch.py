#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_arch.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build an Arch Linux package from ``packaging/arch/PKGBUILD``.

Canonical Python replacement for ``scripts/build-and-package-arch.sh``. It runs
``makepkg`` against the tracked ``packaging/arch/PKGBUILD``, normalizes the raw
output to ``releases/<version>/ecli_<version>_arch_<arch>.pkg.tar.zst``, writes a
SHA256 sidecar, and runs the runtime verifier.

makepkg needs a real Arch ``base-devel`` toolchain, which the Ubuntu release
runner does not have. The release-canonical path runs this script inside the
``docker/build-arch-package.Dockerfile`` helper (``make package-arch-docker``);
the host-only ``make package-arch`` target remains for Arch developer machines.

Raw/intermediate makepkg output (the native
``ecli-editor-<ver>-<rel>-<arch>.pkg.tar.zst`` plus the makepkg ``src``/``pkg``
trees) is kept under ``build/`` and never under ``releases/`` so that
``releases/<version>/`` only ever holds the canonical normalized artifact and its
checksum sidecar (#93). makepkg is run from a copy of the PKGBUILD under
``build/arch`` so the tracked source tree is never written to and a non-root
build user can own every output path inside the Docker helper.

``pkgver`` is taken from ``pyproject.toml`` (the version source of truth) and
written into the build-only PKGBUILD copy. The tracked
``packaging/arch/PKGBUILD`` is never mutated as a build side effect (AUD-003).

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built, normalized, and verified
* ``1`` version unreadable or normalized artifact not found
* ``5`` a required Arch tool (``makepkg``/``sha256sum``) is missing
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging_common import write_sha256


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MISSING_TOOL = 5

PACKAGE_NAME = "ecli-editor"


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def normalize_arch() -> str:
    raw = os.uname().machine
    if raw in ("amd64", "x86_64"):
        return "x86_64"
    if raw in ("aarch64", "arm64"):
        return "aarch64"
    return raw


def arch_build_dir(root: Path) -> Path:
    """Return the ``build/`` staging dir for raw makepkg output (never releases/).

    makepkg writes its ``src``/``pkg`` working trees and the raw
    ``ecli-editor-<ver>-<rel>-<arch>.pkg.tar.zst`` here. Keeping this under
    ``build/`` guarantees ``releases/<version>/`` holds only the canonical
    normalized artifact and its checksum sidecar (#93), mirroring the RPM raw
    output isolation in ``scripts/build_and_package_rpm.py``.
    """
    return root / "build" / "arch"


def stage_pkgbuild(root: Path, build_dir: Path, version: str) -> Path:
    """Copy the tracked PKGBUILD into *build_dir* with ``pkgver`` set to *version*.

    The tracked ``packaging/arch/PKGBUILD`` is never modified. Only the build-only
    copy is rewritten so the package metadata tracks ``pyproject.toml`` instead of
    a hard-coded ``pkgver`` (AUD-003). makepkg is then run from *build_dir*, so the
    source tree is never used as a makepkg working directory.
    """
    source = (root / "packaging" / "arch" / "PKGBUILD").read_text(encoding="utf-8")
    rewritten = re.sub(r"(?m)^pkgver=.*$", f"pkgver={version}", source, count=1)
    target = build_dir / "PKGBUILD"
    target.write_text(rewritten, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    """Build and normalize the Arch package; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_arch.py",
        description="Build an Arch Linux package from packaging/arch/PKGBUILD.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    try:
        version = read_version(root)
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        print("ERROR: Cannot read version from pyproject.toml", file=sys.stderr)
        return EXIT_ERROR

    subprocess.run(
        [sys.executable, "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    arch = normalize_arch()

    if shutil.which("makepkg") is None:
        print(
            "Arch makepkg is required to build pkg.tar.zst packages.",
            file=sys.stderr,
        )
        return EXIT_MISSING_TOOL
    if shutil.which("sha256sum") is None:
        print("sha256sum is required to write package checksums.", file=sys.stderr)
        return EXIT_MISSING_TOOL

    releases_dir = root / "releases" / version
    releases_dir.mkdir(parents=True, exist_ok=True)
    normalized = releases_dir / f"ecli_{version}_arch_{arch}.pkg.tar.zst"

    # Raw makepkg output and working trees stay under build/ (never releases/) and
    # makepkg runs from a copy of the PKGBUILD so the tracked source tree is never
    # written to (#93).
    build_dir = arch_build_dir(root)
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    stage_pkgbuild(root, build_dir, version)

    print("==> Building Arch package")
    # --nodeps: the build environment (the docker/build-arch-package.Dockerfile
    # helper, or a prepared Arch host) provisions the toolchain. PyInstaller is
    # not in the official Arch repos (AUR only) and is installed with pip, so
    # makepkg's pacman dependency check would otherwise fail on python-pyinstaller.
    subprocess.run(
        ["makepkg", "--clean", "--force", "--noconfirm", "--nodeps"],
        cwd=build_dir,
        env={**os.environ, "ECLI_REPO_ROOT": str(root), "PKGDEST": str(build_dir)},
        check=True,
    )

    raw_candidates = sorted(build_dir.glob(f"{PACKAGE_NAME}-{version}-*.pkg.tar.*"))
    if not raw_candidates or not raw_candidates[0].is_file():
        print(
            f"ERROR: Arch package artifact not found under {build_dir}.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    raw_artifact = raw_candidates[0]

    print("==> Normalizing release artifact")
    normalized.unlink(missing_ok=True)
    (releases_dir / f"{normalized.name}.sha256").unlink(missing_ok=True)
    shutil.copy2(raw_artifact, normalized)

    print("==> Writing checksum")
    write_sha256(releases_dir, normalized)
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(normalized)],
        cwd=root,
        check=True,
    )

    print(f"Raw makepkg artifact: {raw_artifact}")
    print(f"DONE: {normalized}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
