# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/providers/planned.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Planned-provider catalog and the SonarQube project-quality provider (#104).

This is **metadata only**. None of these providers execute in this build: each
records the professional external tool ECLI intends to integrate behind a safe
adapter (no custom lint rules, no runtime auto-install). The provider catalog
concept is ported from `fnando/vscode-linter` (MIT); see
``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..provider_metadata import (
    ProviderCategory,
    ProviderExecutionMode,
    ProviderMetadata,
    ProviderStatus,
)


__all__ = [
    "FILENAME_LANGUAGE",
    "LANGUAGE_LABELS",
    "PLANNED_NOTE_OVERRIDES",
    "PLANNED_PROVIDERS",
    "SONARQUBE_PROVIDER",
]


@dataclass(frozen=True)
class PlannedProviderSpec:
    """Immutable metadata input for one planned diagnostics provider."""

    provider_id: str
    display_name: str
    tool_name: str
    category: ProviderCategory
    execution_mode: ProviderExecutionMode
    language_ids: tuple[str, ...]
    extensions: tuple[str, ...] = ()
    short_label: str = ""
    docs_url: str | None = None


def _planned(spec: PlannedProviderSpec) -> ProviderMetadata:
    return ProviderMetadata(
        id=spec.provider_id,
        display_name=spec.display_name,
        tool_name=spec.tool_name,
        category=spec.category,
        execution_mode=spec.execution_mode,
        status=ProviderStatus.PLANNED,
        language_ids=spec.language_ids,
        extensions=spec.extensions,
        executable=spec.tool_name,
        short_label=spec.short_label or spec.display_name,
        docs_url=spec.docs_url,
        runnable_in_build=False,
    )


_LINT = ProviderCategory.LINT
_TYPECHECK = ProviderCategory.TYPECHECK
_FORMAT = ProviderCategory.FORMAT_CHECK
_SCHEMA = ProviderCategory.SCHEMA
_COMPILER = ProviderCategory.COMPILER
_LS = ProviderCategory.LANGUAGE_SERVER
_STATIC = ProviderCategory.STATIC_ANALYSIS
_BUILD = ProviderCategory.BUILD_DIAGNOSTICS

_CURRENT = ProviderExecutionMode.CURRENT_FILE
_WORKSPACE = ProviderExecutionMode.WORKSPACE
_PROJECT = ProviderExecutionMode.PROJECT_AWARE


