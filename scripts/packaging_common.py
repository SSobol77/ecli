#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/packaging_common.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Small side-effect-free helpers shared by ECLI packaging scripts."""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_DOCS = ("LICENSE", "README.md")


def normalize_arch(raw: str) -> str:
    if raw in ("amd64", "x86_64"):
        return "x86_64"
    if raw in ("aarch64", "arm64"):
        return "arm64"
    return raw


def filename_arch() -> str:
    return normalize_arch(os.uname().machine)


def missing_tool_message(name: str) -> str:
    return f"ERROR: Missing required tool: {name}"


def require_tool(name: str) -> bool:
    if shutil.which(name) is None:
        print(missing_tool_message(name), file=sys.stderr)
        return False
    return True


def install_file(src: Path, dst: Path, mode: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(mode)


def gzip_file(path: Path, level: int = 9, mtime: int = 0) -> Path:
    gz = path.with_name(path.name + ".gz")
    gz.write_bytes(gzip.compress(path.read_bytes(), compresslevel=level, mtime=mtime))
    path.unlink()
    return gz


def write_sha256(
    releases_dir: Path,
    artifact: Path,
    *,
    prefer_freebsd_sha256: bool = False,
    remove_existing: bool = False,
) -> None:
    name = artifact.name
    sidecar = releases_dir / f"{name}.sha256"
    if remove_existing:
        sidecar.unlink(missing_ok=True)

    tool_order = (
        ("sha256", "shasum")
        if prefer_freebsd_sha256
        else ("sha256sum", "shasum", "sha256")
    )
    for tool in tool_order:
        if shutil.which(tool) is None:
            continue
        if tool == "sha256sum":
            result = subprocess.run(
                ["sha256sum", name],
                cwd=releases_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            sidecar.write_text(result.stdout, encoding="utf-8")
            return
        if tool == "shasum":
            result = subprocess.run(
                ["shasum", "-a", "256", name],
                cwd=releases_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            sidecar.write_text(result.stdout, encoding="utf-8")
            return

        digest = subprocess.run(
            ["sha256", "-q", str(artifact)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        sidecar.write_text(f"{digest}  {name}\n", encoding="utf-8")
        return

    print("WARNING: no sha256 tool found; skipping checksum.", file=sys.stderr)


def install_docs(
    root: Path,
    doc_dir: Path,
    names: tuple[str, ...] = DEFAULT_DOCS,
) -> None:
    for name in names:
        src = root / name
        if src.is_file():
            install_file(src, doc_dir / name, 0o644)


def install_desktop_entry(
    root: Path, dst: Path, package_name: str, fallback_text: str
) -> None:
    src = root / "packaging/linux/fpm-common" / f"{package_name}.desktop"
    if src.is_file():
        install_file(src, dst, 0o644)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(fallback_text, encoding="utf-8")


def install_icon(root: Path, dst: Path) -> bool:
    src = root / "src/ecli/assets/ecli.png"
    if not src.is_file():
        return False
    install_file(src, dst, 0o644)
    return True
