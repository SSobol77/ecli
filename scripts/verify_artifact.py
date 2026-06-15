#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/verify_artifact.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Verify a release artifact against its basename-only SHA256 sidecar.

This is the canonical Python replacement for the legacy
``scripts/verify-artifact.sh`` shell verifier. It is a structural, local,
read-only check: it never publishes, uploads, signs, tags, pushes, or mutates
any tracked file.

The verifier expects the sidecar at ``<artifact>.sha256`` using coreutils
basename-only format on its first line::

    <64 lowercase hex characters>  <artifact basename>

Exit-code contract (stable; CI logic branches on these values):

* ``0`` artifact verified
* ``1`` invalid invocation or malformed checksum sidecar
* ``2`` artifact missing
* ``3`` checksum sidecar missing
* ``4`` checksum mismatch
* ``5`` missing SHA256 verification tool (retained for contract compatibility;
  the standard-library ``hashlib`` implementation never reaches this state)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_ARTIFACT_MISSING = 2
EXIT_SIDECAR_MISSING = 3
EXIT_MISMATCH = 4
EXIT_NO_TOOL = 5

SIDECAR_SUFFIX = ".sha256"
_READ_CHUNK = 1024 * 1024
_HEX_DIGITS = frozenset("0123456789abcdef")


class _ContractArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that maps usage errors to the exit-1 invocation contract."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_digest(sidecar: Path, artifact_basename: str) -> str | None:
    """Return the expected lowercase hex digest, or ``None`` if malformed.

    The sidecar must be basename-only coreutils format; the recorded name on the
    first line must equal ``artifact_basename`` and the digest must be 64 hex
    characters.
    """
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    digest, separator, recorded_name = lines[0].partition("  ")
    if not separator or recorded_name != artifact_basename:
        return None
    digest = digest.strip().lower()
    if len(digest) != 64 or any(character not in _HEX_DIGITS for character in digest):
        return None
    return digest


def main(argv: list[str] | None = None) -> int:
    """Verify one artifact against its SHA256 sidecar; return the exit code."""
    parser = _ContractArgumentParser(
        prog="verify_artifact.py",
        description="Verify an artifact against its basename-only SHA256 sidecar.",
    )
    parser.add_argument("artifact", help="path to the artifact to verify")
    args = parser.parse_args(argv)

    artifact = Path(args.artifact)
    sidecar = Path(f"{artifact}{SIDECAR_SUFFIX}")

    if not artifact.is_file():
        print(f"Missing {artifact}")
        return EXIT_ARTIFACT_MISSING

    if not sidecar.is_file():
        print(f"Missing {sidecar}")
        return EXIT_SIDECAR_MISSING

    expected = _expected_digest(sidecar, artifact.name)
    if expected is None:
        print(f"Malformed checksum sidecar: {sidecar}")
        return EXIT_INVALID

    if _sha256(artifact) != expected:
        print(f"checksum mismatch: {artifact}")
        return EXIT_MISMATCH

    print(f"{artifact.name}: OK")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
