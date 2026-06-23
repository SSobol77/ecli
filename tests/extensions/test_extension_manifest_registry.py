# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extension_manifest_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the data-only extension manifest registry (#100).

These tests exercise the deterministic adapter over the imported, read-only
extension tree under ``src/ecli/extensions/``. They assert discovery, lookups,
deterministic diagnostics for malformed input, shallow (non-recursive)
discovery, path containment, and that the registry exposes no executable
surface. They never modify imported upstream files.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import (
    ExtensionManifest,
    ExtensionRegistry,
    ThemeContribution,
    build_registry,
    manifest as manifest_module,
    paths as paths_module,
    registry as registry_module,
)


REPRESENTATIVE_MANIFEST_DIRS = (
    "bat",
    "python",
    "json",
    "javascript",
    "typescript-basics",
    "markdown-basics",
    "cpp",
)

# (file extension, expected language id) using actual imported metadata.
REPRESENTATIVE_EXTENSIONS = (
    (".py", "python"),
    (".json", "json"),
    (".js", "javascript"),
    (".ts", "typescript"),
    (".md", "markdown"),
    (".c", "c"),
    (".cpp", "cpp"),
    (".h", "cpp"),
    (".bat", "bat"),
)


@pytest.fixture(scope="module")
def registry() -> ExtensionRegistry:
    return build_registry()


def _make_extension(root: Path, name: str, manifest: object) -> Path:
    """Create a throwaway extension folder with a ``package.json`` payload.

    Manifests are placed under the ``lang/`` asset group because discovery only
    scans the curated ``lang/`` and ``themes/`` groups (never the tree root).
    """
    directory = root / "lang" / name
    directory.mkdir(parents=True)
    payload = manifest if isinstance(manifest, str) else json.dumps(manifest)
    (directory / "package.json").write_text(payload, encoding="utf-8")
    return directory


# --------------------------------------------------------------------------- #
# Discovery + lookups against the real imported tree.
# --------------------------------------------------------------------------- #


def test_real_tree_discovery_is_clean(registry: ExtensionRegistry) -> None:
    assert registry.list_manifests(), "no manifests discovered in imported tree"
    # The pristine imported tree must parse without diagnostics.
    assert registry.list_diagnostics() == ()


@pytest.mark.parametrize("directory_name", REPRESENTATIVE_MANIFEST_DIRS)
def test_discovers_representative_manifests(
    registry: ExtensionRegistry, directory_name: str
) -> None:
    names = {manifest.directory_name for manifest in registry.list_manifests()}
    assert directory_name in names


def test_lists_representative_language_ids(registry: ExtensionRegistry) -> None:
    language_ids = set(registry.language_ids())
    expected = {
        "python",
        "json",
        "javascript",
        "typescript",
        "markdown",
        "bat",
        "c",
        "cpp",
    }
    assert expected <= language_ids


@pytest.mark.parametrize(("extension", "expected_id"), REPRESENTATIVE_EXTENSIONS)
def test_extension_lookup(
    registry: ExtensionRegistry, extension: str, expected_id: str
) -> None:
    language = registry.find_language_by_extension(extension)
    assert language is not None, f"no language resolved for {extension}"
    assert language.language_id == expected_id


def test_extension_lookup_is_case_insensitive(registry: ExtensionRegistry) -> None:
    assert registry.find_language_by_extension(".PY") is not None
    assert registry.find_language_by_extension("py") is not None


@pytest.mark.parametrize(
    ("language_id", "scope_name"),
    [
        ("python", "source.python"),
        ("json", "source.json"),
        ("bat", "source.batchfile"),
        ("cpp", "source.cpp"),
    ],
)
def test_grammar_lookup(
    registry: ExtensionRegistry, language_id: str, scope_name: str
) -> None:
    scopes = {g.scope_name for g in registry.find_grammars_by_language(language_id)}
    assert scope_name in scopes


def test_snippet_lookup_where_present(registry: ExtensionRegistry) -> None:
    bat_snippets = registry.find_snippets_by_language("bat")
    assert bat_snippets, "expected at least one bat snippet contribution"
    assert any(
        s.path_repo_relative
        and s.path_repo_relative.endswith("batchfile.code-snippets")
        for s in bat_snippets
    )
    assert registry.find_snippets_by_language("cpp"), "expected cpp snippets"


