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


def _evidence_record(records: tuple[Any, ...], tool_id: str) -> Any:
    for record in records:
        if record.tool_id == tool_id:
            return record
    raise AssertionError(f"missing distro evidence record: {tool_id}")


def _manifest_distro_evidence(
    manifest: dict[str, Any],
    tool_id: str = "yamllint",
) -> dict[str, Any]:
    return _manifest_tool(manifest, tool_id)["distro_mapping"]["evidence"]


def _complete_verified_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    promoted = dict(evidence)
    promoted.update(
        {
            "evidence_source": "synthetic-official-source",
            "evidence_source_type": "official-distro-metadata",
            "evidence_status": "verified-official-source",
            "official_source_name": "synthetic distro package index",
            "official_source_url": "synthetic-official-source",
            "official_source_kind": "distro-package-index",
            "verification_scope": "package-name-and-executable",
            "verified_package_names": list(evidence["package_names"]),
            "verified_executable_names": list(evidence["executable_names"]),
            "verification_note": "Synthetic promotion record for gate validation.",
            "external_verification_required_for_new_mappings": False,
            "release_blocking": False,
            "blocker_reason": None,
        }
    )
    return promoted


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


def test_distro_evidence_scope_is_approved_package_mappings_only(
    linux_helper: ModuleType,
) -> None:
    evidence_artifacts = {
        "deb",
        "rpm",
        "opensuse-rpm",
        "arch-pkgbuild",
        "slackware-txz",
        "docker-deb-helper",
        "docker-rpm-helper",
    }
    matrix = linux_helper.linux_distro_mapping_evidence_matrix()

    assert {record.artifact_entry_id for record in matrix} == evidence_artifacts
    assert all(
        record.evidence_source_type == "repository-local-policy" for record in matrix
    )
    assert all(record.evidence_status == "current-policy-baseline" for record in matrix)
    for artifact_id in (
        "linux-pyinstaller",
        "linux-tarball",
        "appimage",
        "nix-flake",
        "nixos-package",
    ):
        assert (
            linux_helper.linux_distro_mapping_evidence_catalog_for_artifact(artifact_id)
            == ()
        )


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
    deb_evidence = linux_helper.linux_distro_mapping_evidence_catalog_for_artifact(
        "deb"
    )
    yamllint = _mapping_record(deb, "yamllint")
    yamllint_evidence = _evidence_record(deb_evidence, "yamllint")

    assert yamllint.mapping_status == "approved-existing-policy"
    assert yamllint.provenance_status == "distro-signed-package"
    assert yamllint.trust_boundary == "distro-package-manager"
    assert yamllint.package_names == ("yamllint",)
    assert yamllint.evidence_record_id == yamllint_evidence.evidence_record_id
    assert yamllint.evidence_source == "OS_PACKAGE_NAMES"
    assert "OS_PACKAGE_NAMES policy" in yamllint.evidence_note
    assert yamllint.release_blocking is False
    assert yamllint_evidence.evidence_source == "OS_PACKAGE_NAMES"
    assert yamllint_evidence.evidence_source_type == "repository-local-policy"
    assert yamllint_evidence.evidence_status == "current-policy-baseline"
    assert yamllint_evidence.package_names == yamllint.package_names


def test_generated_distro_evidence_preserves_repository_local_baseline(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)

    assert evidence["evidence_source"] == "OS_PACKAGE_NAMES"
    assert evidence["evidence_source_type"] == "repository-local-policy"
    assert evidence["evidence_status"] == "current-policy-baseline"
    assert evidence["external_verification_required_for_new_mappings"] is True
    assert evidence["release_blocking"] is False
    for field in (
        "official_source_name",
        "official_source_url",
        "official_source_kind",
        "verification_scope",
        "verification_note",
    ):
        assert evidence.get(field) in (None, "")
    assert evidence.get("verified_package_names") in (None, [])
    assert evidence.get("verified_executable_names") in (None, [])
    assert linux_helper.verify_linux_provisioning_manifest(manifest) == []


