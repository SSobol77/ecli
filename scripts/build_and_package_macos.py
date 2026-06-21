#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_macos.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build the macOS Universal2 DMG (and optional ``.app`` bundle).

Canonical Python replacement for ``scripts/build-and-package-macos.sh``. It
builds per-arch PyInstaller binaries, merges them with ``lipo`` into a Universal2
executable, ad-hoc codesigns it, and produces
``releases/<version>/ecli_<version>_macos_universal2.dmg`` plus a SHA256 sidecar.

Phase 1 policy is preserved: ad-hoc codesign only; no Developer ID, notarization,
or stapling. When ``ECLI_BUILD_MACOS_APP=1`` an ``ECLI.app`` bundle is staged.

This script orchestrates the local macOS toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` DMG built and verified
* ``1`` not on Darwin, version unreadable, or Universal2 merge failed
* ``2`` DMG missing after creation
* ``3`` SHA256 sidecar missing after creation
* ``5`` a required macOS tool is missing
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

from packaging_common import require_tool


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DMG_MISSING = 2
EXIT_SHA_MISSING = 3
EXIT_MISSING_TOOL = 5

APP_NAME = "ECLI"
MACOS_ARCH = "universal2"
ONIGURUMA_HEADER = "oniguruma.h"
ONIGURUMA_PKG_CONFIG_NAME = "oniguruma"
ONIGURUMA_COMMON_PREFIXES = (
    "/opt/homebrew/opt/oniguruma",
    "/usr/local/opt/oniguruma",
    "/opt/homebrew",
    "/usr/local",
)


def python_bin() -> str:
    return os.environ.get("PYTHON", "python3")


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def build_arch(root: Path, spec: Path, arch_name: str, arch_flag: str) -> Path | None:
    """Build a per-arch PyInstaller binary; return its path or None on failure."""
    native_env = macos_native_dependency_env(os.environ)
    venv_dir = root / "build" / f"macos_venv_{arch_name}"
    build_dir = root / "build" / f"macos_{arch_name}"
    dist_dir = root / "dist" / f"macos_{arch_name}"
    output = dist_dir / "ecli"
    venv_python = venv_dir / "bin" / "python"

    print(f"==> Preparing {arch_name} Python environment...")
    shutil.rmtree(venv_dir, ignore_errors=True)
    subprocess.run([python_bin(), "-m", "venv", str(venv_dir)], cwd=root, check=True)
    subprocess.run(
        [
            "arch",
            arch_flag,
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "wheel",
            "setuptools",
        ],
        cwd=root,
        env=native_env,
        check=True,
    )
    subprocess.run(
        [
            "arch",
            arch_flag,
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-e",
            ".[dev]",
        ],
        cwd=root,
        env=native_env,
        check=True,
    )

    print(f"==> Building {arch_name} PyInstaller binary...")
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(dist_dir, ignore_errors=True)
    subprocess.run(
        [
            "arch",
            arch_flag,
            str(venv_python),
            "-m",
            "PyInstaller",
            str(spec),
            "--clean",
            "--noconfirm",
            "--workpath",
            str(build_dir),
            "--distpath",
            str(dist_dir),
        ],
        cwd=root,
        env={
            **native_env,
            "ECLI_REPO_ROOT": str(root),
            "ECLI_PYINSTALLER_ONEDIR": "0",
            "ECLI_BUILD_MACOS_APP": "0",
        },
        check=True,
    )

    if not (output.is_file() and os.access(output, os.X_OK)):
        print(f"ERR PyInstaller output missing: {output}", file=sys.stderr)
        return None
    subprocess.run(["lipo", "-info", str(output)], cwd=root, check=True)
    return output


def info_plist(version: str, icon_entry: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"  <key>CFBundleName</key><string>{APP_NAME}</string>\n"
        f"  <key>CFBundleDisplayName</key><string>{APP_NAME}</string>\n"
        "  <key>CFBundleIdentifier</key><string>io.ecli.editor</string>\n"
        f"  <key>CFBundleVersion</key><string>{version}</string>\n"
        f"  <key>CFBundleShortVersionString</key><string>{version}</string>\n"
        "  <key>CFBundleExecutable</key><string>ecli</string>\n"
        "  <key>CFBundlePackageType</key><string>APPL</string>\n"
        "  <key>LSMinimumSystemVersion</key><string>12.0</string>\n"
        "  <key>NSHighResolutionCapable</key><true/>\n"
        f"{icon_entry}\n"
        "</dict>\n"
        "</plist>\n"
    )


def check_packaging_prerequisites() -> int:
    for tool in ("arch", "lipo", "codesign", "hdiutil", "shasum", "pkg-config"):
        if not require_tool(tool):
            return EXIT_MISSING_TOOL
    if shutil.which(python_bin()) is None:
        print(f"ERR Missing Python interpreter: {python_bin()}", file=sys.stderr)
        return EXIT_MISSING_TOOL
    if not check_oniguruma_prerequisites():
        return EXIT_MISSING_TOOL
    return EXIT_OK


def _capture_stdout(command: list[str]) -> str | None:
    """Return stripped stdout for a command, or ``None`` on failure."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output = result.stdout.strip()
    return output or None


def _unique_existing_paths(paths_in_order: list[Path]) -> list[Path]:
    """Return existing paths without duplicates, preserving order."""
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths_in_order:
        resolved = path.resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def oniguruma_prefixes() -> list[Path]:
    """Return deterministic candidate prefixes for macOS Oniguruma."""
    candidates: list[Path] = []
    env_prefix = os.environ.get("ECLI_ONIGURUMA_PREFIX")
    if env_prefix:
        candidates.append(Path(env_prefix))
    brew_prefix = _capture_stdout(["brew", "--prefix", "oniguruma"])
    if brew_prefix:
        candidates.append(Path(brew_prefix))
    candidates.extend(Path(prefix) for prefix in ONIGURUMA_COMMON_PREFIXES)
    return _unique_existing_paths(candidates)


def _oniguruma_include_dirs(prefixes: list[Path]) -> list[Path]:
    return _unique_existing_paths([prefix / "include" for prefix in prefixes])


def _oniguruma_lib_dirs(prefixes: list[Path]) -> list[Path]:
    return _unique_existing_paths([prefix / "lib" for prefix in prefixes])


def _oniguruma_pkg_config_dirs(prefixes: list[Path]) -> list[Path]:
    return _unique_existing_paths(
        [
            *(prefix / "lib" / "pkgconfig" for prefix in prefixes),
            *(prefix / "share" / "pkgconfig" for prefix in prefixes),
        ]
    )


def _prepend_flags(existing: str | None, flags: list[str]) -> str:
    parts = [*flags, *(existing or "").split()]
    return " ".join(dict.fromkeys(part for part in parts if part))


def _prepend_path_list(existing: str | None, paths_in_order: list[Path]) -> str:
    parts = [str(path) for path in paths_in_order]
    if existing:
        parts.extend(existing.split(os.pathsep))
    return os.pathsep.join(dict.fromkeys(part for part in parts if part))


def macos_native_dependency_env(base_env: Mapping[str, str]) -> dict[str, str]:
    """Return env with deterministic Oniguruma build flags for pip subprocesses."""
    env = dict(base_env)
    prefixes = oniguruma_prefixes()
    include_dirs = _oniguruma_include_dirs(prefixes)
    lib_dirs = _oniguruma_lib_dirs(prefixes)
    pkg_config_dirs = _oniguruma_pkg_config_dirs(prefixes)
    include_flags = [f"-I{path}" for path in include_dirs]
    lib_flags = [f"-L{path}" for path in lib_dirs]
    env["CPPFLAGS"] = _prepend_flags(env.get("CPPFLAGS"), include_flags)
    env["CFLAGS"] = _prepend_flags(env.get("CFLAGS"), include_flags)
    env["LDFLAGS"] = _prepend_flags(env.get("LDFLAGS"), lib_flags)
    env["PKG_CONFIG_PATH"] = _prepend_path_list(
        env.get("PKG_CONFIG_PATH"), pkg_config_dirs
    )
    return env


def check_oniguruma_prerequisites() -> bool:
    """Verify native Oniguruma headers/libs are visible before pip installs."""
    prefixes = oniguruma_prefixes()
    include_dirs = _oniguruma_include_dirs(prefixes)
    lib_dirs = _oniguruma_lib_dirs(prefixes)
    header_found = any(
        (include_dir / ONIGURUMA_HEADER).is_file() for include_dir in include_dirs
    )
    pkg_config_found = (
        subprocess.run(
            ["pkg-config", "--exists", ONIGURUMA_PKG_CONFIG_NAME],
            check=False,
        ).returncode
        == 0
    )
    lib_found = any(
        (lib_dir / candidate).exists()
        for lib_dir in lib_dirs
        for candidate in ("libonig.dylib", "libonig.a")
    )
    if header_found and (pkg_config_found or lib_found):
        print("OK  Oniguruma native dependency is available for TextMate builds.")
        return True
    searched = ", ".join(str(prefix) for prefix in prefixes) or "<none>"
    print(
        "ERR Missing Oniguruma native dependency for python-textmate/onigurumacffi. "
        "Install Homebrew packages 'oniguruma' and 'pkg-config' before macOS "
        f"packaging. Searched prefixes: {searched}",
        file=sys.stderr,
    )
    return False


def verify_python_arches(root: Path) -> None:
    for arch_flag, label in (("-x86_64", "python-x86_64"), ("-arm64", "python-arm64")):
        subprocess.run(
            [
                "arch",
                arch_flag,
                python_bin(),
                "-c",
                f'import platform; print("{label}", platform.machine())',
            ],
            cwd=root,
            check=True,
        )


def clean_previous_builds(root: Path, universal_dir: Path) -> None:
    print("==> Cleaning previous macOS build artifacts...")
    for path in (
        root / "build/macos_venv_x86_64",
        root / "build/macos_venv_arm64",
        root / "build/macos_x86_64",
        root / "build/macos_arm64",
        universal_dir,
        root / "dist/macos_x86_64",
        root / "dist/macos_arm64",
    ):
        shutil.rmtree(path, ignore_errors=True)


def build_arch_binaries(root: Path, spec: Path) -> bool:
    return (
        build_arch(root, spec, "x86_64", "-x86_64") is not None
        and build_arch(root, spec, "arm64", "-arm64") is not None
    )


def merge_universal_binary(
    root: Path, universal_dir: Path, universal_bin: Path
) -> bool:
    print("==> Merging binaries into Universal2 executable...")
    universal_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "lipo",
            "-create",
            "dist/macos_x86_64/ecli",
            "dist/macos_arm64/ecli",
            "-output",
            str(universal_bin),
        ],
        cwd=root,
        check=True,
    )
    universal_bin.chmod(0o755)
    lipo_info = subprocess.run(
        ["lipo", "-info", str(universal_bin)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    print(lipo_info)
    if "x86_64" in lipo_info and "arm64" in lipo_info:
        return True
    print(
        "ERR Universal2 binary does not contain both x86_64 and arm64.",
        file=sys.stderr,
    )
    return False


def stage_app_bundle(
    root: Path, dmg_staging: Path, universal_bin: Path, version: str
) -> None:
    app_dir = dmg_staging / f"{APP_NAME}.app"
    contents = app_dir / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(parents=True, exist_ok=True)
    shutil.copy2(universal_bin, contents / "MacOS" / "ecli")
    (contents / "MacOS" / "ecli").chmod(0o755)
    icns = root / "img" / "logo_m.icns"
    if icns.is_file():
        shutil.copy2(icns, contents / "Resources" / "AppIcon.icns")
        icon_entry = "  <key>CFBundleIconFile</key><string>AppIcon</string>"
    else:
        icon_entry = ""
        print(
            "ERR No deterministic .icns asset found; macOS app icon is not set.",
            file=sys.stderr,
        )
    (contents / "Info.plist").write_text(
        info_plist(version, icon_entry), encoding="utf-8"
    )
    subprocess.run(
        ["codesign", "--sign", "-", "--force", "--deep", str(app_dir)],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["codesign", "--verify", "--verbose", str(app_dir)], cwd=root, check=True
    )
    (dmg_staging / "Applications").symlink_to("/Applications")


def stage_dmg_tree(
    root: Path, dmg_staging: Path, universal_bin: Path, version: str
) -> None:
    print("==> Creating DMG staging tree...")
    shutil.rmtree(dmg_staging, ignore_errors=True)
    dmg_staging.mkdir(parents=True, exist_ok=True)

    if os.environ.get("ECLI_BUILD_MACOS_APP", "0") == "1":
        stage_app_bundle(root, dmg_staging, universal_bin, version)
        return

    shutil.copy2(universal_bin, dmg_staging / "ecli")
    (dmg_staging / "ecli").chmod(0o755)


def create_dmg(
    root: Path,
    dmg_staging: Path,
    dmg_path: Path,
    sha_path: Path,
    pkg_base: str,
    version: str,
) -> None:
    print("==> Creating compressed DMG...")
    dmg_path.unlink(missing_ok=True)
    sha_path.unlink(missing_ok=True)
    vol_name = f"ECLI-{version}"
    dmg_tmp = dmg_path.with_name(f"{pkg_base}-tmp.dmg")
    dmg_tmp.unlink(missing_ok=True)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            vol_name,
            "-srcfolder",
            str(dmg_staging),
            "-ov",
            "-fs",
            "HFS+",
            "-format",
            "UDRW",
            str(dmg_tmp),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "hdiutil",
            "convert",
            str(dmg_tmp),
            "-format",
            "UDZO",
            "-imagekey",
            "zlib-level=9",
            "-o",
            str(dmg_path),
        ],
        cwd=root,
        check=True,
    )
    dmg_tmp.unlink(missing_ok=True)


def write_macos_sha256_sidecar(
    releases_dir: Path, dmg_path: Path, sha_path: Path
) -> None:
    print("==> Writing SHA256 sidecar...")
    result = subprocess.run(
        ["shasum", "-a", "256", dmg_path.name],
        cwd=releases_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    sha_path.write_text(result.stdout, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Build and verify the macOS DMG; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_macos.py",
        description="Build the macOS Universal2 DMG.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent

    if platform.system() != "Darwin":
        print("ERR macOS packaging must run on Darwin.", file=sys.stderr)
        return EXIT_ERROR

    spec = root / "packaging" / "pyinstaller" / "ecli.spec"

    prereq_rc = check_packaging_prerequisites()
    if prereq_rc != EXIT_OK:
        return prereq_rc

    version = read_version(root)
    print(f"OK  Version: {version}")

    subprocess.run(
        [python_bin(), "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    releases_dir = root / "releases" / version
    pkg_base = f"ecli_{version}_macos_{MACOS_ARCH}"
    dmg_path = releases_dir / f"{pkg_base}.dmg"
    sha_path = releases_dir / f"{pkg_base}.dmg.sha256"
    universal_dir = root / "build" / "macos_universal2"
    universal_bin = universal_dir / "ecli"

    verify_python_arches(root)
    clean_previous_builds(root, universal_dir)

    if not build_arch_binaries(root, spec):
        return EXIT_ERROR

    if not merge_universal_binary(root, universal_dir, universal_bin):
        return EXIT_ERROR

    print("==> Applying ad-hoc codesign...")
    subprocess.run(
        ["codesign", "--sign", "-", "--force", str(universal_bin)], cwd=root, check=True
    )
    subprocess.run(
        ["codesign", "--verify", "--verbose", str(universal_bin)], cwd=root, check=True
    )

    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / ".macos.env").write_text(
        "MACOS_ARCH=universal2\n", encoding="utf-8"
    )

    dmg_staging = root / "build" / "macos_dmg"
    stage_dmg_tree(root, dmg_staging, universal_bin, version)
    create_dmg(root, dmg_staging, dmg_path, sha_path, pkg_base, version)
    write_macos_sha256_sidecar(releases_dir, dmg_path, sha_path)

    if not dmg_path.is_file():
        print(f"ERR Missing {dmg_path}", file=sys.stderr)
        return EXIT_DMG_MISSING
    if not sha_path.is_file():
        print(f"ERR Missing {sha_path}", file=sys.stderr)
        return EXIT_SHA_MISSING

    print(f"OK  DMG: {dmg_path}")
    print(f"OK  SHA: {sha_path}")
    subprocess.run(
        [sys.executable, "scripts/verify_runtime.py", str(dmg_path)],
        cwd=root,
        check=True,
    )
    print("==> Done.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
