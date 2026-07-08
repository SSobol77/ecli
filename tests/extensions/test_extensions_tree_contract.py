# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extensions_tree_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the curated ECLI Extensions Layer asset tree.

``src/ecli/extensions/`` is a small, curated runtime asset bundle, not a vendored
copy of full VS Code extension source repositories. Its root contains only:

* ``ecli_integration/`` — ECLI-owned Python adapter code;
* ``linters/`` — ECLI-owned F4 linter microservices Python package (see
  ``docs/architecture/ecli-f4-linter-microservices-design.md``); each linter
  is its own microservice directory with a ``manifest.py`` and
  ``package_contract.py``, and (for Ruff only, in this migration) a working
  ``provider.py``. Raw upstream linter runtime source (VS Code TypeScript or
  otherwise) is never permitted here -- only ECLI-authored Python;
* ``lang/`` — imported language/runtime declarative extension assets, one folder
  per language or language bundle;
* ``themes/`` — imported colour-theme extension assets, one folder per theme
  bundle;
* ``THIRD_PARTY_NOTICES.md`` — legal attribution for retained upstream assets;
* optionally ``README.md`` documenting the bundle.

Imported folders under ``lang/`` and ``themes/`` may retain only inert
declarative assets consumed by ECLI's adapters: package manifests / NLS tables,
TextMate grammars, themes, snippets, language-configuration metadata, and legal
attribution files. Development artifacts, Node build inputs, tests, media/demo
assets, generated output, and extension activation/runtime source are forbidden.