def test_all_generated_linux_manifests_still_verify_with_baseline_evidence(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    for artifact_id in LINUX_ARTIFACT_IDS:
        manifest = _build_manifest(linux_helper, tmp_path, artifact_id)

        assert linux_helper.verify_linux_provisioning_manifest(manifest) == []


def test_distro_evidence_promotion_requirements_are_explicit(
    linux_helper: ModuleType,
) -> None:
    requirements = linux_helper.linux_distro_evidence_promotion_requirements()

    assert set(requirements["required_fields"]) == {
        "official_source_name",
        "official_source_url",
        "official_source_kind",
        "verification_scope",
        "verified_package_names",
        "verified_executable_names",
        "verification_note",
    }
    assert set(requirements["official_source_types"]) == {
        "official-distro-metadata",
        "upstream-project-docs",
    }
    assert set(requirements["official_source_kinds"]) == {
        "distro-package-index",
        "distro-package-recipe",
        "upstream-install-doc",
        "upstream-release-page",
    }
    assert set(requirements["verification_scopes"]) == {
        "package-name-only",
        "package-name-and-executable",
        "package-name-executable-and-license",
    }


def test_generated_baseline_evidence_records_are_not_promotable(
    linux_helper: ModuleType,
) -> None:
    matrix = linux_helper.linux_distro_mapping_evidence_matrix()
    promotion_matrix = linux_helper.linux_distro_mapping_evidence_promotion_matrix()

    assert matrix
    assert len(promotion_matrix) == len(matrix)
    assert all(record.evidence_status == "current-policy-baseline" for record in matrix)
    assert all(
        not linux_helper.linux_distro_mapping_evidence_can_promote(record)
        for record in matrix
    )
    assert all(
        row["promotion_state"] == "baseline-not-promoted" for row in promotion_matrix
    )
    assert all(row["can_promote"] is False for row in promotion_matrix)


def test_complete_synthetic_verified_official_evidence_is_promotable(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))

    assert linux_helper.linux_distro_mapping_evidence_promotion_errors(evidence) == []
    assert linux_helper.linux_distro_mapping_evidence_can_promote(evidence) is True

    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence
    assert linux_helper.verify_linux_provisioning_manifest(manifest) == []


def test_repository_local_evidence_exactly_mirrors_os_package_names(
    linux_helper: ModuleType,
) -> None:
    for artifact_id in (
        "deb",
        "rpm",
        "opensuse-rpm",
        "arch-pkgbuild",
        "slackware-txz",
        "docker-deb-helper",
        "docker-rpm-helper",
    ):
        source_artifact_id = linux_helper.PACKAGE_POLICY_SOURCE_BY_HELPER.get(
            artifact_id,
            artifact_id,
        )
        expected = linux_helper.OS_PACKAGE_NAMES[source_artifact_id]
        evidence = linux_helper.linux_distro_mapping_evidence_catalog_for_artifact(
            artifact_id
        )

        assert {record.tool_id for record in evidence} == set(expected)
        for record in evidence:
            assert record.source_policy_artifact_entry_id == source_artifact_id
            assert record.package_names == expected[record.tool_id]
            assert set(record.package_names) <= set(expected[record.tool_id])


def test_docker_helper_distro_mappings_inherit_deb_and_rpm_policy(
    linux_helper: ModuleType,
) -> None:
    docker_deb = linux_helper.linux_distro_mapping_catalog_for_artifact(
        "docker-deb-helper"
    )
    docker_rpm = linux_helper.linux_distro_mapping_catalog_for_artifact(
        "docker-rpm-helper"
    )
    docker_deb_evidence = (
        linux_helper.linux_distro_mapping_evidence_catalog_for_artifact(
            "docker-deb-helper"
        )
    )
    docker_rpm_evidence = (
        linux_helper.linux_distro_mapping_evidence_catalog_for_artifact(
            "docker-rpm-helper"
        )
    )
    deb_yamllint = _mapping_record(docker_deb, "yamllint")
    rpm_yamllint = _mapping_record(docker_rpm, "yamllint")
    deb_yamllint_evidence = _evidence_record(docker_deb_evidence, "yamllint")
    rpm_yamllint_evidence = _evidence_record(docker_rpm_evidence, "yamllint")

    assert deb_yamllint.distro_family == "debian"
    assert deb_yamllint.package_names == ("yamllint",)
    assert deb_yamllint.source_policy_artifact_entry_id == "deb"
    assert deb_yamllint_evidence.source_policy_artifact_entry_id == "deb"
    assert deb_yamllint_evidence.evidence_record_id == (deb_yamllint.evidence_record_id)
    assert rpm_yamllint.distro_family == "rpm-generic"
    assert rpm_yamllint.package_names == ("python3-yamllint",)
    assert rpm_yamllint.source_policy_artifact_entry_id == "rpm"
    assert rpm_yamllint_evidence.source_policy_artifact_entry_id == "rpm"
    assert rpm_yamllint_evidence.evidence_record_id == (rpm_yamllint.evidence_record_id)


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
    assert (
        yamllint["distro_mapping"]["evidence_record_id"]
        == (yamllint["distro_mapping"]["evidence"]["evidence_record_id"])
    )
    assert yamllint["distro_mapping"]["evidence"]["evidence_source"] == (
        "OS_PACKAGE_NAMES"
    )
    assert yamllint["distro_mapping"]["evidence"]["evidence_source_type"] == (
        "repository-local-policy"
    )
    assert yamllint["distro_mapping"]["evidence"]["evidence_status"] == (
        "current-policy-baseline"
    )
    assert biome["distro_mapping"]["mapping_status"] == (
        "blocked-missing-distro-mapping"
    )
    assert biome["distro_mapping"]["release_blocking"] is True
    assert "evidence" not in biome["distro_mapping"]
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


