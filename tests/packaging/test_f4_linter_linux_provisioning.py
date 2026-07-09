# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_f4_linter_linux_provisioning.py
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
from typing import Any

import pytest
from conftest import CANONICAL_ARTIFACTS, RepoReader, load_script_module

from ecli.extensions.linters.core import provisioning
from ecli.extensions.linters.core.provisioning_registry import (
    load_linter_tool_contracts,
    required_full_tool_ids,
)


LINUX_ARTIFACT_IDS = (
    "linux-pyinstaller",
    "linux-tarball",
    "appimage",
    "deb",
    "rpm",
    "opensuse-rpm",
    "arch-pkgbuild",
    "slackware-txz",
    "docker-deb-helper",
    "docker-rpm-helper",
    "nix-flake",
    "nixos-package",
)


@pytest.fixture
def linux_helper(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root,
        "scripts/f4_linter_linux_provisioning.py",
        "f4_linter_linux_provisioning_script",
    )


@pytest.fixture
def provision_script(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root,
        "scripts/provision_f4_linters.py",
        "provision_f4_linters_linux_manifest_script",
    )


def _build_manifest(
    linux_helper: ModuleType,
    tmp_path: Path,
    artifact_entry_id: str,
) -> dict[str, Any]:
    return linux_helper.build_linux_provisioning_manifest(
        artifact_entry_id=artifact_entry_id,
        target_dir=tmp_path / artifact_entry_id / "target",
        evidence_dir=tmp_path / artifact_entry_id / "evidence",
    )


def _manifest_tool(manifest: dict[str, Any], tool_id: str) -> dict[str, Any]:
    for tool in manifest["tools"]:
        if tool["tool_id"] == tool_id:
            return tool
    raise AssertionError(f"missing manifest tool: {tool_id}")


def test_linux_artifact_scope_is_exactly_active_linux_surfaces(
    linux_helper: ModuleType,
) -> None:
    linux_ids = linux_helper.linux_artifact_ids()
    non_linux_ids = {artifact.key for artifact in CANONICAL_ARTIFACTS} - set(
        LINUX_ARTIFACT_IDS
    )

    assert linux_ids == LINUX_ARTIFACT_IDS
    assert linux_helper.linux_full_artifact_ids() == LINUX_ARTIFACT_IDS
    assert not (set(linux_ids) & non_linux_ids)


def test_every_full_required_tool_has_linux_policy_for_every_linux_artifact(
    linux_helper: ModuleType,
) -> None:
    required = set(required_full_tool_ids(load_linter_tool_contracts()))
    matrix = linux_helper.linux_tool_policy_matrix()

    assert len(matrix) == len(LINUX_ARTIFACT_IDS) * len(required)
    for artifact_id in LINUX_ARTIFACT_IDS:
        policies = linux_helper.linux_provisioning_policy_for_artifact(artifact_id)
        assert {policy.tool_id for policy in policies} == required
        for policy in policies:
            if policy.mechanism == "blocked-missing-provenance":
                assert policy.release_blocking is True
                assert policy.blocker_reason


