# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_parsers.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Fixture tests for every implemented F4 linter microservice parser.

Each parser must return normalized ``Diagnostic`` objects from
``ecli.extensions.linters.core.models`` (design doc section 19.4,
"Parser Fixture Tests") and must never raise on malformed input.
"""

from __future__ import annotations

import json

from ecli.extensions.linters.actionlint.parser import parse_actionlint_output
from ecli.extensions.linters.biome.parser import parse_biome_output
from ecli.extensions.linters.cargo_clippy.parser import parse_cargo_clippy_output
from ecli.extensions.linters.clang_tidy.parser import parse_clang_tidy_output
from ecli.extensions.linters.core.models import Diagnostic
from ecli.extensions.linters.cppcheck.parser import parse_cppcheck_output
from ecli.extensions.linters.hadolint.parser import parse_hadolint_output
from ecli.extensions.linters.java_checkstyle.parser import parse_checkstyle_output
from ecli.extensions.linters.java_pmd.parser import parse_pmd_output
from ecli.extensions.linters.markdownlint.parser import parse_markdownlint_output
from ecli.extensions.linters.shellcheck.parser import parse_shellcheck_output
from ecli.extensions.linters.taplo.parser import parse_taplo_output
from ecli.extensions.linters.yamllint.parser import parse_yamllint_output
from ecli.extensions.linters.zig.parser import parse_zig_output


def _assert_all_diagnostics(result: tuple[Diagnostic, ...]) -> None:
    assert result
    for diagnostic in result:
        assert isinstance(diagnostic, Diagnostic)
        assert diagnostic.line >= 1
        assert diagnostic.column >= 1
        assert diagnostic.severity in ("error", "warning", "info", "hint")
        assert diagnostic.source


# ---------------------------------------------------------------------------
# markdownlint-cli2
# ---------------------------------------------------------------------------


def test_markdownlint_parses_text_output() -> None:
    text = (
        "audit-report.md:12 MD013/line-length Line length "
        "[Expected: 80; Actual: 95]\n"
        "audit-report.md:34:1-34:10 MD047/single-trailing-newline "
        "Files should end with a single newline character\n"
    )
    diagnostics = parse_markdownlint_output(text, default_file="audit-report.md")
    _assert_all_diagnostics(diagnostics)
    assert {d.code for d in diagnostics} == {
        "MD013/line-length",
        "MD047/single-trailing-newline",
    }


def test_markdownlint_ignores_malformed_lines() -> None:
    assert parse_markdownlint_output("Summary: 2 error(s)\n") == ()
    assert parse_markdownlint_output("") == ()


# ---------------------------------------------------------------------------
# yamllint
# ---------------------------------------------------------------------------


def test_yamllint_parses_parsable_output() -> None:
    text = (
        'file.yaml:3:1: [error] duplication of key "foo" in mapping '
        "(key-duplicates)\n"
        "file.yaml:10:80: [warning] line too long (85 > 80 characters) "
        "(line-length)\n"
    )
    diagnostics = parse_yamllint_output(text, default_file="file.yaml")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].severity == "error"
    assert any(d.severity == "warning" for d in diagnostics)


def test_yamllint_ignores_malformed_lines() -> None:
    assert parse_yamllint_output("not a real yamllint line\n") == ()


# ---------------------------------------------------------------------------
# shellcheck
# ---------------------------------------------------------------------------


def test_shellcheck_parses_json_output() -> None:
    raw = json.dumps(
        [
            {
                "file": "deploy.sh",
                "line": 3,
                "column": 1,
                "level": "warning",
                "code": 2086,
                "message": "Double quote to prevent globbing.",
            }
        ]
    )
    diagnostics = parse_shellcheck_output(raw, default_file="deploy.sh")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "SC2086"


def test_shellcheck_returns_empty_for_malformed_json() -> None:
    assert parse_shellcheck_output("not json") == ()
    assert parse_shellcheck_output("") == ()


# ---------------------------------------------------------------------------
# biome (best effort)
# ---------------------------------------------------------------------------


def test_biome_parses_json_diagnostics() -> None:
    raw = json.dumps(
        {
            "diagnostics": [
                {
                    "category": "lint/suspicious/noDoubleEquals",
                    "severity": "warning",
                    "description": "Use === instead of ==.",
                    "location": {"path": {"file": "app.ts"}},
                }
            ]
        }
    )
    diagnostics = parse_biome_output(raw, default_file="app.ts")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "lint/suspicious/noDoubleEquals"


def test_biome_falls_back_to_text_lines_for_non_json_output() -> None:
    text = "app.ts:3:5 Use === instead of ==.\n"
    diagnostics = parse_biome_output(text, default_file="app.ts")
    _assert_all_diagnostics(diagnostics)


def test_biome_returns_empty_for_unrecognized_shape() -> None:
    assert parse_biome_output(json.dumps({"unexpected": True})) == ()
    assert parse_biome_output("") == ()


# ---------------------------------------------------------------------------
# zig (best effort)
# ---------------------------------------------------------------------------


def test_zig_parses_compiler_style_errors() -> None:
    text = "main.zig:3:5: error: expected ';' after statement\n"
    diagnostics = parse_zig_output(text, default_file="main.zig")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].severity == "error"


def test_zig_parses_needs_formatting_filename_only_output() -> None:
    text = "main.zig\n"
    diagnostics = parse_zig_output(text, default_file="main.zig")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].line == 1
    assert diagnostics[0].column == 1


def test_zig_returns_empty_for_blank_output() -> None:
    assert parse_zig_output("") == ()


# ---------------------------------------------------------------------------
# hadolint
# ---------------------------------------------------------------------------


def test_hadolint_parses_json_output() -> None:
    raw = json.dumps(
        [
            {
                "line": 1,
                "column": 1,
                "level": "warning",
                "code": "DL3006",
                "message": "Always tag the version of an image explicitly",
                "file": "Dockerfile",
            }
        ]
    )
    diagnostics = parse_hadolint_output(raw, default_file="Dockerfile")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "DL3006"


def test_hadolint_returns_empty_for_malformed_json() -> None:
    assert parse_hadolint_output("not json") == ()


# ---------------------------------------------------------------------------
# taplo (best effort)
# ---------------------------------------------------------------------------


def test_taplo_parses_diagnostic_report_output() -> None:
    text = (
        "Error: invalid escape sequence\n"
        "   ╭─[config.toml:3:10]\n"
        "   │\n"
        ' 3 │ foo = "bad"\n'
        "   │\n"
    )
    diagnostics = parse_taplo_output(text, default_file="config.toml")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].line == 3


def test_taplo_returns_empty_for_clean_output() -> None:
    assert parse_taplo_output("") == ()


# ---------------------------------------------------------------------------
# actionlint
# ---------------------------------------------------------------------------


def test_actionlint_parses_text_output() -> None:
    text = (
        ".github/workflows/ci.yml:10:5: character '\"' is invalid for "
        "step name [syntax-check]\n"
    )
    diagnostics = parse_actionlint_output(text, default_file=".github/workflows/ci.yml")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "syntax-check"


def test_actionlint_returns_empty_for_clean_output() -> None:
    assert parse_actionlint_output("") == ()


# ---------------------------------------------------------------------------
# clang-tidy
# ---------------------------------------------------------------------------


def test_clang_tidy_parses_text_output() -> None:
    text = (
        "main.cpp:10:5: warning: variable 'x' is not initialized "
        "[cppcoreguidelines-init-variables]\n"
        "main.cpp:15:1: error: use of undeclared identifier 'foo' "
        "[clang-diagnostic-error]\n"
    )
    diagnostics = parse_clang_tidy_output(text, default_file="main.cpp")
    _assert_all_diagnostics(diagnostics)
    assert any(d.severity == "error" for d in diagnostics)
    assert any(d.severity == "warning" for d in diagnostics)


def test_clang_tidy_returns_empty_for_clean_output() -> None:
    assert parse_clang_tidy_output("") == ()


# ---------------------------------------------------------------------------
# cppcheck (gcc template)
# ---------------------------------------------------------------------------


def test_cppcheck_parses_gcc_template_output() -> None:
    text = (
        "main.cpp:10:5: warning: Variable 'x' is not initialized [uninitvar]\n"
        "main.cpp:20:1: style: Variable 'y' is assigned a value that is "
        "never used [unreadVariable]\n"
    )
    diagnostics = parse_cppcheck_output(text, default_file="main.cpp")
    _assert_all_diagnostics(diagnostics)
    assert any(d.code == "uninitvar" for d in diagnostics)


def test_cppcheck_returns_empty_for_clean_output() -> None:
    assert parse_cppcheck_output("") == ()


# ---------------------------------------------------------------------------
# checkstyle (XML)
# ---------------------------------------------------------------------------


def test_checkstyle_parses_xml_output() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<checkstyle version="10.12.1">'
        '<file name="/path/to/File.java">'
        '<error line="3" column="1" severity="warning" '
        'message="Missing a Javadoc comment." '
        'source="com.puppycrawl.tools.checkstyle.checks.javadoc.'
        'MissingJavadocTypeCheck"/>'
        "</file>"
        "</checkstyle>"
    )
    diagnostics = parse_checkstyle_output(xml, default_file="File.java")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "MissingJavadocTypeCheck"


def test_checkstyle_returns_empty_for_malformed_xml() -> None:
    assert parse_checkstyle_output("<not-valid-xml") == ()
    assert parse_checkstyle_output("") == ()


# ---------------------------------------------------------------------------
# PMD (XML)
# ---------------------------------------------------------------------------


def test_pmd_parses_xml_output() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<pmd version="7.0.0" timestamp="2026-01-01T00:00:00.000">'
        '<file name="/path/to/File.java">'
        '<violation beginline="10" endline="10" begincolumn="5" '
        'endcolumn="20" rule="UnusedLocalVariable" '
        'ruleset="Best Practices" priority="3">'
        "Avoid unused local variables such as 'x'."
        "</violation>"
        "</file>"
        "</pmd>"
    )
    diagnostics = parse_pmd_output(xml, default_file="File.java")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "UnusedLocalVariable"


def test_pmd_returns_empty_for_malformed_xml() -> None:
    assert parse_pmd_output("<not-valid-xml") == ()


# ---------------------------------------------------------------------------
# Cargo Clippy (newline-delimited JSON stream)
# ---------------------------------------------------------------------------


def test_cargo_clippy_parses_compiler_message_stream() -> None:
    compiler_artifact = json.dumps({"reason": "compiler-artifact"})
    compiler_message = json.dumps(
        {
            "reason": "compiler-message",
            "message": {
                "message": "unused variable: `x`",
                "level": "warning",
                "code": {"code": "unused_variables"},
                "spans": [
                    {
                        "file_name": "src/main.rs",
                        "line_start": 3,
                        "column_start": 9,
                        "is_primary": True,
                    }
                ],
            },
        }
    )
    stream = f"{compiler_artifact}\n{compiler_message}\n"
    diagnostics = parse_cargo_clippy_output(stream, default_file="src/main.rs")
    _assert_all_diagnostics(diagnostics)
    assert diagnostics[0].code == "unused_variables"


def test_cargo_clippy_ignores_non_compiler_message_records() -> None:
    stream = json.dumps({"reason": "build-script-executed"}) + "\n"
    assert parse_cargo_clippy_output(stream) == ()


def test_cargo_clippy_ignores_malformed_json_lines() -> None:
    assert parse_cargo_clippy_output("not json\n{also not json\n") == ()