def test_manifest_verifier_rejects_missing_evidence_on_approved_distro_mapping(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    del _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"]

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: approved distro_mapping requires evidence" in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_without_official_source_name(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["official_source_name"] = ""
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: missing official_source_name" in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_without_official_source_url(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["official_source_url"] = None
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: missing official_source_url" in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_with_repository_local_source_type(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["evidence_source_type"] = "repository-local-policy"
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: verified-official-source evidence cannot use repository-local-policy"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_with_unknown_source_kind(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["official_source_kind"] = "fabricated-kind"
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: unknown official_source_kind 'fabricated-kind'"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_with_unknown_verification_scope(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["verification_scope"] = "fabricated-scope"
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: unknown verification_scope 'fabricated-scope'"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_with_mismatched_package_names(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["verified_package_names"] = ["wrong-package"]
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: verified_package_names differ from package_names"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_with_mismatched_executable_names(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["verified_executable_names"] = ["wrong-executable"]
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: verified_executable_names differ from executable_names"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_without_verification_note(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["verification_note"] = " "
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: missing verification_note" in error
        for error in errors
    )


def test_manifest_verifier_rejects_verified_evidence_requiring_external_verification(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["external_verification_required_for_new_mappings"] = True
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: verified-official-source evidence must not require external verification"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_current_baseline_without_external_verification(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    _manifest_distro_evidence(manifest)[
        "external_verification_required_for_new_mappings"
    ] = False

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: current-policy-baseline evidence must require external verification"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_current_baseline_with_official_source_claims(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["official_source_name"] = "synthetic distro package index"
    evidence["official_source_url"] = "synthetic-official-source"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: current-policy-baseline evidence must not claim official_source_name"
        in error
        for error in errors
    )
    assert any(
        "yamllint: distro_mapping evidence: current-policy-baseline evidence must not claim official_source_url"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_blocked_missing_official_evidence_not_blocking(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _complete_verified_evidence(_manifest_distro_evidence(manifest))
    evidence["evidence_status"] = "blocked-missing-evidence"
    evidence["release_blocking"] = False
    _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"] = evidence

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence: blocked/missing official evidence must be release_blocking"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_unknown_distro_evidence_status(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["evidence_status"] = "fabricated"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: unknown evidence_status 'fabricated'" in error for error in errors
    )


def test_manifest_verifier_rejects_unknown_distro_evidence_source_type(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["evidence_source_type"] = "fabricated"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: unknown evidence_source_type 'fabricated'" in error
        for error in errors
    )


def test_manifest_verifier_rejects_tampered_distro_evidence_packages(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["package_names"] = ["wrong-package"]

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence package_names differs" in error
        for error in errors
    )


def test_manifest_verifier_rejects_distro_evidence_artifact_mismatch(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["artifact_entry_id"] = "rpm"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence artifact_entry_id mismatch" in error
        for error in errors
    )


def test_manifest_verifier_rejects_distro_evidence_source_policy_mismatch(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_distro_evidence(manifest)
    evidence["source_policy_artifact_entry_id"] = "rpm"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence source_policy_artifact_entry_id mismatch"
        in error
        for error in errors
    )


def test_manifest_verifier_rejects_tampered_distro_evidence_record_id(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    evidence = _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"]
    evidence["evidence_record_id"] = "repository-local-policy:rpm:yamllint"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: distro_mapping evidence evidence_record_id differs" in error
        for error in errors
    )


def test_manifest_verifier_rejects_wrong_docker_evidence_inheritance(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "docker-deb-helper")
    evidence = _manifest_tool(manifest, "yamllint")["distro_mapping"]["evidence"]
    evidence["source_policy_artifact_entry_id"] = "rpm"

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: docker helper distro evidence must inherit deb" in error
        for error in errors
    )


