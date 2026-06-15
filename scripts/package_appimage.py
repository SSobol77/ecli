#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/package_appimage.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build the ECLI Linux AppImage.

Canonical Python replacement for ``scripts/package_appimage.sh``. It builds the
PyInstaller binary, stages an AppDir, runs ``appimage-builder``, and produces
``releases/<version>/ecli_<version>_linux_<arch>.AppImage`` with a SHA256
sidecar.

AUD-003 note: like the legacy shell script, this rewrites the ``version:`` field
in the tracked ``packaging/linux/appimage/appimage-builder.yml`` recipe. That
tracked-descriptor mutation is pre-existing AUD-003 drift, preserved here only to
keep the language migration behavior-identical; it is slated for removal under a
separate gated fix and must not be treated as new behavior.

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` AppImage built and verified
* ``1`` PyInstaller output missing or AppImage not produced
* ``2`` requested version does not match ``pyproject.toml``
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


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VERSION_MISMATCH = 2


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def normalize_arch(raw: str) -> str:
    if raw in ("amd64", "x86_64"):
        return "x86_64"
    if raw in ("aarch64", "arm64"):
        return "arm64"
    return raw


def install_file(src: Path, dst: Path, mode: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(mode)


def find_executable(root: Path) -> Path | None:
    for candidate in (
        root / "build" / "linux" / "dist" / "ecli",
        root / "dist" / "ecli" / "ecli",
        root / "dist" / "ecli",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    """Build and verify the AppImage; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="package_appimage.py",
        description="Build the ECLI Linux AppImage.",
    )
    parser.add_argument("version", nargs="?", default=None)
    parser.add_argument("arch", nargs="?", default=None)
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    project_version = read_version(root)
    version = args.version or project_version
    if version != project_version:
        print(
            f"Requested AppImage version {version} does not match pyproject.toml "
            f"version {project_version}.",
            file=sys.stderr,
        )
        return EXIT_VERSION_MISMATCH

    arch = normalize_arch(args.arch or (os.uname().machine or "x86_64"))
    out_dir = root / "releases" / version
    appdir = root / "packaging" / "linux" / "appimage" / "AppDir"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".linux.env").write_text(f"LINUX_ARCH := {arch}\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(root / "scripts" / "check_runtime_imports.py")],
        cwd=root,
        check=True,
    )

    # 1) Build the PyInstaller binary.
    subprocess.run(
        [sys.executable, str(root / "scripts" / "build_pyinstaller_linux.py")],
        cwd=root,
        check=True,
    )

    # 2) Prepare AppDir and place the payload under deterministic paths.
    shutil.rmtree(appdir, ignore_errors=True)
    for sub in (
        "usr/bin",
        "usr/share/applications",
        "usr/share/icons/hicolor/256x256/apps",
    ):
        (appdir / sub).mkdir(parents=True, exist_ok=True)

    executable = find_executable(root)
    if executable is None:
        print("PyInstaller output not found for AppImage staging.", file=sys.stderr)
        return EXIT_ERROR

    install_file(executable, appdir / "usr/bin/ecli", 0o755)
    install_file(
        root / "packaging/linux/fpm-common/ecli.desktop",
        appdir / "usr/share/applications/ecli.desktop",
        0o644,
    )
    install_file(
        root / "src/ecli/assets/ecli.png",
        appdir / "usr/share/icons/hicolor/256x256/apps/ecli.png",
        0o644,
    )

    # 3) Update the version in appimage-builder.yml (pre-existing AUD-003 drift).
    recipe = root / "packaging/linux/appimage/appimage-builder.yml"
    recipe.write_text(
        re.sub(
            r'version: ".*"',
            f'version: "{version}"',
            recipe.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )

    # 4) Install appimage-builder locally if absent (CI installs it in a job).
    builder_env = {**os.environ}
    if shutil.which("appimage-builder") is None:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "appimage-builder"],
            cwd=root,
            check=True,
        )
        local_bin = str(Path.home() / ".local" / "bin")
        builder_env["PATH"] = f"{local_bin}{os.pathsep}{builder_env.get('PATH', '')}"

    # 5) Build the AppImage.
    subprocess.run(
        [
            "appimage-builder",
            "--recipe",
            "packaging/linux/appimage/appimage-builder.yml",
            "--appdir",
            str(appdir),
            "--skip-test",
        ],
        cwd=root,
        env=builder_env,
        check=True,
    )

    appimage_file = out_dir / f"ecli_{version}_linux_{arch}.AppImage"
    found = False
    for produced in sorted(root.glob("*.AppImage")):
        if produced.is_file():
            found = True
            appimage_file.unlink(missing_ok=True)
            (out_dir / f"{appimage_file.name}.sha256").unlink(missing_ok=True)
            shutil.move(str(produced), str(appimage_file))
            print(f"Created AppImage: {appimage_file}")

    if not found or not appimage_file.is_file():
        print(f"AppImage build did not produce {appimage_file}.", file=sys.stderr)
        return EXIT_ERROR

    # zsync (optional for AppImageUpdate).
    if shutil.which("appimagetool"):
        subprocess.run(
            ["appimagetool", "--sign", "-v", appimage_file.name],
            cwd=out_dir,
            check=False,
        )

    result = subprocess.run(
        ["sha256sum", appimage_file.name],
        cwd=out_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    (out_dir / f"{appimage_file.name}.sha256").write_text(
        result.stdout, encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(appimage_file)],
        cwd=root,
        check=True,
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
