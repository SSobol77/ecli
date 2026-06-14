#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tools/license_guard.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""GPL-2.0-only license-header guard and verifier for ECLI.

Role
----
The ECLI tree is relicensed to GPL-2.0-only. This tool is primarily a CI gate
that *verifies* the new invariant, and secondarily can relicense or insert
headers if any straggler is found.

Modes
-----
- ``--check`` (default, no writes): report and FAIL (exit 1) on any of
    * a project-owned in-scope file missing an SPDX header,
    * an SPDX value other than GPL-2.0-only in a header (e.g. residual
      Apache-2.0, or an ambiguous/invalid form such as ``GPL-2-only``,
      ``GPL2``, ``GPLv2``, or ``GPL-2.0-or-later`` which contradicts "only"),
    * any residual ``Apache`` license token anywhere in a project-owned file
      (header or body), reported with file:line for manual correction.
- ``--apply``: insert the GPL-2.0-only short header where missing AND relicense
  Apache-2.0 header lines in the head region. Idempotent. Never edits file
  bodies or format-specific metadata tokens (those are reported, not rewritten,
  because they are format-sensitive and must stay maintainer-owned).

Contract preserved from the previous tool: shebangs, PEP 263 coding cookies,
Dockerfile ``# syntax=`` directives, YAML/TOML markers, Markdown front matter,
``set -e`` lines and module docstrings are never reordered. Stdlib only, 3.11+.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --------------------------------------------------------------------------- #
# Canonical GPL-2.0-only metadata (Option A: short, SPDX-centric).
# --------------------------------------------------------------------------- #
SPDX_ID = "GPL-2.0-only"
SPDX_LINE_TOKEN = "SPDX-License-Identifier:"
NOTE_LINE = "Licensed under the GNU General Public License version 2 only."
SEE_LINE = "See the LICENSE file in the project root for full license text."

_PROJECT = "Ecli"
_WEBSITE = "https://www.ecli.io"
_REPO = "https://github.com/SSobol77/ecli"
_PYPI = "https://pypi.org/project/ecli-editor/0.0.1/"
_COPYRIGHT = "Copyright (c) 2026 Siergej Sobolewski"

_HEAD_SCAN_LINES = 20

# Head-region relicense rewrites (old -> new), applied only in the first
# _HEAD_SCAN_LINES lines, only under --apply.
_HEAD_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"SPDX-License-Identifier:\s*Apache-2\.0"),
        f"SPDX-License-Identifier: {SPDX_ID}",
    ),
    (
        re.compile(r"Licensed under the Apache License,\s*Version 2\.0\."),
        NOTE_LINE,
    ),
    (
        re.compile(r"License:\s*Apache License,\s*Version 2\.0"),
        "License: GNU General Public License version 2 only",
    ),
)

# Invalid / contradictory SPDX forms that must fail the gate.
_INVALID_SPDX = {
    "Apache-2.0",
    "Apache 2.0",
    "Apache",
    "GPL-2-only",
    "GPL2",
    "GPLv2",
    "GPL-2.0",
    "GPL-2.0-or-later",
    "GPL-2.0+",
}

# Residual Apache license tokens (header or body or metadata) to surface.
_APACHE_TOKEN = re.compile(
    r"Apache(?:[-\s]2\.0|\s+License|\s+Software License)?",
    re.IGNORECASE,
)
_APACHE_RESIDUE_ALLOWLIST = {
    ".claude/PIPELINE.md",
    "tools/license_guard.py",
}


class Style(Enum):
    """Supported comment styles for generated headers."""

    HASH = "hash"
    HTML = "html"


@dataclass(frozen=True)
class Handler:
    """Header rendering and leading-line preservation policy for one file type."""

    name: str
    style: Style
    preserve_leading: Callable[[list[str]], int]


@dataclass
class Report:
    """Accumulated license guard findings."""

    ok: list[str] = field(default_factory=list)
    inserted: list[str] = field(default_factory=list)
    relicensed: list[str] = field(default_factory=list)
    missing_header: list[str] = field(default_factory=list)
    bad_spdx: list[tuple[str, str]] = field(default_factory=list)        # (path, value)
    apache_residue: list[tuple[str, int, str]] = field(default_factory=list)  # (path, line, text)
    skipped: list[str] = field(default_factory=list)
    exceptions: list[tuple[str, str]] = field(default_factory=list)


