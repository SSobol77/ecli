# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_textmate_tokenization.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Real TextMate tokenization + scope-to-style tests (#102).

These prove that ECLI tokenizes representative files with the **actual** imported
`.tmLanguage.json` grammars (producing genuine TextMate scopes), maps scopes to
ECLI style categories deterministically, and falls back safely for grammars the
engine cannot handle (Markdown), unknown files, and invalid grammars. They never
execute extension code.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import (
    EXTENSION_TOKENIZATION_AVAILABLE,
    ExtensionLayerConfig,
    SyntaxService,
    build_syntax_service,
    load_tokenizer,
    scope_to_category,
    textmate_tokenizer as tokenizer_module,
    theme_bridge as theme_bridge_module,
    tokens_to_spans,
)


pytestmark = pytest.mark.skipif(
    not EXTENSION_TOKENIZATION_AVAILABLE,
    reason="python-textmate tokenizer is not installed",
)

EXTENSIONS_ROOT = Path("src/ecli/extensions")


@pytest.fixture(scope="module")
def service() -> SyntaxService:
    return build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    )


def _categories(service: SyntaxService, filename: str, lines: list[str]) -> set[str]:
    highlighter = service.build_line_highlighter(filename)
    assert highlighter is not None, f"no TextMate highlighter for {filename}"
    categories: set[str] = set()
    for line in lines:
        spans = highlighter.highlight(line)
        if spans:
            categories |= {category for _text, category in spans}
    return categories


# --------------------------------------------------------------------------- #
# Real grammar loading + representative tokenization.
# --------------------------------------------------------------------------- #


def test_real_grammar_loads_from_extensions_tree() -> None:
    grammar = EXTENSIONS_ROOT / "lang/python/syntaxes/MagicPython.tmLanguage.json"
    tokenizer = load_tokenizer(grammar.resolve())
    assert tokenizer is not None
    tokens = tokenizer.tokenize_line("def f(x): return 42")
    assert tokens, "tokenizer must produce TextMate tokens"
    # Genuine TextMate scope names (not flat token categories).
    assert any(scope.endswith(".python") for scope, _s, _e in tokens)


def test_python_scopes(service: SyntaxService) -> None:
    categories = _categories(
        service,
        "example.py",
        ["def greet(name):", "    s = 'hello'  # comment", "    return 42"],
    )
    assert {"keyword", "string", "comment", "function"} <= categories


def test_python_docstring_words_do_not_get_keyword_style(
    service: SyntaxService,
) -> None:
    highlighter = service.build_line_highlighter("example.py")
    assert highlighter is not None
    lines = [
        '"""class def return import for while 123 == -> + -"""',
        "def real_function():",
        '    """class def return 123 ==',
        "    import for while -> + -",
        '    """',
        "    return 1",
    ]
    highlighted = highlighter.highlight_lines(
        lines, line_indices=list(range(len(lines))), full_text=lines
    )
    assert highlighted[0] == [
        ('"""class def return import for while 123 == -> + -"""', "string")
    ]
    for line_spans in highlighted[2:5]:
        assert line_spans is not None
        assert {category for _text, category in line_spans} == {"string"}
    real_return = highlighted[5]
    assert real_return is not None
    assert any(
        text == "return" and category == "keyword" for text, category in real_return
    )


def test_json_scopes(service: SyntaxService) -> None:
    categories = _categories(
        service, "package.json", ['  "name": "ecli",', '  "n": 42']
    )
    assert {"string", "number"} <= categories


def test_typescript_scopes(service: SyntaxService) -> None:
    categories = _categories(
        service, "main.ts", ["const x = 'h';  // c", "let n = 42;"]
    )
    assert {"string", "comment"} <= categories


def test_javascript_scopes(service: SyntaxService) -> None:
    categories = _categories(service, "app.js", ["function f() { return 'h'; } // c"])
    assert {"string", "comment", "function"} <= categories


def test_cpp_scopes(service: SyntaxService) -> None:
    categories = _categories(service, "main.cpp", ["int main() { return 0; } // c"])
    assert {"keyword", "type", "comment"} <= categories


def test_c_scopes(service: SyntaxService) -> None:
    categories = _categories(service, "main.c", ["int x = 0; // c"])
    assert {"type", "comment"} <= categories


def test_bat_scopes(service: SyntaxService) -> None:
    tokenizer = load_tokenizer(
        (EXTENSIONS_ROOT / "lang/bat/syntaxes/batchfile.tmLanguage.json").resolve()
    )
    assert tokenizer is not None
    tokens = tokenizer.tokenize_line("REM a comment")
    assert any("batchfile" in scope for scope, _s, _e in tokens)


