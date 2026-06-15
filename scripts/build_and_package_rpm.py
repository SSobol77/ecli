#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_rpm.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build and package ECLI into an ``.rpm``.

Canonical Python replacement for ``scripts/build-and-package-rpm.sh`` and the
shared flow behind ``scripts/build-and-package-opensuse-rpm.sh``. It builds a
PyInstaller binary, stages an FHS payload, produces an RPM with FPM, normalizes
the filename to ``ecli_<version>_<platform>_<arch>.rpm``, and writes a SHA256
sidecar.

Contract-relevant environment variables are preserved:

* ``PYTHON`` (default ``python3.11``)
* ``PACKAGE_NAME``, ``MAINTAINER``, ``HOMEPAGE``, ``LICENSE``, ``CATEGORY``
* ``RPM_PLATFORM_LABEL`` (default ``linux``; the openSUSE flow sets ``opensuse``)
* ``RPM_DEPENDS`` (``;``-separated; default ``ncurses-libs;libyaml``)
* ``RELEASES_DIR`` (must equal ``releases/<version>``)

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built and verified
* ``1`` missing tool/version/output, or an invalid ``RELEASES_DIR`` override
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


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def python_bin() -> str:
    return env("PYTHON", "python3.11")


def read_version(root: Path, interpreter: str) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def normalized_arch() -> str:
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


def desktop_entry(package_name: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ECLI\n"
        "Comment=Terminal-first engineering operations workbench\n"
        f"Exec={package_name}\n"
        f"Icon={package_name}\n"
        "Terminal=true\n"
        "Categories=Development;IDE;Utility;\n"
        "StartupNotify=false\n"
    )


def man_page(package_name: str, version: str, maintainer: str, homepage: str) -> str:
    date_str = datetime.now().strftime("%B %Y")
    author = maintainer.split(" <", 1)[0]
    return (
        f'.TH {package_name.upper()} 1 "{date_str}" "{package_name} {version}" '
        '"User Commands"\n'
        ".SH NAME\n"
        f"{package_name} - Terminal code editor\n"
        ".SH SYNOPSIS\n"
        f".B {package_name}\n"
        "[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]\n"
        ".SH DESCRIPTION\n"
        f"{package_name.upper()} is a fast terminal code editor with AI and Git "
        "integration.\n"
        ".SH OPTIONS\n"
        "\\fB--help\\fR     Show help\n"
        "\\fB--version\\fR  Show version\n"
        ".SH AUTHOR\n"
        f"{author}\n"
        ".SH HOMEPAGE\n"
        f"{homepage}\n"
    )


def find_executable(root: Path, package_name: str) -> Path | None:
    onedir = root / "dist" / package_name / package_name
    onefile = root / "dist" / package_name
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    return None


def run_pyinstaller(root: Path, package_name: str) -> None:
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
            package_name,
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


def stage_payload(
    root: Path,
    staging: Path,
    executable: Path,
    package_name: str,
    version: str,
    maintainer: str,
    homepage: str,
) -> None:
    bin_dir = staging / "usr/bin"
    apps_dir = staging / "usr/share/applications"
    icon_dir = staging / "usr/share/icons/hicolor/256x256/apps"
    doc_dir = staging / "usr/share/doc" / package_name
    man_dir = staging / "usr/share/man/man1"
    for directory in (bin_dir, apps_dir, icon_dir, doc_dir, man_dir):
        directory.mkdir(parents=True, exist_ok=True)

    install_file(executable, bin_dir / package_name, 0o755)

    desktop_src = root / "packaging/linux/fpm-common" / f"{package_name}.desktop"
    if desktop_src.is_file():
        install_file(desktop_src, apps_dir / f"{package_name}.desktop", 0o644)
    else:
        (apps_dir / f"{package_name}.desktop").write_text(
            desktop_entry(package_name), encoding="utf-8"
        )

    icon_src = root / "src/ecli/assets/ecli.png"
    if icon_src.is_file():
        install_file(icon_src, icon_dir / f"{package_name}.png", 0o644)

    for name in ("LICENSE", "README.md"):
        src = root / name
        if src.is_file():
            install_file(src, doc_dir / name, 0o644)
            gzip_file(doc_dir / name)

    man_dst = man_dir / f"{package_name}.1"
    repo_man = root / "man" / f"{package_name}.1"
    if repo_man.is_file():
        install_file(repo_man, man_dst, 0o644)
    else:
        man_dst.write_text(
            man_page(package_name, version, maintainer, homepage), encoding="utf-8"
        )
    gzip_file(man_dst)


