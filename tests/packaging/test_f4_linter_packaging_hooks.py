# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_f4_linter_packaging_hooks.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import CANONICAL_ARTIFACTS, RepoReader, load_script_module

from ecli.extensions.linters.core.provisioning import (
    build_provisioning_plan,
    evidence_to_dict,
    plan_to_evidence,
    verify_evidence_payload,
)


@pytest.fixture
def f4_packaging(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root,
        "scripts/f4_linter_packaging.py",
        "f4_linter_packaging_script",
    )


def test_artifact_policy_map_covers_exactly_twenty_one_entries(
    f4_packaging: ModuleType,
) -> None:
    policies = f4_packaging.artifact_provisioning_policies()
    by_id = {policy.artifact_entry_id: policy for policy in policies}
    counts = {
        kind: sum(policy.kind == kind for policy in policies)
        for kind in ("full-provisioning-hook", "constrained-minimal", "nix-policy")
    }

    assert tuple(by_id) == tuple(artifact.key for artifact in CANONICAL_ARTIFACTS)
    assert len(by_id) == 21
    assert "Source code (zip)" not in by_id
    assert "Source code (tar.gz)" not in by_id
    assert counts == {
        "full-provisioning-hook": 17,
        "constrained-minimal": 2,
        "nix-policy": 2,
    }
    assert {
        by_id[artifact_id].kind for artifact_id in ("pypi-wheel", "pypi-sdist")
    } == {"constrained-minimal"}
    assert {
        by_id[artifact_id].kind for artifact_id in ("nix-flake", "nixos-package")
    } == {"nix-policy"}
    assert sum(counts.values()) == 21


def test_evidence_command_contains_artifact_paths_mode_and_profile(
    f4_packaging: ModuleType,
    tmp_path: Path,
) -> None:
    root = tmp_path
    command = f4_packaging.build_provisioning_command(
        root,
        artifact_entry_id="deb",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
        mode="dry-run",
        profile="custom",
        include_tools=("pylint",),
        exclude_tools=("clang-format",),
        selection_json=tmp_path / "selection.json",
        json_output=True,
    )

    assert "scripts/provision_f4_linters.py" in command[1]
    assert command[command.index("--artifact") + 1] == "deb"
    assert command[command.index("--target-dir") + 1] == str(tmp_path / "target")
    assert command[command.index("--evidence-dir") + 1] == str(tmp_path / "evidence")
    assert command[command.index("--mode") + 1] == "dry-run"
    assert command[command.index("--profile") + 1] == "custom"
    assert command.count("--include-tool") == 1
    assert command.count("--exclude-tool") == 1
    assert "--selection-json" in command
    assert "--json" in command


def test_verification_command_supports_all_artifacts(
    f4_packaging: ModuleType,
    tmp_path: Path,
) -> None:
    command = f4_packaging.build_verification_command(
        tmp_path,
        all_artifacts=True,
        evidence_dir=tmp_path / "evidence",
    )

    assert "scripts/verify_f4_linter_provisioning.py" in command[1]
    assert "--all-artifacts" in command
    assert command[command.index("--evidence-dir") + 1] == str(tmp_path / "evidence")


def test_custom_selection_can_be_supplied_non_interactively(
    f4_packaging: ModuleType,
    tmp_path: Path,
) -> None:
    selection = f4_packaging.selection_from_env(
        {
            "ECLI_F4_LINTER_PROFILE": "custom",
            "ECLI_F4_LINTER_PROVISIONING_MODE": "verify-only",
            "ECLI_F4_LINTER_INCLUDE_TOOLS": "ruff,pylint",
            "ECLI_F4_LINTER_EXCLUDE_TOOLS": "clang-format;spotbugs",
            "ECLI_F4_LINTER_SELECTION_JSON": str(tmp_path / "selection.json"),
        }
    )

    assert selection.profile == "custom"
    assert selection.mode == "verify-only"
    assert selection.include_tools == ("ruff", "pylint")
    assert selection.exclude_tools == ("clang-format", "spotbugs")
    assert selection.selection_json == tmp_path / "selection.json"


