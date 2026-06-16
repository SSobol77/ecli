# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_common.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for shared packaging helpers."""

from __future__ import annotations

import gzip
import os
import stat
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def common(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/packaging_common.py", "packaging_common"
    )


def test_normalize_arch(common: ModuleType) -> None:
    assert common.normalize_arch("amd64") == "x86_64"
    assert common.normalize_arch("x86_64") == "x86_64"
    assert common.normalize_arch("aarch64") == "arm64"
    assert common.normalize_arch("arm64") == "arm64"
    assert common.normalize_arch("riscv64") == "riscv64"


def test_filename_arch(common: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        common.os,
        "uname",
        lambda: os.uname_result(("Linux", "h", "r", "v", "aarch64")),
    )
    assert common.filename_arch() == "arm64"


def test_install_file_copies_and_chmods(common: ModuleType, tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "nested" / "dst.txt"
    src.write_text("payload", encoding="utf-8")

    common.install_file(src, dst, 0o640)

    assert dst.read_text(encoding="utf-8") == "payload"
    assert stat.S_IMODE(dst.stat().st_mode) == 0o640


def test_gzip_file_is_deterministic_and_removes_source(
    common: ModuleType, tmp_path: Path
) -> None:
    src = tmp_path / "manual.1"
    src.write_bytes(b"manual page\n")

    gz = common.gzip_file(src)

    assert gz == tmp_path / "manual.1.gz"
    assert not src.exists()
    assert gzip.decompress(gz.read_bytes()) == b"manual page\n"


def test_write_sha256_uses_basename_sidecar(
    common: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "ecli.pkg"
    artifact.write_bytes(b"payload")
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "/usr/bin/sha256sum" if name == "sha256sum" else None

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        assert cwd == tmp_path
        return subprocess.CompletedProcess(cmd, 0, "abcd  ecli.pkg\n", "")

    monkeypatch.setattr(common.shutil, "which", fake_which)
    monkeypatch.setattr(common.subprocess, "run", fake_run)

    common.write_sha256(tmp_path, artifact, remove_existing=True)

    assert calls == [["sha256sum", "ecli.pkg"]]
    assert (tmp_path / "ecli.pkg.sha256").read_text(encoding="utf-8") == (
        "abcd  ecli.pkg\n"
    )


def test_write_sha256_can_prefer_freebsd_sha256(
    common: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "ecli.pkg"
    artifact.write_bytes(b"payload")

    monkeypatch.setattr(
        common.shutil,
        "which",
        lambda name: "/sbin/sha256" if name == "sha256" else None,
    )
    monkeypatch.setattr(
        common.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "beef\n", ""),
    )

    common.write_sha256(tmp_path, artifact, prefer_freebsd_sha256=True)

    assert (tmp_path / "ecli.pkg.sha256").read_text(encoding="utf-8") == (
        "beef  ecli.pkg\n"
    )


def test_install_docs_copies_existing_docs_only(
    common: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    doc_dir = tmp_path / "docs"

    common.install_docs(root, doc_dir)

    copied = doc_dir / "LICENSE"
    assert copied.read_text(encoding="utf-8") == "license\n"
    assert stat.S_IMODE(copied.stat().st_mode) == 0o644
    assert not (doc_dir / "README.md").exists()