# Ordered per language so the panel's "Planned providers: …" summary matches the
# product spec exactly.
PLANNED_PROVIDERS: tuple[ProviderMetadata, ...] = (
    # -- Python (Ruff is the active provider; these are planned) ----------- #
    _planned(
        PlannedProviderSpec(
            "mypy",
            "mypy",
            "mypy",
            _TYPECHECK,
            _WORKSPACE,
            ("python",),
            (".py", ".pyi"),
            "mypy",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "pylint",
            "pylint",
            "pylint",
            _LINT,
            _WORKSPACE,
            ("python",),
            (".py",),
            "pylint",
        )
    ),
    # -- Rust -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "rust-analyzer",
            "rust-analyzer",
            "rust-analyzer",
            _LS,
            _PROJECT,
            ("rust",),
            (".rs",),
            "rust-analyzer",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "cargo-check",
            "cargo check",
            "cargo",
            _COMPILER,
            _PROJECT,
            ("rust",),
            (".rs",),
            "cargo check",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "cargo-clippy",
            "cargo clippy",
            "cargo",
            _LINT,
            _PROJECT,
            ("rust",),
            (".rs",),
            "cargo clippy",
        )
    ),
    # -- C / C++ ----------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "clangd",
            "clangd",
            "clangd",
            _LS,
            _PROJECT,
            ("cpp",),
            (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
            "clangd",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "clang-tidy",
            "clang-tidy",
            "clang-tidy",
            _STATIC,
            _PROJECT,
            ("cpp",),
            (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
            "clang-tidy",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "cppcheck",
            "cppcheck",
            "cppcheck",
            _STATIC,
            _PROJECT,
            ("cpp",),
            (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
            "cppcheck",
        )
    ),
    # -- Assembler --------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "nasm",
            "nasm",
            "nasm",
            _COMPILER,
            _CURRENT,
            ("asm",),
            (".asm", ".nasm"),
            "nasm",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "yasm", "yasm", "yasm", _COMPILER, _CURRENT, ("asm",), (".asm",), "yasm"
        )
    ),
    _planned(
        PlannedProviderSpec(
            "gas",
            "GNU as / GAS",
            "as",
            _COMPILER,
            _CURRENT,
            ("asm",),
            (".s", ".S"),
            "GNU as/GAS",
        )
    ),
    # -- Java -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "jdtls",
            "Eclipse JDT LS",
            "jdtls",
            _LS,
            _PROJECT,
            ("java",),
            (".java",),
            "JDT LS",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "checkstyle",
            "Checkstyle",
            "checkstyle",
            _LINT,
            _PROJECT,
            ("java",),
            (".java",),
            "Checkstyle",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "pmd", "PMD", "pmd", _STATIC, _PROJECT, ("java",), (".java",), "PMD"
        )
    ),
    _planned(
        PlannedProviderSpec(
            "spotbugs",
            "SpotBugs",
            "spotbugs",
            _STATIC,
            _PROJECT,
            ("java",),
            (".java",),
            "SpotBugs",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "maven-gradle",
            "Maven/Gradle diagnostics",
            "mvn",
            _BUILD,
            _PROJECT,
            ("java",),
            (".java",),
            "Maven/Gradle diagnostics",
        )
    ),
    # -- PHP --------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "phpstan",
            "PHPStan",
            "phpstan",
            _STATIC,
            _PROJECT,
            ("php",),
            (".php",),
            "PHPStan",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "psalm", "Psalm", "psalm", _STATIC, _PROJECT, ("php",), (".php",), "Psalm"
        )
    ),
    _planned(
        PlannedProviderSpec(
            "phpcs",
            "PHP_CodeSniffer",
            "phpcs",
            _LINT,
            _PROJECT,
            ("php",),
            (".php",),
            "PHP_CodeSniffer",
        )
    ),
    # -- JavaScript / TypeScript / TSX ------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "biome-js",
            "Biome",
            "biome",
            _LINT,
            _PROJECT,
            ("javascript",),
            (".js", ".jsx", ".mjs", ".cjs"),
            "Biome",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "eslint-js",
            "ESLint",
            "eslint",
            _LINT,
            _PROJECT,
            ("javascript",),
            (".js", ".jsx", ".mjs", ".cjs"),
            "ESLint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "biome-ts",
            "Biome",
            "biome",
            _LINT,
            _PROJECT,
            ("typescript",),
            (".ts",),
            "Biome",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "eslint-ts",
            "ESLint",
            "eslint",
            _LINT,
            _PROJECT,
            ("typescript",),
            (".ts",),
            "ESLint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "biome-tsx",
            "Biome",
            "biome",
            _LINT,
            _PROJECT,
            ("typescriptreact",),
            (".tsx",),
            "Biome",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "eslint-tsx",
            "ESLint",
            "eslint",
            _LINT,
            _PROJECT,
            ("typescriptreact",),
            (".tsx",),
            "ESLint",
        )
    ),
    # -- CSS / SCSS / LESS ------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "stylelint",
            "Stylelint",
            "stylelint",
            _LINT,
            _PROJECT,
            ("css",),
            (".css", ".scss", ".less"),
            "Stylelint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "biome-css",
            "Biome",
            "biome",
            _FORMAT,
            _PROJECT,
            ("css",),
            (".css",),
            "Biome",
        )
    ),
    # -- JSON -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "biome-json",
            "Biome",
            "biome",
            _LINT,
            _PROJECT,
            ("json",),
            (".json",),
            "Biome",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "json-schema",
            "JSON schema diagnostics",
            "json-schema",
            _SCHEMA,
            _WORKSPACE,
            ("json",),
            (".json",),
            "JSON schema diagnostics",
        )
    ),
    # -- TOML -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "taplo",
            "Taplo",
            "taplo",
            _FORMAT,
            _WORKSPACE,
            ("toml",),
            (".toml",),
            "Taplo",
        )
    ),
    # -- YAML -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "yamllint",
            "yamllint",
            "yamllint",
            _LINT,
            _WORKSPACE,
            ("yaml",),
            (".yaml", ".yml"),
            "yamllint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "yaml-schema",
            "YAML schema diagnostics",
            "yaml-schema",
            _SCHEMA,
            _WORKSPACE,
            ("yaml",),
            (".yaml", ".yml"),
            "YAML schema diagnostics",
        )
    ),
    # -- Dockerfile -------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "hadolint",
            "Hadolint",
            "hadolint",
            _LINT,
            _CURRENT,
            ("dockerfile",),
            (".dockerfile",),
            "Hadolint",
        )
    ),
    # -- Shell ------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "shellcheck",
            "ShellCheck",
            "shellcheck",
            _LINT,
            _CURRENT,
            ("shell",),
            (".sh", ".bash", ".zsh", ".ksh"),
            "ShellCheck",
        )
    ),
    # -- Markdown ---------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "markdownlint",
            "markdownlint",
            "markdownlint",
            _LINT,
            _CURRENT,
            ("markdown",),
            (".md", ".markdown"),
            "markdownlint",
        )
    ),
    # -- SQL --------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "sqlfluff",
            "SQLFluff",
            "sqlfluff",
            _LINT,
            _WORKSPACE,
            ("sql",),
            (".sql",),
            "SQLFluff",
        )
    ),
    # -- Terraform / HCL --------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "tflint",
            "TFLint",
            "tflint",
            _LINT,
            _PROJECT,
            ("terraform",),
            (".tf", ".tfvars"),
            "TFLint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "terraform-validate",
            "terraform validate",
            "terraform",
            _SCHEMA,
            _PROJECT,
            ("terraform",),
            (".tf",),
            "terraform validate",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "tflint-hcl",
            "TFLint",
            "tflint",
            _LINT,
            _PROJECT,
            ("hcl",),
            (".hcl",),
            "TFLint",
        )
    ),
    # -- Kubernetes / Helm ------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "kubeconform",
            "kubeconform",
            "kubeconform",
            _SCHEMA,
            _PROJECT,
            ("kubernetes",),
            (),
            "kubeconform",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "helm-lint",
            "helm lint",
            "helm",
            _LINT,
            _PROJECT,
            ("helm",),
            (),
            "helm lint",
        )
    ),
    # -- Makefile ---------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "checkmake",
            "checkmake",
            "checkmake",
            _LINT,
            _CURRENT,
            ("makefile",),
            (".mk",),
            "checkmake",
        )
    ),
    # -- CMake ------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "cmakelint",
            "cmakelint",
            "cmakelint",
            _LINT,
            _CURRENT,
            ("cmake",),
            (".cmake",),
            "cmakelint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "cmake-configure",
            "cmake configure diagnostics",
            "cmake",
            _BUILD,
            _PROJECT,
            ("cmake",),
            (".cmake",),
            "cmake configure diagnostics",
        )
    ),
    # -- Ruby -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "rubocop",
            "RuboCop",
            "rubocop",
            _LINT,
            _PROJECT,
            ("ruby",),
            (".rb",),
            "RuboCop",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "reek", "Reek", "reek", _STATIC, _PROJECT, ("ruby",), (".rb",), "Reek"
        )
    ),
    _planned(
        PlannedProviderSpec(
            "brakeman",
            "Brakeman",
            "brakeman",
            _STATIC,
            _PROJECT,
            ("ruby",),
            (".rb",),
            "Brakeman",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "erb_lint",
            "erb_lint",
            "erb_lint",
            _LINT,
            _PROJECT,
            ("ruby",),
            (".erb",),
            "erb_lint",
        )
    ),
    # -- Elixir ------------------------------------------------------------ #
    _planned(
        PlannedProviderSpec(
            "credo",
            "Credo",
            "credo",
            _LINT,
            _PROJECT,
            ("elixir",),
            (".ex", ".exs"),
            "Credo",
        )
    ),
    # -- Dart -------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "dart-analyzer",
            "Dart analyzer",
            "dart",
            _STATIC,
            _PROJECT,
            ("dart",),
            (".dart",),
            "Dart analyzer",
        )
    ),
    # -- Lua --------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "luacheck",
            "Luacheck",
            "luacheck",
            _LINT,
            _CURRENT,
            ("lua",),
            (".lua",),
            "Luacheck",
        )
    ),
    # -- Swift ------------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "swiftlint",
            "swiftlint",
            "swiftlint",
            _LINT,
            _PROJECT,
            ("swift",),
            (".swift",),
            "swiftlint",
        )
    ),
    # -- Text / prose ------------------------------------------------------ #
    _planned(
        PlannedProviderSpec(
            "languagetool",
            "LanguageTool",
            "languagetool",
            _LINT,
            _WORKSPACE,
            ("text",),
            (".txt",),
            "LanguageTool",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "proselint",
            "proselint",
            "proselint",
            _LINT,
            _CURRENT,
            ("text",),
            (".txt",),
            "proselint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "textlint",
            "textlint",
            "textlint",
            _LINT,
            _WORKSPACE,
            ("text",),
            (".txt",),
            "textlint",
        )
    ),
    _planned(
        PlannedProviderSpec(
            "vale", "Vale", "vale", _LINT, _WORKSPACE, ("text",), (".txt",), "Vale"
        )
    ),
    # -- Gherkin ----------------------------------------------------------- #
    _planned(
        PlannedProviderSpec(
            "gherkin-lint",
            "gherkin-lint",
            "gherkin-lint",
            _LINT,
            _CURRENT,
            ("gherkin",),
            (".feature",),
            "gherkin-lint",
        )
    ),
)