These are read-only tree assertions. They never modify the imported tree.
"""

from __future__ import annotations

import subprocess
from fnmatch import fnmatch
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS_ROOT = REPO_ROOT / "src" / "ecli" / "extensions"

# Curated asset groups that hold imported declarative extension folders.
ASSET_GROUP_DIRS: tuple[str, ...] = ("lang", "themes")

# The only entries permitted directly under ``src/ecli/extensions/``.
ALLOWED_ROOT_ENTRIES = frozenset(
    {
        "ecli_integration",
        "linters",
        "lang",
        "themes",
        "THIRD_PARTY_NOTICES.md",
        "README.md",
    }
)

# Extensions-root Python packages that hold ECLI-owned runtime code, not
# imported upstream declarative assets. Any file type is permitted inside
# these; everything else under the root is asset-group-only (lang/, themes/).
ECLI_OWNED_RUNTIME_PACKAGES = frozenset({"ecli_integration", "linters"})


# Representative imported assets that must exist verbatim in the tree, expressed
# relative to ``src/ecli/extensions/``. If any path ever differs from the
# imported upstream layout, fix the path here -- never rename the upstream file.
REPRESENTATIVE_ASSETS: tuple[str, ...] = (
    "lang/bat/package.json",
    "lang/bat/language-configuration.json",
    "lang/bat/syntaxes/batchfile.tmLanguage.json",
    "lang/bat/snippets/batchfile.code-snippets",
    "lang/git-base/languages/ignore.language-configuration.json",
    "lang/python/package.json",
    "lang/python/language-configuration.json",
    "lang/json/package.json",
    "lang/javascript/package.json",
    "lang/markdown-basics/package.json",
    "lang/cpp/package.json",
    "themes/defaults/themes/dark_plus.json",
)

# Paths that must NOT exist under the extensions root: a nested
# ``extensions/extensions/`` directory, the upstream structure note, a generated
# inventory file, removed runtime-only extensions, and any flat (pre-normalized)
# language/theme folder that should now live under ``lang/`` or ``themes/``.
FORBIDDEN_PATHS: tuple[str, ...] = (
    "extensions",
    "EXTENSIONS_FOLDER-structure.md",
    "src-ecli-extensions.txt",
    # removed VS Code UI/runtime-only or non-declarative extensions
    "notebook-renderers",
    "references-view",
    "copilot",
    "npm",
    "configuration-editing",
    "extension-editing",
    # flat (un-normalized) folders that must now live under lang/ or themes/
    "python",
    "json",
    "cpp",
    "git-base",
    "theme-defaults",
    "theme-monokai",
)

FORBIDDEN_FILE_PATTERNS: tuple[str, ...] = (
    ".vscodeignore",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig*.json",
    "esbuild*.mts",
    "webpack.config.*",
    "rollup.config.*",
)

FORBIDDEN_DIR_NAMES = frozenset(
    {
        ".github",
        ".vscode",
        "demo",
        "demos",
        "dist",
        "media",
        "node_modules",
        "out",
        "screenshots",
        "src",
        "test",
        "tests",
    }
)

FORBIDDEN_SOURCE_SUFFIXES = frozenset({".js", ".mjs", ".ts", ".tsx"})

# Files permitted at the root of an imported folder (``lang/<x>`` or
# ``themes/<x>``) and at the extensions tree root.
TOP_LEVEL_FILE_PATTERNS: tuple[str, ...] = (
    "package.json",
    "package.nls.json",
    "package.nls.*.json",
    "*language-configuration*.json",
    "LICENSE*",
    "NOTICE*",
    "THIRD_PARTY_NOTICES*",
    "README.md",
)

# Files permitted inside a named asset subdirectory of an imported folder.
ASSET_DIR_FILE_PATTERNS: dict[str, tuple[str, ...]] = {
    "languages": ("*language-configuration*.json",),
    "snippets": ("*.code-snippets",),
    "syntaxes": ("*.tmLanguage", "*.tmLanguage.json"),
    "themes": ("*.json",),
}


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(name, pattern) for pattern in patterns)


def _is_ecli_integration(relative: Path) -> bool:
    return bool(relative.parts) and relative.parts[0] == "ecli_integration"


def test_extensions_root_exists() -> None:
    assert EXTENSIONS_ROOT.is_dir(), (
        f"imported extensions root missing: {EXTENSIONS_ROOT}"
    )


def test_root_contains_only_allowed_entries() -> None:
    """The tree root must be small: only ecli_integration, lang, themes, notices."""
    entries = {child.name for child in EXTENSIONS_ROOT.iterdir()}
    unexpected = sorted(entries - ALLOWED_ROOT_ENTRIES)
    assert unexpected == [], (
        f"unexpected entries at extensions root (only {sorted(ALLOWED_ROOT_ENTRIES)} "
        f"allowed): {unexpected}"
    )
    for required in ("ecli_integration", "linters", "lang", "themes"):
        assert (EXTENSIONS_ROOT / required).is_dir(), f"missing root dir: {required}"


def test_no_flat_language_or_theme_folders_at_root() -> None:
    """No ``theme-*`` or bare language extension folders may sit at the root."""
    offenders = [
        child.name
        for child in EXTENSIONS_ROOT.iterdir()
        if child.is_dir() and child.name not in ALLOWED_ROOT_ENTRIES
    ]
    assert offenders == [], (
        f"flat extension folders must move under lang/ or themes/: {offenders}"
    )


@pytest.mark.parametrize("relative_path", REPRESENTATIVE_ASSETS)
def test_representative_asset_exists(relative_path: str) -> None:
    asset = EXTENSIONS_ROOT / relative_path
    assert asset.is_file(), (
        f"imported extension asset missing: src/ecli/extensions/{relative_path}"
    )
    assert asset.stat().st_size > 0, (
        f"imported extension asset is empty: src/ecli/extensions/{relative_path}"
    )


@pytest.mark.parametrize("relative_path", FORBIDDEN_PATHS)
def test_forbidden_path_absent(relative_path: str) -> None:
    forbidden = EXTENSIONS_ROOT / relative_path
    assert not forbidden.exists(), (
        f"unexpected path present under extensions root: "
        f"src/ecli/extensions/{relative_path}"
    )


def test_every_lang_folder_has_a_manifest() -> None:
    lang_dir = EXTENSIONS_ROOT / "lang"
    missing = [
        child.name
        for child in lang_dir.iterdir()
        if child.is_dir() and not (child / "package.json").is_file()
    ]
    assert missing == [], f"lang folders missing package.json: {missing}"
    assert any(child.is_dir() for child in lang_dir.iterdir()), "lang/ is empty"


def test_every_theme_folder_has_a_manifest() -> None:
    themes_dir = EXTENSIONS_ROOT / "themes"
    missing = [
        child.name
        for child in themes_dir.iterdir()
        if child.is_dir() and not (child / "package.json").is_file()
    ]
    assert missing == [], f"theme folders missing package.json: {missing}"
    assert any(child.is_dir() for child in themes_dir.iterdir()), "themes/ is empty"


# Representative file *types* that the imported tree must contain at least once.
# ``glob_pattern`` is matched recursively under the extensions root.
REPRESENTATIVE_TYPES: tuple[tuple[str, str], ...] = (
    ("package.json", "lang/**/package.json"),
    ("package.nls.json", "lang/**/package.nls.json"),
    ("language-configuration.json", "lang/**/language-configuration.json"),
    ("*.tmLanguage.json", "lang/**/*.tmLanguage.json"),
    ("*.code-snippets", "lang/**/*.code-snippets"),
    ("theme JSON", "themes/**/themes/*.json"),
)


@pytest.mark.parametrize(("label", "glob_pattern"), REPRESENTATIVE_TYPES)
def test_representative_file_type_present(label: str, glob_pattern: str) -> None:
    matches = list(EXTENSIONS_ROOT.glob(glob_pattern))
    assert matches, (
        f"imported tree has no {label} file (pattern {glob_pattern!r}) under "
        f"src/ecli/extensions/"
    )


def _is_allowed_runtime_asset(relative: Path) -> bool:
    """Return True when ``relative`` (a file path) is permitted runtime data."""
    parts = relative.parts
    if not parts:
        return False
    # ECLI-owned runtime packages (adapter code, F4 linter microservices):
    # any Python file/data is allowed.
    if parts[0] in ECLI_OWNED_RUNTIME_PACKAGES:
        return True
    # Root-level files (THIRD_PARTY_NOTICES.md, README.md, legal notices).
    if len(parts) == 1:
        return _matches_any(parts[0], TOP_LEVEL_FILE_PATTERNS)
    # Everything else must live inside a curated asset group.
    if parts[0] not in ASSET_GROUP_DIRS:
        return False
    # group/<folder>/<file>  -> a file at the imported folder root.
    if len(parts) == 3:
        return _matches_any(parts[-1], TOP_LEVEL_FILE_PATTERNS)
    # group/<folder>/<subdir>/<file>  -> a file inside a named asset subdir.
    # Anything deeper, or in an unknown subdir, is not an approved shape.
    patterns = ASSET_DIR_FILE_PATTERNS.get(parts[2]) if len(parts) == 4 else None
    return bool(patterns and _matches_any(parts[-1], patterns))


def test_imported_tree_contains_only_runtime_assets() -> None:
    offenders = []
    for path in EXTENSIONS_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(EXTENSIONS_ROOT)
        if _is_ecli_integration(relative):
            continue
        if not _is_allowed_runtime_asset(relative):
            offenders.append(relative.as_posix())

    assert offenders == [], f"non-runtime files under extensions tree: {offenders}"


def test_forbidden_runtime_artifacts_absent() -> None:
    offenders = []
    for path in EXTENSIONS_ROOT.rglob("*"):
        relative = path.relative_to(EXTENSIONS_ROOT)
        if _is_ecli_integration(relative):
            continue

        if path.is_dir() and path.name in FORBIDDEN_DIR_NAMES:
            offenders.append(relative.as_posix())
            continue

        if not path.is_file():
            continue
        is_forbidden_file = (
            _matches_any(path.name, FORBIDDEN_FILE_PATTERNS)
            or path.suffix in FORBIDDEN_SOURCE_SUFFIXES
            or any(
                "screenshot" in part.lower() or "demo" in part.lower()
                for part in relative.parts
            )
        )

        if is_forbidden_file:
            offenders.append(relative.as_posix())

    assert offenders == [], (
        f"forbidden runtime artifacts under extensions tree: {offenders}"
    )


# ---------------------------------------------------------------------------
# F4 linter microservices: src/ecli/extensions/linters/ is an allowed
# Extensions Layer root entry, precisely scoped -- ECLI-owned Python runtime
# is permitted, raw upstream (VS Code TypeScript/JavaScript) linter source
# is not. See docs/architecture/ecli-f4-linter-microservices-design.md.
# ---------------------------------------------------------------------------

LINTERS_ROOT = EXTENSIONS_ROOT / "linters"


def test_linters_root_is_an_allowed_extensions_entry() -> None:
    assert "linters" in ALLOWED_ROOT_ENTRIES
    assert LINTERS_ROOT.is_dir(), (
        f"F4 linter microservices root missing: {LINTERS_ROOT}"
    )
    assert (LINTERS_ROOT / "__init__.py").is_file()
    assert (LINTERS_ROOT / "core").is_dir()
    assert (LINTERS_ROOT / "ruff").is_dir()


def test_no_raw_typescript_or_javascript_under_linters() -> None:
    offenders = [
        str(path.relative_to(LINTERS_ROOT))
        for path in LINTERS_ROOT.rglob("*")
        if path.is_file() and path.suffix in FORBIDDEN_SOURCE_SUFFIXES
    ]
    assert offenders == [], (
        f"raw upstream TypeScript/JavaScript source found under "
        f"src/ecli/extensions/linters/: {offenders}"
    )


def test_no_node_build_artifacts_under_linters() -> None:
    offenders = [
        str(path.relative_to(LINTERS_ROOT))
        for path in LINTERS_ROOT.rglob("*")
        if path.is_file() and _matches_any(path.name, FORBIDDEN_FILE_PATTERNS)
    ]
    assert offenders == [], (
        f"forbidden Node/TS build artifacts under "
        f"src/ecli/extensions/linters/: {offenders}"
    )


def test_no_wrong_extensions_paths_at_src_root() -> None:
    """``src/extentions`` (typo) and ``src/extensions`` (wrong nesting depth)
    must never exist as siblings of ``src/ecli/``; the only valid location is
    ``src/ecli/extensions/``.
    """
    src_root = REPO_ROOT / "src"
    for wrong_name in ("extentions", "extensions"):
        wrong_path = src_root / wrong_name
        assert not wrong_path.exists(), (
            f"wrong extensions path present: {wrong_path}; the only valid "
            "location is src/ecli/extensions/"
        )


def test_no_pycache_or_pyc_tracked_under_linters() -> None:
    """``__pycache__/`` and ``*.pyc`` are build artifacts, never source; they
    must not be tracked by git under the F4 linter microservices tree.
    """
    completed = subprocess.run(
        ["git", "ls-files", "src/ecli/extensions/linters"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    tracked = completed.stdout.splitlines()
    offenders = [
        path for path in tracked if "__pycache__" in path or path.endswith(".pyc")
    ]
    assert offenders == [], f"pycache/.pyc files are tracked by git: {offenders}"
