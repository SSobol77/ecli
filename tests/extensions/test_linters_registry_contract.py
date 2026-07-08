# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_linters_registry_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the ECLI Linter Pack registry (``ecli.extensions.linters``).

This is the successor to the retired ``tests/core/test_linter_catalog.py``:
the catalog moved from ``src/ecli/diagnostics/linter_catalog.py`` (one
monolithic file) to ``src/ecli/extensions/linters/core/registry.py`` (the
shared ``LinterDefinition``/``PackageContract`` types and generic lookup
helpers) plus one ``manifest.py`` per linter microservice, aggregated by
``src/ecli/extensions/linters/__init__.py``.

This catalog is data only. These tests assert the *shape* and *safety* of
the declared metadata -- not any command execution or output parsing.
Also guards the architectural decision that raw VS Code TypeScript linter
extension source must never live under ``src/ecli/extensions/`` (see
``tests/extensions/test_extensions_tree_contract.py`` for the broader tree
contract).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ecli.extensions.linters import (
    LINTER_CATALOG,
    get_linter,
    iter_linters,
    linters_for_language,
)
from ecli.extensions.linters.core.registry import (
    ALLOWED_INSTALL_GROUPS,
    ALLOWED_PARSERS,
    ALLOWED_TIERS,
    LinterDefinition,
)


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_LINTER_NAMES: frozenset[str] = frozenset(
    {
        "ruff",
        "biome",
        "oxlint",
        "eslint",
        "stylelint",
        "cargo-clippy",
        "zig",
        "clang-tidy",
        "cppcheck",
        "clang-format",
        "checkstyle",
        "pmd",
        "spotbugs",
        "shellcheck",
        "actionlint",
        "hadolint",
        "tflint",
        "sqlfluff",
        "golangci-lint",
        "pylint",
        "markdownlint-cli2",
        "yamllint",
        "taplo",
    }
)

# Executable names that must never appear as `entry.executable`: a linter
# integration must shell out to the actual tool binary, not to the package
# manager that installs it. Toolchain launchers that legitimately front a
# real subcommand (e.g. "cargo clippy") are not package managers and are
# intentionally not in this set.
_BANNED_EXECUTABLES: frozenset[str] = frozenset(
    {"npm", "npx", "pip", "pip3", "apt", "apt-get", "brew", "yum", "dnf"}
)

_SHELL_METACHARACTERS: tuple[str, ...] = ("&&", "||", "|", ";", ">", "<")


def _default_or_recommended(entries: tuple[LinterDefinition, ...]):
    return tuple(
        entry
        for entry in entries
        if entry.enabled_by_default or entry.tier in ("core", "recommended")
    )


_DEFAULT_ENTRIES: tuple[LinterDefinition, ...] = tuple(
    entry for entry in LINTER_CATALOG if entry.enabled_by_default
)

_BUNDLED_ENTRIES: tuple[LinterDefinition, ...] = tuple(
    entry for entry in LINTER_CATALOG if entry.bundled_with_full_install
)


# ---------------------------------------------------------------------------
# 1. Expected linter names
# ---------------------------------------------------------------------------


def test_catalog_contains_expected_linter_names() -> None:
    names = {entry.name for entry in LINTER_CATALOG}
    assert names == EXPECTED_LINTER_NAMES


def test_catalog_contains_biome() -> None:
    assert get_linter("biome").name == "biome"


def test_catalog_contains_zig() -> None:
    assert get_linter("zig").name == "zig"


def test_catalog_contains_the_cpp_first_class_profile() -> None:
    for name in ("clang-tidy", "cppcheck", "clang-format"):
        assert get_linter(name).name == name


def test_catalog_contains_the_java_first_class_profile() -> None:
    for name in ("checkstyle", "pmd", "spotbugs"):
        assert get_linter(name).name == name


def test_get_linter_returns_entry_by_name() -> None:
    for name in EXPECTED_LINTER_NAMES:
        assert get_linter(name).name == name


def test_get_linter_raises_key_error_for_unknown_name() -> None:
    with pytest.raises(KeyError):
        get_linter("not-a-real-linter")


