"""Display helpers for diagnostics UI surfaces."""

from __future__ import annotations

import os
from pathlib import Path


def diagnostic_display_path(
    file_path: str | None,
    *,
    project_root: str | os.PathLike[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> str:
    """Return a stable user-facing path for diagnostics.

    Absolute provider paths are reduced to a project-relative path when possible.
    If the file is outside the known roots, the basename is used so diagnostics
    rows never start with a terminal-width-consuming absolute path.
    """
    if not file_path:
        return "<buffer>"

    raw_path = str(file_path)
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        return _normalize_separator(raw_path)

    for root in _candidate_roots(project_root=project_root, cwd=cwd):
        relative = _relative_under_root(path, root)
        if relative is not None:
            return _normalize_separator(relative)

    return path.name or raw_path


def truncate_middle(text: str, max_width: int) -> str:
    """Truncate text in the middle using ASCII dots."""
    if max_width <= 0:
        return ""
    if len(text) <= max_width:
        return text
    if max_width <= 3:
        return text[:max_width]
    keep = max_width - 3
    left = max(1, keep // 2)
    right = max(1, keep - left)
    return f"{text[:left]}...{text[-right:]}"


def truncate_end(text: str, max_width: int) -> str:
    """Truncate text at the end using ASCII dots."""
    if max_width <= 0:
        return ""
    if len(text) <= max_width:
        return text
    if max_width <= 3:
        return text[:max_width]
    return f"{text[: max_width - 3]}..."


def _candidate_roots(
    *,
    project_root: str | os.PathLike[str] | None,
    cwd: str | os.PathLike[str] | None,
) -> tuple[Path, ...]:
    roots: list[Path] = []
    if project_root:
        roots.append(Path(project_root).expanduser())
    roots.append(Path(cwd).expanduser() if cwd else Path.cwd())

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        root_abs = Path(os.path.abspath(os.fspath(root)))
        key = os.fspath(root_abs)
        if key not in seen:
            seen.add(key)
            unique.append(root_abs)
    return tuple(unique)


def _relative_under_root(path: Path, root: Path) -> str | None:
    try:
        relative = os.path.relpath(os.fspath(path), os.fspath(root))
    except ValueError:
        return None
    if relative == ".":
        return path.name
    if relative == ".." or relative.startswith(f"..{os.sep}"):
        return None
    return relative


def _normalize_separator(path: str) -> str:
    return path.replace(os.sep, "/").replace("\\", "/")
