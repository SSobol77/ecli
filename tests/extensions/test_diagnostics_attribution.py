# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_attribution.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""License/attribution and docs-contract tests for the diagnostics framework."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_third_party_notice_credits_vscode_linter_under_mit() -> None:
    notice = _read("THIRD_PARTY_NOTICES.md")
    assert "fnando/vscode-linter" in notice
    assert "MIT License" in notice
    assert "https://github.com/fnando/vscode-linter" in notice
    # States the port is conceptual and runs no VS Code runtime.
    assert "Python" in notice
    assert "does not" in notice.lower()
    assert "vs code" in notice.lower()


def test_extensions_layer_docs_state_no_custom_linters_and_no_vscode_runtime() -> None:
    docs = _read("docs/architecture/extensions-layer.md").lower()
    assert "does not implement custom linters" in docs
    assert "fnando/vscode-linter" in docs
    assert "does not execute vs code" in docs or "no vs code runtime" in docs
    assert "ruff" in docs
    assert "sonarqube" in docs


def test_docs_state_no_silent_auto_install() -> None:
    docs = _read("docs/architecture/extensions-layer.md").lower()
    assert "auto-install" in docs or "auto install" in docs