_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "node_modules", "dist", "build", "releases",
    ".tox", "AppDir", "_coverage", "audit-evidence", "logs",
    "ecli_github_backlog_bundle_v4_19_clean",
}
_SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".log", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".svg", ".so", ".o", ".a", ".bin", ".whl", ".tar", ".gz", ".xz", ".zip",
    ".deb", ".rpm", ".pkg", ".sha256", ".lock", ".typed",
}
_SKIP_NAMES = {
    "LICENSE", "LICENCE", "COPYING", "COPYING.txt", "uv.lock", "thirdparty.lock",
    "py.typed", "editor.log", "editorlog.txt", "progress.log",
}


def _spdx_value(head: list[str]) -> str | None:
    for line in head[:_HEAD_SCAN_LINES]:
        i = line.find(SPDX_LINE_TOKEN)
        if i != -1:
            return line[i + len(SPDX_LINE_TOKEN):].strip()
    return None


# -- leading-line preservation predicates ----------------------------------- #
def _p_python(lines: list[str]) -> int:
    keep = 1 if lines and lines[0].startswith("#!") else 0
    if keep < len(lines) and "coding:" in lines[keep] and lines[keep].lstrip().startswith("#"):
        keep += 1
    return keep


def _p_shebang(lines: list[str]) -> int:
    return 1 if lines and lines[0].startswith("#!") else 0


def _p_none(_: list[str]) -> int:
    return 0


def _p_docker(lines: list[str]) -> int:
    return 1 if lines and lines[0].lstrip().lower().startswith("# syntax=") else 0


def _p_md(lines: list[str]) -> int:
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def _p_yaml(lines: list[str]) -> int:
    return 1 if lines and lines[0].strip() == "---" else 0


def resolve_handler(path: Path) -> Handler | None:
    """Return the header handler for a project-owned file path."""
    name, suf = path.name, path.suffix.lower()
    handler: Handler | None = None
    if name == "Dockerfile" or suf == ".dockerfile" or name.endswith(".Dockerfile"):
        handler = Handler("dockerfile", Style.HASH, _p_docker)
    elif name == "Makefile" or suf == ".mk":
        handler = Handler("make", Style.HASH, _p_none)
    elif suf in (".py", ".spec"):
        handler = Handler("python", Style.HASH, _p_python)
    elif suf in (".sh", ".bash"):
        handler = Handler("bash", Style.HASH, _p_shebang)
    elif suf == ".ps1":
        handler = Handler("powershell", Style.HASH, _p_none)
    elif suf == ".md":
        handler = Handler("markdown", Style.HTML, _p_md)
    elif suf in (".yml", ".yaml"):
        handler = Handler("yaml", Style.HASH, _p_yaml)
    elif suf in (".toml", ".cfg", ".ini", ".properties", ".nix"):
        handler = Handler("conf", Style.HASH, _p_none)
    elif suf == ".desktop":
        handler = Handler("desktop", Style.HASH, _p_none)
    return handler


def render_header(style: Style, rel: str) -> str:
    """Render the canonical GPL-2.0-only header for one relative path."""
    body = [
        f"{SPDX_LINE_TOKEN} {SPDX_ID}",
        "",
        f"Project: {_PROJECT}",
        f"File: {rel}",
        f"Website: {_WEBSITE}",
        f"Repository: {_REPO}",
        f"PyPI: {_PYPI}",
        "",
        _COPYRIGHT,
        "",
        NOTE_LINE,
        SEE_LINE,
    ]
    if style is Style.HTML:
        return "<!--\n" + "\n".join(body) + "\n-->\n"
    return "\n".join("#" if b == "" else f"# {b}" for b in body) + "\n"


def _scan_apache(rel: str, lines: list[str], report: Report) -> None:
    if rel in _APACHE_RESIDUE_ALLOWLIST:
        return

    for n, line in enumerate(lines, start=1):
        if _APACHE_TOKEN.search(line):
            report.apache_residue.append((rel, n, line.strip()[:120]))


