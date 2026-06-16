# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_freebsd_port_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_freebsd_port.py (no real ports build)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def port(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_freebsd_port.py", "freebsd_port"
    )


def test_non_freebsd_returns_error(
    port: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(port.platform, "system", lambda: "Linux")
    assert port.main([]) == port.EXIT_ERROR


def test_port_makefile_structure(port: ModuleType) -> None:
    dist_dir = Path("/repo/build/freebsd_port_distfiles")
    makefile = port.port_makefile("4.5.6", dist_dir)
    assert "DISTVERSION=    4.5.6" in makefile
    assert "MASTER_SITES=   file:///repo/build/freebsd_port_distfiles/" in makefile
    # Recipe lines must be tab-indented for make to accept them.
    assert (
        "\t@cd ${WRKSRC} && python3.11 ./scripts/build_and_package_freebsd.py"
        in makefile
    )
    assert "do-build:" in makefile
    assert "do-install:" in makefile
    assert "PLIST_FILES= \\" in makefile
    assert "\tbin/ecli \\" in makefile


def test_pkg_descr_and_host_deps(port: ModuleType) -> None:
    assert "ECLI is a fast terminal-first code editor" in port.PKG_DESCR
    assert "python311" in port.HOST_DEPS


def test_normalize_arch(port: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr(
        port.normalize_arch.__globals__["os"],
        "uname",
        lambda: os.uname_result(("FreeBSD", "h", "r", "v", "amd64")),
    )
    assert port.normalize_arch() == "x86_64"
