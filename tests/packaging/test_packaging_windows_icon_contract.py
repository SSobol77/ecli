# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_windows_icon_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Windows application-icon packaging contract (issue #93).

These regression checks lock the Windows icon wiring so the portable ``.exe`` and
the NSIS installer always embed the real ECLI Windows icon (``img/logo_m.ico``)
rather than the raw ``img/logo_m.png`` bitmap, which Windows cannot use directly
as an executable or installer icon.

The checks are deliberately source-only: ``releases/`` is git-ignored, so the
contract is asserted against tracked packaging surfaces (PyInstaller spec, NSIS
script, the Windows PowerShell packager, and the release workflow) plus the
canonical asset generator -- never against transient release staging.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, TokenAssertion, load_script_module


# Tracked authoritative Windows icon, derived from the ECLI logo source.
WINDOWS_ICON = "img/logo_m.ico"
# Raw bitmap that must never be used directly as the Windows exe/installer icon.
RAW_LOGO_PNG = "logo_m.png"
# Standard little-endian ICONDIR header for a real Windows ``.ico`` resource.
ICO_MAGIC = b"\x00\x00\x01\x00"

SPEC = "packaging/pyinstaller/ecli.spec"
NSI = "packaging/windows/nsis/ecli.nsi"
PS1 = "scripts/build-and-package-windows.ps1"
RELEASE_WORKFLOW = ".github/workflows/release.yml"
WINDOWS_WORKFLOW = ".github/workflows/windows-installer.yml"

WINDOWS_PORTABLE_TOKEN = "15_windows_portable__ecli_{v}_win_x86_64.exe"
WINDOWS_NSIS_TOKEN = "16_windows_nsis__ecli_{v}_win_x86_64_setup.exe"


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


# --------------------------------------------------------------------------- #
# Icon source asset integrity.
# --------------------------------------------------------------------------- #


def test_windows_icon_source_is_a_real_ico_resource(repo_root: Path) -> None:
    icon = repo_root / WINDOWS_ICON
    assert icon.is_file(), f"missing tracked Windows icon source: {WINDOWS_ICON}"

    data = icon.read_bytes()
    assert data, f"empty Windows icon source: {WINDOWS_ICON}"
    # Guard against a renamed PNG masquerading as an ``.ico``: a genuine icon
    # resource starts with the ICONDIR magic, while a PNG starts with \x89PNG.
    assert data.startswith(ICO_MAGIC), (
        f"{WINDOWS_ICON} is not a real Windows ICO resource (bad ICONDIR header)"
    )
    assert not data.startswith(b"\x89PNG"), (
        f"{WINDOWS_ICON} appears to be a renamed PNG, not an ICO resource"
    )


# --------------------------------------------------------------------------- #
# 1. PyInstaller (portable .exe) embeds the expected .ico.
# --------------------------------------------------------------------------- #


def test_pyinstaller_spec_embeds_windows_ico(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    spec = read_repo_text(SPEC)

    assert_tokens_present(
        spec,
        (
            'windows_icon = project_root / "img" / "logo_m.ico"',
            '{"icon": str(windows_icon)}',
            'sys.platform == "win32" and windows_icon.is_file()',
            "**exe_icon_kwargs",
        ),
    )
    # The Windows exe icon must be the derived .ico, never the raw PNG bitmap.
    assert RAW_LOGO_PNG not in spec, (
        "PyInstaller spec must not reference logo_m.png as the Windows exe icon"
    )
    assert '"icon": str(asset_icon)' not in spec, (
        "PyInstaller spec must not use the packaged ecli.png as the exe icon"
    )


# --------------------------------------------------------------------------- #
# 2. NSIS installer references the expected .ico for every icon surface.
# --------------------------------------------------------------------------- #


def test_nsis_script_wires_ico_for_installer_and_uninstaller(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    nsi = read_repo_text(NSI)

    assert_tokens_present(
        nsi,
        (
            "ICON_ICO",
            'Icon "${ICON_ICO}"',  # installer executable icon
            '!define MUI_ICON "${ICON_ICO}"',  # installer wizard icon
            '!define MUI_UNICON "${ICON_ICO}"',  # uninstaller wizard icon
        ),
    )
    # Add/Remove Programs (DisplayIcon) and the Start Menu shortcut both resolve
    # to the installed ecli.exe, which carries the PyInstaller-embedded icon.
    assert r'"DisplayIcon" "$INSTDIR\ecli.exe"' in nsi, (
        "NSIS DisplayIcon must point at the installed ecli.exe"
    )
    assert "CreateShortCut" in nsi and r'"$INSTDIR\ecli.exe"' in nsi, (
        "NSIS Start Menu shortcut must target the installed ecli.exe"
    )


def test_windows_packager_passes_ico_define_to_nsis(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    ps1 = read_repo_text(PS1)

    assert_tokens_present(
        ps1,
        (
            r'$iconPath = Join-Path $projectRoot "img\logo_m.ico"',
            "if (Test-Path -LiteralPath $iconPath) {",
            "/DICON_ICO=$iconPath",
        ),
    )


# --------------------------------------------------------------------------- #
# 3. logo_m.png is never used directly as a Windows exe/installer icon.
# --------------------------------------------------------------------------- #


def test_logo_png_is_not_used_as_windows_icon(read_repo_text: RepoReader) -> None:
    nsi = read_repo_text(NSI)
    ps1 = read_repo_text(PS1)

    assert RAW_LOGO_PNG not in nsi, (
        "NSIS installer must not reference logo_m.png as an icon"
    )
    assert RAW_LOGO_PNG not in ps1, (
        "Windows packager must not pass logo_m.png as the NSIS icon define"
    )


# --------------------------------------------------------------------------- #
# 4. Windows workflow still produces both canonical Windows assets.
# --------------------------------------------------------------------------- #


def test_release_workflow_still_produces_both_windows_assets(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    release_workflow = read_repo_text(RELEASE_WORKFLOW)
    windows_workflow = read_repo_text(WINDOWS_WORKFLOW)
    ps1 = read_repo_text(PS1)

    assert_tokens_present(
        release_workflow,
        (
            WINDOWS_PORTABLE_TOKEN.format(v="${version}"),
            WINDOWS_NSIS_TOKEN.format(v="${version}"),
        ),
    )
    assert "scripts/build-and-package-windows.ps1" in windows_workflow, (
        "Windows workflow must build through the canonical PowerShell packager"
    )
    assert_tokens_present(
        ps1,
        (
            "ecli_${version}_win_${winArch}.exe",
            "ecli_${version}_win_${winArch}_setup.exe",
        ),
    )


# --------------------------------------------------------------------------- #
# 5. The exact-21 release contract is unchanged by the icon wiring.
# --------------------------------------------------------------------------- #


def test_exact_twenty_one_contract_still_includes_windows_assets(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names("0.2.3")

    assert len(names) == 21
    assert len(set(names)) == 21
    assert WINDOWS_PORTABLE_TOKEN.format(v="0.2.3") in names
    assert WINDOWS_NSIS_TOKEN.format(v="0.2.3") in names


# --------------------------------------------------------------------------- #
# 6. The top-level .sha256 policy remains enforced for Windows assets.
# --------------------------------------------------------------------------- #


def test_top_level_windows_sha256_sidecar_is_rejected(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    for name in names:
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    (tmp_path / ".checksums").mkdir()

    windows_portable = WINDOWS_NSIS_TOKEN.format(v="1.2.3")
    (tmp_path / f"{windows_portable}.sha256").write_text(
        "0" * 64 + f"  {windows_portable}\n", encoding="utf-8"
    )

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )
