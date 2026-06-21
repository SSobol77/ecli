# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_textmate_dependency_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Dependency + documentation contract for the TextMate engine (#102).

Real TextMate tokenization depends on ``python-textmate`` (which pulls
``onigurumacffi`` / the native **Oniguruma** library). These gates ensure the
dependency is actually declared and that install/build/packaging docs tell users
about the native dependency and the safe runtime fallback — so the project never
silently ships "TextMate support" that cannot build or run.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.fail(f"required doc missing: {relative}")
    return path.read_text(encoding="utf-8")


def test_pyproject_declares_python_textmate() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data.get("project", {}).get("dependencies", [])
    assert any(dep.lower().startswith("python-textmate") for dep in dependencies), (
        dependencies
    )


def test_install_docs_describe_oniguruma_and_fallback() -> None:
    text = _read("docs/INSTALL.md").lower()
    assert "onigurumacffi" in text
    assert "oniguruma" in text
    # Source-build native dependency is documented...
    assert "source" in text and ("libonig" in text or "oniguruma development" in text)
    # ...and so is the safe runtime fallback when it is unavailable.
    assert "fallback" in text or "fall back" in text


def test_build_from_source_docs_mention_native_dependency() -> None:
    text = _read("docs/contributor/build-from-source.md").lower()
    assert "onigurumacffi" in text
    assert "oniguruma" in text
    assert (
        "libonig" in text or "development header" in text or "devel/oniguruma" in text
    )


def test_packaging_release_docs_mention_oniguruma_source_build() -> None:
    text = _read("docs/release/packaging-flows.md").lower()
    assert "oniguruma" in text
    assert "source build" in text or "source builds" in text
    assert "python-textmate" in text or "onigurumacffi" in text