def test_theme_contributions_are_metadata_only(registry: ExtensionRegistry) -> None:
    themes = registry.list_themes()
    assert themes, "expected imported theme contributions"
    assert all(isinstance(theme, ThemeContribution) for theme in themes)
    monokai = registry.find_theme_by_id("Monokai")
    assert monokai is not None
    assert monokai.path_repo_relative == (
        "src/ecli/extensions/themes/monokai/themes/monokai-color-theme.json"
    )


def test_configuration_contributions_are_metadata_only(
    registry: ExtensionRegistry,
) -> None:
    # At least one manifest in the imported tree contributes configuration.
    with_config = [m for m in registry.list_manifests() if m.configuration]
    assert with_config, "expected configuration contributions in the imported tree"
    for block in with_config[0].configuration:
        # Only declarative metadata is exposed; no values/schemas are applied.
        assert isinstance(block.property_keys, tuple)


# --------------------------------------------------------------------------- #
# Shallow discovery (no recursion into nested package.json).
# --------------------------------------------------------------------------- #


def test_discovery_is_shallow(registry: ExtensionRegistry) -> None:
    extensions_root = paths_module.extensions_root()
    # Manifests live in the curated ``lang/`` and ``themes/`` asset groups, one
    # shallow level under each group dir. The tree root itself holds no manifest.
    group_children = {
        child.name
        for group in ("lang", "themes")
        for child in (extensions_root / group).iterdir()
        if child.is_dir() and (child / "package.json").is_file()
    }
    discovered = {m.directory_name for m in registry.list_manifests()}
    assert discovered == group_children
    # The tree root and the ECLI-owned adapter package are never manifests.
    assert "ecli_integration" not in discovered
    assert "lang" not in discovered
    assert "themes" not in discovered
    # A nested server manifest must never appear as its own entry.
    assert "server" not in discovered
    # Curated language/theme assets are present...
    assert "git-base" in discovered
    assert "python" in discovered
    assert "defaults" in discovered
    # ...while non-runtime VS Code UI/runtime extension folders are pruned.
    assert "html-language-features" not in discovered
    assert "notebook-renderers" not in discovered
    assert "references-view" not in discovered
    assert "copilot" not in discovered


def test_discovery_ignores_nested_package_json(tmp_path: Path) -> None:
    parent = _make_extension(
        tmp_path,
        "outer",
        {"name": "outer", "contributes": {"languages": [{"id": "outer-lang"}]}},
    )
    nested = parent / "server"
    nested.mkdir()
    (nested / "package.json").write_text(
        json.dumps(
            {"name": "nested", "contributes": {"languages": [{"id": "nested"}]}}
        ),
        encoding="utf-8",
    )

    built = build_registry(root=tmp_path)
    discovered = {m.directory_name for m in built.list_manifests()}
    assert discovered == {"outer"}
    assert built.find_language_by_id("nested") is None


# --------------------------------------------------------------------------- #
# Deterministic diagnostics for malformed / edge-case manifests.
# --------------------------------------------------------------------------- #


def test_malformed_json_is_diagnosed_not_fatal(tmp_path: Path) -> None:
    _make_extension(tmp_path, "broken", "{ this is not valid json ")
    _make_extension(
        tmp_path,
        "good",
        {
            "name": "good",
            "contributes": {"languages": [{"id": "good", "extensions": [".good"]}]},
        },
    )

    first = build_registry(root=tmp_path)
    second = build_registry(root=tmp_path)

    # Discovery did not crash and the valid manifest is still available.
    assert {m.directory_name for m in first.list_manifests()} == {"good"}
    assert first.find_language_by_extension(".good") is not None

    # Exactly one error diagnostic, pointing at the broken manifest.
    errors = [d for d in first.list_diagnostics() if d.level == "error"]
    assert len(errors) == 1
    assert "broken" in errors[0].manifest

    # Diagnostics are deterministic across repeated builds.
    assert first.list_diagnostics() == second.list_diagnostics()


def test_malformed_contributes_does_not_crash(tmp_path: Path) -> None:
    _make_extension(
        tmp_path, "weird", {"name": "weird", "contributes": "not-an-object"}
    )
    built = build_registry(root=tmp_path)
    manifest = built.list_manifests()[0]
    assert manifest.languages == ()
    assert any(d.level == "warning" for d in built.list_diagnostics())


