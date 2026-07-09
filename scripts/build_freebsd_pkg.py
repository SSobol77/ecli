#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_freebsd_pkg.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Local FreeBSD package builder for ECLI (FreeBSD 14.x).

Canonical Python replacement for ``scripts/build-freebsd-pkg.sh``. It builds a
PyInstaller one-file binary and produces a native ``.pkg`` via ``pkg create``,
trying UCL then YAML manifests then a current-directory fallback, normalizing the
artifact to ``releases/<version>/ecli_<version>_freebsd_<arch>.pkg`` with a
SHA256 sidecar. It requires root and re-execs through ``sudo`` when needed.

This script orchestrates the local FreeBSD toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built and verified
* ``1`` a build phase failed (deps, missing tool, missing artifact)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

from f4_linter_packaging import run_or_record_f4_linter_provisioning
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
PYTHON_CMD = "python3.11"

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

REQUIRED_COMMANDS = (PYTHON_CMD, "pip", "pyinstaller", "pkg", "install", "git")
normalize_arch = filename_arch


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def check_dependencies() -> bool:
    missing = [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]
    if missing:
        print(f"ERROR: Missing commands: {' '.join(missing)}", file=sys.stderr)
        return False
    return True


def install_system_dependencies() -> bool:
    print("==> ECLI FreeBSD Package Builder")
    missing = [
        pkg
        for pkg in SYSTEM_PACKAGES
        if subprocess.run(
            ["pkg", "info", "-e", pkg], capture_output=True, check=False
        ).returncode
        != 0
    ]
    if missing:
        print(f"==> Installing missing packages: {' '.join(missing)}")
        if (
            subprocess.run(["pkg", "install", "-y", *missing], check=False).returncode
            != 0
        ):
            print("ERROR: Failed to install system dependencies", file=sys.stderr)
            return False
    else:
        print("==> All required packages already installed")
    return True


def install_python_dependencies(root: Path) -> bool:
    print("==> Installing Python runtime dependencies...")
    if (
        subprocess.run(
            [PYTHON_CMD, "-c", "import tomllib"], capture_output=True, check=False
        ).returncode
        != 0
    ):
        subprocess.run([PYTHON_CMD, "-m", "pip", "install", "tomli"], check=False)
    if (
        subprocess.run(
            [PYTHON_CMD, "-m", "pip", "install", *PIP_PACKAGES], cwd=root, check=False
        ).returncode
        != 0
    ):
        print("ERROR: Failed to install Python dependencies", file=sys.stderr)
        return False
    return True


