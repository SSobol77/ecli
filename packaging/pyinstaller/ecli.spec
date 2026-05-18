# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: packaging/pyinstaller/ecli.spec
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""PyInstaller specification for ECLI release artifacts."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(os.environ.get("ECLI_REPO_ROOT", os.getcwd())).resolve()
entry_point = project_root / "main.py"
src_dir = project_root / "src"
config_file = project_root / "config.toml"
pyproject_file = project_root / "pyproject.toml"
asset_icon = src_dir / "ecli" / "assets" / "ecli.png"
windows_icon = project_root / "img" / "logo_m.ico"

if not entry_point.is_file():
    raise SystemExit(f"Missing PyInstaller entry point: {entry_point}")
if not config_file.is_file():
    raise SystemExit(f"Missing PyInstaller data file: {config_file}")
if not pyproject_file.is_file():
    raise SystemExit(f"Missing PyInstaller metadata file: {pyproject_file}")
if not asset_icon.is_file():
    raise SystemExit(f"Missing packaged icon asset: {asset_icon}")

one_dir = os.environ.get("ECLI_PYINSTALLER_ONEDIR") == "1"
build_macos_app = (
    sys.platform == "darwin" and os.environ.get("ECLI_BUILD_MACOS_APP") == "1"
)
strip_binaries = sys.platform != "win32"

datas = [
    (str(config_file), "."),
    (str(pyproject_file), "."),
    (str(asset_icon), "ecli/assets"),
]
binaries = []
exe_icon_kwargs = (
    {"icon": str(windows_icon)}
    if sys.platform == "win32" and windows_icon.is_file()
    else {}
)

hiddenimports = [
    "ecli",
    "dotenv",
    "toml",
    "yaml",
    "aiohttp",
    "aiosignal",
    "yarl",
    "multidict",
    "frozenlist",
    "pyperclip",
    "pygments",
    "chardet",
    "wcwidth",
]

for package in (
    "pygments.lexers",
    "pygments.formatters",
    "chardet",
    "wcwidth",
):
    hiddenimports.extend(collect_submodules(package))

hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(entry_point)],
    pathex=[str(src_dir), str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging/pyinstaller/rthooks/force_imports.py")],
    excludes=["tkinter", "test", "unittest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

if one_dir or build_macos_app:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="ecli",
        debug=False,
        bootloader_ignore_signals=False,
        strip=strip_binaries,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        **exe_icon_kwargs,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=strip_binaries,
        upx=True,
        upx_exclude=[],
        name="ecli",
    )
    if build_macos_app:
        app = BUNDLE(
            coll,
            name="dist/ECLI.app",
            bundle_identifier="io.ecli.editor",
            info_plist={
                "CFBundleName": "ECLI",
                "CFBundleDisplayName": "ECLI",
                "CFBundleExecutable": "ecli",
                "CFBundlePackageType": "APPL",
                "LSMinimumSystemVersion": "12.0",
                "NSHighResolutionCapable": True,
            },
        )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="ecli",
        debug=False,
        bootloader_ignore_signals=False,
        strip=strip_binaries,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        **exe_icon_kwargs,
    )
