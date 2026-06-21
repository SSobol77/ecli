# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/paths.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Path helpers for the deterministic extension manifest registry (#100).

These helpers locate the imported extension asset tree and resolve
contribution-relative paths **safely**, guaranteeing that every resolved path
stays under ``src/ecli/extensions/``. They never read, execute, or import any
extension asset; they only compute and validate filesystem locations.
"""

from __future__ import annotations

from pathlib import Path


# Logical repository-relative prefix for the imported extension tree. This is a
# stable identifier used in diagnostics and contribution records; it does not
# depend on where the package is installed at runtime.
REPO_RELATIVE_PREFIX = "src/ecli/extensions"


def extensions_root() -> Path:
    """Return the absolute path to the imported ``ecli/extensions`` asset tree.

    ``paths.py`` lives at ``ecli/extensions/ecli_integration/paths.py``, so the
    asset tree root is this file's grandparent directory. This works both in a
    source checkout and inside an installed wheel.
    """
    return Path(__file__).resolve().parent.parent


def to_repo_relative(path: Path, root: Path | None = None) -> str:
    """Return ``path`` as a logical ``src/ecli/extensions/...`` POSIX string.

    The returned value is a stable, install-location-independent identifier
    suitable for diagnostics and contribution records.
    """
    base = (root or extensions_root()).resolve()
    relative = path.resolve().relative_to(base).as_posix()
    return (
        f"{REPO_RELATIVE_PREFIX}/{relative}"
        if relative != "."
        else REPO_RELATIVE_PREFIX
    )


def is_within_root(path: Path, root: Path | None = None) -> bool:
    """Return ``True`` if ``path`` resolves to a location under ``root``."""
    base = (root or extensions_root()).resolve()
    resolved = path.resolve()
    return resolved == base or resolved.is_relative_to(base)


def resolve_contribution_path(
    base_dir: Path, relative: str, root: Path | None = None
) -> Path | None:
    """Resolve a manifest-relative contribution path, rejecting traversal.

    ``relative`` is a path declared inside a ``package.json`` contribution (for
    example ``./syntaxes/batchfile.tmLanguage.json``). The result is resolved
    against ``base_dir`` (the manifest's own directory) and returned only if it
    stays under the imported extension tree root. Any path that escapes the tree
    (via ``..`` or an absolute path) yields ``None`` so the caller can record a
    diagnostic instead of touching a file outside the tree.
    """
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (base_dir / relative).resolve()
    return candidate if is_within_root(candidate, root) else None
