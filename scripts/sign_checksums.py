#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/sign_checksums.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Write coreutils basename-only SHA256 checksum sidecars for release artifacts.

This is the canonical Python implementation that replaces the legacy
``scripts/sign_checksums.sh`` stub. For each artifact path it computes the
SHA256 digest and writes a sidecar at ``<artifact>.sha256`` containing one line
in coreutils basename-only format::

    <64 lowercase hex characters>  <artifact basename>

The sidecars produced here satisfy the checksum requirement in
``docs/release/artifact-contract.md`` and are the inputs verified by
``scripts/verify_artifact.py``.

Scope: this tool produces SHA256 checksum sidecars only. It does NOT create
GPG or otherwise detached cryptographic signatures, and it never publishes,
uploads, tags, pushes, or triggers any release action.

Exit codes:

* ``0`` all requested sidecars were written
* ``1`` a requested artifact is missing
* ``2`` invalid invocation (argparse usage error)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_MISSING_ARTIFACT = 1

SIDECAR_SUFFIX = ".sha256"
_READ_CHUNK = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    """Write a SHA256 sidecar for each artifact; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="sign_checksums.py",
        description=(
            "Write basename-only SHA256 checksum sidecars (<artifact>.sha256) "
            "for the given release artifacts."
        ),
    )
    parser.add_argument(
        "artifacts",
        nargs="+",
        help="artifact file paths to checksum",
    )
    args = parser.parse_args(argv)

    missing = [raw for raw in args.artifacts if not Path(raw).is_file()]
    if missing:
        for raw in missing:
            print(f"Missing artifact: {raw}", file=sys.stderr)
        return EXIT_MISSING_ARTIFACT

    for raw in args.artifacts:
        artifact = Path(raw)
        sidecar = Path(f"{artifact}{SIDECAR_SUFFIX}")
        sidecar.write_text(f"{_sha256(artifact)}  {artifact.name}\n", encoding="utf-8")
        print(f"{sidecar}")

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
