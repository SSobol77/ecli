#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_freebsd.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build and package ECLI into a native FreeBSD ``.pkg`` (FreeBSD 14.x).

Canonical Python replacement for ``scripts/build-and-package-freebsd.sh``. It
must run inside a real FreeBSD 14.x environment (host or VM). It installs system
and Python build dependencies, builds a one-file PyInstaller binary, stages a
``/usr/local`` payload, generates ``+MANIFEST`` plus a plist, runs ``pkg create``,
and produces ``releases/<version>/ecli_<version>_freebsd_<arch>.pkg`` with a
SHA256 sidecar.

This script orchestrates the local FreeBSD toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built and verified
* ``1`` a build phase failed (dependency install, missing tool, missing artifact)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

from packaging_common import (
    filename_arch,
    gzip_file,
    install_desktop_entry,
    install_docs,
    install_file,
    install_icon,
    write_sha256,
)


EXIT_OK = 0
EXIT_ERROR = 1

PACKAGE_NAME = "ecli"
MAINTAINER = "Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE = "https://ecli.io"
LICENSE = "GPL-2.0-only"
COMMENT = "Terminal DevOps editor with AI and Git integration"
CATEGORY = "editors"

SYSTEM_PACKAGES = (
    "ca_root_nss",
    "curl",
    "git",
    "gmake",
    "pkgconf",
    "python311",
    "py311-pip",
    "py311-pyinstaller",
    "py311-setuptools",
    "py311-wheel",
    "py311-ruff",
    "ncurses",
    "libyaml",
)

PIP_PACKAGES = (
    "aiohttp",
    "aiosignal",
    "yarl",
    "multidict",
    "frozenlist",
    "python-dotenv",
    "toml",
    "chardet",
    "pyperclip",
    "wcwidth",
    "pygments",
    "tato",
    "PyYAML",
)

normalize_arch = filename_arch


def python_bin() -> str:
    return os.environ.get("PYTHON", "python3.11")


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def install_system_dependencies() -> bool:
    print("==> ECLI FreeBSD Package Builder")
    print("  -> Installing system build dependencies...", file=sys.stderr)
    pkg_env = {**os.environ, "ASSUME_ALWAYS_YES": "yes"}
    for attempt in range(1, 4):
        if (
            subprocess.run(["pkg", "update", "-f"], env=pkg_env, check=False).returncode
            == 0
        ):
            break
        print(
            f"WARN: pkg update attempt {attempt} failed, retrying...", file=sys.stderr
        )
        time.sleep(attempt * 5)
    if (
        subprocess.run(
            ["pkg", "install", "-y", *SYSTEM_PACKAGES], env=pkg_env, check=False
        ).returncode
        != 0
    ):
        print("ERROR: Failed to install system packages", file=sys.stderr)
        return False
    if shutil.which("pyinstaller") is None:
        print(
            "ERROR: pyinstaller is not in PATH (expected from py311-pyinstaller)",
            file=sys.stderr,
        )
        return False
    if shutil.which("ruff") is None:
        print(
            "WARN: py311-ruff installed but binary not found in PATH", file=sys.stderr
        )
    return True


def install_python_dependencies(root: Path) -> bool:
    print(
        "  -> Installing Python (pip) dependencies for Python 3.11...", file=sys.stderr
    )
    subprocess.run(
        [
            python_bin(),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "wheel",
            "setuptools",
        ],
        cwd=root,
        check=False,
    )
    if (
        subprocess.run(
            [
                python_bin(),
                "-m",
                "pip",
                "install",
                "--no-input",
                "--progress-bar",
                "off",
                *PIP_PACKAGES,
            ],
            cwd=root,
            check=False,
        ).returncode
        != 0
    ):
        print("ERROR: pip install failed", file=sys.stderr)
        return False
    return True


