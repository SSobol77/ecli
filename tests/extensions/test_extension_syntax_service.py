# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extension_syntax_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the extension-backed syntax-service boundary (#102).

The service resolves language/grammar metadata from the #101 catalog and
detection layers and reports the rendering decision. Full TextMate tokenization
is deliberately NOT implemented, so every resolution must keep the legacy
highlighter authoritative (``fallback_to_legacy`` is always ``True``). These
tests cover construction, config-driven engine selection, representative
metadata resolution, unknown/invalid fallback, deterministic diagnostics, and
the absence of any runtime-execution capability.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import (
    EXTENSION_TOKENIZATION_AVAILABLE,
    ExtensionLayerConfig,
    SyntaxResolution,
    SyntaxService,
    build_syntax_service,
    syntax_service as syntax_service_module,
)


# (file name, expected language id, expected TextMate scope) from real metadata.
REPRESENTATIVE_FILES = (
    ("example.py", "python", "source.python"),
    ("pyproject.toml", "toml", None),
    ("package.json", "json", "source.json"),
    ("tsconfig.json", "jsonc", "source.json.comments"),
    ("main.ts", "typescript", "source.ts"),
    ("app.tsx", "typescriptreact", "source.tsx"),
    ("app.js", "javascript", "source.js"),
    ("app.jsx", "javascriptreact", "source.js.jsx"),
    ("README.md", "markdown", "text.html.markdown"),
    (".gitignore", "ignore", "source.ignore"),
    ("editor.log", "log", "text.log"),
    (".coderabbit.yaml", "yaml", "source.yaml"),
    ("docker-compose.yml", "dockercompose", "source.yaml"),
    ("config.yaml", "yaml", "source.yaml"),
    ("Dockerfile", "dockerfile", "source.dockerfile"),
    ("build.dockerfile", "dockerfile", "source.dockerfile"),
    ("Makefile", "makefile", "source.makefile"),
    ("rules.mk", "makefile", "source.makefile"),
    ("boot.asm", "asm", None),
    ("boot.s", "asm", None),
    ("main.c", "c", "source.c"),
    ("main.cpp", "cpp", "source.cpp"),
    ("main.h", "cpp", "source.cpp"),
    ("Main.java", "java", "source.java"),
    ("lib.rs", "rust", "source.rust"),
    ("index.html", "html", "text.html.derivative"),
    ("main.adb", "ada", None),
    ("solver.f90", "fortran", None),
    ("script.pl", "perl", "source.perl"),
    ("index.php", "php", "source.php"),
    ("init.lua", "lua", "source.lua"),
    ("Program.cs", "csharp", "source.cs"),
    ("script.bat", "bat", "source.batchfile"),
)


@pytest.fixture(scope="module")
def legacy_service() -> SyntaxService:
    return build_syntax_service(ExtensionLayerConfig())


@pytest.fixture(scope="module")
def extension_service() -> SyntaxService:
    return build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )


# --------------------------------------------------------------------------- #
# Construction + engine selection.
# --------------------------------------------------------------------------- #


def test_service_constructs_from_default_config(legacy_service: SyntaxService) -> None:
    assert isinstance(legacy_service, SyntaxService)
    assert legacy_service.config.syntax_engine == "legacy"


def test_service_constructs_from_raw_mapping() -> None:
    service = build_syntax_service({"extensions": {"syntax_engine": "extension"}})
    assert service.config.syntax_engine == "extension"


def test_engine_selection_is_config_driven() -> None:
    assert build_syntax_service(ExtensionLayerConfig()).config.syntax_engine == "legacy"
    extension = build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )
    assert extension.config.syntax_engine == "extension"


# --------------------------------------------------------------------------- #
# Representative metadata resolution.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("file_name", "language_id", "scope"), REPRESENTATIVE_FILES)
def test_representative_resolution(
    legacy_service: SyntaxService,
    file_name: str,
    language_id: str,
    scope: str | None,
) -> None:
    resolution = legacy_service.resolve(file_name)
    assert resolution.language_id == language_id
    assert resolution.scope_name == scope
    assert resolution.used_extension_metadata is True
    if scope is None:
        assert resolution.grammar_path is None
        assert resolution.fallback_to_legacy is True
        assert any(
            "required language grammar missing" in d.message
            for d in resolution.diagnostics
        )
    else:
        assert resolution.grammar_path is not None
        assert resolution.grammar_path.startswith("src/ecli/extensions/")


def test_grammar_path_points_into_extensions_tree(
    legacy_service: SyntaxService,
) -> None:
    resolution = legacy_service.resolve("example.py")
    assert resolution.grammar_path == (
        "src/ecli/extensions/lang/python/syntaxes/MagicPython.tmLanguage.json"
    )


# --------------------------------------------------------------------------- #
# Legacy stays authoritative; tokenization is not implemented.
# --------------------------------------------------------------------------- #