def build_binary(root: Path) -> Path | None:
    print("==> Building standalone binary with PyInstaller...")
    spec = root / "packaging" / "pyinstaller" / "ecli.spec"
    built = False
    if spec.is_file():
        if (
            subprocess.run(
                ["pyinstaller", str(spec), "--clean", "--noconfirm"],
                cwd=root,
                check=False,
            ).returncode
            == 0
        ):
            built = True
        else:
            print(
                "WARNING: spec build failed, trying direct method...", file=sys.stderr
            )
    if not built:
        result = subprocess.run(
            [
                "pyinstaller",
                str(root / "main.py"),
                "--name",
                PACKAGE_NAME,
                "--onefile",
                "--clean",
                "--noconfirm",
                "--strip",
                "--paths",
                str(root / "src"),
                "--add-data",
                f"{root / 'config.toml'}:.",
                "--hidden-import=ecli",
                "--hidden-import=curses",
                "--hidden-import=_curses",
                "--hidden-import=_curses_panel",
                "--hidden-import=locale",
                "--hidden-import=signal",
                "--hidden-import=queue",
                "--hidden-import=threading",
                "--hidden-import=subprocess",
                "--hidden-import=shlex",
                "--hidden-import=tempfile",
                "--hidden-import=unicodedata",
                "--hidden-import=json",
                "--hidden-import=importlib.util",
                "--hidden-import=traceback",
                "--hidden-import=types",
                "--hidden-import=shutil",
                "--hidden-import=textwrap",
                "--hidden-import=re",
                "--hidden-import=functools",
                "--hidden-import=logging",
                "--hidden-import=time",
                "--hidden-import=pathlib",
                "--hidden-import=asyncio",
                "--hidden-import=dotenv",
                "--collect-all=dotenv",
                "--hidden-import=toml",
                "--collect-all=toml",
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
                "--collect-binaries=_curses",
                "--collect-binaries=_curses_panel",
                "--collect-data=pygments",
                "--collect-data=wcwidth",
                "--runtime-hook",
                str(root / "packaging/pyinstaller/rthooks/force_imports.py"),
            ],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            print("ERROR: PyInstaller build failed", file=sys.stderr)
            return None

    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return Path("dist") / PACKAGE_NAME / PACKAGE_NAME
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return Path("dist") / PACKAGE_NAME
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
        f"{PACKAGE_NAME} is a fast terminal code editor with AI and Git integration.\n"
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


def stage_package_files(
    root: Path, staging_root: Path, executable: Path, version: str
) -> bool:
    abs_exec = root / executable
    if not (abs_exec.is_file() and os.access(abs_exec, os.X_OK)):
        print(f"ERROR: Executable not usable: {abs_exec}", file=sys.stderr)
        return False

    install_file(abs_exec, staging_root / "usr/local/bin" / PACKAGE_NAME, 0o755)

    install_desktop_entry(
        root,
        staging_root / "usr/local/share/applications" / f"{PACKAGE_NAME}.desktop",
        PACKAGE_NAME,
        desktop_entry(),
    )

    if not install_icon(
        root,
        staging_root
        / "usr/local/share/icons/hicolor/256x256/apps"
        / f"{PACKAGE_NAME}.png",
    ):
        icon_src = root / "src/ecli/assets/ecli.png"
        print(f"WARNING: Application icon not found: {icon_src}", file=sys.stderr)

    install_docs(root, staging_root / "usr/local/share/doc" / PACKAGE_NAME)

    man_dst = staging_root / "usr/local/man/man1" / f"{PACKAGE_NAME}.1"
    repo_man = root / "man" / f"{PACKAGE_NAME}.1"
    if repo_man.is_file():
        install_file(repo_man, man_dst, 0o644)
    else:
        man_dst.write_text(man_page(version), encoding="utf-8")
    gzip_file(man_dst)
    return True


def yaml_manifest(version: str, abi: str) -> str:
    p = PACKAGE_NAME
    return (
        f'name: "{p}"\n'
        f'version: "{version}"\n'
        f'origin: "{CATEGORY}/{p}"\n'
        f'comment: "{COMMENT}"\n'
        f'desc: "{COMMENT}"\n'
        f'maintainer: "{MAINTAINER}"\n'
        f'www: "{HOMEPAGE}"\n'
        f'abi: "{abi}"\n'
        'prefix: "/usr/local"\n'
        f'categories: ["{CATEGORY}"]\n'
        f'licenses: ["{LICENSE}"]\n\n'
        "deps: {\n"
        '  ncurses: {origin: "devel/ncurses",    version: ">=6.0"},\n'
        '  libyaml: {origin: "textproc/libyaml", version: ">=0.2"}\n'
        "}\n\n"
        "files: {\n"
        f"  /usr/local/bin/{p}: {{uname: root, gname: wheel, perm: 0755}},\n"
        f"  /usr/local/share/applications/{p}.desktop: "
        "{uname: root, gname: wheel, perm: 0644},\n"
        f"  /usr/local/share/icons/hicolor/256x256/apps/{p}.png: "
        "{uname: root, gname: wheel, perm: 0644},\n"
        f"  /usr/local/share/doc/{p}/LICENSE: {{uname: root, gname: wheel, perm: 0644}},\n"
        f"  /usr/local/share/doc/{p}/README.md: "
        "{uname: root, gname: wheel, perm: 0644},\n"
        f"  /usr/local/man/man1/{p}.1.gz: {{uname: root, gname: wheel, perm: 0644}}\n"
        "}\n"
    )


def ucl_manifest(version: str, abi: str) -> str:
    p = PACKAGE_NAME
    return (
        f'name = "{p}";\n'
        f'version = "{version}";\n'
        f'origin = "{CATEGORY}/{p}";\n'
        f'comment = "{COMMENT}";\n'
        f'desc = "{COMMENT}";\n'
        f'maintainer = "{MAINTAINER}";\n'
        f'www = "{HOMEPAGE}";\n'
        f'abi = "{abi}";\n'
        'prefix = "/usr/local";\n'
        f'categories = ["{CATEGORY}"];\n'
        f'licenses = ["{LICENSE}"];\n\n'
        "deps = {\n"
        '  "ncurses" = { origin = "devel/ncurses";    version = ">=6.0"; };\n'
        '  "libyaml" = { origin = "textproc/libyaml"; version = ">=0.2"; };\n'
        "};\n\n"
        "files = {\n"
        f'  "/usr/local/bin/{p}" = {{uname = "root"; gname = "wheel"; perm = 0755;}};\n'
        f'  "/usr/local/share/applications/{p}.desktop" = '
        '{uname = "root"; gname = "wheel"; perm = 0644;};\n'
        f'  "/usr/local/share/icons/hicolor/256x256/apps/{p}.png" = '
        '{uname = "root"; gname = "wheel"; perm = 0644;};\n'
        f'  "/usr/local/share/doc/{p}/LICENSE" = '
        '{uname = "root"; gname = "wheel"; perm = 0644;};\n'
        f'  "/usr/local/share/doc/{p}/README.md" = '
        '{uname = "root"; gname = "wheel"; perm = 0644;};\n'
        f'  "/usr/local/man/man1/{p}.1.gz" = '
        '{uname = "root"; gname = "wheel"; perm = 0644;};\n'
        "};\n"
    )


def create_package(
    root: Path, staging_root: Path, meta_dir: Path, releases_dir: Path, version: str
) -> Path | None:
    print("==> Creating FreeBSD package manifest...")
    abi = (
        subprocess.run(
            ["pkg", "config", "ABI"], capture_output=True, text=True, check=False
        ).stdout.strip()
        or "FreeBSD:14:amd64"
    )
    manifest_file = meta_dir / "+MANIFEST"
    ucl_file = meta_dir / "+MANIFEST.ucl"
    manifest_file.write_text(yaml_manifest(version, abi), encoding="utf-8")
    ucl_file.write_text(ucl_manifest(version, abi), encoding="utf-8")

    releases_dir.mkdir(parents=True, exist_ok=True)
    for pattern in (
        f"{PACKAGE_NAME}-{version}*.pkg*",
        f"{PACKAGE_NAME}_{version}_*.pkg*",
    ):
        for stale in releases_dir.glob(pattern):
            stale.unlink(missing_ok=True)

    created = False
    for manifest in (ucl_file, manifest_file):
        if (
            subprocess.run(
                [
                    "pkg",
                    "create",
                    "-M",
                    str(manifest),
                    "-r",
                    str(staging_root),
                    "-o",
                    str(releases_dir),
                ],
                cwd=root,
                check=False,
            ).returncode
            == 0
        ):
            created = True
            break
    if not created and (
        subprocess.run(
            ["pkg", "create", "-M", str(ucl_file), "-r", str(staging_root)],
            cwd=root,
            check=False,
        ).returncode
        == 0
    ):
        produced = root / f"{PACKAGE_NAME}-{version}.pkg"
        if produced.is_file():
            shutil.move(str(produced), str(releases_dir / produced.name))
            created = True
    if not created:
        print("ERROR: All pkg create methods failed", file=sys.stderr)
        return None

    candidates = sorted(releases_dir.glob(f"{PACKAGE_NAME}-{version}*.pkg"))
    if not candidates:
        print("ERROR: pkg create did not produce a .pkg file", file=sys.stderr)
        return None

    arch = filename_arch()
    normalized = releases_dir / f"{PACKAGE_NAME}_{version}_freebsd_{arch}.pkg"
    normalized.unlink(missing_ok=True)
    shutil.move(str(candidates[0]), str(normalized))
    (releases_dir / ".freebsd.env").write_text(
        f"FREEBSD_ARCH := {arch}\n", encoding="utf-8"
    )
    write_sha256(releases_dir, normalized, remove_existing=True)
    return normalized


def main(argv: list[str] | None = None) -> int:
    """Build and verify the local FreeBSD .pkg; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_freebsd_pkg.py",
        description="Local FreeBSD package builder for ECLI.",
    )
    parser.parse_args(argv)

    root = Path(
        os.environ.get("PROJECT_ROOT") or Path(__file__).resolve().parent.parent
    )

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("This script requires root privileges. Restarting with sudo...")
        os.execvp(
            "sudo",
            [
                "sudo",
                f"PROJECT_ROOT={root}",
                sys.executable,
                str(Path(__file__).resolve()),
                *(argv if argv is not None else sys.argv[1:]),
            ],
        )

    if not check_dependencies():
        print("ERROR: Dependencies check failed", file=sys.stderr)
        return EXIT_ERROR
    if not install_system_dependencies():
        return EXIT_ERROR
    if not install_python_dependencies(root):
        return EXIT_ERROR

    version = read_version(root)
    print(f"Detected version: {version}")

    executable = build_binary(root)
    if executable is None:
        return EXIT_ERROR

    releases_dir = root / "releases" / version
    staging_root = root / "build" / "freebsd_pkg_staging"
    meta_dir = root / "build" / "freebsd_pkg_meta"
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
    releases_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    if not stage_package_files(root, staging_root, executable, version):
        return EXIT_ERROR

    pkg_path = create_package(root, staging_root, meta_dir, releases_dir, version)
    if pkg_path is None:
        return EXIT_ERROR

    if (
        subprocess.run(
            ["pkg", "info", "-F", str(pkg_path)], capture_output=True, check=False
        ).returncode
        == 0
    ):
        subprocess.run(["pkg", "info", "-l", "-F", str(pkg_path)], check=False)

    print("==> BUILD COMPLETE")
    print(f"Package: {pkg_path}")
    if (Path(f"{pkg_path}.sha256")).is_file():
        print(f"Checksum: {pkg_path}.sha256")
    print("==> Recording F4 linter provisioning evidence")
    f4_rc = run_or_record_f4_linter_provisioning(root, "freebsd-pkg")
    if f4_rc != EXIT_OK:
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
