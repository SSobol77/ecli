#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/check_log_invariant.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Fail if generated development artifacts are written outside ``logs/``.

This is the canonical Python replacement for the legacy
``scripts/check-log-invariant.sh``. It is read-only: it inspects the git index
and working tree through ``git ls-files`` and never mutates the repository.

Exit codes:

* ``0`` the development log invariant is satisfied
* ``1`` a generated/runtime artifact was found outside ``logs/``
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path


# Generated artifact globs (matched against the full repo-relative path; ``*``
# spans path separators, mirroring the original shell ``case`` semantics).
GENERATED_ARTIFACT_GLOBS = (
    "*.log",
    "*.log.*",
    "*.trace",
    "*.dump",
    "*.tmp",
    "*.pid",
    "*.sock",
)

# Top-level untracked evidence/scratch prefixes that must never escape ``logs/``.
UNTRACKED_PREFIX_GLOBS = (
    "dry-run-*",
    "test-evidence-*",
    "smoke-output-*",
    "agent-debug-*",
)

# Forbidden runtime/cache locations for untracked artifacts.
FORBIDDEN_RUNTIME_GLOBS = (
    ".ecli/*",
    ".ecli/vmlab/*",
    "tmp/*",
    ".tmp/*",
    ".cache/*",
)

# Tracked files allowed to live directly under ``logs/``.
TRACKED_LOG_ALLOWLIST = frozenset({"logs/.gitkeep", "logs/README-logs.md"})


def _matches_any(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, glob) for glob in globs)


def _git_lines(args: list[str], cwd: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _check_untracked_generated(paths: list[str], failures: list[str]) -> None:
    for path in paths:
        if path.startswith("logs/"):
            continue
        if _matches_any(path, GENERATED_ARTIFACT_GLOBS) or _matches_any(
            path, UNTRACKED_PREFIX_GLOBS
        ):
            failures.append(
                f"ERROR: untracked generated artifact outside logs/: {path}"
            )


def _check_tracked_generated(paths: list[str], failures: list[str]) -> None:
    for path in paths:
        if path in TRACKED_LOG_ALLOWLIST or path.startswith("logs/"):
            continue
        if _matches_any(path, GENERATED_ARTIFACT_GLOBS):
            failures.append(f"ERROR: tracked generated artifact outside logs/: {path}")


def _check_forbidden_runtime(paths: list[str], failures: list[str]) -> None:
    for path in paths:
        if _matches_any(path, FORBIDDEN_RUNTIME_GLOBS):
            failures.append(
                f"ERROR: generated/runtime artifact in forbidden location: {path}"
            )


def main(argv: list[str] | None = None) -> int:
    """Validate the development log invariant; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="check_log_invariant.py",
        description="Fail if generated development artifacts exist outside logs/.",
    )
    parser.parse_args(argv)

    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: cannot determine git repository root: {exc}", file=sys.stderr)
        return 1

    root = Path(toplevel)
    failures: list[str] = []

    untracked = _git_lines(["ls-files", "--others", "--exclude-standard"], root)
    tracked = _git_lines(["ls-files"], root)

    _check_untracked_generated(untracked, failures)
    _check_tracked_generated(tracked, failures)
    _check_forbidden_runtime(untracked, failures)

    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        print(
            "\nDevelopment artifacts must be written only under logs/.",
            file=sys.stderr,
        )
        return 1

    print("OK: development log invariant satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