def test_iter_linters_returns_the_full_catalog() -> None:
    assert iter_linters() == LINTER_CATALOG


def test_linters_for_language_finds_python_providers() -> None:
    matches = linters_for_language("python")
    assert any(entry.name == "ruff" for entry in matches)
    assert any(entry.name == "pylint" for entry in matches)


def test_linters_for_language_returns_empty_for_unknown_language() -> None:
    assert linters_for_language("cobol") == ()


# ---------------------------------------------------------------------------
# 2. Non-empty languages or extensions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_entry_has_non_empty_languages_or_extensions(entry: LinterDefinition) -> None:
    assert entry.languages or entry.file_extensions, (
        f"{entry.name} declares neither languages nor file_extensions"
    )


# ---------------------------------------------------------------------------
# 3. Executable name present and never a package manager
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_entry_has_executable_name(entry: LinterDefinition) -> None:
    assert entry.executable
    assert isinstance(entry.executable, str)
    assert entry.executable.strip() == entry.executable


@pytest.mark.parametrize("entry", _DEFAULT_ENTRIES, ids=lambda e: e.name)
def test_default_linter_executable_is_not_a_package_manager(
    entry: LinterDefinition,
) -> None:
    assert entry.executable not in _BANNED_EXECUTABLES, (
        f"{entry.name} declares executable {entry.executable!r}, which is a "
        "package manager, not the linter binary itself"
    )


# ---------------------------------------------------------------------------
# 4 & 5. argv templates are argv lists, never shell strings/syntax
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_argv_template_is_a_tuple_of_plain_tokens(entry: LinterDefinition) -> None:
    assert isinstance(entry.argv_template, tuple)
    assert entry.argv_template, f"{entry.name} has an empty argv_template"
    for token in entry.argv_template:
        assert isinstance(token, str)
        assert token, f"{entry.name} has an empty argv token"


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_argv_template_contains_no_shell_syntax(entry: LinterDefinition) -> None:
    for token in entry.argv_template:
        for meta in _SHELL_METACHARACTERS:
            assert meta not in token, (
                f"{entry.name} argv_template token {token!r} contains shell "
                f"metacharacter {meta!r}"
            )


def test_no_shell_true_anywhere_in_registry_module_source() -> None:
    """Regression guard: the registry module must never gain command execution."""
    source = Path(
        REPO_ROOT / "src" / "ecli" / "extensions" / "linters" / "core" / "registry.py"
    ).read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "import subprocess" not in source
    assert "os.system" not in source


def test_catalog_has_no_raw_shell_commands() -> None:
    """No entry's argv_template is (or contains) a single shell string."""
    for entry in LINTER_CATALOG:
        assert isinstance(entry.argv_template, tuple), (
            f"{entry.name} argv_template must be a tuple, not a shell string"
        )
        for token in entry.argv_template:
            assert " && " not in token
            assert " | " not in token


# ---------------------------------------------------------------------------
# 6. Parser identifiers come from an explicit allow-list
# ---------------------------------------------------------------------------


def test_allowed_parsers_is_non_empty() -> None:
    assert ALLOWED_PARSERS


def test_allowed_parsers_includes_zig_text() -> None:
    assert "zig_text" in ALLOWED_PARSERS


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_entry_parser_is_in_allow_list(entry: LinterDefinition) -> None:
    assert entry.parser in ALLOWED_PARSERS


@pytest.mark.parametrize("entry", _DEFAULT_ENTRIES, ids=lambda e: e.name)
def test_every_default_linter_has_a_parser_identifier(entry: LinterDefinition) -> None:
    """Every default/recommended linter names a parser, even though no
    parser runtime is implemented at this stage.
    """
    assert entry.parser
    assert entry.parser in ALLOWED_PARSERS


def test_definition_rejects_unknown_parser_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown parser"):
        LinterDefinition(
            name="fake",
            display_name="Fake",
            languages=("fakelang",),
            file_extensions=(".fake",),
            executable="fake-linter",
            argv_template=("fake-linter", "{file}"),
            stdin_mode="unsupported",
            parser="not_a_real_parser",  # type: ignore[arg-type]
            config_files=(),
            capabilities=("lint",),
            tier="optional",
            install_group="language",
            install_hint="n/a",
            homepage_url="https://example.invalid/",
        )