# SonarQube / SonarCloud is a project-quality provider. It does NOT run during
# F4 rendering: no scanner, no network, no token, no server URL. Future modes are
# cached/manual project scans, surfaced via System Doctor and explicit actions.
SONARQUBE_PROVIDER = ProviderMetadata(
    id="sonarqube",
    display_name="SonarQube / SonarCloud",
    tool_name="sonar-scanner",
    category=ProviderCategory.PROJECT_QUALITY,
    execution_mode=ProviderExecutionMode.CACHED_EXTERNAL,
    status=ProviderStatus.PLANNED,
    language_ids=(),
    extensions=(),
    executable="sonar-scanner",
    docs_url="https://docs.sonarsource.com/",
    short_label="SonarQube",
    runnable_in_build=False,
    summary_lines=(
        "SonarQube project-quality provider is planned.",
        "Future mode: cached/manual project scan, not per-render linting.",
    ),
)


# Human-readable language labels used in panel messages. Defaults to a
# title-cased language id; overrides match the product spec wording exactly.
LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "rust": "Rust",
    "cpp": "C/C++",
    "asm": "assembler",
    "java": "Java",
    "php": "PHP",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "typescriptreact": "TSX",
    "css": "CSS",
    "json": "JSON",
    "toml": "TOML",
    "yaml": "YAML",
    "dockerfile": "Dockerfile",
    "shell": "shell scripts",
    "markdown": "Markdown",
    "sql": "SQL",
    "terraform": "Terraform",
    "hcl": "HCL",
    "kubernetes": "Kubernetes",
    "helm": "Helm",
    "makefile": "Makefile",
    "cmake": "CMake",
    "ruby": "Ruby",
    "elixir": "Elixir",
    "dart": "Dart",
    "lua": "Lua",
    "swift": "Swift",
    "text": "text",
    "gherkin": "Gherkin",
}


# Special-file detection where the file name (not the extension) is meaningful.
FILENAME_LANGUAGE: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "cmakelists.txt": "cmake",
}


# Per-language overrides for the planned summary line (exact product wording).
PLANNED_NOTE_OVERRIDES: dict[str, str] = {
    "asm": "Planned providers depend on syntax: nasm, yasm, GNU as/GAS.",
}
