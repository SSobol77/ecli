# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_grammar_catalog.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the data-only TextMate grammar catalog (#101).

The catalog is built from the #100 manifest registry. These tests verify
representative grammar lookups against the real imported tree, path containment,
and deterministic, non-fatal diagnostics for missing/traversal/malformed/
conflicting grammar metadata (using temp fixtures). They never tokenize text,
render syntax, or modify imported upstream files.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import (
    GrammarCatalog,
    build_grammar_catalog,
    paths as paths_module,
)


# (language id, expected TextMate scope) using actual imported metadata.
REPRESENTATIVE_GRAMMARS = (
    ("python", "source.python"),
    ("json", "source.json"),
    ("javascript", "source.js"),
    ("typescript", "source.ts"),
    ("markdown", "text.html.markdown"),
    ("ignore", "source.ignore"),
    ("yaml", "source.yaml"),
    ("dockercompose", "source.yaml"),
    ("bat", "source.batchfile"),
    ("c", "source.c"),
    ("cpp", "source.cpp"),
)


@pytest.fixture(scope="module")
def catalog() -> GrammarCatalog:
    return build_grammar_catalog()


def _make_extension(
    root: Path,
    name: str,
    manifest: Mapping[str, object],
    files: Mapping[str, str] | None = None,
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    for relative, content in (files or {}).items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return directory


def _grammar_manifest(name: str, scope: str, path: str) -> dict[str, object]:
    return {
        "name": name,
        "contributes": {
            "grammars": [{"language": name, "scopeName": scope, "path": path}]
        },
    }


# --------------------------------------------------------------------------- #
# Real imported tree.
# --------------------------------------------------------------------------- #


def test_catalog_builds_from_real_registry(catalog: GrammarCatalog) -> None:
    assert catalog.list_grammars(), "catalog must discover grammars from the registry"
    # The pristine imported tree resolves every grammar file without diagnostics.
    assert catalog.list_diagnostics() == ()


def test_real_catalog_is_deterministic() -> None:
    first = build_grammar_catalog()
    second = build_grammar_catalog()
    assert first.list_grammars() == second.list_grammars()
    assert first.list_diagnostics() == second.list_diagnostics()


@pytest.mark.parametrize(("language_id", "scope_name"), REPRESENTATIVE_GRAMMARS)
def test_representative_grammar_lookup(
    catalog: GrammarCatalog, language_id: str, scope_name: str
) -> None:
    grammars = catalog.grammars_for_language(language_id)
    assert grammars, f"no grammar for language {language_id}"
    scopes = {g.scope_name for g in grammars}
    assert scope_name in scopes
    assert all(g.exists for g in grammars if g.scope_name == scope_name)


def test_grammar_lookup_by_scope(catalog: GrammarCatalog) -> None:
    grammar = catalog.grammar_for_scope("source.batchfile")
    assert grammar is not None
    assert grammar.language_id == "bat"


def test_grammar_paths_stay_under_extensions_root(catalog: GrammarCatalog) -> None:
    extensions_root = paths_module.extensions_root()
    prefix = f"{paths_module.REPO_RELATIVE_PREFIX}/"
    for grammar in catalog.list_grammars():
        if grammar.path_repo_relative is None:
            continue
        assert grammar.path_repo_relative.startswith(prefix)
        relative = grammar.path_repo_relative[len(prefix) :]
        resolved = (extensions_root / relative).resolve()
        assert resolved.is_relative_to(extensions_root.resolve())


def test_embedded_language_metadata_is_exposed(catalog: GrammarCatalog) -> None:
    # Markdown embeds many fenced languages; metadata must be exposed as data.
    embedded = catalog.embedded_languages_for_language("markdown")
    assert embedded, "expected embedded-language metadata for markdown"
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in embedded)


# --------------------------------------------------------------------------- #
# Deterministic diagnostics via fixtures.
# --------------------------------------------------------------------------- #


def test_missing_grammar_file_is_diagnosed(tmp_path: Path) -> None:
    _make_extension(
        tmp_path, "ghost", _grammar_manifest("ghost", "source.ghost", "./missing.json")
    )
    catalog = build_grammar_catalog(root=tmp_path)
    grammar = catalog.grammar_for_language("ghost")
    assert grammar is not None and grammar.exists is False
    assert any("missing" in d.message for d in catalog.list_diagnostics())


def test_grammar_path_traversal_is_diagnosed(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "escape",
        _grammar_manifest("escape", "source.escape", "../../../../etc/passwd"),
    )
    catalog = build_grammar_catalog(root=tmp_path)
    grammar = catalog.grammar_for_language("escape")
    assert grammar is not None and grammar.path_repo_relative is None
    assert any(
        "escapes extension tree" in d.message for d in catalog.list_diagnostics()
    )


def test_missing_scope_name_is_diagnosed(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "noscope",
        {
            "name": "noscope",
            "contributes": {"grammars": [{"language": "noscope", "path": "./g.json"}]},
        },
        files={"g.json": "{}"},
    )
    catalog = build_grammar_catalog(root=tmp_path)
    assert any("missing scopeName" in d.message for d in catalog.list_diagnostics())


def test_conflicting_scope_is_diagnosed_deterministically(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "a_one",
        _grammar_manifest("a_one", "source.shared", "./a.json"),
        files={"a.json": "{}"},
    )
    _make_extension(
        tmp_path,
        "b_two",
        {
            "name": "b_two",
            "contributes": {
                "grammars": [
                    {
                        "language": "b_two",
                        "scopeName": "source.shared",
                        "path": "./b.json",
                    }
                ]
            },
        },
        files={"b.json": "{}"},
    )
    first = build_grammar_catalog(root=tmp_path)
    second = build_grammar_catalog(root=tmp_path)
    assert any(
        "conflicting grammar paths for scope source.shared" in d.message
        for d in first.list_diagnostics()
    )
    assert first.list_diagnostics() == second.list_diagnostics()
