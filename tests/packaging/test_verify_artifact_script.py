# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_verify_artifact_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/verify_artifact.py exit-code contract."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def verify_artifact(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_artifact.py", "verify_artifact"
    )


def _write_artifact(directory: Path, name: str, payload: bytes) -> Path:
    artifact = directory / name
    artifact.write_bytes(payload)
    return artifact


def _write_sidecar(
    artifact: Path, digest: str, recorded_name: str | None = None
) -> Path:
    sidecar = artifact.with_name(f"{artifact.name}.sha256")
    sidecar.write_text(
        f"{digest}  {recorded_name or artifact.name}\n", encoding="utf-8"
    )
    return sidecar


def test_verified_artifact_returns_zero(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    payload = b"ecli release artifact\n"
    artifact = _write_artifact(tmp_path, "ecli_0.0.1_linux_x86_64.tar.gz", payload)
    _write_sidecar(artifact, hashlib.sha256(payload).hexdigest())

    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_OK


def test_missing_artifact_returns_two(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    missing = tmp_path / "absent.tar.gz"
    assert verify_artifact.main([str(missing)]) == verify_artifact.EXIT_ARTIFACT_MISSING


def test_missing_sidecar_returns_three(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    artifact = _write_artifact(tmp_path, "artifact.bin", b"data")
    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_SIDECAR_MISSING


def test_malformed_sidecar_wrong_name_returns_one(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    payload = b"data"
    artifact = _write_artifact(tmp_path, "artifact.bin", payload)
    _write_sidecar(
        artifact,
        hashlib.sha256(payload).hexdigest(),
        recorded_name="other-name.bin",
    )
    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_INVALID


def test_malformed_sidecar_bad_digest_returns_one(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    artifact = _write_artifact(tmp_path, "artifact.bin", b"data")
    _write_sidecar(artifact, "not-a-valid-hex-digest")
    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_INVALID


def test_checksum_mismatch_returns_four(
    verify_artifact: ModuleType, tmp_path: Path
) -> None:
    artifact = _write_artifact(tmp_path, "artifact.bin", b"data")
    _write_sidecar(artifact, "0" * 64)
    assert verify_artifact.main([str(artifact)]) == verify_artifact.EXIT_MISMATCH


def test_invalid_invocation_returns_one(verify_artifact: ModuleType) -> None:
    with pytest.raises(SystemExit) as no_args:
        verify_artifact.main([])
    assert no_args.value.code == verify_artifact.EXIT_INVALID

    with pytest.raises(SystemExit) as too_many:
        verify_artifact.main(["a", "b"])
    assert too_many.value.code == verify_artifact.EXIT_INVALID
