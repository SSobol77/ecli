# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_f4_linter_microservices_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Docs contract tests for the F4 linter microservices design.

docs/architecture/ecli-f4-linter-microservices-design.md is the
authoritative architecture contract for F4 Linter Microservices. These
tests guard that other tracked documentation does not reintroduce the
stale claims it replaced (ESLint-as-default, "install the linter pack"
as a normal post-install step) and that the profile matrix it defines
stays discoverable from the existing catalog docs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN_DOC = "docs/architecture/ecli-f4-linter-microservices-design.md"
LINTER_LAYER_DOC = "docs/extensions/diagnostics-linter-layer.md"

# The design doc itself is allowed to name `ecli doctor --install-linter-pack`
# (it defines the term and explains it is a repair/verification tool, not the
# normal install path), so it is excluded from the stale-phrase scan below.
_EXEMPT_FROM_STALE_SCAN = {DESIGN_DOC}

_STALE_PHRASES: tuple[str, ...] = (
    "doctor --install-linter-pack",
    "eslint is the default",
    "eslint as the default",
)


def _tracked_markdown_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_f4_linter_microservices_design_doc_exists() -> None:
    assert (ROOT / DESIGN_DOC).is_file()


def test_diagnostics_linter_layer_doc_references_the_authoritative_contract() -> None:
    text = (ROOT / LINTER_LAYER_DOC).read_text(encoding="utf-8")
    assert DESIGN_DOC in text


def test_no_doc_reintroduces_stale_linter_pack_or_eslint_default_claims() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _tracked_markdown_files():
        if path in _EXEMPT_FROM_STALE_SCAN:
            continue
        candidate = ROOT / path
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8").lower()
        for phrase in _STALE_PHRASES:
            if phrase in text:
                offenders.append((path, phrase))
    assert offenders == []


def test_design_doc_treats_biome_zig_cpp_and_java_as_first_class() -> None:
    text = (ROOT / DESIGN_DOC).read_text(encoding="utf-8")
    for marker in ("Biome", "Zig", "C/C++", "Java"):
        assert marker in text, f"{marker!r} missing from the design doc"