def test_definition_rejects_unknown_tier_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown tier"):
        LinterDefinition(
            name="fake",
            display_name="Fake",
            languages=("fakelang",),
            file_extensions=(".fake",),
            executable="fake-linter",
            argv_template=("fake-linter", "{file}"),
            stdin_mode="unsupported",
            parser="text_lines",
            config_files=(),
            capabilities=("lint",),
            tier="not_a_real_tier",  # type: ignore[arg-type]
            install_group="language",
            install_hint="n/a",
            homepage_url="https://example.invalid/",
        )


def test_definition_rejects_unknown_install_group_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown install_group"):
        LinterDefinition(
            name="fake",
            display_name="Fake",
            languages=("fakelang",),
            file_extensions=(".fake",),
            executable="fake-linter",
            argv_template=("fake-linter", "{file}"),
            stdin_mode="unsupported",
            parser="text_lines",
            config_files=(),
            capabilities=("lint",),
            tier="optional",
            install_group="not_a_real_group",  # type: ignore[arg-type]
            install_hint="n/a",
            homepage_url="https://example.invalid/",
        )


def test_definition_rejects_unknown_provider_kind_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown provider_kind"):
        LinterDefinition(
            name="fake",
            display_name="Fake",
            languages=("fakelang",),
            file_extensions=(".fake",),
            executable="fake-linter",
            argv_template=("fake-linter", "{file}"),
            stdin_mode="unsupported",
            parser="text_lines",
            config_files=(),
            capabilities=("lint",),
            tier="optional",
            install_group="language",
            install_hint="n/a",
            homepage_url="https://example.invalid/",
            provider_kind="not_a_real_kind",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# 7. Tiers and install groups are limited to the allowed sets
# ---------------------------------------------------------------------------


def test_allowed_tiers_is_exactly_the_documented_set() -> None:
    assert ALLOWED_TIERS == {"core", "recommended", "optional", "legacy"}


def test_allowed_install_groups_is_exactly_the_documented_set() -> None:
    assert ALLOWED_INSTALL_GROUPS == {
        "core",
        "web",
        "systems",
        "devops",
        "data",
        "infra",
        "language",
        "prose",
    }


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_entry_tier_is_in_allow_list(entry: LinterDefinition) -> None:
    assert entry.tier in ALLOWED_TIERS


@pytest.mark.parametrize("entry", LINTER_CATALOG, ids=lambda e: e.name)
def test_entry_install_group_is_in_allow_list(entry: LinterDefinition) -> None:
    assert entry.install_group in ALLOWED_INSTALL_GROUPS


# ---------------------------------------------------------------------------
# 8. Curated-pack metadata: install hints, homepage URLs, install groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry", _default_or_recommended(LINTER_CATALOG), ids=lambda e: e.name
)
def test_default_or_recommended_linters_have_install_hint_and_homepage(
    entry: LinterDefinition,
) -> None:
    assert entry.install_hint.strip(), f"{entry.name} has an empty install_hint"
    assert entry.homepage_url.strip(), f"{entry.name} has an empty homepage_url"
    assert entry.homepage_url.startswith("https://"), (
        f"{entry.name} homepage_url {entry.homepage_url!r} is not https://"
    )


@pytest.mark.parametrize("entry", _BUNDLED_ENTRIES, ids=lambda e: e.name)
def test_bundled_with_full_install_linters_have_an_install_group(
    entry: LinterDefinition,
) -> None:
    assert entry.install_group in ALLOWED_INSTALL_GROUPS


# ---------------------------------------------------------------------------
# 9. Modern default-enablement decisions
# ---------------------------------------------------------------------------


def test_default_js_ts_linter_is_biome_not_eslint() -> None:
    for language in ("javascript", "typescript"):
        defaults = [
            entry.name
            for entry in linters_for_language(language)
            if entry.enabled_by_default
        ]
        assert defaults == ["biome"], (
            f"expected only biome enabled by default for {language!r}, got {defaults}"
        )


