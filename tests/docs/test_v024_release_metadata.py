# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_v024_release_metadata.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""v0.2.4 release documentation metadata contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.2.4"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def test_readme_presents_v024_as_current_release() -> None:
    readme = _read("README.md")

    assert "The v0.2.4 release layers the Extensions Foundation" in readme
    assert "ECLI v0.2.4 keeps the existing editor/TUI behavior" in readme
    assert "**Safety boundaries for v0.2.4:**" in readme


def test_changelog_contains_ordered_v024_v023_v022_sections() -> None:
    changelog = _read("CHANGELOG.md")
    normalized = _one_line(changelog)
    v024 = changelog.index("## 0.2.4 - Extensions, Diagnostics")
    v023 = changelog.index("## 0.2.3 - Panel Console Stabilization")
    v022 = changelog.index("## 0.2.2 - Packaged Runtime Startup Fixes")

    assert v024 < v023 < v022
    assert "F11 PySH Console Panel" in changelog
    assert "F12 focus switching" in changelog
    assert "subprocess argv backend" in changelog
    assert "exactly 21 clean public asset names" in normalized


def test_v024_release_notes_exist_and_are_indexed() -> None:
    notes = _read("docs/release/v0.2.4.md")
    normalized = _one_line(notes)
    index = _read("docs/release/README-release.md")

    assert "# ECLI v0.2.4 Release Notes" in notes
    assert "Extensions, Diagnostics, and Release Gate Hardening" in normalized
    assert "exactly 21 ECLI-owned physical GitHub Release assets" in normalized
    assert "ecli_0.2.4_workflow_contract_evidence.tar.gz" in notes
    assert "- `v0.2.4.md`" in index
    assert index.index("- `v0.2.4.md`") < index.index("- `v0.2.3.md`")


def test_historical_v023_release_notes_remain_v023_specific() -> None:
    notes = _read("docs/release/v0.2.3.md")

    assert "# ECLI v0.2.3 Release Notes" in notes
    assert "ecli_editor-0.2.3-py3-none-any.whl" in notes
    assert "ecli_0.2.3_workflow_contract_evidence.tar.gz" in notes
    assert "0.2.4" not in notes
    assert "v0.2.4" not in notes


def test_no_completed_clean_machine_debian13_validation_claim_is_added() -> None:
    current_docs = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "CHANGELOG.md",
            "docs/release/README-release.md",
            "docs/release/v0.2.4.md",
        )
    ).lower()

    forbidden_claims = (
        "clean-machine debian 13 validation completed",
        "validated on a second clean debian 13",
        "physically validated on a second clean debian 13",
        "debian 13 clean-machine installer validation passed",
    )
    for claim in forbidden_claims:
        assert claim not in current_docs

    assert (
        "clean-machine debian 13 installer validation has not yet been "
        "completed" in current_docs
    )


def test_public_release_surfaces_omit_internal_maintainer_process_language() -> None:
    surfaces = {
        "README.md": _read("README.md"),
        "CHANGELOG.md": _read("CHANGELOG.md"),
        "docs/release/v0.2.4.md": _read("docs/release/v0.2.4.md"),
    }

    forbidden_terms = (
        "this release metadata",
        "release metadata update",
        "for v0.2.4 release metadata",
        "no tag, upload",
        "created by this document",
        "post-cut",
        "pr #145",
        "pr #146",
        "pr #147",
        "agent prompt",
        "chore/prepare-v0.2.4",
    )

    for surface_name, text in surfaces.items():
        lowered = text.lower()
        for term in forbidden_terms:
            assert term not in lowered, (
                f"{surface_name} contains forbidden term: {term!r}"
            )


def test_debian_clean_machine_limitation_appears_exactly_once() -> None:
    notes = _read("docs/release/v0.2.4.md")
    marker = "Clean-machine Debian 13 installer validation has not yet been completed."

    assert notes.count(marker) == 1


def test_canonical_release_identity_is_consistent_across_public_surfaces() -> None:
    readme = _read("README.md")
    changelog = _read("CHANGELOG.md")
    notes = _one_line(_read("docs/release/v0.2.4.md"))

    identity = "Extensions, Diagnostics, and Release Gate Hardening"

    assert "## 0.2.4 - Extensions, Diagnostics, and Release Gate Hardening" in (
        changelog
    )
    assert f"ECLI v0.2.4 is an {identity} release." in notes
    assert "release gate hardening" in readme.lower()

    assert "release evidence" not in readme.lower()
    assert "release evidence" not in changelog.lower()
    assert "release evidence" not in notes.lower()
