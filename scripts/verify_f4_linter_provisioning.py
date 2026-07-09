#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/verify_f4_linter_provisioning.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Verify F4 linter provisioning evidence.

The verifier enforces the canonical 21-entry artifact matrix for release-level
checks. GitHub-generated ``Source code (zip)`` and ``Source code (tar.gz)``
archives are ignored because they are not ECLI-owned artifact contract entries.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecli.extensions.linters.core.provisioning import (  # noqa: E402
    verify_evidence_dir,
)


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_CONTRACT_FAILED = 2


class _ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractArgumentParser(
        prog="verify_f4_linter_provisioning.py",
        description="Verify F4 linter provisioning evidence.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--artifact", help="canonical artifact entry id, e.g. deb")
    target.add_argument(
        "--all-artifacts",
        action="store_true",
        help="verify all 21 canonical artifact entries",
    )
    parser.add_argument("--evidence-dir", required=True, help="evidence directory")
    parser.add_argument("--json", action="store_true", help="print JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = verify_evidence_dir(
        Path(args.evidence_dir),
        artifact_entry_id=args.artifact,
        all_artifacts=args.all_artifacts,
    )
    if args.json:
        print(
            json.dumps(
                {"ok": not errors, "errors": errors},
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        target = "all 21 artifacts" if args.all_artifacts else args.artifact
        print(f"PASS: F4 linter provisioning evidence verified for {target}")
    return EXIT_CONTRACT_FAILED if errors else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
