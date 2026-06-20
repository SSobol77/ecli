#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_slackware.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build a traditional Slackware ``.txz`` package from the PyInstaller binary.

Canonical Python replacement for ``scripts/build-and-package-slackware.sh``. It
builds the Linux PyInstaller binary, stages a Slackware payload (including
``install/slack-desc``), runs Slackware ``makepkg``, writes a SHA256 sidecar, and
verifies the artifact as ``releases/<version>/ecli_<version>_slackware_<arch>.txz``.

Slackware ``makepkg`` needs a real Slackware pkgtools environment, which the
Ubuntu release runner does not have. The release-canonical path runs this script
inside the ``docker/build-slackware-package.Dockerfile`` helper
(``make package-slackware-docker``); the host-only ``make package-slackware``
target remains for Slackware developer machines.

Raw/intermediate makepkg output is written under ``build/slackware`` and only the
normalized canonical artifact and its checksum sidecar are copied into
``releases/<version>/`` so that ``releases/<version>/`` never holds a raw package
name as a top-level release asset (#93), mirroring the Arch/RPM raw-output
isolation.

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built, normalized, and verified
* ``1`` version unreadable or PyInstaller output missing
* ``5`` a required Slackware tool (``makepkg``/``sha256sum``) is missing
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging_common import install_docs, install_file, write_sha256


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MISSING_TOOL = 5

PACKAGE_NAME = "ecli"
README_FILE = "README.md"


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


def find_executable(root: Path) -> Path | None:
    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    return None


def slackware_build_dir(root: Path) -> Path:
    """Return the ``build/`` staging dir for raw makepkg output (never releases/).

    Slackware ``makepkg`` packages the staged payload tree (``pkg/``) and writes
    the raw ``.txz`` here. Keeping this under ``build/`` guarantees
    ``releases/<version>/`` holds only the canonical normalized artifact and its
    checksum sidecar (#93), mirroring ``scripts/build_and_package_arch.py``.
    """
    return root / "build" / "slackware"


def slack_desc() -> str:
    p = PACKAGE_NAME
    return (
        f"{p}: {p} (terminal-first engineering operations workbench)\n"
        f"{p}:\n"
        f"{p}: ECLI is a terminal-first engineering operations workbench.\n"
        f"{p}: It combines a curses editor with operational diagnostics,\n"
        f"{p}: command-plan previews, Git visibility, and service panels.\n"
        f"{p}:\n"
        f"{p}: Homepage: https://www.ecli.io\n"
        f"{p}: Repository: https://github.com/SSobol77/ecli\n"
        f"{p}:\n"
        f"{p}: License: GPL-2.0-only\n"
        f"{p}:\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Build and verify the Slackware .txz; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_slackware.py",
        description="Build a Slackware .txz package from the PyInstaller binary.",
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
        print("Slackware makepkg is required to build .txz packages.", file=sys.stderr)
        return EXIT_MISSING_TOOL
    if shutil.which("sha256sum") is None:
        print("sha256sum is required to write package checksums.", file=sys.stderr)
        return EXIT_MISSING_TOOL

    releases_dir = root / "releases" / version
    build_root = slackware_build_dir(root)
    staging_root = build_root / "pkg"
    artifact_name = f"{PACKAGE_NAME}_{version}_slackware_{arch}.txz"
    # Raw makepkg output stays under build/ (never releases/); the normalized
    # canonical artifact is copied into releases/<version>/ (#93).
    raw_txz = build_root / artifact_name
    normalized = releases_dir / artifact_name

    print("==> Building ECLI PyInstaller binary")
    subprocess.run(
        [sys.executable, str(root / "scripts" / "build_pyinstaller_linux.py")],
        cwd=root,
        check=True,
    )

    executable = find_executable(root)
    if executable is None:
        print("ERROR: PyInstaller output not found under dist/.", file=sys.stderr)
        return EXIT_ERROR

    print("==> Staging Slackware package")
    shutil.rmtree(build_root, ignore_errors=True)
    for sub in (
        "usr/bin",
        "usr/share/applications",
        "usr/share/icons/hicolor/256x256/apps",
        f"usr/doc/{PACKAGE_NAME}-{version}",
        "install",
    ):
        (staging_root / sub).mkdir(parents=True, exist_ok=True)
    releases_dir.mkdir(parents=True, exist_ok=True)

    install_file(executable, staging_root / "usr/bin" / PACKAGE_NAME, 0o755)
    install_file(
        root / "packaging/linux/fpm-common" / f"{PACKAGE_NAME}.desktop",
        staging_root / "usr/share/applications" / f"{PACKAGE_NAME}.desktop",
        0o644,
    )
    install_file(
        root / "src/ecli/assets/ecli.png",
        staging_root / "usr/share/icons/hicolor/256x256/apps" / f"{PACKAGE_NAME}.png",
        0o644,
    )
    install_docs(
        root,
        staging_root / f"usr/doc/{PACKAGE_NAME}-{version}",
        ("LICENSE", README_FILE),
    )

    (staging_root / "install" / "slack-desc").write_text(slack_desc(), encoding="utf-8")

    print("==> Building Slackware package")
    raw_txz.unlink(missing_ok=True)
    subprocess.run(
        ["makepkg", "-l", "y", "-c", "n", str(raw_txz)],
        cwd=staging_root,
        check=True,
    )
    if not raw_txz.is_file():
        print(
            f"ERROR: Slackware package artifact not found under {build_root}.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    print("==> Normalizing release artifact")
    normalized.unlink(missing_ok=True)
    (releases_dir / f"{normalized.name}.sha256").unlink(missing_ok=True)
    shutil.copy2(raw_txz, normalized)

    print("==> Writing checksum")
    write_sha256(releases_dir, normalized)
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(normalized)],
        cwd=root,
        check=True,
    )

    print(f"Raw makepkg artifact: {raw_txz}")
    print(f"DONE: {normalized}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
