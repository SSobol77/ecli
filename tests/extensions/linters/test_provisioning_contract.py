# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_provisioning_contract.py
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

import pytest

from ecli.extensions.linters.core.provisioning import (
    build_component_model,
    build_provisioning_plan,
    evidence_filename,
    evidence_to_dict,
    plan_has_release_blocking_failure,
    plan_to_evidence,
    verify_evidence_dir,
    verify_evidence_payload,
)
from ecli.extensions.linters.core.provisioning_contract import (
    LinterToolContract,
    VersionProbe,
)
from ecli.extensions.linters.core.provisioning_registry import (
    ARTIFACT_CONTRACT_ENTRIES,
    get_artifact_entry,
    load_linter_tool_contracts,
    optional_tool_ids,
    required_full_tool_ids,
)
from ecli.extensions.linters.core.registry import CANONICAL_ARTIFACT_ENTRY_IDS


REQUIRED_FULL_TOOL_IDS = (
    "ruff",
    "biome",
    "markdownlint-cli2",
    "yamllint",
    "shellcheck",
    "zig",
    "hadolint",
    "taplo",
    "actionlint",
    "clang-tidy",
    "cppcheck",
    "clang-format",
    "checkstyle",
    "pmd",
    "spotbugs",
    "cargo-clippy",
    "golangci-lint",
    "sqlfluff",
    "tflint",
)


def test_artifact_registry_has_exactly_twenty_one_entries() -> None:
    assert len(ARTIFACT_CONTRACT_ENTRIES) == 21
    assert [entry.index for entry in ARTIFACT_CONTRACT_ENTRIES] == list(range(1, 22))
    assert tuple(entry.artifact_entry_id for entry in ARTIFACT_CONTRACT_ENTRIES) == (
        CANONICAL_ARTIFACT_ENTRY_IDS
    )


def test_required_full_baseline_comes_from_package_contracts() -> None:
    contracts = load_linter_tool_contracts()
    assert required_full_tool_ids(contracts) == REQUIRED_FULL_TOOL_IDS
    assert set(optional_tool_ids(contracts)) == {
        "eslint",
        "stylelint",
        "oxlint",
        "pylint",
    }


def test_package_contracts_have_provisioning_metadata() -> None:
    for contract in load_linter_tool_contracts():
        assert contract.allowed_install_mechanisms
        assert contract.provenance_requirements
        assert contract.source_url is not None
        assert contract.version_probe.command
        assert contract.artifact_entry_ids == CANONICAL_ARTIFACT_ENTRY_IDS


def test_component_model_selects_every_full_required_tool_by_default() -> None:
    contracts = load_linter_tool_contracts()
    model = build_component_model(get_artifact_entry("deb"), "full", contracts)
    by_id = {option.tool_id: option for option in model.options}

    for tool_id in REQUIRED_FULL_TOOL_IDS:
        assert by_id[tool_id].required_for_full is True
        assert by_id[tool_id].selected_by_default is True
    for tool_id in ("eslint", "stylelint", "oxlint", "pylint"):
        assert by_id[tool_id].required_for_full is False
        assert by_id[tool_id].selected_by_default is False


def test_excluding_required_full_tool_marks_plan_custom_partial(tmp_path: Path) -> None:
    plan = build_provisioning_plan(
        artifact_entry_id="deb",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
        mode="dry-run",
        profile="full",
        exclude_tools=("clang-format",),
    )

    assert plan.profile.effective_profile == "custom"
    assert plan.profile.full_profile_complete is False
    assert "clang-format" in (plan.profile.custom_profile_reason or "")
    clang_format = next(
        action for action in plan.actions if action.tool_id == "clang-format"
    )
    assert clang_format.selected is False
    assert clang_format.user_opted_out is True


def test_minimal_profile_selects_only_internal_ruff(tmp_path: Path) -> None:
    plan = build_provisioning_plan(
        artifact_entry_id="deb",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
        mode="dry-run",
        profile="minimal",
    )

    selected = {action.tool_id for action in plan.actions if action.selected}
    assert selected == {"ruff"}
    assert plan.profile.full_profile_complete is False


def test_deb_dry_run_evidence_satisfies_full_release_contract(tmp_path: Path) -> None:
    plan = build_provisioning_plan(
        artifact_entry_id="deb",
        target_dir=tmp_path / "target",
        evidence_dir=tmp_path / "evidence",
        mode="dry-run",
        profile="full",
    )
    evidence = plan_to_evidence(
        plan,
        ecli_version="0.2.3",
        timestamp="1970-01-01T00:00:00Z",
    )
    payload = evidence_to_dict(evidence)

    assert plan.profile.full_profile_complete is True
    assert plan_has_release_blocking_failure(plan) is False
    assert verify_evidence_payload(payload) == []


def test_pypi_full_evidence_records_documented_minimal_constraint(
    tmp_path: Path,
) -> None:
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
            ecli_version="0.2.3",
            timestamp="1970-01-01T00:00:00Z",
        )
    )

    assert plan.profile.effective_profile == "minimal"
    assert plan.profile.full_profile_complete is False
    assert "Python wheel metadata" in (plan.profile.custom_profile_reason or "")
    assert verify_evidence_payload(payload) == []


def test_verifier_ignores_github_generated_source_archives() -> None:
    assert verify_evidence_payload({"artifact_entry_id": "Source code (zip)"}) == []
    assert verify_evidence_payload({"artifact_entry_id": "Source code (tar.gz)"}) == []


def test_evidence_filename_rejects_pathlike_artifact_ids(tmp_path: Path) -> None:
    absolute_artifact_id = str(tmp_path.resolve() / "deb")
    for artifact_id in ("../deb", absolute_artifact_id, "deb/../rpm", r"C:\escape\deb"):
        with pytest.raises(ValueError):
            evidence_filename(artifact_id)


def test_evidence_filename_rejects_unknown_artifact_ids() -> None:
    with pytest.raises(KeyError):
        evidence_filename("not-a-canonical-artifact")


def test_build_plan_rejects_pathlike_artifact_id_before_path_construction(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        build_provisioning_plan(
            artifact_entry_id="../deb",
            target_dir=tmp_path / "target",
            evidence_dir=tmp_path / "evidence",
            mode="dry-run",
            profile="full",
        )


def test_verify_evidence_dir_rejects_absolute_artifact_id_before_path_construction(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        verify_evidence_dir(
            tmp_path / "evidence",
            artifact_entry_id=str(tmp_path.resolve() / "deb"),
        )


def test_planned_target_path_rejects_escape_executable_name(
    tmp_path: Path,
) -> None:
    bad_contract = LinterToolContract(
        tool_id="bad-tool",
        display_name="Bad Tool",
        languages=("text",),
        install_group="test",
        tier="required",
        provider_kind="external",
        required_for_full=True,
        bundled_with_full_install=False,
        selected_by_default=True,
        executable_names=("../escape",),
        version_probe=VersionProbe(command=("bad-tool", "--version")),
        allowed_install_mechanisms=("os-package-manager",),
        provenance_requirements=("package-manager-metadata",),
        source_url="https://example.invalid/bad-tool",
        pinned_version=None,
        checksum_required_for_downloads=False,
        artifact_entry_ids=CANONICAL_ARTIFACT_ENTRY_IDS,
        delivery_notes="test-only contract",
    )

    with pytest.raises(ValueError):
        build_provisioning_plan(
            artifact_entry_id="deb",
            target_dir=tmp_path / "target",
            evidence_dir=tmp_path / "evidence",
            mode="dry-run",
            profile="full",
            contracts=(bad_contract,),
        )
