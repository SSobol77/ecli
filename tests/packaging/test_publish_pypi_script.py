# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_publish_pypi_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/publish_pypi.py guard (never publishes)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def publish_pypi(repo_root: Path) -> ModuleType:
    return load_script_module(repo_root, "scripts/publish_pypi.py", "publish_pypi")


def test_default_is_blocked(publish_pypi: ModuleType) -> None:
    assert publish_pypi.main([]) == publish_pypi.EXIT_BLOCKED


def test_dry_run_is_structural_only(publish_pypi: ModuleType) -> None:
    assert publish_pypi.main(["--dry-run"]) == publish_pypi.EXIT_OK


def test_publish_requires_confirmation(
    publish_pypi: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(publish_pypi.PUBLISH_CONFIRM_ENV, raising=False)
    assert publish_pypi.main(["--publish"]) == publish_pypi.EXIT_BLOCKED


def test_publish_with_confirmation_still_does_not_upload(
    publish_pypi: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(publish_pypi.PUBLISH_CONFIRM_ENV, "1")
    # Confirmed path prints the manual procedure but still refuses to upload.
    assert publish_pypi.main(["--publish"]) == publish_pypi.EXIT_BLOCKED


def test_source_never_executes_upload(repo_root: Path) -> None:
    source = (repo_root / "scripts" / "publish_pypi.py").read_text(encoding="utf-8")
    assert "twine upload" not in source
    assert "subprocess" not in source


def test_dry_run_reads_real_version(publish_pypi: ModuleType, repo_root: Path) -> None:
    version = publish_pypi._project_version(repo_root)
    assert version and all(part.isalnum() for part in version.replace(".", "").split())