def run_pyinstaller(root: Path) -> Path | None:
    print("  -> Cleaning previous artifacts (build/, dist/)...", file=sys.stderr)
    shutil.rmtree(root / "build", ignore_errors=True)
    shutil.rmtree(root / "dist", ignore_errors=True)

    spec = root / "packaging" / "pyinstaller" / "ecli.spec"
    if spec.is_file():
        subprocess.run(
            [
                "pyinstaller",
                "packaging/pyinstaller/ecli.spec",
                "--clean",
                "--noconfirm",
            ],
            cwd=root,
            check=True,
        )
    else:
        subprocess.run(
            [
                "pyinstaller",
                "main.py",
                "--name",
                PACKAGE_NAME,
                "--onefile",
                "--clean",
                "--noconfirm",
                "--strip",
                "--paths",
                "src",
                "--add-data",
                "config.toml:.",
                "--add-data",
                "pyproject.toml:.",
                "--hidden-import=ecli",
                "--hidden-import=dotenv",
                "--collect-all=dotenv",
                "--hidden-import=toml",
                "--hidden-import=PyYAML",
                "--collect-all=PyYAML",
                "--hidden-import=aiohttp",
                "--collect-all=aiohttp",
                "--hidden-import=aiosignal",
                "--collect-all=aiosignal",
                "--hidden-import=yarl",
                "--collect-all=yarl",
                "--hidden-import=multidict",
                "--collect-all=multidict",
                "--hidden-import=frozenlist",
                "--collect-all=frozenlist",
                "--hidden-import=chardet",
                "--collect-all=chardet",
                "--hidden-import=pyperclip",
                "--collect-all=pyperclip",
                "--hidden-import=wcwidth",
                "--collect-all=wcwidth",
                "--hidden-import=pygments",
                "--collect-all=pygments",
                "--runtime-hook",
                "packaging/pyinstaller/rthooks/force_imports.py",
            ],
            cwd=root,
            check=True,
        )

    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    print("ERROR: PyInstaller output not found in dist/", file=sys.stderr)
    return None


def man_page(version: str) -> str:
    date_str = datetime.now().strftime("%B %Y")
    return (
        f'.TH {PACKAGE_NAME} 1 "{date_str}" "{PACKAGE_NAME} {version}" '
        '"User Commands"\n'
        ".SH NAME\n"
        f"{PACKAGE_NAME} - Terminal code editor\n"
        ".SH SYNOPSIS\n"
        f".B {PACKAGE_NAME}\n"
        "[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]\n"
        ".SH DESCRIPTION\n"
        f"{PACKAGE_NAME} is a fast terminal code editor.\n"
        ".SH OPTIONS\n"
        "\\fB--help\\fR     Show help\n"
        "\\fB--version\\fR  Show version\n"
        ".SH AUTHOR\n"
        f"{MAINTAINER}\n"
        ".SH HOMEPAGE\n"
        f"{HOMEPAGE}\n"
    )


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Name=ECLI\n"
        "Comment=Terminal-first engineering operations workbench\n"
        f"Exec={PACKAGE_NAME}\n"
        f"Icon={PACKAGE_NAME}\n"
        "Terminal=true\n"
        "Type=Application\n"
        "Categories=Development;IDE;Utility;\n"
        "StartupNotify=false\n"
    )


def stage_files(root: Path, executable: Path, version: str) -> Path:
    staging_root = root / "build" / "freebsd_pkg_staging"
    meta_dir = root / "build" / "freebsd_pkg_meta"
    print(f"  -> Staging filesystem under {staging_root} ...", file=sys.stderr)
    shutil.rmtree(staging_root, ignore_errors=True)
    shutil.rmtree(meta_dir, ignore_errors=True)
    for sub in (
        "usr/local/bin",
        "usr/local/share/applications",
        "usr/local/share/icons/hicolor/256x256/apps",
        f"usr/local/share/doc/{PACKAGE_NAME}",
        "usr/local/man/man1",
    ):
        (staging_root / sub).mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    install_file(executable, staging_root / "usr/local/bin" / PACKAGE_NAME, 0o755)

    install_desktop_entry(
        root,
        staging_root / "usr/local/share/applications" / f"{PACKAGE_NAME}.desktop",
        PACKAGE_NAME,
        desktop_entry(),
    )

    install_icon(
        root,
        staging_root
        / "usr/local/share/icons/hicolor/256x256/apps"
        / f"{PACKAGE_NAME}.png",
    )
    install_docs(root, staging_root / "usr/local/share/doc" / PACKAGE_NAME)

    man_dst = staging_root / "usr/local/man/man1" / f"{PACKAGE_NAME}.1"
    repo_man = root / "man" / f"{PACKAGE_NAME}.1"
    if repo_man.is_file():
        install_file(repo_man, man_dst, 0o644)
    else:
        man_dst.write_text(man_page(version), encoding="utf-8")
    gzip_file(man_dst)

    return staging_root


