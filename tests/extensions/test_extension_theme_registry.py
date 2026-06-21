# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extension_theme_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the extension-backed theme registry."""

from __future__ import annotations

import inspect

from ecli.extensions.ecli_integration import (
    TARGET_THEME_NUMBERS,
    ThemeRegistry,
    build_theme_registry,
    theme_registry as theme_registry_module,
)
from ecli.utils.themes import get_theme, resolve_theme


def test_theme_registry_loads_real_contributed_themes() -> None:
    registry = build_theme_registry()
    assert isinstance(registry, ThemeRegistry)
    names = {theme.name for theme in registry.list_available_extension_themes()}
    assert {"Dark+", "Light+", "Monokai", "Quiet Light"} <= names


def test_professional_theme_numbers_are_source_of_truth() -> None:
    registry = build_theme_registry()
    expected = {
        104: "Visual Studio Light",
        106: "Light Modern",
        107: "Light+",
        108: "Quiet Light",
        109: "Solarized Light",
        204: "Visual Studio Dark",
        206: "Dark Modern",
        207: "Dark+",
        208: "Monokai",
        209: "Monokai Dimmed",
        210: "Tomorrow Night Blue",
        211: "Abyss",
        213: "Kimbie Dark",
        214: "Solarized Dark",
        215: "Red",
        301: "Dark High Contrast",
        304: "Light High Contrast",
    }
    for theme_id, name in expected.items():
        theme = registry.get_theme(theme_id)
        assert theme is not None, (theme_id, name)
        assert theme.name == name
        assert theme.token_colors


def test_missing_target_themes_are_diagnosed_not_faked() -> None:
    registry = build_theme_registry()
    missing = registry.missing_target_names()
    assert "GitHub Dark" in missing
    assert "Atom One Dark" in missing
    assert registry.get_theme(202) is None
    assert registry.get_theme(212) is None
    assert any("GitHub Dark" in d.message for d in registry.list_diagnostics())


def test_theme_jsonc_and_includes_are_resolved() -> None:
    dark_plus = build_theme_registry().get_theme(207)
    assert dark_plus is not None
    # dark_plus.json includes dark_vs.json; the merged result therefore has both
    # base editor colours and Dark+-specific token rules.
    assert dark_plus.colors["editor.background"] == "#1E1E1E"
    assert dark_plus.resolve_token_style("source entity.name.function").foreground


def test_token_color_matching_prefers_specific_scope() -> None:
    dark_plus = build_theme_registry().get_theme(207)
    assert dark_plus is not None
    generic = dark_plus.resolve_token_style("source keyword")
    specific = dark_plus.resolve_token_style("source keyword.control")
    assert generic.foreground is not None
    assert specific.foreground is not None
    assert specific.specificity >= generic.specificity


def test_utils_theme_resolution_uses_extension_theme_colours() -> None:
    palette = resolve_theme({"theme": 207})
    assert palette.theme_id == 207
    assert palette.name == "Dark+"
    assert palette.background == "#1E1E1E"
    # Comes from the imported theme's tokenColors, not a hand-maintained ECLI
    # bright palette.
    assert palette.keyword == "#C586C0"
    assert palette.comment == "#6A9955"


def test_kimbie_dark_uses_imported_theme_json() -> None:
    registry = build_theme_registry()
    theme = registry.get_theme(213)
    assert theme is not None
    assert theme.name == "Kimbie Dark"
    assert theme.path_repo_relative.endswith(
        "theme-kimbie-dark/themes/kimbie-dark-color-theme.json"
    )
    palette = resolve_theme({"theme": 213})
    assert palette.name == "Kimbie Dark"
    assert palette.background == theme.colors["editor.background"]
    assert palette.string != palette.keyword


def test_markdown_roles_do_not_collapse_under_kimbie_dark() -> None:
    palette = resolve_theme({"theme": 213})
    markdown_roles = {
        palette.function,
        palette.type_,
        palette.string,
        palette.comment,
        palette.operator,
    }
    assert len(markdown_roles) >= 4
    assert palette.comment not in {palette.keyword, palette.string}


def test_light_modern_readability_roles_are_distinct() -> None:
    palette = resolve_theme({"theme": 106})
    assert palette.name == "Light Modern"
    assert palette.background == "#FFFFFF"
    assert palette.foreground != palette.background
    assert palette.comment != palette.foreground
    assert palette.keyword != palette.string


def test_builtin_compatibility_themes_remain_available() -> None:
    assert get_theme(181).name == "PySH Light"
    assert get_theme(281).name == "PySH Dark"
    assert get_theme(382).name == "ECLI High Contrast Dark"


def test_invalid_theme_number_reports_diagnostic() -> None:
    palette = resolve_theme({"theme": 202})
    assert palette.theme_id == 207
    assert palette.diagnostics
    assert "Invalid theme" in palette.diagnostics[-1]


def test_numbering_policy_ranges_are_enforced() -> None:
    registry = build_theme_registry()
    for number, name in TARGET_THEME_NUMBERS.items():
        theme = registry.get_theme(number)
        if theme is None:
            continue
        assert theme.name == name
        if 100 <= number <= 199:
            assert theme.theme_type == "light"
        elif 200 <= number <= 299:
            assert theme.theme_type == "dark"
        elif 300 <= number <= 399:
            assert theme.theme_type == "high-contrast"
        else:  # pragma: no cover - protects future contract edits
            raise AssertionError(f"unexpected theme range: {number}")


def test_reserved_custom_theme_range_is_not_silently_assigned() -> None:
    registry = build_theme_registry()
    assert all(
        theme.number is None or not 800 <= theme.number <= 899
        for theme in registry.themes
    )
    assert resolve_theme({"theme": 800}).theme_id == 207


def test_theme_registry_has_no_execution_primitives() -> None:
    source = inspect.getsource(theme_registry_module)
    for token in (
        "subprocess",
        "os.system",
        "os.popen",
        "pty.",
        "eval(",
        "exec(",
        "__import__(",
    ):
        assert token not in source, f"theme_registry must not reference {token!r}"
