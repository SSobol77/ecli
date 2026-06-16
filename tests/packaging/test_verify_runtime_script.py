# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_verify_runtime_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/verify_runtime.py exit-code and structural logic."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def verify_runtime(repo_root: Path) -> ModuleType:
    return load_script_module(repo_root, "scripts/verify_runtime.py", "verify_runtime")


def _make_payload_tree(root: Path, with_launcher: bool = True) -> Path:
    tree = root / "tree"
    (tree / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    if with_launcher:
        launcher = tree / "usr" / "bin" / "ecli"
        launcher.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
        launcher.chmod(0o755)
    return tree


def _make_tarball(root: Path, name: str, with_launcher: bool = True) -> Path:
    tree = _make_payload_tree(root, with_launcher=with_launcher)
    tarball = root / name
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(tree / "usr", arcname="usr")
    return tarball


def test_normalize_arch(verify_runtime: ModuleType) -> None:
    assert verify_runtime.normalize_arch("x86_64") == "x86_64"
    assert verify_runtime.normalize_arch("amd64") == "x86_64"
    assert verify_runtime.normalize_arch("aarch64") == "arm64"
    assert verify_runtime.normalize_arch("arm64") == "arm64"
    assert verify_runtime.normalize_arch("riscv64") == "riscv64"


def test_can_execute_artifact_by_host(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    deb = tmp_path / "ecli_x_linux_x86_64.deb"
    deb.write_bytes(b"x")
    pkg = tmp_path / "ecli_x_freebsd_x86_64.pkg"
    pkg.write_bytes(b"x")
    assert verify_runtime.can_execute_artifact(deb, "Linux") is True
    assert verify_runtime.can_execute_artifact(deb, "Darwin") is False
    assert verify_runtime.can_execute_artifact(pkg, "FreeBSD") is True
    assert verify_runtime.can_execute_artifact(pkg, "Linux") is False


def test_find_launcher(verify_runtime: ModuleType, tmp_path: Path) -> None:
    tree = _make_payload_tree(tmp_path, with_launcher=True)
    found = verify_runtime.find_launcher(tree)
    assert found is not None and found.name == "ecli"
    assert (
        verify_runtime.find_launcher(_make_payload_tree(tmp_path / "e", False)) is None
    )


def test_invalid_mode_returns_two(verify_runtime: ModuleType, tmp_path: Path) -> None:
    artifact = tmp_path / "a.tar.gz"
    artifact.write_bytes(b"x")
    assert verify_runtime.main(["--mode", "bogus", str(artifact)]) == 2


def test_missing_artifact_returns_three(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    missing = tmp_path / "absent.deb"
    assert verify_runtime.main(["--allow-nonrelease", str(missing)]) == 3


def test_outside_release_returns_four(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    artifact = tmp_path / "ecli_x.tar.gz"
    artifact.write_bytes(b"x")
    assert verify_runtime.main([str(artifact)]) == 4


def test_structural_pass_returns_zero(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    tarball = _make_tarball(tmp_path, "ecli_x_linux_x86_64.tar.gz")
    rc = verify_runtime.main(
        ["--allow-nonrelease", "--mode", "structural", str(tarball)]
    )
    assert rc == 0


def test_structural_fail_without_launcher_returns_one(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    tarball = _make_tarball(tmp_path, "empty_x.tar.gz", with_launcher=False)
    rc = verify_runtime.main(
        ["--allow-nonrelease", "--mode", "structural", str(tarball)]
    )
    assert rc == 1


def test_native_mode_missing_launcher_returns_five(
    verify_runtime: ModuleType, tmp_path: Path
) -> None:
    empty_dir = tmp_path / "payload"
    empty_dir.mkdir()
    rc = verify_runtime.main(["--allow-nonrelease", "--mode", "native", str(empty_dir)])
    assert rc == 5


def test_rpm_extraction_failure_returns_error(
    verify_runtime: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    return_codes = iter((1, 0))

    class FakeProcess:
        def __init__(self, cmd: list[str], **kwargs: object) -> None:
            self.cmd = cmd
            self.stdin = io.BytesIO() if kwargs.get("stdin") is not None else None
            self._return_code = next(return_codes)

        def wait(self) -> int:
            return self._return_code

    monkeypatch.setattr(verify_runtime.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(verify_runtime.subprocess, "Popen", FakeProcess)

    artifact = tmp_path / "ecli.rpm"
    artifact.write_bytes(b"rpm")
    payload = tmp_path / "payload"
    payload.mkdir()

    assert verify_runtime._extract_rpm(artifact, payload, tmp_path) == 1


def test_scan_logs_reports_bounded_redacted_excerpt(
    verify_runtime: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / ".config" / "ecli" / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "editor.log"
    log_file.write_text(
        "\n".join(
            [
                "line 1",
                "line 2",
                "api_key=SECRET ModuleNotFoundError",
                "line 4",
                "line 5",
                "line 6",
                "line 7",
            ]
        ),
        encoding="utf-8",
    )

    assert verify_runtime.scan_logs(tmp_path) is False
    captured = capsys.readouterr()
    assert "SECRET" not in captured.err
    assert "api_key=<redacted>" in captured.err
    assert "line 7" not in captured.err
    assert "omitted" in captured.err