def manifest_text(version: str, abi: str) -> str:
    return (
        f"name: {PACKAGE_NAME}\n"
        f"version: {version}\n"
        f"origin: {CATEGORY}/{PACKAGE_NAME}\n"
        f"comment: {COMMENT}\n"
        "desc: |\n"
        f"  {COMMENT}\n"
        f"maintainer: {MAINTAINER}\n"
        f"www: {HOMEPAGE}\n"
        f"abi: {abi}\n"
        "prefix: /usr/local\n"
        f"categories: [{CATEGORY}]\n"
        f"licenses: [{LICENSE}]\n"
        "licenselogic: single\n"
    )


def make_pkg(root: Path, staging_root: Path, version: str) -> Path | None:
    meta_dir = root / "build" / "freebsd_pkg_meta"
    abi = (
        subprocess.run(
            ["pkg", "config", "ABI"], capture_output=True, text=True, check=False
        ).stdout.strip()
        or "FreeBSD:14:amd64"
    )
    meta_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = meta_dir / "+MANIFEST"
    plist_file = meta_dir / "pkg-plist"
    manifest_file.write_text(manifest_text(version, abi), encoding="utf-8")

    prefix = staging_root / "usr" / "local"
    entries = sorted(
        str(path.relative_to(prefix))
        for path in prefix.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    plist_file.write_text(
        "@cwd /usr/local\n" + "".join(f"{entry}\n" for entry in entries),
        encoding="utf-8",
    )

    releases_dir = root / "releases" / version
    releases_dir.mkdir(parents=True, exist_ok=True)

    print("  -> Creating .pkg with pkg create...", file=sys.stderr)
    subprocess.run(
        [
            "pkg",
            "create",
            "-M",
            str(manifest_file),
            "-p",
            str(plist_file),
            "-r",
            str(staging_root),
            "-o",
            str(releases_dir),
        ],
        cwd=root,
        check=True,
    )

    arch = filename_arch()
    candidates = sorted(releases_dir.glob(f"{PACKAGE_NAME}-{version}*.pkg"))
    if not candidates:
        print("ERROR: pkg create did not produce a .pkg file", file=sys.stderr)
        return None
    orig_pkg = candidates[0]
    dest_pkg = releases_dir / f"{PACKAGE_NAME}_{version}_freebsd_{arch}.pkg"
    if orig_pkg != dest_pkg:
        shutil.move(str(orig_pkg), str(dest_pkg))
    (releases_dir / ".freebsd.env").write_text(
        f"FREEBSD_ARCH := {arch}\n", encoding="utf-8"
    )

    write_sha256(releases_dir, dest_pkg, prefer_freebsd_sha256=True)
    return dest_pkg


def main(argv: list[str] | None = None) -> int:
    """Build and verify the FreeBSD .pkg; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_freebsd.py",
        description="Build and package ECLI into a native FreeBSD .pkg.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent

    if not install_system_dependencies():
        return EXIT_ERROR
    if not install_python_dependencies(root):
        return EXIT_ERROR

    version = read_version(root)
    print(f"  -> Version detected: {version}", file=sys.stderr)

    print("  -> Checking production runtime imports...", file=sys.stderr)
    subprocess.run(
        [python_bin(), "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    executable = run_pyinstaller(root)
    if executable is None:
        return EXIT_ERROR
    print(f"  -> Executable: {executable}", file=sys.stderr)

    staging_root = stage_files(root, executable, version)
    pkg_path = make_pkg(root, staging_root, version)
    if pkg_path is None:
        return EXIT_ERROR

    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(pkg_path)],
        cwd=root,
        check=True,
        env={**os.environ, "PYTHON": python_bin()},
    )

    print("==> DONE")
    print(f"  -> Package:   {pkg_path}", file=sys.stderr)
    print(f"  -> Checksum:  {pkg_path}.sha256", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