def build_fpm_command(
    staging: Path,
    package_name: str,
    version: str,
    maintainer: str,
    homepage: str,
    license_id: str,
    category: str,
    depends: list[str],
    tmp_rpm_out: Path,
) -> list[str]:
    """Construct the FPM .rpm command array (deterministic, no shell)."""
    cmd = [
        "fpm",
        "-s",
        "dir",
        "-t",
        "rpm",
        "-n",
        package_name,
        "-v",
        version,
        "--maintainer",
        maintainer,
        "--description",
        "Ecli — terminal DevOps editor with AI and Git integration",
        "--url",
        homepage,
        "--license",
        license_id,
        "--category",
        category,
        "--rpm-os",
        "linux",
        "--rpm-summary",
        "Terminal DevOps editor with AI and Git integration",
    ]
    for dep in depends:
        cmd += ["--depends", dep]
    cmd += [
        "--rpm-auto-add-directories",
        "--after-install",
        "packaging/linux/fpm-common/postinst",
        "--before-remove",
        "packaging/linux/fpm-common/prerm",
        "--after-remove",
        "packaging/linux/fpm-common/postrm",
        "--package",
        str(tmp_rpm_out),
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
    """Build the RPM and verify it; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_rpm.py",
        description="Build and package ECLI into an .rpm (generic or openSUSE).",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    package_name = env("PACKAGE_NAME", "ecli")
    maintainer = env("MAINTAINER", "Siergej Sobolewski <s.sobolewski@hotmail.com>")
    homepage = env("HOMEPAGE", "https://ecli.io")
    license_id = env("LICENSE", "GPL-2.0-only")
    category = env("CATEGORY", "editors")
    platform_label = env("RPM_PLATFORM_LABEL", "linux")
    depends = [d for d in env("RPM_DEPENDS", "ncurses-libs;libyaml").split(";") if d]
    arch = normalized_arch()

    version = read_version(root, python_bin())
    print(f"==> Version: {version}")

    releases_dir_value = env("RELEASES_DIR", f"releases/{version}")
    if releases_dir_value != f"releases/{version}":
        print(
            f"ERROR: RELEASES_DIR must match current project version: "
            f"releases/{version}",
            file=sys.stderr,
        )
        return EXIT_ERROR
    releases_dir = root / releases_dir_value

    print("==> Checking production runtime imports")
    subprocess.run(
        [python_bin(), "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    print("==> Checking build tools")
    for tool in ("python3.11", python_bin(), "pyinstaller", "fpm", "rpmbuild", "gzip"):
        if not require_tool(tool):
            return EXIT_ERROR

    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / ".linux.env").write_text(
        f"LINUX_ARCH := {arch}\n", encoding="utf-8"
    )
    normalized = releases_dir / f"{package_name}_{version}_{platform_label}_{arch}.rpm"
    normalized.unlink(missing_ok=True)
    (releases_dir / f"{normalized.name}.sha256").unlink(missing_ok=True)

    print("==> Building executable with PyInstaller")
    build_dir = root / "build" / "rpm"
    staging = build_dir / "staging"
    shutil.rmtree(build_dir, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    run_pyinstaller(root, package_name)
    executable = find_executable(root, package_name)
    if executable is None:
        print("ERROR: PyInstaller output not found in dist/", file=sys.stderr)
        return EXIT_ERROR

    print("==> Staging payload (FHS)")
    stage_payload(
        root, staging, executable, package_name, version, maintainer, homepage
    )

    print("==> Building .rpm with FPM")
    tmp_rpm_out = releases_dir / f"{package_name}-{version}.rpm"
    subprocess.run(
        build_fpm_command(
            staging,
            package_name,
            version,
            maintainer,
            homepage,
            license_id,
            category,
            depends,
            tmp_rpm_out,
        ),
        cwd=root,
        check=True,
    )

    print("==> Locating final RPM")
    candidates = sorted(releases_dir.glob(f"{package_name}-*.rpm"))
    if not candidates:
        print(f"ERROR: RPM not found under {releases_dir}", file=sys.stderr)
        return EXIT_ERROR
    actual_rpm = candidates[0]

    if actual_rpm != normalized:
        shutil.copy2(actual_rpm, normalized)

    print("==> Generating SHA-256 checksum")
    write_sha256(releases_dir, normalized)

    print("DONE")
    print(f"RPM (actual): {actual_rpm}")
    print(f"RPM (normalized): {normalized}")
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(normalized)],
        cwd=root,
        check=True,
        env={**os.environ, "PYTHON": python_bin()},
    )

    if shutil.which("rpm"):
        print("==> RPM metadata (quick peek):")
        subprocess.run(["rpm", "-qpi", str(actual_rpm)], cwd=root, check=False)

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