def test_manifest_generation_is_deterministic_and_paths_are_contained(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    kwargs = {
        "artifact_entry_id": "linux-tarball",
        "target_dir": tmp_path / "target",
        "evidence_dir": tmp_path / "evidence",
    }

    first = linux_helper.build_linux_provisioning_manifest(**kwargs)
    second = linux_helper.build_linux_provisioning_manifest(**kwargs)

    assert first == second
    assert first["artifact_entry_id"] == "linux-tarball"
    assert first["policy_kind"] == "linux-f4-provisioning-policy"
    assert first["release_blocking"] is True
    expected_count = len(required_full_tool_ids(load_linter_tool_contracts()))
    assert first["full_required_tool_count"] == expected_count
    assert first["selected_tools"] == list(
        required_full_tool_ids(load_linter_tool_contracts())
    )
    assert linux_helper.verify_linux_provisioning_manifest(first) == []

    target_dir = Path(first["target_dir"])
    evidence_dir = Path(first["evidence_dir"])
    assert Path(first["manifest_path"]).relative_to(target_dir)
    for tool in first["tools"]:
        assert Path(tool["target_dir"]).relative_to(target_dir)
        assert Path(tool["evidence_dir"]).relative_to(evidence_dir)


def test_manifest_writer_round_trips_verified_json(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = linux_helper.build_linux_provisioning_manifest(
        artifact_entry_id="deb",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
    )

    path = linux_helper.write_linux_provisioning_manifest(manifest)

    assert path.name == "f4-linux-tools.json"
    assert json.loads(path.read_text(encoding="utf-8")) == manifest
    assert linux_helper.verify_linux_provisioning_manifest(path) == []


def test_linux_manifest_rejects_invalid_or_non_linux_artifact_ids(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    for artifact_id in ("../deb", "freebsd-pkg"):
        with pytest.raises(ValueError):
            linux_helper.build_linux_provisioning_manifest(
                artifact_entry_id=artifact_id,
                target_dir=tmp_path / "target",
                evidence_dir=tmp_path / "evidence",
            )


def test_linux_full_artifact_ids_reports_missing_registry_entry(
    linux_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_registry = linux_helper._registry_module()

    class MissingDebRegistry:
        ARTIFACT_CONTRACT_ENTRIES = tuple(
            entry
            for entry in real_registry.ARTIFACT_CONTRACT_ENTRIES
            if entry.artifact_entry_id != "deb"
        )

    monkeypatch.setattr(
        linux_helper,
        "_registry_module",
        lambda _root=None: MissingDebRegistry,
    )

    with pytest.raises(ValueError, match="deb"):
        linux_helper.linux_full_artifact_ids()


def test_manifest_builder_rejects_duplicate_selected_tool_ids(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="duplicate selected Linux Full tool"):
        linux_helper.build_linux_provisioning_manifest(
            artifact_entry_id="deb",
            target_dir=tmp_path / "target",
            evidence_dir=tmp_path / "evidence",
            selected_tool_ids=("ruff", "ruff"),
        )


def test_manifest_verifier_rejects_tampered_tool_mechanism(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["mechanism"] = "toolchain-component"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: mechanism differs" in error for error in errors)


def test_manifest_verifier_rejects_tampered_os_package_names(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["package_names"] = ["wrong-package"]

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: package_names differ" in error for error in errors)


def test_manifest_verifier_rejects_tampered_release_blocking_summary(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "linux-tarball")
    assert any(tool["release_blocking"] is True for tool in manifest["tools"])
    manifest["release_blocking"] = False

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("release_blocking does not match" in error for error in errors)


def test_manifest_verifier_rejects_duplicate_selected_tools(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest["selected_tools"].append(manifest["selected_tools"][0])

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("duplicate selected Linux tool" in error for error in errors)


def test_manifest_verifier_rejects_duplicate_tool_entries(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest["tools"].append(dict(manifest["tools"][0]))

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("duplicate Linux manifest tool entry" in error for error in errors)


def test_manifest_verifier_rejects_wrong_required_tool_count(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest["full_required_tool_count"] = 0

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("full_required_tool_count does not match" in error for error in errors)


def test_manifest_verifier_rejects_tool_target_dir_escape(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["target_dir"] = str(
        Path(manifest["target_dir"]).parent / "escaped-target"
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint target_dir escapes base directory" in error for error in errors
    )


def test_manifest_verifier_rejects_tool_evidence_dir_escape(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["evidence_dir"] = str(
        Path(manifest["evidence_dir"]).parent / "escaped-evidence"
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint evidence_dir escapes base directory" in error for error in errors
    )


def test_package_manager_policies_include_package_names_when_used(
    linux_helper: ModuleType,
) -> None:
    for artifact_id in (
        "deb",
        "rpm",
        "opensuse-rpm",
        "arch-pkgbuild",
        "slackware-txz",
    ):
        policies = linux_helper.linux_provisioning_policy_for_artifact(artifact_id)
        mechanisms = {policy.tool_id: policy.mechanism for policy in policies}
        os_package_policies = [
            policy for policy in policies if policy.mechanism == "os-package-manager"
        ]

        assert os_package_policies
        assert mechanisms["ruff"] == "bundled-internal"
        assert mechanisms["cargo-clippy"] == "toolchain-component"
        for policy in os_package_policies:
            assert policy.package_names
        for policy in policies:
            if policy.mechanism != "os-package-manager":
                assert policy.mechanism in {
                    "bundled-internal",
                    "toolchain-component",
                    "blocked-missing-provenance",
                }


def test_self_contained_artifacts_define_tools_layout_without_binaries(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    for artifact_id in ("linux-pyinstaller", "linux-tarball", "appimage"):
        manifest = linux_helper.build_linux_provisioning_manifest(
            artifact_entry_id=artifact_id,
            target_dir=tmp_path / artifact_id / "target",
            evidence_dir=tmp_path / artifact_id / "evidence",
        )
        tools_dir = linux_helper.linux_artifact_tools_dir(
            tmp_path / artifact_id / "target",
            artifact_id,
        )
        mechanisms = {tool["tool_id"]: tool["mechanism"] for tool in manifest["tools"]}

        assert tools_dir == (tmp_path / artifact_id / "target" / "tools").resolve()
        assert mechanisms["ruff"] == "bundled-internal"
        assert {
            mechanism for tool_id, mechanism in mechanisms.items() if tool_id != "ruff"
        } == {"blocked-missing-provenance"}
        assert linux_helper.verify_linux_provisioning_manifest(manifest) == []


def test_docker_helper_manifests_record_inherited_linux_policy(
    linux_helper: ModuleType,
    read_repo_text: RepoReader,
    tmp_path: Path,
) -> None:
    deb_manifest = linux_helper.build_linux_provisioning_manifest(
        artifact_entry_id="docker-deb-helper",
        target_dir=tmp_path / "docker-deb" / "target",
        evidence_dir=tmp_path / "docker-deb" / "evidence",
    )
    rpm_manifest = linux_helper.build_linux_provisioning_manifest(
        artifact_entry_id="docker-rpm-helper",
        target_dir=tmp_path / "docker-rpm" / "target",
        evidence_dir=tmp_path / "docker-rpm" / "evidence",
    )

    assert deb_manifest["builder_helper"]["inherits_artifact_policy"] == "deb"
    assert rpm_manifest["builder_helper"]["inherits_artifact_policy"] == "rpm"
    assert "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS=docker-deb-helper" in read_repo_text(
        "docker/build-linux-deb.Dockerfile"
    )
    assert "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS=docker-rpm-helper" in read_repo_text(
        "docker/build-linux-rpm.Dockerfile"
    )


def test_nix_artifacts_are_declarative_only(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    for artifact_id in ("nix-flake", "nixos-package"):
        manifest = linux_helper.build_linux_provisioning_manifest(
            artifact_entry_id=artifact_id,
            target_dir=tmp_path / artifact_id / "target",
            evidence_dir=tmp_path / artifact_id / "evidence",
        )
        mechanisms = {tool["mechanism"] for tool in manifest["tools"]}

        assert mechanisms == {"bundled-internal", "nix-derivation"}
        assert manifest["release_blocking"] is False
        assert manifest["nix_policy"]["declarative_only"] is True
        assert manifest["nix_policy"]["imperative_package_manager"] is False
        assert manifest["nix_policy"]["imperative_upstream_download"] is False


def test_linux_provision_mode_writes_manifest_and_fails_on_blockers(
    provision_script: ModuleType,
    linux_helper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(provisioning.shutil, "which", lambda _name: None)
    monkeypatch.setenv("ECLI_F4_PROVISIONING_TIMESTAMP", "1970-01-01T00:00:00Z")

    target_dir = tmp_path / "target"
    evidence_dir = tmp_path / "evidence"
    rc = provision_script.main(
        [
            "--artifact",
            "linux-tarball",
            "--target-dir",
            str(target_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--mode",
            "provision",
            "--json",
        ]
    )

    evidence = evidence_dir / "f4-linter-provisioning-linux-tarball.json"
    manifest_path = linux_helper.linux_artifact_manifest_path(
        target_dir,
        "linux-tarball",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == provision_script.EXIT_PROVISIONING_FAILED
    assert evidence.is_file()
    assert manifest["release_blocking"] is True
    assert any(
        tool["mechanism"] == "blocked-missing-provenance" for tool in manifest["tools"]
    )
    assert linux_helper.verify_linux_provisioning_manifest(manifest_path) == []


def test_linux_dry_run_still_writes_verifiable_evidence_and_manifest(
    provision_script: ModuleType,
    linux_helper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ECLI_F4_PROVISIONING_TIMESTAMP", "1970-01-01T00:00:00Z")

    target_dir = tmp_path / "target"
    evidence_dir = tmp_path / "evidence"
    rc = provision_script.main(
        [
            "--artifact",
            "deb",
            "--target-dir",
            str(target_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--mode",
            "dry-run",
            "--json",
        ]
    )

    manifest_path = linux_helper.linux_artifact_manifest_path(target_dir, "deb")
    assert rc == provision_script.EXIT_OK
    assert (evidence_dir / "f4-linter-provisioning-deb.json").is_file()
    assert linux_helper.verify_linux_provisioning_manifest(manifest_path) == []


def test_verify_only_is_non_installing_and_records_manifest(
    provision_script: ModuleType,
    linux_helper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(provisioning.shutil, "which", lambda _name: None)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("verify-only must not run installation commands")

    monkeypatch.setattr(provisioning.subprocess, "run", fail_if_called)
    target_dir = tmp_path / "target"
    evidence_dir = tmp_path / "evidence"
    rc = provision_script.main(
        [
            "--artifact",
            "linux-tarball",
            "--target-dir",
            str(target_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--mode",
            "verify-only",
            "--json",
        ]
    )

    manifest_path = linux_helper.linux_artifact_manifest_path(
        target_dir,
        "linux-tarball",
    )
    assert rc == provision_script.EXIT_PROVISIONING_FAILED
    assert linux_helper.verify_linux_provisioning_manifest(manifest_path) == []