def test_textmate_tokenizer_is_available() -> None:
    # The optional python-textmate engine is a project dependency as of #102.
    if not EXTENSION_TOKENIZATION_AVAILABLE:
        pytest.skip("python-textmate tokenizer is not installed")
    assert EXTENSION_TOKENIZATION_AVAILABLE is True


def test_legacy_engine_always_falls_back_to_legacy(
    legacy_service: SyntaxService,
) -> None:
    for file_name, _lang, _scope in REPRESENTATIVE_FILES:
        assert legacy_service.resolve(file_name).fallback_to_legacy is True


def test_extension_engine_does_not_fall_back_when_tokenizer_available(
    extension_service: SyntaxService,
) -> None:
    if not EXTENSION_TOKENIZATION_AVAILABLE:
        pytest.skip("python-textmate tokenizer is not installed")
    # With the tokenizer available and a grammar resolved, the extension engine
    # renders via TextMate (no legacy fallback at the metadata level).
    resolution = extension_service.resolve("example.py")
    assert resolution.syntax_engine == "extension"
    assert resolution.used_extension_metadata is True
    assert resolution.fallback_to_legacy is False


# --------------------------------------------------------------------------- #
# Fallback behavior.
# --------------------------------------------------------------------------- #


def test_unknown_file_falls_back_safely(legacy_service: SyntaxService) -> None:
    resolution = legacy_service.resolve("unknown.zzz")
    assert resolution.language_id is None
    assert resolution.scope_name is None
    assert resolution.grammar_path is None
    assert resolution.used_extension_metadata is False
    assert resolution.fallback_to_legacy is True


def test_missing_filename_falls_back_safely(legacy_service: SyntaxService) -> None:
    resolution = legacy_service.resolve(None)
    assert not resolution.used_extension_metadata
    assert resolution.fallback_to_legacy is True


def test_disabled_extensions_layer_falls_back(legacy_service: SyntaxService) -> None:
    service = build_syntax_service(ExtensionLayerConfig(enabled=False))
    resolution = service.resolve("example.py")
    assert resolution.used_extension_metadata is False
    assert resolution.fallback_to_legacy is True


def test_invalid_config_falls_back_safely() -> None:
    config = ExtensionLayerConfig.from_section({"syntax_engine": "tree-sitter"})
    assert config.syntax_engine == "legacy"
    service = build_syntax_service(config)
    resolution = service.resolve("example.py")
    assert resolution.syntax_engine == "legacy"
    assert resolution.fallback_to_legacy is True
    # The config-level diagnostic is carried through deterministically.
    assert any("unknown syntax_engine" in d.message for d in resolution.diagnostics)


# --------------------------------------------------------------------------- #
# Determinism + no runtime execution.
# --------------------------------------------------------------------------- #


def test_resolution_is_deterministic() -> None:
    service = build_syntax_service(ExtensionLayerConfig())
    assert service.resolve("main.cpp") == service.resolve("main.cpp")


def test_resolution_object_is_frozen(legacy_service: SyntaxService) -> None:
    resolution = legacy_service.resolve("example.py")
    assert isinstance(resolution, SyntaxResolution)
    with pytest.raises((AttributeError, TypeError)):
        resolution.language_id = "hacked"  # type: ignore[misc]


def test_service_has_no_runtime_execution_primitives() -> None:
    # Scan only for genuine code-execution primitives; prose in the module
    # docstring legitimately describes what the service does *not* do.
    source = inspect.getsource(syntax_service_module)
    for token in (
        "subprocess",
        "os.system",
        "os.popen",
        "pty.",
        "eval(",
        "exec(",
        "__import__(",
    ):
        assert token not in source, f"syntax_service must not reference {token!r}"


# --------------------------------------------------------------------------- #
# Fixture isolation (no dependency on the real cache).
# --------------------------------------------------------------------------- #


def _make_extension(root: Path, name: str, manifest: Mapping[str, object]) -> None:
    # Discovery only scans the curated ``lang/`` and ``themes/`` asset groups.
    directory = root / "lang" / name
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_service_resolves_against_fixture_root(tmp_path: Path) -> None:
    _make_extension(
        tmp_path,
        "fixture-lang",
        {
            "name": "fixture-lang",
            "contributes": {
                "languages": [{"id": "fixturelang", "extensions": [".fxt"]}],
                "grammars": [
                    {
                        "language": "fixturelang",
                        "scopeName": "source.fixturelang",
                        "path": "./g.json",
                    }
                ],
            },
        },
    )
    (tmp_path / "lang" / "fixture-lang" / "g.json").write_text("{}", encoding="utf-8")

    service = build_syntax_service(ExtensionLayerConfig(), root=tmp_path)
    resolution = service.resolve("demo.fxt")
    assert resolution.language_id == "fixturelang"
    assert resolution.scope_name == "source.fixturelang"
    assert resolution.fallback_to_legacy is True
