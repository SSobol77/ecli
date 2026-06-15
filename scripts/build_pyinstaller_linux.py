#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_pyinstaller_linux.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build the ECLI binary with PyInstaller on Linux.

Canonical Python replacement for ``scripts/build_pyinstaller_linux.sh``. It
prefers ``packaging/pyinstaller/ecli.spec`` and falls back to a ``main.py``
one-file build, then runs an isolated runtime smoke check on the produced
binary.

This script orchestrates the local toolchain only. It never publishes, uploads,
signs, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` build and smoke check succeeded
* ``1`` a required tool/module is missing, or the build produced no binary
* a non-zero subprocess return code is propagated when an underlying tool fails
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_ERROR = 1

PACKAGE_NAME = "ecli"
MAIN_SCRIPT = "main.py"
SPEC_FILE = Path("packaging/pyinstaller/ecli.spec")


def require_tool(name: str) -> bool:
    """Return True if ``name`` is on PATH; otherwise print an error and False."""
    if shutil.which(name) is None:
        print(f"ERR: missing required tool: {name}", file=sys.stderr)
        return False
    return True


def require_python_module(module: str) -> bool:
    """Return True if ``module`` is importable; otherwise print an error."""
    if importlib.util.find_spec(module) is None:
        print(f"ERR: missing required Python module: {module}", file=sys.stderr)
        return False
    return True


def build_pyi_args(root: Path) -> list[str]:
    """Build the spec-less PyInstaller argument list (matches the shell flags)."""
    args = ["--onefile", "--clean", "--noconfirm", "--strip"]
    if (root / "config.toml").is_file():
        args += ["--add-data", "config.toml:."]
    if (root / "pyproject.toml").is_file():
        args += ["--add-data", "pyproject.toml:."]
    if (root / "config").is_dir():
        args += ["--add-data", "config:config"]
    return args


def find_executable(root: Path) -> Path | None:
    """Return the produced PyInstaller binary, or None if absent."""
    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file():
        return onedir
    if onefile.is_file():
        return onefile
    return None


def main(argv: list[str] | None = None) -> int:
    """Build the Linux PyInstaller binary and smoke-check it."""
    parser = argparse.ArgumentParser(
        prog="build_pyinstaller_linux.py",
        description="Build the ECLI binary with PyInstaller (Linux).",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent

    print("==> Checking prerequisites")
    if not (
        require_tool("python3")
        and require_tool("pyinstaller")
        and require_python_module("PyInstaller")
    ):
        return EXIT_ERROR

    subprocess.run(
        [sys.executable, str(root / "scripts" / "check_runtime_imports.py")],
        cwd=root,
        check=True,
    )

    print("==> Cleaning previous artifacts")
    shutil.rmtree(root / "build", ignore_errors=True)
    shutil.rmtree(root / "dist", ignore_errors=True)

    print("==> Building with PyInstaller")
    if (root / SPEC_FILE).is_file():
        subprocess.run(
            ["pyinstaller", str(SPEC_FILE), "--clean", "--noconfirm"],
            cwd=root,
            check=True,
        )
    else:
        subprocess.run(
            ["pyinstaller", MAIN_SCRIPT, "--name", PACKAGE_NAME, *build_pyi_args(root)],
            cwd=root,
            check=True,
        )

    executable = find_executable(root)
    if executable is None:
        print("Build output not found in dist/. Aborting.", file=sys.stderr)
        return EXIT_ERROR

    print(f"==> OK: {executable.relative_to(root)}")
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "verify_runtime.py"),
            "--allow-nonrelease",
            str(executable),
        ],
        cwd=root,
        check=True,
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
