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


def _provenance_record(records: tuple[Any, ...], tool_id: str) -> Any:
    for record in records:
        if record.tool_id == tool_id:
            return record
    raise AssertionError(f"missing provenance record: {tool_id}")


def _mapping_record(records: tuple[Any, ...], tool_id: str) -> Any:
    for record in records:
        if record.tool_id == tool_id:
            return record
    raise AssertionError(f"missing distro mapping record: {tool_id}")


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
    assert {
        record.artifact_entry_id for record in linux_helper.linux_provenance_matrix()
    } == set(LINUX_ARTIFACT_IDS)


def test_distro_mapping_scope_is_package_manager_and_docker_only(
    linux_helper: ModuleType,
) -> None:
    mapping_artifacts = {
        "deb",
        "rpm",
        "opensuse-rpm",
        "arch-pkgbuild",
        "slackware-txz",
        "docker-deb-helper",
        "docker-rpm-helper",
    }
    matrix = linux_helper.linux_distro_mapping_matrix()

    assert {record.artifact_entry_id for record in matrix} == mapping_artifacts
    for artifact_id in mapping_artifacts:
        assert linux_helper.linux_distro_mapping_catalog_for_artifact(artifact_id)
    for artifact_id in (
        "linux-pyinstaller",
        "linux-tarball",
        "appimage",
        "nix-flake",
        "nixos-package",
    ):
        assert linux_helper.linux_distro_mapping_catalog_for_artifact(artifact_id) == ()


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


def test_every_full_required_tool_has_linux_provenance_for_every_linux_artifact(
    linux_helper: ModuleType,
) -> None:
    required = set(required_full_tool_ids(load_linter_tool_contracts()))
    matrix = linux_helper.linux_provenance_matrix()

    assert len(matrix) == len(LINUX_ARTIFACT_IDS) * len(required)
    for artifact_id in LINUX_ARTIFACT_IDS:
        records = linux_helper.linux_provenance_catalog_for_artifact(artifact_id)

        assert {record.tool_id for record in records} == required
        assert {record.artifact_entry_id for record in records} == {artifact_id}


def test_linux_provenance_statuses_match_current_policy_taxonomy(
    linux_helper: ModuleType,
) -> None:
    deb = linux_helper.linux_provenance_catalog_for_artifact("deb")
    nix = linux_helper.linux_provenance_catalog_for_artifact("nix-flake")
    tarball = linux_helper.linux_provenance_catalog_for_artifact("linux-tarball")

    ruff = _provenance_record(deb, "ruff")
    yamllint = _provenance_record(deb, "yamllint")
    cargo_clippy = _provenance_record(deb, "cargo-clippy")
    unmapped = _provenance_record(deb, "biome")

    assert ruff.provenance_status == "internal-bundled"
    assert ruff.trust_boundary == "ecli-source-tree"
    assert yamllint.provenance_status == "distro-signed-package"
    assert yamllint.trust_boundary == "distro-package-manager"
    assert yamllint.package_names == ("yamllint",)
    assert cargo_clippy.provenance_status == "toolchain-component"
    assert cargo_clippy.trust_boundary == "rust-toolchain"
    assert unmapped.provenance_status == "blocked-missing-distro-mapping"
    assert unmapped.release_blocking is True
    assert "distro package" in str(unmapped.blocker_reason)
    assert {record.provenance_status for record in nix if record.tool_id != "ruff"} == {
        "nix-derivation"
    }
    assert {
        record.provenance_status for record in tarball if record.tool_id != "ruff"
    } == {"blocked-missing-version-pin"}


def test_existing_os_package_policy_has_approved_distro_mapping_evidence(
    linux_helper: ModuleType,
) -> None:
    deb = linux_helper.linux_distro_mapping_catalog_for_artifact("deb")
    yamllint = _mapping_record(deb, "yamllint")

    assert yamllint.mapping_status == "approved-existing-policy"
    assert yamllint.provenance_status == "distro-signed-package"
    assert yamllint.trust_boundary == "distro-package-manager"
    assert yamllint.package_names == ("yamllint",)
    assert yamllint.evidence_source == "OS_PACKAGE_NAMES"
    assert "OS_PACKAGE_NAMES policy" in yamllint.evidence_note
    assert yamllint.release_blocking is False


