# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_toolchain_check.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the F4 toolchain availability check and ``--f4-check``."""

from __future__ import annotations

import logging

import pytest

from ecli.extensions.linters.core import toolchain_check as tc


def test_toolchain_is_exactly_nineteen_tools():
    definitions = tc.toolchain_definitions()
    assert len(definitions) == tc.TOOLCHAIN_TOTAL == 19
    executables = {definition.executable for definition in definitions}
    assert executables == tc.MANAGED_EXECUTABLES | tc.SYSTEM_EXECUTABLES


def test_managed_and_system_split_contract():
    assert len(tc.MANAGED_EXECUTABLES) == tc.MANAGED_TOOL_COUNT == 11
    assert len(tc.SYSTEM_EXECUTABLES) == tc.SYSTEM_TOOL_COUNT == 8
    assert not tc.MANAGED_EXECUTABLES & tc.SYSTEM_EXECUTABLES


def test_missing_toolchain_executables_lists_all_on_empty_path():
    missing = tc.missing_toolchain_executables(path="/nonexistent")
    assert len(missing) == 19


def test_provider_count_is_fixed_at_fourteen_not_nineteen():
    """Regression guard: the registered-provider count must never silently
    drift to equal the 19-tool toolchain count without a deliberate change
    (i.e. implementing the five missing providers).
    """
    assert tc._register_f4_providers() == 14
    assert 14 != tc.TOOLCHAIN_TOTAL


def test_no_narrative_surface_claims_nineteen_active_providers():
    """Static guard against reintroducing the "19 providers" conflation
    the codebase must never claim: 19 tools are provisioned/verified, only
    14 have a registered diagnostic provider.
    """
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    forbidden = ("19 providers", "19 active provider", "19 active F4 provider")
    surfaces = (
        repo_root / "src/ecli/extensions/linters/core/toolchain_check.py",
        repo_root / "src/ecli/__main__.py",
        repo_root / "docs/install/debian.md",
        repo_root / "scripts/build_and_package_deb.py",
        repo_root / "scripts/install_ecli_linters.py",
    )
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, f"{surface}: forbidden phrase {phrase!r}"


def test_log_toolchain_availability_never_raises(caplog):
    logger = logging.getLogger("toolchain-check-test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        tc.log_toolchain_availability(logger, path="/nonexistent")
    assert any("missing" in record.message for record in caplog.records)


@pytest.fixture
def fake_toolchain(tmp_path, monkeypatch):
    """Build a fake 11-managed / 8-system toolchain layout on disk."""
    managed_dir = tmp_path / "payload-bin"
    system_dir = tmp_path / "usr-bin"
    managed_dir.mkdir()
    system_dir.mkdir()
    for name in tc.MANAGED_EXECUTABLES:
        path = managed_dir / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    for name in tc.SYSTEM_EXECUTABLES:
        path = system_dir / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setattr(tc, "MANAGED_PATH_PREFIX", f"{managed_dir}/")
    monkeypatch.setattr(tc, "SYSTEM_PATH_PREFIXES", (f"{system_dir}/",))
    monkeypatch.setattr(tc, "_register_f4_providers", lambda: 14)
    return managed_dir, system_dir


def test_f4_check_passes_for_contract_layout(fake_toolchain, capsys):
    managed_dir, system_dir = fake_toolchain
    rc = tc.f4_check_main(path=f"{managed_dir}:{system_dir}")
    out = capsys.readouterr().out
    assert rc == 0
    assert "F4 toolchain: 19/19 executables provisioned and verified" in out
    assert "(11 managed, 8 system)" in out
    assert "F4 registered diagnostic providers: 14" in out


def test_f4_check_fails_when_tool_resolves_from_unapproved_dir(
    fake_toolchain, tmp_path, capsys
):
    managed_dir, system_dir = fake_toolchain
    rogue_dir = tmp_path / "usr-local-bin"
    rogue_dir.mkdir()
    (managed_dir / "ruff").rename(rogue_dir / "ruff")
    rc = tc.f4_check_main(path=f"{rogue_dir}:{managed_dir}:{system_dir}")
    out = capsys.readouterr().out
    assert rc == 1
    assert "[DISALLOWED]" in out
    assert "managed tool count 10 != required 11" in out


def test_f4_check_fails_on_missing_tool(fake_toolchain, capsys):
    managed_dir, system_dir = fake_toolchain
    (system_dir / "sqlfluff").unlink()
    rc = tc.f4_check_main(path=f"{managed_dir}:{system_dir}")
    out = capsys.readouterr().out
    assert rc == 1
    assert "[MISSING]" in out
    assert "Debian tool count 7 != required 8" in out


def test_f4_provider_layer_registers_fourteen_providers():
    assert tc._register_f4_providers() == 14
