# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the diagnostics provider registry and planned catalog (#104)."""

from __future__ import annotations

import pytest

from ecli.extensions.ecli_integration.diagnostics import (
    ProviderCategory,
    ProviderStatus,
    build_default_registry,
)


REGISTRY = build_default_registry()


# --------------------------------------------------------------------------- #
# Active provider: Ruff for Python.
# --------------------------------------------------------------------------- #


def test_ruff_is_the_active_provider_for_python() -> None:
    assert REGISTRY.active_provider_for("a.py") is not None
    assert REGISTRY.active_provider_for("a.pyi") is not None
    ruff = REGISTRY.find("ruff")
    assert ruff is not None
    assert ruff.status is ProviderStatus.SUPPORTED_EXTERNAL
    assert ruff.category is ProviderCategory.LINT
    assert ruff.is_active is True
    assert ruff.is_planned is False
    assert "python" in ruff.language_ids


def test_no_active_provider_for_non_python_languages() -> None:
    for path in ("a.java", "a.rs", "a.php", "a.css", "a.tsx", "a.json"):
        assert REGISTRY.active_provider_for(path) is None


# --------------------------------------------------------------------------- #
# Planned provider catalog: id -> (category, language).
# --------------------------------------------------------------------------- #

_PLANNED_MATRIX = [
    ("mypy", ProviderCategory.TYPECHECK, "python"),
    ("pylint", ProviderCategory.LINT, "python"),
    ("rust-analyzer", ProviderCategory.LANGUAGE_SERVER, "rust"),
    ("cargo-check", ProviderCategory.COMPILER, "rust"),
    ("cargo-clippy", ProviderCategory.LINT, "rust"),
    ("clangd", ProviderCategory.LANGUAGE_SERVER, "cpp"),
    ("clang-tidy", ProviderCategory.STATIC_ANALYSIS, "cpp"),
    ("cppcheck", ProviderCategory.STATIC_ANALYSIS, "cpp"),
    ("nasm", ProviderCategory.COMPILER, "asm"),
    ("yasm", ProviderCategory.COMPILER, "asm"),
    ("gas", ProviderCategory.COMPILER, "asm"),
    ("jdtls", ProviderCategory.LANGUAGE_SERVER, "java"),
    ("checkstyle", ProviderCategory.LINT, "java"),
    ("pmd", ProviderCategory.STATIC_ANALYSIS, "java"),
    ("spotbugs", ProviderCategory.STATIC_ANALYSIS, "java"),
    ("maven-gradle", ProviderCategory.BUILD_DIAGNOSTICS, "java"),
    ("phpstan", ProviderCategory.STATIC_ANALYSIS, "php"),
    ("psalm", ProviderCategory.STATIC_ANALYSIS, "php"),
    ("phpcs", ProviderCategory.LINT, "php"),
    ("biome-js", ProviderCategory.LINT, "javascript"),
    ("eslint-js", ProviderCategory.LINT, "javascript"),
    ("biome-ts", ProviderCategory.LINT, "typescript"),
    ("eslint-ts", ProviderCategory.LINT, "typescript"),
    ("biome-tsx", ProviderCategory.LINT, "typescriptreact"),
    ("eslint-tsx", ProviderCategory.LINT, "typescriptreact"),
    ("stylelint", ProviderCategory.LINT, "css"),
    ("biome-css", ProviderCategory.FORMAT_CHECK, "css"),
    ("biome-json", ProviderCategory.LINT, "json"),
    ("json-schema", ProviderCategory.SCHEMA, "json"),
    ("taplo", ProviderCategory.FORMAT_CHECK, "toml"),
    ("yamllint", ProviderCategory.LINT, "yaml"),
    ("yaml-schema", ProviderCategory.SCHEMA, "yaml"),
    ("hadolint", ProviderCategory.LINT, "dockerfile"),
    ("shellcheck", ProviderCategory.LINT, "shell"),
    ("markdownlint", ProviderCategory.LINT, "markdown"),
    ("sqlfluff", ProviderCategory.LINT, "sql"),
    ("tflint", ProviderCategory.LINT, "terraform"),
    ("terraform-validate", ProviderCategory.SCHEMA, "terraform"),
    ("tflint-hcl", ProviderCategory.LINT, "hcl"),
    ("kubeconform", ProviderCategory.SCHEMA, "kubernetes"),
    ("helm-lint", ProviderCategory.LINT, "helm"),
    ("checkmake", ProviderCategory.LINT, "makefile"),
    ("cmakelint", ProviderCategory.LINT, "cmake"),
    ("cmake-configure", ProviderCategory.BUILD_DIAGNOSTICS, "cmake"),
    ("rubocop", ProviderCategory.LINT, "ruby"),
    ("reek", ProviderCategory.STATIC_ANALYSIS, "ruby"),
    ("brakeman", ProviderCategory.STATIC_ANALYSIS, "ruby"),
    ("erb_lint", ProviderCategory.LINT, "ruby"),
    ("credo", ProviderCategory.LINT, "elixir"),
    ("dart-analyzer", ProviderCategory.STATIC_ANALYSIS, "dart"),
    ("luacheck", ProviderCategory.LINT, "lua"),
    ("swiftlint", ProviderCategory.LINT, "swift"),
    ("languagetool", ProviderCategory.LINT, "text"),
    ("proselint", ProviderCategory.LINT, "text"),
    ("textlint", ProviderCategory.LINT, "text"),
    ("vale", ProviderCategory.LINT, "text"),
    ("gherkin-lint", ProviderCategory.LINT, "gherkin"),
]