def test_docker_helper_distro_mappings_inherit_deb_and_rpm_policy(
    linux_helper: ModuleType,
) -> None:
    docker_deb = linux_helper.linux_distro_mapping_catalog_for_artifact(
        "docker-deb-helper"
    )
    docker_rpm = linux_helper.linux_distro_mapping_catalog_for_artifact(
        "docker-rpm-helper"
    )
    deb_yamllint = _mapping_record(docker_deb, "yamllint")
    rpm_yamllint = _mapping_record(docker_rpm, "yamllint")

    assert deb_yamllint.distro_family == "debian"
    assert deb_yamllint.package_names == ("yamllint",)
    assert deb_yamllint.source_policy_artifact_entry_id == "deb"
    assert rpm_yamllint.distro_family == "rpm-generic"
    assert rpm_yamllint.package_names == ("python3-yamllint",)
    assert rpm_yamllint.source_policy_artifact_entry_id == "rpm"


def test_package_manager_unmapped_tools_remain_explicit_mapping_blockers(
    linux_helper: ModuleType,
) -> None:
    required = set(required_full_tool_ids(load_linter_tool_contracts()))
    deb_records = linux_helper.linux_distro_mapping_catalog_for_artifact("deb")
    deb_tool_ids = {record.tool_id for record in deb_records}
    unmapped = linux_helper.linux_unmapped_package_manager_tools("deb")
    unmapped_ids = {record.tool_id for record in unmapped}

    assert deb_tool_ids == required - {"ruff", "cargo-clippy"}
    assert "biome" in unmapped_ids
    assert "yamllint" not in unmapped_ids
    assert {record.mapping_status for record in unmapped} == {
        "blocked-missing-distro-mapping"
    }
    assert all(record.release_blocking is True for record in unmapped)
    assert all(record.blocker_reason for record in unmapped)


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
        assert isinstance(tool["provenance_status"], str)
        assert isinstance(tool["trust_boundary"], str)
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


