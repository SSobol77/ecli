#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_deb.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build and package ECLI into a Debian/Ubuntu ``.deb``.

Canonical Python replacement for ``scripts/build-and-package-deb.sh``. It builds
a standalone executable with PyInstaller, stages a minimal FHS payload, and
produces ``releases/<version>/ecli_<version>_linux_<arch>.deb`` with FPM plus a
SHA256 sidecar. Artifact naming, output locations, and the FPM dependency set are
preserved exactly.

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built and verified
* ``1`` missing tool, missing version, or missing PyInstaller output
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path


EXIT_OK = 0
EXIT_ERROR = 1

PACKAGE_NAME = "ecli"
MAINTAINER = "Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE = "https://ecli.io"
LICENSE = "GPL-2.0-only"
CATEGORY = "editors"

DEB_DEPENDS = (
    "libncurses6",
    "libncursesw6",
    "libtinfo6",
    "ncurses-term",
    "libyaml-0-2",
    "xclip | xsel",
)


def python_bin() -> str:
    return os.environ.get("PYTHON", "python3")


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def filename_arch() -> str:
    raw = os.uname().machine
    if raw in ("amd64", "x86_64"):
        return "x86_64"
    if raw in ("aarch64", "arm64"):
        return "arm64"
    return raw


def require_tool(name: str) -> bool:
    if shutil.which(name) is None:
        print(f"ERROR: Missing required tool: {name}", file=sys.stderr)
        return False
    return True


def install_file(src: Path, dst: Path, mode: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(mode)


def gzip_file(path: Path, level: int = 9) -> Path:
    gz = path.with_name(path.name + ".gz")
    gz.write_bytes(gzip.compress(path.read_bytes(), compresslevel=level, mtime=0))
    path.unlink()
    return gz


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ECLI\n"
        "Comment=Terminal-first engineering operations workbench\n"
        f"Exec={PACKAGE_NAME}\n"
        f"Icon={PACKAGE_NAME}\n"
        "Terminal=true\n"
        "Categories=Development;IDE;Utility;\n"
        "StartupNotify=false\n"
    )


def man_page(version: str) -> str:
    date_str = datetime.now().strftime("%B %Y")
    author = MAINTAINER.split(" <", 1)[0]
    return (
        f'.TH {PACKAGE_NAME.upper()} 1 "{date_str}" "{PACKAGE_NAME} {version}" '
        '"User Commands"\n'
        ".SH NAME\n"
        f"{PACKAGE_NAME} - Terminal code editor\n"
        ".SH SYNOPSIS\n"
        f".B {PACKAGE_NAME}\n"
        "[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]\n"
        ".SH DESCRIPTION\n"
        f"{PACKAGE_NAME.upper()} is a fast terminal code editor.\n"
        ".SH OPTIONS\n"
        "\\fB--help\\fR     Show help\n"
        "\\fB--version\\fR  Show version\n"
        ".SH AUTHOR\n"
        f"{author}\n"
        ".SH REPORTING BUGS\n"
        f"{HOMEPAGE}\n"
    )


def find_executable(root: Path) -> Path | None:
    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    return None


def run_pyinstaller(root: Path) -> None:
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
        return
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
            "--runtime-hook",
            "packaging/pyinstaller/rthooks/force_imports.py",
        ],
        cwd=root,
        check=True,
    )


def stage_payload(root: Path, staging: Path, executable: Path, version: str) -> None:
    """Stage the FHS payload tree under ``staging`` (matches the shell layout)."""
    shutil.rmtree(staging, ignore_errors=True)
    for sub in (
        "usr/bin",
        "usr/share/applications",
        "usr/share/icons/hicolor/256x256/apps",
        f"usr/share/doc/{PACKAGE_NAME}",
        "usr/share/man/man1",
    ):
        (staging / sub).mkdir(parents=True, exist_ok=True)

    install_file(executable, staging / "usr/bin" / PACKAGE_NAME, 0o755)

    desktop_src = root / "packaging/linux/fpm-common" / f"{PACKAGE_NAME}.desktop"
    desktop_dst = staging / "usr/share/applications" / f"{PACKAGE_NAME}.desktop"
    if desktop_src.is_file():
        install_file(desktop_src, desktop_dst, 0o644)
    else:
        desktop_dst.write_text(desktop_entry(), encoding="utf-8")

    icon_src = root / "src/ecli/assets/ecli.png"
    if icon_src.is_file():
        install_file(
            icon_src,
            staging / "usr/share/icons/hicolor/256x256/apps" / f"{PACKAGE_NAME}.png",
            0o644,
        )

    doc_dir = staging / "usr/share/doc" / PACKAGE_NAME
    for name in ("LICENSE", "README.md"):
        src = root / name
        if src.is_file():
            install_file(src, doc_dir / name, 0o644)
            gzip_file(doc_dir / name)

    man_dst = staging / "usr/share/man/man1" / f"{PACKAGE_NAME}.1"
    repo_man = root / "man" / f"{PACKAGE_NAME}.1"
    if repo_man.is_file():
        install_file(repo_man, man_dst, 0o644)
    else:
        man_dst.write_text(man_page(version), encoding="utf-8")
    gzip_file(man_dst)


