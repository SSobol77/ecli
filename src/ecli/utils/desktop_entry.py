# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/utils/desktop_entry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""User-level Linux desktop-entry installer for PyPI/pipx installs."""

from __future__ import annotations

import shutil
import sys
from importlib import resources
from pathlib import Path

from ecli.utils.resources import get_icon_path


DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=ECLI
Comment=Terminal-first engineering operations workbench
Exec=ecli
Icon=ecli
Terminal=true
Categories=Development;IDE;Utility;
StartupNotify=false
"""


def install_linux_desktop_entry() -> tuple[Path, Path]:
    """Install or replace the current user's ECLI launcher and icon."""
    home = Path.home()
    applications_dir = home / ".local" / "share" / "applications"
    icon_dir = home / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    desktop_file = applications_dir / "ecli.desktop"
    icon_file = icon_dir / "ecli.png"

    applications_dir.mkdir(parents=True, exist_ok=True)
    icon_dir.mkdir(parents=True, exist_ok=True)

    with resources.as_file(get_icon_path()) as packaged_icon:
        shutil.copyfile(packaged_icon, icon_file)
    desktop_file.write_text(DESKTOP_ENTRY, encoding="utf-8", newline="\n")

    return desktop_file, icon_file


def main() -> int:
    """Console-script entry point."""
    if not sys.platform.startswith("linux"):
        print(
            "ECLI desktop launcher installation is handled by native platform "
            "packages or installers on this operating system."
        )
        return 0

    desktop_file, icon_file = install_linux_desktop_entry()
    print("Installed ECLI desktop launcher:")
    print(f"  desktop entry: {desktop_file}")
    print(f"  icon: {icon_file}")
    print("This command is idempotent and safe to run again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