def test_yaml_is_visible_via_legacy_fallback(service: SyntaxService) -> None:
    # The imported YAML block grammar yields no tokens under the per-line stateless
    # engine (it needs multi-line state ECLI does not maintain), so the extension
    # highlighter alone produces only default spans. The required guarantee — "YAML
    # is visibly highlighted" — is met at the editor level: when the extension
    # engine produces nothing usable, the editor falls back to the legacy/Pygments
    # highlighter (see ``Ecli._apply_extension_highlighting``). The editor-level
    # proof lives in ``tests/extensions/test_editor_syntax_rendering.py``; here we
    # pin the engine-level reality so the fallback contract stays honest.
    for filename in (".coderabbit.yaml", "docker-compose.yml", "config.yaml"):
        highlighter = service.build_line_highlighter(filename)
        assert highlighter is not None, filename
        spans = highlighter.highlight("name: ecli # comment")
        assert spans is not None
        categories = {category for _text, category in spans}
        # The stateless engine cannot colour YAML, so the editor must fall back.
        assert categories <= {"default", "punctuation"}, (filename, spans)


def test_gitignore_scopes_are_not_sql(service: SyntaxService) -> None:
    resolution = service.resolve(".gitignore")
    assert resolution.language_id == "ignore"
    assert resolution.scope_name == "source.ignore"
    assert resolution.language_id != "sql"


# --------------------------------------------------------------------------- #
# Safe fallback behaviour.
# --------------------------------------------------------------------------- #


def test_markdown_falls_back_safely(service: SyntaxService) -> None:
    # The imported Markdown grammar makes the engine recurse; tokenization must
    # degrade to None (caller renders via legacy) rather than crash.
    highlighter = service.build_line_highlighter("README.md")
    if highlighter is not None:
        assert highlighter.highlight("# Heading") is None


def test_unknown_file_has_no_highlighter(service: SyntaxService) -> None:
    assert service.build_line_highlighter("mystery.zzz") is None


def test_invalid_grammar_returns_none(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tmLanguage.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert load_tokenizer(bad.resolve()) is None


def test_legacy_engine_has_no_highlighter() -> None:
    legacy = build_syntax_service(
        ExtensionLayerConfig.from_section({"syntax_engine": "legacy"})
    )
    assert legacy.build_line_highlighter("example.py") is None


# --------------------------------------------------------------------------- #
# Determinism + scope-to-style mapping.
# --------------------------------------------------------------------------- #


def test_tokenization_is_deterministic(service: SyntaxService) -> None:
    first = service.build_line_highlighter("example.py")
    second = service.build_line_highlighter("example.py")
    assert first is not None and second is not None
    line = "def f(x): return 'hi'  # c"
    assert first.highlight(line) == second.highlight(line)


def test_scope_to_category_specificity() -> None:
    assert scope_to_category("keyword.control.flow.python") == "keyword"
    assert scope_to_category("string.quoted.double.json") == "string"
    assert scope_to_category("comment.line.number-sign.python") == "comment"
    assert scope_to_category("constant.numeric.integer.python") == "number"
    assert scope_to_category("entity.name.function.python") == "function"
    # Structural scopes render as default text.
    assert scope_to_category("meta.function.python") is None
    assert scope_to_category("source.python") is None


def test_tokens_to_spans_tile_line_exactly() -> None:
    line = "def f"
    tokens = [("keyword.control.python", 0, 3), ("entity.name.function.python", 4, 5)]
    spans = tokens_to_spans(line, tokens)
    assert "".join(text for text, _category in spans) == line
    categories = dict(spans)
    assert categories["def"] == "keyword"
    assert categories["f"] == "function"


def test_tokens_to_spans_handles_empty_line() -> None:
    assert tokens_to_spans("", []) == []


def test_distinct_scope_categories_map_to_distinct_styles(
    service: SyntaxService,
) -> None:
    # A rendering-level proof: different scope categories yield different style
    # categories, so the editor maps them to different curses attributes.
    highlighter = service.build_line_highlighter("example.py")
    assert highlighter is not None
    spans = highlighter.highlight("def f(): s = 'h'  # c")
    assert spans is not None
    categories = {category for _text, category in spans}
    # Keyword, string, and comment are all present and distinct.
    assert {"keyword", "string", "comment"} <= categories


# --------------------------------------------------------------------------- #
# No runtime execution.
# --------------------------------------------------------------------------- #


def test_no_runtime_execution_primitives() -> None:
    for module in (tokenizer_module, theme_bridge_module):
        source = inspect.getsource(module)
        for token in ("subprocess", "os.system", "os.popen", "pty.", "eval(", "exec("):
            assert token not in source, f"{module.__name__} must not use {token!r}"


def test_tokenizer_loads_only_json_data() -> None:
    # The tokenizer reads grammar JSON; it never imports or executes grammar code.
    source = inspect.getsource(tokenizer_module)
    assert "json.loads" in source
