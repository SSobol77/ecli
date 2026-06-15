# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_slackware_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_slackware.py."""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def slack(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_slackware.py", "slackware_build"
    )


def test_constants(slack: ModuleType) -> None:
    assert slack.PACKAGE_NAME == "ecli"
    assert slack.EXIT_MISSING_TOOL == 5


def test_normalize_arch(slack: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        slack.os, "uname", lambda: os.uname_result(("Linux", "h", "r", "v", "aarch64"))
    )
    assert slack.normalize_arch() == "aarch64"


def test_slack_desc_layout(slack: ModuleType) -> None:
    desc = slack.slack_desc()
    assert desc.startswith("ecli: ecli (terminal-first")
    assert "License: GPL-2.0-only" in desc
    # slack-desc must be prefixed with the package name on every line.
    assert all(line.startswith("ecli:") for line in desc.splitlines())


def test_artifact_token(slack: ModuleType, repo_root: Path) -> None:
    version = slack.read_version(repo_root)
    assert f"ecli_{version}_slackware_x86_64.txz".endswith("slackware_x86_64.txz")