def test_eslint_is_legacy_optional_and_not_enabled_by_default() -> None:
    entry = get_linter("eslint")
    assert entry.tier == "legacy"
    assert entry.enabled_by_default is False


def test_pylint_is_optional_and_not_enabled_by_default() -> None:
    entry = get_linter("pylint")
    assert entry.tier == "optional"
    assert entry.enabled_by_default is False


def test_stylelint_is_optional_and_not_enabled_by_default() -> None:
    entry = get_linter("stylelint")
    assert entry.tier == "optional"
    assert entry.enabled_by_default is False


def test_oxlint_is_optional_secondary_and_not_enabled_by_default() -> None:
    entry = get_linter("oxlint")
    assert entry.tier == "optional"
    assert entry.enabled_by_default is False


def test_biome_supersedes_eslint_and_stylelint() -> None:
    entry = get_linter("biome")
    assert "eslint" in entry.supersedes
    assert "stylelint" in entry.supersedes


def test_ruff_is_internal_core_and_not_replaced_by_pylint() -> None:
    ruff = get_linter("ruff")
    pylint = get_linter("pylint")
    assert ruff.provider_kind == "internal"
    assert ruff.tier == "core"
    assert ruff.enabled_by_default is True
    assert pylint.enabled_by_default is False
    python_defaults = [
        entry.name
        for entry in linters_for_language("python")
        if entry.enabled_by_default
    ]
    assert python_defaults == ["ruff"]


# ---------------------------------------------------------------------------
# 10. Zig entry requirements
# ---------------------------------------------------------------------------


def test_zig_entry_supports_language_and_extension() -> None:
    entry = get_linter("zig")
    assert "zig" in entry.languages
    assert ".zig" in entry.file_extensions


def test_zig_executable_is_zig() -> None:
    assert get_linter("zig").executable == "zig"


def test_zig_argv_template_is_argv_tuple_with_no_shell_syntax() -> None:
    entry = get_linter("zig")
    assert isinstance(entry.argv_template, tuple)
    for token in entry.argv_template:
        for meta in _SHELL_METACHARACTERS:
            assert meta not in token


def test_zig_command_template_uses_fmt_check_ast_check() -> None:
    entry = get_linter("zig")
    assert "fmt" in entry.argv_template
    assert "--check" in entry.argv_template
    assert "--ast-check" in entry.argv_template


def test_zig_has_install_hint_and_homepage_url() -> None:
    entry = get_linter("zig")
    assert entry.install_hint.strip()
    assert entry.homepage_url == "https://ziglang.org/"


def test_zig_is_bundled_with_full_install_and_systems_group() -> None:
    entry = get_linter("zig")
    assert entry.bundled_with_full_install is True
    assert entry.install_group == "systems"
    assert entry.enabled_by_default is True


# ---------------------------------------------------------------------------
# 11. C/C++ and Java first-class profile requirements
# ---------------------------------------------------------------------------


def test_cpp_profile_is_recommended_and_bundled() -> None:
    for name in ("clang-tidy", "cppcheck", "clang-format"):
        entry = get_linter(name)
        assert entry.tier == "recommended"
        assert entry.install_group == "systems"
        assert entry.bundled_with_full_install is True
        assert entry.install_hint.strip()
        assert entry.homepage_url.startswith("https://")


def test_java_profile_is_recommended_and_bundled() -> None:
    for name in ("checkstyle", "pmd", "spotbugs"):
        entry = get_linter(name)
        assert entry.tier == "recommended"
        assert entry.install_group == "language"
        assert entry.bundled_with_full_install is True
        assert entry.install_hint.strip()
        assert entry.homepage_url.startswith("https://")


def test_clang_format_never_implies_mutating_capability() -> None:
    """Design doc section 11.3: clang-format must never rewrite files during
    F4 diagnostics, so its capability set must not claim "fix".
    """
    entry = get_linter("clang-format")
    assert entry.capabilities == ("lint",)
    assert "--dry-run" in entry.argv_template
