# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_release_gate_contract_alignment.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Current documentation contract for Gate 2 and release artifact validation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CURRENT_GATE_DOCS = (
    "docs/contributor/development-setup.md",
    "docs/release/release-process.md",
    "docs/release/release-checklist.md",
    "docs/release/artifact-verification.md",
    "docs/release/artifact-contract.md",
    "docs/release/packaging-flows.md",
    "docs/release/build-matrix.md",
    "docs/release/README-release.md",
    "README.md",
)

HISTORICAL_GATE_DOCS = (
    "audit-report.md",
    "docs/planning/gate2-phase0-report.md",
    "docs/planning/phase1-implementation-report.md",
    "docs/planning/phase1-implementation-log.md",
    "docs/planning/post-merge-defects.md",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _combined(paths: tuple[str, ...]) -> str:
    return "\n".join(_read(path) for path in paths)


def test_current_docs_define_three_separate_validation_layers() -> None:
    text = " ".join(_combined(CURRENT_GATE_DOCS).split())

    required = (
        "`make validate-gate2` is source and structural contract validation only",
        "does not require built release artifacts or `twine`",
        "`make validate-built-artifacts` is explicit release-oriented physical "
        "artifact validation",
        "partial sets fail closed",
        "complete PyPI wheel/sdist set",
        "`make validate-release-assets` verifies the exact final GitHub Release "
        "asset set",
        "21 uploaded ECLI-owned assets",
        "non-uploaded `.checksums/` evidence",
    )
    for marker in required:
        assert marker in text


def test_twine_is_not_documented_as_source_only_gate2_dependency() -> None:
    development_setup = _read("docs/contributor/development-setup.md")
    release_process = _read("docs/release/release-process.md")

    assert "PyPI artifact validation in `make validate-gate2`" not in (
        development_setup
    )
    assert "| `twine` | Release-only | Final PyPI built-artifact validation" in (
        development_setup
    )
    assert "without built release artifacts and without final release-only tooling" in (
        release_process
    )
    assert "such as `twine`" in release_process


def test_current_docs_do_not_make_gate2_the_final_artifact_verifier() -> None:
    text = _combined(CURRENT_GATE_DOCS)

    forbidden = (
        "Gate 2 validation completed for built artifacts",
        "PyPI artifact validation in `make validate-gate2`",
        "`make validate-gate2` for explicit final artifact verification",
        "`make validate-gate2` validates complete artifact/sidecar pairs",
        "`make validate-gate2` delegates to `validate-pypi-contract`",
    )
    for marker in forbidden:
        assert marker not in text


def test_current_release_docs_preserve_asset_and_checksum_contract() -> None:
    text = " ".join(_combined(CURRENT_GATE_DOCS).split())

    required = (
        "exactly 21 ECLI-owned physical GitHub Release assets",
        "Source code (zip)",
        "Source code (tar.gz)",
        "not part of the canonical 21 artifact contract entries",
        "Checksum sidecars are mandatory CI/release verification evidence",
        "not uploaded as separate GitHub Release assets",
        "releases/<version>/.checksums/",
    )
    for marker in required:
        assert marker in text


def test_historical_gate2_reports_are_classified_as_history() -> None:
    text = _combined(HISTORICAL_GATE_DOCS)

    assert "Gate 2 Phase 0 Report" in text
    assert "Gate 2 Phase 1 Implementation Report" in text
    assert "Gate 2 validation completed for built artifacts" in text
