# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_readme_naming_policy.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Repository README naming policy tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_README = "README.md"
OLD_RELEASE_README = "docs/release/" + ROOT_README
NEW_RELEASE_README = "docs/release/README-release.md"

# Nested README.md files under the imported, read-only upstream VS Code /
# TextMate extension asset tree (issue #98) belong to the upstream assets and
# are exempt from the ECLI README naming policy. The policy is unchanged for the
# rest of the repository. See docs/architecture/extensions-layer.md.
IMPORTED_EXTENSIONS_PREFIX = "src/ecli/extensions/"


def tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.splitlines()


def test_root_readme_is_the_only_tracked_global_readme() -> None:
    files = tracked_files()

    assert ROOT_README in files
    assert NEW_RELEASE_README in files
    assert OLD_RELEASE_README not in files

    non_root_readmes = [
        path
        for path in files
        if (path.endswith(f"/{ROOT_README}") or path == ROOT_README)
        and not path.startswith(IMPORTED_EXTENSIONS_PREFIX)
    ]
    assert non_root_readmes == [ROOT_README]


def test_tracked_text_files_do_not_reference_old_release_readme_path() -> None:
    offenders: list[str] = []

    for path in tracked_files():
        candidate = ROOT / path
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD_RELEASE_README in text:
            offenders.append(path)

    assert offenders == []
