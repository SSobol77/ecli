#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/publish_pypi.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ECLI PyPI publish guard — canonical replacement for ``scripts/publish_pypi.sh``.

This tool intentionally does **not** upload anything. Publishing to PyPI for
ECLI is maintainer-owned and is performed either by
``.github/workflows/release.yml`` (job ``publish-pypi``, via OIDC + PyPI Trusted
Publishers on tag push) or by the maintainer running the documented manual
procedure in ``docs/release/release-process.md``.

Preserving the legacy semantics, the default invocation refuses to run so that
automated chains (Makefile recipes, CI hooks) cannot trigger an accidental local
publish. Two non-publishing modes are provided:

* ``--dry-run`` performs read-only structural validation (version readable,
  releases directory resolvable, any already-built distribution files match the
  expected naming) and exits ``0``. It never builds, signs, or uploads.
* ``--publish`` is the explicit, env-confirmed maintainer path. It requires
  ``ECLI_ALLOW_PUBLISH=1`` and then prints the exact manual upload procedure for
  the maintainer to run by hand. The script itself still does not upload.

Exit codes:

* ``0`` ``--dry-run`` structural validation passed
* ``1`` default guard (publish blocked) or a structural/confirmation failure
* ``2`` invalid invocation (argparse usage error)
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path


EXIT_OK = 0
EXIT_BLOCKED = 1

PUBLISH_CONFIRM_ENV = "ECLI_ALLOW_PUBLISH"

GUIDANCE = """\
ERROR: scripts/publish_pypi.py does not publish automatically.

PyPI publishing for ECLI is performed by .github/workflows/release.yml on tag
push (OIDC + PyPI Trusted Publishers). For a maintainer-side local publish,
follow the explicit procedure in docs/release/release-process.md:

  version=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
  python3 -m build --outdir "releases/${version}"
  python3 -m twine check --strict "releases/${version}"/*.whl "releases/${version}"/ecli_editor-*.tar.gz
  python3 -m twine "upload" "releases/${version}"/*.whl "releases/${version}"/ecli_editor-*.tar.gz

Re-run with --dry-run for non-publishing structural validation, or with
--publish and ECLI_ALLOW_PUBLISH=1 to print the env-confirmed manual procedure.
"""


def _project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def _dry_run(root: Path) -> int:
    """Validate publish readiness without building, signing, or uploading."""
    try:
        version = _project_version(root)
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR: cannot read [project].version: {exc}", file=sys.stderr)
        return EXIT_BLOCKED

    releases_dir = root / "releases" / version
    print(f"dry-run: project version {version}")
    print(f"dry-run: release directory releases/{version}")

    wheels = sorted(releases_dir.glob("*.whl")) if releases_dir.is_dir() else []
    sdists = (
        sorted(releases_dir.glob("ecli_editor-*.tar.gz"))
        if releases_dir.is_dir()
        else []
    )
    for artifact in (*wheels, *sdists):
        print(f"dry-run: found distribution {artifact.relative_to(root)}")
    if not wheels and not sdists:
        print(
            f"dry-run: no built distributions yet (expected under releases/{version}/)"
        )

    print("dry-run: OK (no build, sign, or upload performed)")
    return EXIT_OK


def _publish() -> int:
    """Env-confirmed maintainer path; prints the manual procedure, never uploads."""
    if os.environ.get(PUBLISH_CONFIRM_ENV) != "1":
        print(
            "ERROR: refusing --publish without explicit confirmation. "
            f"Set {PUBLISH_CONFIRM_ENV}=1 to acknowledge maintainer ownership.",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    print(GUIDANCE, file=sys.stderr)
    print(
        "Confirmation acknowledged: run the procedure above manually. "
        "This script does not upload.",
        file=sys.stderr,
    )
    return EXIT_BLOCKED


def main(argv: list[str] | None = None) -> int:
    """Run the publish guard; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="publish_pypi.py",
        description=(
            "Maintainer-owned PyPI publish guard. Does not upload. Use --dry-run "
            "for structural validation."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="non-publishing structural validation (exit 0 on success)",
    )
    mode.add_argument(
        "--publish",
        action="store_true",
        help=(
            "print the env-confirmed maintainer publish procedure "
            f"(requires {PUBLISH_CONFIRM_ENV}=1); never uploads"
        ),
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent

    if args.dry_run:
        return _dry_run(root)
    if args.publish:
        return _publish()

    print(GUIDANCE, file=sys.stderr)
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
