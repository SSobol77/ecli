# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_f4_linter_provisioning_scripts.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def provision_script(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root,
        "scripts/provision_f4_linters.py",
        "provision_f4_linters_script",
    )


@pytest.fixture
def verify_script(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root,
        "scripts/verify_f4_linter_provisioning.py",
        "verify_f4_linter_provisioning_script",
    )


def test_list_selection_options_outputs_required_tools_selected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    provision_script: ModuleType,
) -> None:
    rc = provision_script.main(
        [
            "--artifact",
            "deb",
            "--target-dir",
            str(tmp_path / "target"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--mode",
            "dry-run",
            "--list-selection-options",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    options = payload["artifacts"][0]["options"]
    by_id = {option["tool_id"]: option for option in options}
    for tool_id in (
        "clang-format",
        "spotbugs",
        "golangci-lint",
        "sqlfluff",
        "tflint",
    ):
        assert by_id[tool_id]["required_for_full"] is True
        assert by_id[tool_id]["selected_by_default"] is True


def test_dry_run_deb_writes_evidence_and_verifier_accepts_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provision_script: ModuleType,
    verify_script: ModuleType,
) -> None:
    monkeypatch.setenv(
        "ECLI_F4_PROVISIONING_TIMESTAMP",
        "1970-01-01T00:00:00Z",
    )
    evidence_dir = tmp_path / "evidence"
    rc = provision_script.main(
        [
            "--artifact",
            "deb",
            "--target-dir",
            str(tmp_path / "target"),
            "--evidence-dir",
            str(evidence_dir),
            "--mode",
            "dry-run",
            "--json",
        ]
    )

    assert rc == 0
    evidence = evidence_dir / "f4-linter-provisioning-deb.json"
    assert evidence.is_file()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["artifact_entry_id"] == "deb"
    assert payload["full_profile_complete"] is True
    assert payload["summary"]["required_total"] == 19
    assert (
        verify_script.main(["--artifact", "deb", "--evidence-dir", str(evidence_dir)])
        == 0
    )


def test_all_artifacts_dry_run_writes_twenty_one_evidence_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provision_script: ModuleType,
    verify_script: ModuleType,
) -> None:
    monkeypatch.setenv(
        "ECLI_F4_PROVISIONING_TIMESTAMP",
        "1970-01-01T00:00:00Z",
    )
    evidence_dir = tmp_path / "evidence-all"
    rc = provision_script.main(
        [
            "--all-artifacts",
            "--target-dir",
            str(tmp_path / "target"),
            "--evidence-dir",
            str(evidence_dir),
            "--mode",
            "dry-run",
            "--json",
        ]
    )

    assert rc == 0
    assert len(list(evidence_dir.glob("f4-linter-provisioning-*.json"))) == 21
    assert (
        verify_script.main(["--all-artifacts", "--evidence-dir", str(evidence_dir)])
        == 0
    )


def test_verify_fails_when_required_artifact_evidence_is_missing(
    tmp_path: Path,
    verify_script: ModuleType,
) -> None:
    assert (
        verify_script.main(
            [
                "--artifact",
                "deb",
                "--evidence-dir",
                str(tmp_path / "missing"),
            ]
        )
        == 2
    )