def test_missing_target_file_is_diagnosed_not_fatal(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "ghost",
        {
            "name": "ghost",
            "contributes": {
                "grammars": [
                    {
                        "language": "ghost",
                        "scopeName": "source.ghost",
                        "path": "./missing.json",
                    }
                ]
            },
        },
    )
    built = build_registry(root=tmp_path)
    assert built.list_manifests(), "manifest with a missing target must still load"
    grammars = built.find_grammars_by_language("ghost")
    assert grammars and grammars[0].path == "./missing.json"
    assert any("missing" in d.message for d in built.list_diagnostics())


# --------------------------------------------------------------------------- #
# Path containment / traversal safety.
# --------------------------------------------------------------------------- #


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "escape",
        {
            "name": "escape",
            "contributes": {
                "grammars": [
                    {
                        "language": "escape",
                        "scopeName": "source.escape",
                        "path": "../../../../../../etc/passwd",
                    }
                ]
            },
        },
    )
    built = build_registry(root=tmp_path)
    grammar = built.find_grammars_by_language("escape")[0]
    # The escaping path is preserved as raw metadata but never resolved.
    assert grammar.path_repo_relative is None
    assert any("escapes extension tree" in d.message for d in built.list_diagnostics())


def test_resolved_paths_stay_under_extensions_root(
    registry: ExtensionRegistry,
) -> None:
    extensions_root = paths_module.extensions_root()
    prefix = f"{paths_module.REPO_RELATIVE_PREFIX}/"
    for manifest in registry.list_manifests():
        records = (
            [g.path_repo_relative for g in manifest.grammars]
            + [s.path_repo_relative for s in manifest.snippets]
            + [theme.path_repo_relative for theme in manifest.themes]
            + [language.configuration_repo_path for language in manifest.languages]
        )
        for repo_path in records:
            if repo_path is None:
                continue
            assert repo_path.startswith(prefix)
            relative = repo_path[len(paths_module.REPO_RELATIVE_PREFIX) + 1 :]
            resolved = (extensions_root / relative).resolve()
            assert resolved.is_relative_to(extensions_root.resolve())


def test_real_contribution_targets_resolve(registry: ExtensionRegistry) -> None:
    extensions_root = paths_module.extensions_root()
    prefix = f"{paths_module.REPO_RELATIVE_PREFIX}/"
    unresolved: list[str] = []

    for manifest in registry.list_manifests():
        records = (
            [(g.path, g.path_repo_relative) for g in manifest.grammars]
            + [(s.path, s.path_repo_relative) for s in manifest.snippets]
            + [(theme.path, theme.path_repo_relative) for theme in manifest.themes]
            + [
                (language.configuration_path, language.configuration_repo_path)
                for language in manifest.languages
            ]
        )
        for raw_path, repo_path in records:
            if raw_path is None:
                continue
            if repo_path is None:
                unresolved.append(f"{manifest.manifest_repo_path}: {raw_path}")
                continue
            relative = repo_path[len(prefix) :] if repo_path.startswith(prefix) else ""
            if not relative or not (extensions_root / relative).is_file():
                unresolved.append(repo_path)

    assert unresolved == []


# --------------------------------------------------------------------------- #
# No executable / runtime surface.
# --------------------------------------------------------------------------- #


def test_manifest_model_exposes_no_executable_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(ExtensionManifest)}
    forbidden = {
        "scripts",
        "activation_events",
        "activationEvents",
        "main",
        "browser",
        "commands",
    }
    assert field_names.isdisjoint(forbidden)


def test_copilot_manifest_is_data_only(registry: ExtensionRegistry) -> None:
    copilot = next(
        (m for m in registry.list_manifests() if m.directory_name == "copilot"), None
    )
    if copilot is None:
        pytest.skip("copilot extension not present in imported tree")
    # It is exposed as inert metadata, never as an activatable runtime.
    assert copilot.name
    assert not hasattr(copilot, "activation_events")
    assert not hasattr(copilot, "scripts")


def test_adapter_modules_have_no_execution_primitives() -> None:
    execution_tokens = (
        "subprocess",
        "os.system",
        "os.popen",
        "pty.",
        "eval(",
        "exec(",
        "__import__(",
    )
    for module in (paths_module, manifest_module, registry_module):
        source = inspect.getsource(module)
        for token in execution_tokens:
            assert token not in source, f"{module.__name__} must not use {token!r}"