def process(path: Path, root: Path, apply: bool, report: Report) -> None:
    """Validate, and optionally update, the license header for one file."""
    rel = str(path.relative_to(root))
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        report.skipped.append(rel)
        return

    lines = text.splitlines()
    head = lines[:_HEAD_SCAN_LINES]
    spdx = _spdx_value(head)

    if spdx is not None:
        if spdx == SPDX_ID:
            _scan_apache(rel, lines, report)
            report.ok.append(rel)
            return

        if apply and spdx == "Apache-2.0":
            new_lines = list(lines)
            for i in range(min(_HEAD_SCAN_LINES, len(new_lines))):
                for pat, repl in _HEAD_REWRITES:
                    new_lines[i] = pat.sub(repl, new_lines[i])

            out = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
            path.write_text(out, encoding="utf-8")

            report.relicensed.append(rel)
            _scan_apache(rel, new_lines, report)
            return

        report.bad_spdx.append((rel, spdx))
        _scan_apache(rel, lines, report)
        return

    handler = resolve_handler(path)
    if handler is None:
        report.exceptions.append((rel, "unhandled project-owned text file"))
        _scan_apache(rel, lines, report)
        return

    if apply:
        keep = handler.preserve_leading(lines)
        leading, remainder = lines[:keep], lines[keep:]
        header = render_header(handler.style, rel).rstrip("\n")

        parts = ([("\n".join(leading))] if leading else []) + [header]
        if remainder:
            parts += ["", "\n".join(remainder)]

        out = "\n".join(parts) + ("\n" if text.endswith("\n") else "")
        path.write_text(out, encoding="utf-8")

        report.inserted.append(rel)
        _scan_apache(rel, out.splitlines(), report)
        return

    report.missing_header.append(rel)
    _scan_apache(rel, lines, report)


def walk(root: Path):
    """Yield project-owned files that are in scope for license validation."""
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in _SKIP_SUFFIXES or p.name in _SKIP_NAMES:
            continue
        if resolve_handler(p) is None:
            # Out-of-scope text (e.g. .gitignore, .json, .txt): ignore unless it
            # already carries an SPDX line we must validate.
            try:
                if _spdx_value(p.read_text(encoding="utf-8", errors="ignore").splitlines()) is None:
                    continue
            except OSError:
                continue
        yield p


def main(argv: list[str] | None = None) -> int:
    """Run the license guard CLI."""
    ap = argparse.ArgumentParser(description="ECLI GPL-2.0-only license guard.")
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Insert missing GPL-2.0-only headers and relicense Apache head lines.",
    )
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)

    root = Path(a.root).resolve()
    report = Report()
    for p in walk(root):
        process(p, root, a.apply, report)

    md = _fmt(report, applied=a.apply, root=root)
    print(md)
    if a.report:
        Path(a.report).write_text(md, encoding="utf-8")

    failed = bool(report.missing_header) or bool(report.bad_spdx) or bool(report.apache_residue)
    # In apply mode, post-write state is re-derivable by re-running --check; we
    # still return non-zero if anything could not be auto-resolved (residue).
    if a.apply:
        return 1 if report.apache_residue or report.exceptions else 0
    return 1 if failed else 0


def _fmt(r: Report, applied: bool, root: Path) -> str:
    """Format a Markdown license guard report."""
    out = [
        "# ECLI GPL-2.0-only license guard",
        "",
        f"Root: `{root}`  |  Mode: {'APPLY' if applied else 'CHECK'}  |  Target SPDX: `{SPDX_ID}`",
        "",
        f"- Compliant (GPL-2.0-only header): **{len(r.ok)}**",
        f"- Headers inserted: **{len(r.inserted)}**",
        f"- Relicensed Apache->GPL head: **{len(r.relicensed)}**",
        f"- MISSING header: **{len(r.missing_header)}**",
        f"- WRONG/invalid SPDX value: **{len(r.bad_spdx)}**",
        f"- Residual `Apache` tokens (MANUAL): **{len(r.apache_residue)}**",
        f"- Skipped/out-of-scope: **{len(r.skipped)}**",
        f"- Unhandled exceptions: **{len(r.exceptions)}**",
        "",
    ]
    if r.missing_header:
        out += ["## Missing header", *[f"- `{p}`" for p in r.missing_header], ""]
    if r.bad_spdx:
        out += [
            "## Wrong SPDX (must be GPL-2.0-only)",
            *[f"- `{p}` -> `{v}`" for p, v in r.bad_spdx],
            "",
        ]
    if r.apache_residue:
        out += [
            "## Residual Apache tokens (edit manually; do not auto-rewrite metadata/UI)",
            *[f"- `{p}:{n}`  {t}" for p, n, t in r.apache_residue],
            "",
        ]
    if r.exceptions:
        out += ["## Unhandled", *[f"- `{p}` ({why})" for p, why in r.exceptions], ""]
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