@pytest.mark.parametrize(("provider_id", "category", "language"), _PLANNED_MATRIX)
def test_planned_provider_metadata(
    provider_id: str, category: ProviderCategory, language: str
) -> None:
    metadata = REGISTRY.find(provider_id)
    assert metadata is not None, provider_id
    assert metadata.status is ProviderStatus.PLANNED
    assert metadata.is_planned is True
    assert metadata.is_active is False
    assert metadata.category is category
    assert language in metadata.language_ids
    assert metadata.tool_name  # wraps an external tool, no custom engine


# --------------------------------------------------------------------------- #
# Matching by language id and extension.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("language", "expected_ids"),
    [
        ("rust", {"rust-analyzer", "cargo-check", "cargo-clippy"}),
        ("cpp", {"clangd", "clang-tidy", "cppcheck"}),
        ("java", {"jdtls", "checkstyle", "pmd", "spotbugs", "maven-gradle"}),
        ("php", {"phpstan", "psalm", "phpcs"}),
        ("typescriptreact", {"biome-tsx", "eslint-tsx"}),
        ("shell", {"shellcheck"}),
        ("toml", {"taplo"}),
    ],
)
def test_planned_lookup_by_language(language: str, expected_ids: set[str]) -> None:
    assert {m.id for m in REGISTRY.planned_for_language(language)} == expected_ids


@pytest.mark.parametrize(
    ("extension", "expected_ids"),
    [
        (".php", {"phpstan", "psalm", "phpcs"}),
        (".rs", {"rust-analyzer", "cargo-check", "cargo-clippy"}),
        (".tsx", {"biome-tsx", "eslint-tsx"}),
        (".toml", {"taplo"}),
    ],
)
def test_planned_lookup_by_extension(extension: str, expected_ids: set[str]) -> None:
    assert {m.id for m in REGISTRY.planned_for_extension(extension)} == expected_ids


def test_active_lookup_by_extension_and_language() -> None:
    assert REGISTRY.active_metadata_for_extension(".py")[0].id == "ruff"
    assert REGISTRY.active_metadata_for_language("python")[0].id == "ruff"
    assert REGISTRY.active_metadata_for_extension(".java") == ()


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("x.py", "python"),
        ("x.java", "java"),
        ("x.c", "cpp"),
        ("x.hpp", "cpp"),
        ("Dockerfile", "dockerfile"),
        ("CMakeLists.txt", "cmake"),
        ("Makefile", "makefile"),
        ("x.tsx", "typescriptreact"),
    ],
)
def test_language_resolution(path: str, language: str) -> None:
    assert REGISTRY.language_for(path) == language


# --------------------------------------------------------------------------- #
# Active vs planned distinction + project quality.
# --------------------------------------------------------------------------- #


def test_active_provider_missing_is_distinct_from_planned() -> None:
    ruff = REGISTRY.find("ruff")
    mypy = REGISTRY.find("mypy")
    assert ruff is not None and mypy is not None
    # Ruff is an active provider whose tool may be missing; mypy is only planned.
    assert ruff.is_active and not ruff.is_planned
    assert mypy.is_planned and not mypy.is_active


def test_sonarqube_is_a_planned_project_quality_provider() -> None:
    sonar = REGISTRY.find("sonarqube")
    assert sonar is not None
    assert sonar.category is ProviderCategory.PROJECT_QUALITY
    assert sonar.status is ProviderStatus.PLANNED
    assert sonar in REGISTRY.project_quality_providers()
    # It is not offered as a per-file active provider.
    assert REGISTRY.active_provider_for("a.py") is not REGISTRY.find("sonarqube")