def test_manifest_records_distro_mapping_for_package_manager_tools(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    yamllint = _manifest_tool(manifest, "yamllint")
    biome = _manifest_tool(manifest, "biome")
    cargo_clippy = _manifest_tool(manifest, "cargo-clippy")
    ruff = _manifest_tool(manifest, "ruff")

    assert yamllint["distro_mapping"]["mapping_status"] == "approved-existing-policy"
    assert yamllint["distro_mapping"]["package_names"] == ["yamllint"]
    assert biome["distro_mapping"]["mapping_status"] == (
        "blocked-missing-distro-mapping"
    )
    assert biome["distro_mapping"]["release_blocking"] is True
    assert "distro_mapping" in biome["evidence_fields_required"]
    assert "distro_mapping" not in cargo_clippy
    assert "distro_mapping" not in ruff
    assert linux_helper.verify_linux_provisioning_manifest(manifest) == []


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


def test_manifest_verifier_rejects_tampered_provenance_status(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["provenance_status"] = "internal-bundled"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: provenance_status differs" in error for error in errors)
    assert any(
        "yamllint: provenance_status is inconsistent with mechanism" in error
        for error in errors
    )


def test_manifest_verifier_rejects_tampered_trust_boundary(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["trust_boundary"] = "nix-store"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: trust_boundary differs" in error for error in errors)
    assert any(
        "yamllint: trust_boundary is inconsistent with provenance_status" in error
        for error in errors
    )


def test_manifest_verifier_rejects_distro_provenance_without_packages(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "yamllint")["package_names"] = []

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro-signed-package provenance requires package_names" in error
        for error in errors
    )


def test_manifest_verifier_rejects_tampered_distro_mapping_status(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    mapping = _manifest_tool(manifest, "yamllint")["distro_mapping"]
    mapping["mapping_status"] = "blocked-unverified"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping mapping_status differs" in error for error in errors
    )


def test_manifest_verifier_rejects_tampered_distro_family(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    mapping = _manifest_tool(manifest, "yamllint")["distro_mapping"]
    mapping["distro_family"] = "arch"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping distro_family differs" in error for error in errors
    )


def test_manifest_verifier_rejects_tampered_distro_mapping_packages(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    mapping = _manifest_tool(manifest, "yamllint")["distro_mapping"]
    mapping["package_names"] = ["wrong-package"]

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping package_names differs" in error for error in errors
    )


def test_manifest_verifier_rejects_missing_distro_mapping_on_os_package_tool(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    del _manifest_tool(manifest, "yamllint")["distro_mapping"]

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: missing distro_mapping" in error for error in errors)


def test_manifest_verifier_rejects_blocked_distro_mapping_without_reason(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_tool(manifest, "biome")["distro_mapping"]["blocker_reason"] = None

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: blocked distro_mapping requires blocker_reason" in error
        for error in errors
    )


def test_manifest_verifier_rejects_self_contained_distro_mapping(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    deb_manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest = _build_manifest(linux_helper, tmp_path, "linux-tarball")
    _manifest_tool(manifest, "biome")["distro_mapping"] = dict(
        _manifest_tool(deb_manifest, "yamllint")["distro_mapping"]
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: self-contained artifact must not declare distro_mapping" in error
        for error in errors
    )


def test_manifest_verifier_rejects_nix_distro_mapping(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    deb_manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest = _build_manifest(linux_helper, tmp_path, "nix-flake")
    _manifest_tool(manifest, "yamllint")["distro_mapping"] = dict(
        _manifest_tool(deb_manifest, "yamllint")["distro_mapping"]
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: Nix artifact must not declare distro_mapping" in error
        for error in errors
    )


def test_manifest_verifier_rejects_wrong_docker_mapping_inheritance(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "docker-deb-helper")
    mapping = _manifest_tool(manifest, "yamllint")["distro_mapping"]
    mapping["source_policy_artifact_entry_id"] = "rpm"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: docker helper distro_mapping must inherit deb" in error
        for error in errors
    )


def test_manifest_verifier_rejects_pinned_upstream_without_checksum(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    tool = _manifest_tool(manifest, "yamllint")
    tool["provenance_status"] = "pinned-upstream-artifact"
    tool["trust_boundary"] = "upstream-release"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: pinned-upstream-artifact requires checksum" in error
        for error in errors
    )


def test_manifest_verifier_rejects_blocked_provenance_without_release_blocking(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "linux-tarball")
    _manifest_tool(manifest, "biome")["release_blocking"] = False

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: blocked provenance must be release_blocking" in error
        for error in errors
    )


def test_manifest_verifier_rejects_blocked_provenance_without_reason(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "linux-tarball")
    _manifest_tool(manifest, "biome")["blocker_reason"] = None

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: blocked provenance requires blocker_reason" in error for error in errors
    )


def test_manifest_verifier_rejects_fabricated_provenance_material(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    tool = _manifest_tool(manifest, "yamllint")
    tool["source_url"] = "https://example.invalid/yamllint"
    tool["pinned_version"] = "999.0"
    tool["checksum"] = "00" * 32

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any("yamllint: source_url differs" in error for error in errors)
    assert any("yamllint: pinned_version differs" in error for error in errors)
    assert any("yamllint: checksum differs" in error for error in errors)


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
        assert all("distro_mapping" not in tool for tool in manifest["tools"])
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
        assert all("distro_mapping" not in tool for tool in manifest["tools"])


def test_release_blocking_provenance_summary_tracks_current_linux_gaps(
    linux_helper: ModuleType,
) -> None:
    tarball_blockers = linux_helper.linux_release_blocking_provenance_items(
        "linux-tarball"
    )
    nix_blockers = linux_helper.linux_release_blocking_provenance_items("nix-flake")
    deb_blockers = linux_helper.linux_release_blocking_provenance_items("deb")
    deb_summary = linux_helper.linux_provenance_summary_for_artifact("deb")
    mapping_summary = linux_helper.linux_distro_mapping_summary_for_artifact("deb")
    docker_summary = linux_helper.linux_distro_mapping_summary_for_artifact(
        "docker-deb-helper"
    )

    assert tarball_blockers
    assert {record.tool_id for record in tarball_blockers} == (
        set(required_full_tool_ids(load_linter_tool_contracts())) - {"ruff"}
    )
    assert nix_blockers == ()
    assert "biome" in {record.tool_id for record in deb_blockers}
    assert "yamllint" not in {record.tool_id for record in deb_blockers}
    assert "cargo-clippy" not in {record.tool_id for record in deb_blockers}
    assert deb_summary["artifact_entry_id"] == "deb"
    assert deb_summary["release_blocking_count"] == len(deb_blockers)
    assert deb_summary["tool_count"] == len(
        required_full_tool_ids(load_linter_tool_contracts())
    )
    assert (
        deb_summary["distro_mapping_status_counts"]
        == (mapping_summary["mapping_status_counts"])
    )
    assert mapping_summary["approved_count"] > 0
    assert mapping_summary["blocked_count"] > 0
    assert mapping_summary["mapping_status_counts"]["approved-existing-policy"] > 0
    assert (
        mapping_summary["mapping_status_counts"]["blocked-missing-distro-mapping"] > 0
    )
    assert (
        docker_summary["mapping_status_counts"]
        == (mapping_summary["mapping_status_counts"])
    )


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
    assert any(
        tool["provenance_status"].startswith("blocked-") for tool in manifest["tools"]
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
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == provision_script.EXIT_OK
    assert (evidence_dir / "f4-linter-provisioning-deb.json").is_file()
    assert all("provenance_status" in tool for tool in manifest["tools"])
    assert all("trust_boundary" in tool for tool in manifest["tools"])
    assert any("distro_mapping" in tool for tool in manifest["tools"])
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