def test_manifest_verifier_rejects_blocked_mapping_with_approved_evidence(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(linux_helper, tmp_path, "deb")
    approved_evidence = _manifest_tool(manifest, "yamllint")["distro_mapping"][
        "evidence"
    ]
    _manifest_tool(manifest, "biome")["distro_mapping"]["evidence"] = dict(
        approved_evidence
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: blocked distro_mapping must not declare approved evidence" in error
        for error in errors
    )


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


def test_manifest_verifier_rejects_self_contained_distro_evidence(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    deb_manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest = _build_manifest(linux_helper, tmp_path, "linux-tarball")
    _manifest_tool(manifest, "biome")["distro_evidence"] = dict(
        _manifest_tool(deb_manifest, "yamllint")["distro_mapping"]["evidence"]
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "biome: self-contained artifact must not declare distro evidence" in error
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


def test_manifest_verifier_rejects_nix_distro_evidence(
    linux_helper: ModuleType,
    tmp_path: Path,
) -> None:
    deb_manifest = _build_manifest(linux_helper, tmp_path, "deb")
    manifest = _build_manifest(linux_helper, tmp_path, "nix-flake")
    _manifest_tool(manifest, "yamllint")["distro_evidence"] = dict(
        _manifest_tool(deb_manifest, "yamllint")["distro_mapping"]["evidence"]
    )

    errors = linux_helper.verify_linux_provisioning_manifest(manifest)

    assert any(
        "yamllint: Nix artifact must not declare distro evidence" in error
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
    evidence_summary = linux_helper.linux_distro_mapping_evidence_summary_for_artifact(
        "deb"
    )
    promotion_summary = (
        linux_helper.linux_distro_mapping_evidence_promotion_summary_for_artifact("deb")
    )
    docker_summary = linux_helper.linux_distro_mapping_summary_for_artifact(
        "docker-deb-helper"
    )
    docker_evidence_summary = (
        linux_helper.linux_distro_mapping_evidence_summary_for_artifact(
            "docker-deb-helper"
        )
    )
    docker_promotion_summary = (
        linux_helper.linux_distro_mapping_evidence_promotion_summary_for_artifact(
            "docker-deb-helper"
        )
    )
    tarball_evidence_summary = (
        linux_helper.linux_distro_mapping_evidence_summary_for_artifact("linux-tarball")
    )
    tarball_promotion_summary = (
        linux_helper.linux_distro_mapping_evidence_promotion_summary_for_artifact(
            "linux-tarball"
        )
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
        evidence_summary["evidence_record_count"] == mapping_summary["approved_count"]
    )
    assert evidence_summary["evidence_status_counts"] == {
        "current-policy-baseline": evidence_summary["evidence_record_count"]
    }
    assert evidence_summary["evidence_source_type_counts"] == {
        "repository-local-policy": evidence_summary["evidence_record_count"]
    }
    assert (
        mapping_summary["evidence_status_counts"]
        == (evidence_summary["evidence_status_counts"])
    )
    assert (
        promotion_summary["evidence_record_count"]
        == evidence_summary["evidence_record_count"]
    )
    assert promotion_summary["promotable_count"] == 0
    assert (
        promotion_summary["baseline_not_promoted_count"]
        == (evidence_summary["evidence_record_count"])
    )
    assert promotion_summary["verified_official_source_count"] == 0
    assert promotion_summary["promotion_state_counts"] == {
        "baseline-not-promoted": evidence_summary["evidence_record_count"]
    }
    assert (
        docker_summary["mapping_status_counts"]
        == (mapping_summary["mapping_status_counts"])
    )
    assert (
        docker_evidence_summary["evidence_status_counts"]
        == (evidence_summary["evidence_status_counts"])
    )
    assert (
        docker_promotion_summary["promotion_state_counts"]
        == (promotion_summary["promotion_state_counts"])
    )
    assert tarball_evidence_summary["evidence_record_count"] == 0
    assert tarball_promotion_summary["evidence_record_count"] == 0


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