def test_selection_env_accepts_explicit_provision_mode(
    f4_packaging: ModuleType,
) -> None:
    selection = f4_packaging.selection_from_env(
        {"ECLI_F4_LINTER_PROVISIONING_MODE": "provision"}
    )

    assert selection.mode == "provision"


def test_selection_env_rejects_invalid_mode_without_downgrade(
    f4_packaging: ModuleType,
) -> None:
    with pytest.raises(ValueError):
        f4_packaging.selection_from_env({"ECLI_F4_LINTER_PROVISIONING_MODE": "bogus"})


def test_evidence_hook_uses_explicit_argv_without_shell(
    f4_packaging: ModuleType,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    def fake_run(command: list[str], **kwargs: object) -> Result:
        calls.append(command)
        assert isinstance(command, list)
        assert "shell" not in kwargs
        assert kwargs["cwd"] == repo_root
        assert kwargs["check"] is False
        return Result()

    monkeypatch.setattr(f4_packaging.subprocess, "run", fake_run)

    rc = f4_packaging.run_or_record_f4_linter_provisioning(repo_root, "deb")

    assert rc == 0
    assert len(calls) == 2
    assert "provision_f4_linters.py" in calls[0][1]
    assert "verify_f4_linter_provisioning.py" in calls[1][1]


def test_invalid_artifact_id_is_rejected_before_command_construction(
    f4_packaging: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        f4_packaging.build_verification_command(
            tmp_path,
            artifact_entry_id="../deb",
            evidence_dir=tmp_path / "evidence",
        )


def test_packaging_scripts_reference_f4_evidence_hooks(
    read_repo_text: RepoReader,
) -> None:
    expected = {
        "scripts/build_and_package_deb.py": "run_or_record_f4_linter_provisioning",
        "scripts/build_and_package_rpm.py": "run_or_record_f4_linter_provisioning",
        "scripts/build_and_package_opensuse_rpm.py": "ECLI_F4_LINTER_ARTIFACT_ID",
        "scripts/build_and_package_arch.py": "arch-pkgbuild",
        "scripts/build_and_package_slackware.py": "slackware-txz",
        "scripts/package_appimage.py": "appimage",
        "scripts/build_pyinstaller_linux.py": "linux-pyinstaller",
        "scripts/build_and_package_freebsd.py": "freebsd-pkg",
        "scripts/build_freebsd_pkg.py": "freebsd-pkg",
        "scripts/build_freebsd_port.py": "freebsd-ports-chroot",
        "scripts/build_and_package_macos.py": "macos-dmg",
        "scripts/build-and-package-windows.ps1": "Invoke-F4LinterEvidenceHook",
        "docker/build-linux-deb.Dockerfile": "docker-deb-helper",
        "docker/build-linux-rpm.Dockerfile": "docker-rpm-helper",
        ".github/workflows/release.yml": "verify_f4_linter_provisioning.py",
    }

    for relative_path, token in expected.items():
        assert token in read_repo_text(relative_path), relative_path


def test_docker_and_opensuse_artifact_env_wiring(
    read_repo_text: RepoReader,
) -> None:
    deb_dockerfile = read_repo_text("docker/build-linux-deb.Dockerfile")
    rpm_dockerfile = read_repo_text("docker/build-linux-rpm.Dockerfile")
    deb_script = read_repo_text("scripts/build_and_package_deb.py")
    rpm_script = read_repo_text("scripts/build_and_package_rpm.py")
    opensuse_script = read_repo_text("scripts/build_and_package_opensuse_rpm.py")

    assert "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS=docker-deb-helper" in deb_dockerfile
    assert "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS=docker-rpm-helper" in rpm_dockerfile
    assert 'artifact_ids_from_env(("deb",), root=root)' in deb_script
    assert 'artifact_ids_from_env(("rpm",), root=root)' in rpm_script
    assert 'child_env.setdefault("ECLI_F4_LINTER_ARTIFACT_ID", "opensuse-rpm")' in (
        opensuse_script
    )


def test_release_verifier_references_f4_evidence_gate(
    read_repo_text: RepoReader,
) -> None:
    verifier = read_repo_text("scripts/verify_release_assets.py")

    assert "--f4-evidence-dir" in verifier
    assert "verify_f4_linter_provisioning.py" in verifier


def test_release_verifier_without_f4_evidence_keeps_legacy_behavior(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_assets = load_script_module(
        repo_root,
        "scripts/verify_release_assets.py",
        "verify_release_assets_legacy_gate",
    )

    monkeypatch.setattr(
        release_assets,
        "verify_release_assets",
        lambda _release_dir, _version: release_assets.EXIT_OK,
    )

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("F4 verifier must not run without --f4-evidence-dir")

    monkeypatch.setattr(release_assets.subprocess, "run", fail_if_called)

    rc = release_assets.main(
        [
            "--version",
            "1.2.3",
            "--release-dir",
            str(tmp_path / "release"),
        ]
    )

    assert rc == release_assets.EXIT_OK


def test_release_verifier_invokes_f4_gate_when_evidence_dir_is_supplied(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_assets = load_script_module(
        repo_root,
        "scripts/verify_release_assets.py",
        "verify_release_assets_invokes_f4_gate",
    )
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    monkeypatch.setattr(
        release_assets,
        "verify_release_assets",
        lambda _release_dir, _version: release_assets.EXIT_OK,
    )

    def fake_run(command: list[str], **kwargs: object) -> Result:
        calls.append(command)
        assert kwargs["cwd"] == repo_root
        assert kwargs["check"] is False
        return Result()

    monkeypatch.setattr(release_assets.subprocess, "run", fake_run)

    rc = release_assets.main(
        [
            "--version",
            "1.2.3",
            "--release-dir",
            str(tmp_path / "release"),
            "--f4-evidence-dir",
            str(tmp_path / "f4-evidence"),
        ]
    )

    assert rc == release_assets.EXIT_OK
    assert len(calls) == 1
    assert "verify_f4_linter_provisioning.py" in calls[0][1]
    assert "--all-artifacts" in calls[0]


def test_release_verifier_propagates_f4_evidence_failure(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_assets = load_script_module(
        repo_root,
        "scripts/verify_release_assets.py",
        "verify_release_assets_f4_gate",
    )

    class Result:
        returncode = 2

    monkeypatch.setattr(
        release_assets,
        "verify_release_assets",
        lambda _release_dir, _version: release_assets.EXIT_OK,
    )
    monkeypatch.setattr(
        release_assets.subprocess,
        "run",
        lambda *_args, **_kwargs: Result(),
    )

    rc = release_assets.main(
        [
            "--version",
            "1.2.3",
            "--release-dir",
            str(tmp_path / "release"),
            "--f4-evidence-dir",
            str(tmp_path / "missing-f4-evidence"),
        ]
    )

    assert rc == 2


def test_constrained_pypi_evidence_requires_reason(tmp_path: Path) -> None:
    plan = build_provisioning_plan(
        artifact_entry_id="pypi-wheel",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
        mode="dry-run",
        profile="full",
    )
    payload = evidence_to_dict(
        plan_to_evidence(
            plan,
            ecli_version="0.2.4",
            timestamp="1970-01-01T00:00:00Z",
        )
    )
    assert verify_evidence_payload(payload) == []

    payload["custom_profile_reason"] = None
    errors = verify_evidence_payload(payload)
    assert any("custom_profile_reason" in error for error in errors)


def test_nix_artifacts_record_nix_derivation_policy(tmp_path: Path) -> None:
    for artifact_id in ("nix-flake", "nixos-package"):
        plan = build_provisioning_plan(
            artifact_entry_id=artifact_id,
            target_dir=tmp_path / "target",
            evidence_dir=tmp_path / "evidence",
            mode="dry-run",
            profile="full",
        )

        required_external = [
            action
            for action in plan.actions
            if action.required_for_full and action.selected and action.tool_id != "ruff"
        ]
        assert required_external
        assert all(
            action.strategy.mechanism == "nix-derivation"
            for action in required_external
        )
