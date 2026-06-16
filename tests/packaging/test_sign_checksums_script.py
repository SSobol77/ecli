# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_sign_checksums_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/sign_checksums.py sidecar generation."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


SIDECAR_LINE = re.compile(r"^[0-9a-f]{64} {2}[^/\n]+\n$")


@pytest.fixture
def sign_checksums(repo_root: Path) -> ModuleType:
    return load_script_module(repo_root, "scripts/sign_checksums.py", "sign_checksums")


@pytest.fixture
def verify_artifact(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_artifact.py", "verify_artifact"
    )


def test_sidecar_has_coreutils_basename_only_format(
    sign_checksums: ModuleType, tmp_path: Path
) -> None:
    payload = b"ecli artifact bytes\n"
    artifact = tmp_path / "ecli_0.0.1_linux_x86_64.deb"
    artifact.write_bytes(payload)

    assert sign_checksums.main([str(artifact)]) == sign_checksums.EXIT_OK

    sidecar = artifact.with_name(f"{artifact.name}.sha256")
    content = sidecar.read_text(encoding="utf-8")
    assert SIDECAR_LINE.match(content), (
        f"sidecar not coreutils basename-only: {content!r}"
    )
    assert content == f"{hashlib.sha256(payload).hexdigest()}  {artifact.name}\n"


def test_sign_then_verify_roundtrip(
    sign_checksums: ModuleType, verify_artifact: ModuleType, tmp_path: Path
) -> None:
    artifact = tmp_path / "ecli_0.0.1_macos_universal2.dmg"
    artifact.write_bytes(b"dmg payload")

    assert sign_checksums.main([str(artifact)]) == sign_checksums.EXIT_OK
    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_OK


def test_multiple_artifacts_each_get_a_sidecar(
    sign_checksums: ModuleType, tmp_path: Path
) -> None:
    artifacts = []
    for name in ("a.bin", "b.bin", "c.bin"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        artifacts.append(path)

    assert sign_checksums.main([str(p) for p in artifacts]) == sign_checksums.EXIT_OK
    for path in artifacts:
        assert path.with_name(f"{path.name}.sha256").is_file()


def test_missing_artifact_returns_one_and_writes_nothing(
    sign_checksums: ModuleType, tmp_path: Path
) -> None:
    missing = tmp_path / "absent.bin"
    assert sign_checksums.main([str(missing)]) == sign_checksums.EXIT_MISSING_ARTIFACT
    assert not missing.with_name(f"{missing.name}.sha256").exists()
