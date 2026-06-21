# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extensions_tree_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the imported ECLI Extensions Layer source tree (#99).

Issue #98 imported the prepared upstream VS Code / TextMate-compatible extension
asset tree **unchanged** under ``src/ecli/extensions/``. This module asserts that
representative imported assets are present in the repository tree, that the
known import-cleanup artifacts are absent, and that each representative file
*type* is represented at least once.

These are read-only tree assertions only. They do not import, execute, parse, or
adapt any extension asset, and they must never modify the imported tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS_ROOT = REPO_ROOT / "src" / "ecli" / "extensions"


# Representative imported assets that must exist verbatim in the tree. If any of
# these ever differs from the imported upstream layout, fix the path here to the
# real imported location -- never rename the upstream file.
REPRESENTATIVE_ASSETS: tuple[str, ...] = (
    "cgmanifest.json",
    "bat/package.json",
    "bat/language-configuration.json",
    "bat/syntaxes/batchfile.tmLanguage.json",
    "bat/snippets/batchfile.code-snippets",
    "python/package.json",
    "python/language-configuration.json",
    "json/package.json",
    "javascript/package.json",
    "markdown-basics/package.json",
    "cpp/package.json",
)

# Import-cleanup artifacts that must NOT exist under the extensions root: a
# nested ``extensions/extensions/`` directory and the upstream structure note.
FORBIDDEN_PATHS: tuple[str, ...] = (
    "extensions",
    "EXTENSIONS_FOLDER-structure.md",
)


def test_extensions_root_exists() -> None:
    assert EXTENSIONS_ROOT.is_dir(), (
        f"imported extensions root missing: {EXTENSIONS_ROOT}"
    )


@pytest.mark.parametrize("relative_path", REPRESENTATIVE_ASSETS)
def test_representative_asset_exists(relative_path: str) -> None:
    asset = EXTENSIONS_ROOT / relative_path
    assert asset.is_file(), (
        f"imported extension asset missing: src/ecli/extensions/{relative_path}"
    )
    assert asset.stat().st_size > 0, (
        f"imported extension asset is empty: src/ecli/extensions/{relative_path}"
    )


@pytest.mark.parametrize("relative_path", FORBIDDEN_PATHS)
def test_forbidden_path_absent(relative_path: str) -> None:
    forbidden = EXTENSIONS_ROOT / relative_path
    assert not forbidden.exists(), (
        f"unexpected path present under extensions root: "
        f"src/ecli/extensions/{relative_path}"
    )


# Representative file *types* that the imported tree must contain at least once.
# ``glob_pattern`` is matched recursively under the extensions root.
REPRESENTATIVE_TYPES: tuple[tuple[str, str], ...] = (
    ("package.json", "**/package.json"),
    ("package.nls.json", "**/package.nls.json"),
    ("language-configuration.json", "**/language-configuration.json"),
    ("*.tmLanguage.json", "**/*.tmLanguage.json"),
    ("*.code-snippets", "**/*.code-snippets"),
    ("cgmanifest.json", "**/cgmanifest.json"),
)


@pytest.mark.parametrize(("label", "glob_pattern"), REPRESENTATIVE_TYPES)
def test_representative_file_type_present(label: str, glob_pattern: str) -> None:
    matches = list(EXTENSIONS_ROOT.glob(glob_pattern))
    assert matches, (
        f"imported tree has no {label} file (pattern {glob_pattern!r}) under "
        f"src/ecli/extensions/"
    )
