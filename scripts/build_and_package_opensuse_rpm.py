#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_opensuse_rpm.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build an openSUSE/SUSE-oriented RPM using the shared RPM packaging flow.

Canonical Python replacement for ``scripts/build-and-package-opensuse-rpm.sh``.
It defaults the openSUSE platform label and runtime dependencies (honoring any
pre-set values) and delegates to ``scripts/build_and_package_rpm.py``, producing
``releases/<version>/ecli_<version>_opensuse_<arch>.rpm``.

This script orchestrates the local packaging toolchain only. It never publishes,
uploads, signs with external keys, tags, pushes, or triggers any workflow.

Exit codes: propagated from ``scripts/build_and_package_rpm.py``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Delegate to the shared RPM flow with openSUSE defaults."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_opensuse_rpm.py",
        description="Build an openSUSE/SUSE RPM via the shared RPM flow.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    child_env = {**os.environ}
    child_env.setdefault("RPM_PLATFORM_LABEL", "opensuse")
    child_env.setdefault("RPM_DEPENDS", "libncurses6;libyaml-0-2")
    child_env.setdefault("ECLI_F4_LINTER_ARTIFACT_ID", "opensuse-rpm")

    return subprocess.run(
        [sys.executable, str(root / "scripts" / "build_and_package_rpm.py")],
        env=child_env,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