def build_fpm_command(staging: Path, version: str, final_deb: Path) -> list[str]:
    """Construct the FPM .deb command array (deterministic, no shell)."""
    cmd = [
        "fpm",
        "-s",
        "dir",
        "-t",
        "deb",
        "-n",
        PACKAGE_NAME,
        "-v",
        version,
        "-a",
        "amd64",
        "--maintainer",
        MAINTAINER,
        "--description",
        "Ecli — terminal DevOps editor with AI and Git integration",
        "--url",
        HOMEPAGE,
        "--license",
        LICENSE,
        "--category",
        CATEGORY,
        "--deb-priority",
        "optional",
        "--deb-compression",
        "xz",
    ]
    for dep in DEB_DEPENDS:
        cmd += ["--depends", dep]
    cmd += [
        "--after-install",
        "packaging/linux/fpm-common/postinst",
        "--before-remove",
        "packaging/linux/fpm-common/prerm",
        "--after-remove",
        "packaging/linux/fpm-common/postrm",
        "--package",
        str(final_deb),
        "-C",
        str(staging),
        "usr",
    ]
    return cmd


def write_sha256(releases_dir: Path, artifact: Path) -> None:
    name = artifact.name
    if shutil.which("sha256sum"):
        result = subprocess.run(
            ["sha256sum", name],
            cwd=releases_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        (releases_dir / f"{name}.sha256").write_text(result.stdout, encoding="utf-8")
    elif shutil.which("shasum"):
        result = subprocess.run(
            ["shasum", "-a", "256", name],
            cwd=releases_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        (releases_dir / f"{name}.sha256").write_text(result.stdout, encoding="utf-8")
    else:
        print(
            "WARNING: no sha256 tool found (sha256sum/shasum). Skipping checksum.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    """Build the Debian package and verify it; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_deb.py",
        description="Build and package ECLI into a Debian/Ubuntu .deb.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    version = read_version(root)

    print("==> Checking production runtime imports")
    subprocess.run(
        [python_bin(), "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    if not (require_tool("pyinstaller") and require_tool("fpm")):
        return EXIT_ERROR

    arch = filename_arch()
    releases_dir = root / "releases" / version
    final_deb = releases_dir / f"{PACKAGE_NAME}_{version}_linux_{arch}.deb"
    staging = root / "build" / "deb_staging"

    print(f"==> Version: {version}")
    shutil.rmtree(root / "build", ignore_errors=True)
    shutil.rmtree(root / "dist", ignore_errors=True)
    final_deb.unlink(missing_ok=True)
    (releases_dir / f"{final_deb.name}.sha256").unlink(missing_ok=True)

    print("==> Building executable with PyInstaller")
    run_pyinstaller(root)
    executable = find_executable(root)
    if executable is None:
        print("PyInstaller output not found", file=sys.stderr)
        return EXIT_ERROR

    print("==> Preparing staging (FHS)")
    stage_payload(root, staging, executable, version)
    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / ".linux.env").write_text(
        f"LINUX_ARCH := {arch}\n", encoding="utf-8"
    )

    print("==> Building .deb with FPM")
    subprocess.run(build_fpm_command(staging, version, final_deb), cwd=root, check=True)

    print("==> Verify")
    if shutil.which("dpkg-deb"):
        subprocess.run(["dpkg-deb", "--info", str(final_deb)], cwd=root, check=False)
        subprocess.run(
            ["dpkg-deb", "--contents", str(final_deb)], cwd=root, check=False
        )
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(final_deb)],
        cwd=root,
        check=True,
    )

    print("==> Generating SHA-256 checksum")
    write_sha256(releases_dir, final_deb)

    print(f"DONE: {final_deb}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
