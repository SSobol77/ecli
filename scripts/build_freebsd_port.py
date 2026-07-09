#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_freebsd_port.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build ECLI via a local FreeBSD ports skeleton and produce a native ``.pkg``.

Canonical Python replacement for ``scripts/build_freebsd_port.sh``. On FreeBSD
14.x (as root) it archives the repo into an owner-controlled build directory,
generates a local port skeleton under ``/usr/ports/editors/ecli_local``, runs ``make makesum`` and
``make clean package``, then copies/renames the result to
``releases/<version>/ecli_<version>_freebsd_<arch>.pkg`` with a SHA256 sidecar.

This script orchestrates the local FreeBSD ports toolchain only. It never
publishes, uploads, signs with external keys, tags, pushes, or triggers any
workflow.

Exit codes:

* ``0`` package built and copied
* ``1`` not FreeBSD/root, missing ports tree, or a ports build phase failed
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from f4_linter_packaging import run_or_record_f4_linter_provisioning
from packaging_common import filename_arch, write_sha256


EXIT_OK = 0
EXIT_ERROR = 1

PORT_CAT = "editors"
PORT_NAME = "ecli_local"
HOST_DEPS = (
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
normalize_arch = filename_arch


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def port_makefile(version: str, dist_dir: Path) -> str:
    """Return the local-port Makefile (tab-indented recipes preserved)."""
    lines = [
        "PORTNAME=       ecli",
        "# DISTVERSION is substituted by the script to actual version",
        f"DISTVERSION=    {version}",
        "CATEGORIES=     editors",
        "",
        "MAINTAINER=     Siergej Sobolewski <s.sobolewski@hotmail.com>",
        "COMMENT=        Terminal DevOps editor with AI and Git integration",
        "WWW=            https://ecli.io",
        "",
        "LICENSE=        GPLv2",
        "LICENSE_FILE=   ${WRKSRC}/LICENSE",
        "",
        "ONLY_FOR_ARCHS= amd64",
        "",
        "# We fetch from a local tarball prepared by the script",
        f"MASTER_SITES=   file://{dist_dir.as_posix()}/",
        "DISTFILES=      ecli-${DISTVERSION}.tar.gz",
        "",
        "# Extracted tree lives here",
        "WRKSRC=         ${WRKDIR}/ecli-${DISTVERSION}",
        "",
        "# We rely on system Python toolchain and utilities",
        "USES=           python:3.11+ gmake",
        "",
        "# Build-time system deps (install via pkg if needed)",
        "BUILD_DEPENDS=  py311-pyinstaller>0:devel/py-pyinstaller@py311 \\",
        "                git:devel/git \\",
        "                gmake:devel/gmake",
        "",
        "# Runtime deps are embedded into PyInstaller binary. Man/desktop/icons "
        "are plain files.",
        "",
        "# --- Build phase: call project's script inside WRKSRC "
        "-------------------------",
        "do-build:",
        "\t@cd ${WRKSRC} && env ASSUME_ALWAYS_YES=yes pkg update -f || true",
        "\t@cd ${WRKSRC} && python3.11 ./scripts/build_and_package_freebsd.py",
        "",
        "# --- Install phase: copy staged tree into ${STAGEDIR} "
        "-------------------------",
        "# The build script stages under build/freebsd_pkg_staging/usr/local/...",
        "do-install:",
        '\t@${ECHO_MSG} ">> Installing staged files to ${STAGEDIR}/usr/local ..."',
        "\t@cd ${WRKSRC}/build/freebsd_pkg_staging && \\",
        "\t\t${FIND} usr -type d -exec ${MKDIR} ${STAGEDIR}/{} \\; && \\",
        "\t\t${FIND} usr -type f -exec ${INSTALL} -m 644 {} ${STAGEDIR}/{} \\;",
        "",
        "# The binary must be executable",
        "\t@${CHMOD} 755 ${STAGEDIR}/usr/local/bin/ecli || true",
        "",
        "# --- Packaging list "
        "-----------------------------------------------------------",
        "# Keep plist simple and stable. Matches what build script stages.",
        "PLIST_FILES= \\",
        "\tbin/ecli \\",
        "\tshare/applications/ecli.desktop \\",
        "\tshare/icons/hicolor/256x256/apps/ecli.png \\",
        "\tshare/doc/ecli/LICENSE \\",
        "\tshare/doc/ecli/README.md \\",
        "\tman/man1/ecli.1.gz",
    ]
    return "\n".join(lines) + "\n"


PKG_DESCR = (
    "ECLI is a fast terminal-first code editor tailored for DevOps workflows:\n"
    "- Git integration\n"
    "- AI-assisted code features\n"
    "- TUI optimized for terminals\n"
    "- First-class support for DevOps config formats\n"
    "\n"
    "This local port builds a native, single-file binary via PyInstaller and\n"
    "installs it under /usr/local.\n"
)


def prepare_dist_dir(root: Path) -> Path:
    """Return an owner-controlled repository build directory for ports distfiles."""
    build_dir = root / "build"
    dist_dir = build_dir / "freebsd_port_distfiles"
    for directory in (build_dir, dist_dir):
        if directory.is_symlink():
            msg = f"Unsafe symlinked build directory: {directory}"
            raise RuntimeError(msg)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(directory.stat().st_mode) & 0o002:
            msg = f"Unsafe world-writable build directory: {directory}"
            raise RuntimeError(msg)
    return dist_dir


def create_source_tarball(root: Path, dist_dir: Path, version: str) -> Path:
    """Create the ports source tarball without using public writable directories."""
    distpath = dist_dir / f"ecli-{version}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="ecli-port-", dir=dist_dir) as tmp:
        tmppath = Path(tmp) / distpath.name
        subprocess.run(
            [
                "tar",
                "--exclude",
                ".git",
                "--exclude",
                "build",
                "--exclude",
                "dist",
                "--exclude",
                ".pytest_cache",
                "--exclude",
                ".ruff_cache",
                "--exclude",
                ".mypy_cache",
                "-czf",
                str(tmppath),
                ".",
            ],
            cwd=root,
            check=True,
        )
        distpath.unlink(missing_ok=True)
        shutil.move(str(tmppath), str(distpath))
    return distpath


def main(argv: list[str] | None = None) -> int:
    """Build the local FreeBSD port and copy the resulting .pkg."""
    parser = argparse.ArgumentParser(
        prog="build_freebsd_port.py",
        description="Build ECLI via a local FreeBSD ports skeleton.",
    )
    parser.parse_args(argv)

    if platform.system() != "FreeBSD":
        print("ERR Run on FreeBSD.", file=sys.stderr)
        return EXIT_ERROR
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("ERR Run as root (sudo).", file=sys.stderr)
        return EXIT_ERROR

    root = Path(__file__).resolve().parent.parent
    version = read_version(root)
    print(f"OK  Version: {version}")

    portdir = Path("/usr/ports") / PORT_CAT / PORT_NAME
    arch = filename_arch()

    if not Path("/usr/ports").is_dir():
        print("ERR Ports tree is required.", file=sys.stderr)
        return EXIT_ERROR

    try:
        dist_dir = prepare_dist_dir(root)
    except RuntimeError as exc:
        print(f"ERR {exc}", file=sys.stderr)
        return EXIT_ERROR
    distpath = dist_dir / f"ecli-{version}.tar.gz"

    print(f"==> Creating source tarball: {distpath}")
    create_source_tarball(root, dist_dir, version)

    print(f"==> Creating local port skeleton at: {portdir}")
    shutil.rmtree(portdir, ignore_errors=True)
    portdir.mkdir(parents=True, exist_ok=True)
    (portdir / "Makefile").write_text(
        port_makefile(version, dist_dir), encoding="utf-8"
    )
    (portdir / "pkg-descr").write_text(PKG_DESCR, encoding="utf-8")

    print("==> Ensuring base system build deps (host) ...")
    subprocess.run(
        ["pkg", "install", "-y", *HOST_DEPS],
        env={**os.environ, "ASSUME_ALWAYS_YES": "yes"},
        check=False,
    )

    print("==> Generating distinfo (makesum) ...")
    if (
        subprocess.run(["make", "-C", str(portdir), "makesum"], check=False).returncode
        != 0
    ):
        print("ERR makesum failed", file=sys.stderr)
        return EXIT_ERROR

    print("==> Building package with ports (this may take a while) ...")
    if (
        subprocess.run(
            ["make", "-C", str(portdir), "clean", "package"], check=False
        ).returncode
        != 0
    ):
        print("ERR make package failed", file=sys.stderr)
        return EXIT_ERROR

    print("==> Locating produced package ...")
    pkgfile = subprocess.run(
        ["make", "-C", str(portdir), "-V", "PKGFILE"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    produced = Path(pkgfile) if pkgfile else None
    if produced is None or not produced.is_file():
        fallback = sorted(Path("/usr/ports/packages/All").glob("ecli-*.pkg"))
        produced = fallback[-1] if fallback else None
    if produced is None or not produced.is_file():
        print(
            "ERR Cannot find produced .pkg; looked at PKGFILE and "
            "/usr/ports/packages/All",
            file=sys.stderr,
        )
        return EXIT_ERROR
    print(f"OK  Found: {produced}")

    releases_dir = root / "releases" / version
    dest_pkg = releases_dir / f"ecli_{version}_freebsd_{arch}.pkg"
    releases_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced, dest_pkg)
    (releases_dir / ".freebsd.env").write_text(
        f"FREEBSD_ARCH := {arch}\n", encoding="utf-8"
    )
    write_sha256(releases_dir, dest_pkg, prefer_freebsd_sha256=True)

    print(f"OK  Copied & renamed -> {dest_pkg}")
    subprocess.run(["pkg", "info", "-F", str(dest_pkg)], check=False)
    print("==> Recording F4 linter provisioning evidence")
    f4_rc = run_or_record_f4_linter_provisioning(root, "freebsd-ports-chroot")
    if f4_rc != EXIT_OK:
        return EXIT_ERROR
    print("==> Done.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
