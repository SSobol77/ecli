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

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built and verified
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


def install_file(src: Path, dst: Path, mode: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(mode)


def find_executable(root: Path) -> Path | None:
    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    return None


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
    build_root = root / "build" / "slackware"
    staging_root = build_root / "pkg"
    final_txz = releases_dir / f"{PACKAGE_NAME}_{version}_slackware_{arch}.txz"

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
    doc_dir = staging_root / f"usr/doc/{PACKAGE_NAME}-{version}"
    if (root / "LICENSE").is_file():
        install_file(root / "LICENSE", doc_dir / "LICENSE", 0o644)
    if (root / README_FILE).is_file():
        install_file(root / README_FILE, doc_dir / README_FILE, 0o644)

    (staging_root / "install" / "slack-desc").write_text(slack_desc(), encoding="utf-8")

    print("==> Building Slackware package")
    final_txz.unlink(missing_ok=True)
    (releases_dir / f"{final_txz.name}.sha256").unlink(missing_ok=True)
    subprocess.run(
        ["makepkg", "-l", "y", "-c", "n", str(final_txz)],
        cwd=staging_root,
        check=True,
    )

    print("==> Writing checksum")
    result = subprocess.run(
        ["sha256sum", final_txz.name],
        cwd=releases_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    (releases_dir / f"{final_txz.name}.sha256").write_text(
        result.stdout, encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(final_txz)],
        cwd=root,
        check=True,
    )

    print(f"DONE: {final_txz}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
