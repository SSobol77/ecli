# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/theme_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Extension-backed VS Code/TextMate theme registry.

This module is ECLI-owned adapter code over the imported extension asset tree.
It discovers ``contributes.themes`` metadata, reads referenced JSON/JSONC theme
files, resolves local ``include`` chains, and exposes deterministic theme and
TextMate token-colour data. It never executes extension code, activation events,
``package.json`` scripts, Node, npm, or any command.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import paths
from .manifest import RegistryDiagnostic, ThemeContribution
from .registry import ExtensionRegistry, build_registry


_SOURCE = "theme_registry"

_TARGET_THEME_NUMBERS: tuple[tuple[int, str], ...] = (
    (101, "GitHub Light Default"),
    (102, "GitHub Light"),
    (103, "GitHub Light Colorblind (Beta)"),
    (104, "Visual Studio Light"),
    (105, "Visual Studio 2017 Light - C++"),
    (106, "Light Modern"),
    (107, "Light+"),
    (108, "Quiet Light"),
    (109, "Solarized Light"),
    (110, "JetBrains Rider New UI Light"),
    (201, "GitHub Dark Default"),
    (202, "GitHub Dark"),
    (203, "GitHub Dark Dimmed"),
    (204, "Visual Studio Dark"),
    (205, "Visual Studio 2017 Dark - C++"),
    (206, "Dark Modern"),
    (207, "Dark+"),
    (208, "Monokai"),
    (209, "Monokai Dimmed"),
    (210, "Tomorrow Night Blue"),
    (211, "Abyss"),
    (212, "Atom One Dark"),
    (213, "Kimbie Dark"),
    (214, "Solarized Dark"),
    (215, "Red"),
    (301, "Dark High Contrast"),
    (302, "GitHub Dark High Contrast"),
    (303, "GitHub Light High Contrast"),
    (304, "Light High Contrast"),
)

TARGET_THEME_NAMES: tuple[str, ...] = tuple(
    name for _number, name in _TARGET_THEME_NUMBERS
)
TARGET_THEME_NUMBERS: Mapping[int, str] = dict(_TARGET_THEME_NUMBERS)
THEME_NUMBERING_POLICY: Mapping[str, str] = {
    "deprecated_aliases": "1-8",
    "light": "100-199",
    "dark": "200-299",
    "high_contrast": "300-399",
    "reserved_custom_imported": "800-899",
}


@dataclass(frozen=True)
class TextMateTokenColor:
    """A normalized ``tokenColors`` rule from a VS Code theme file."""

    scope_selectors: tuple[str, ...]
    foreground: str | None
    font_style: tuple[str, ...] = ()
    name: str | None = None
    rule_index: int = 0


@dataclass(frozen=True)
class TextMateResolvedStyle:
    """Resolved TextMate style for one scope stack."""

    foreground: str | None
    font_style: tuple[str, ...] = ()
    matched_selector: str | None = None
    specificity: int = -1
    rule_index: int = -1


@dataclass(frozen=True)
class ExtensionTheme:
    """Loaded, data-only VS Code colour theme."""

    number: int | None
    name: str
    source_id: str | None
    theme_type: str
    ui_theme: str | None
    path_repo_relative: str
    editor_colors: tuple[tuple[str, str], ...] = ()
    token_colors: tuple[TextMateTokenColor, ...] = ()
    semantic_token_colors: tuple[tuple[str, object], ...] = ()
    source_manifest: str | None = None

    @property
    def colors(self) -> dict[str, str]:
        """Return editor/UI colour keys as a plain dict."""
        return dict(self.editor_colors)

    def resolve_token_style(
        self, scope_stack: str | Sequence[str]
    ) -> TextMateResolvedStyle:
        """Resolve the best token colour for a TextMate scope stack.

        The matching is intentionally VS Code/TextMate-like, not a full selector
        engine: compound selectors must match scope prefixes in stack order, more
        specific selectors beat generic selectors, and later rules break ties.
        This covers the common theme selectors used by the imported VS Code theme
        assets without executing any extension code.
        """
        scopes = (
            tuple(part for part in scope_stack.split() if part)
            if isinstance(scope_stack, str)
            else tuple(scope_stack)
        )
        best = TextMateResolvedStyle(foreground=_default_token_foreground(self))
        for rule in self.token_colors:
            if rule.foreground is None:
                continue
            for selector in rule.scope_selectors:
                specificity = _selector_specificity(selector, scopes)
                if specificity < 0:
                    continue
                if (specificity, rule.rule_index) >= (
                    best.specificity,
                    best.rule_index,
                ):
                    best = TextMateResolvedStyle(
                        foreground=rule.foreground,
                        font_style=rule.font_style,
                        matched_selector=selector,
                        specificity=specificity,
                        rule_index=rule.rule_index,
                    )
        return best


@dataclass(frozen=True)
class ThemeRegistry:
    """Deterministic registry of extension-backed colour themes."""

    themes: tuple[ExtensionTheme, ...] = field(default_factory=tuple)
    diagnostics: tuple[RegistryDiagnostic, ...] = field(default_factory=tuple)

    def list_available_extension_themes(self) -> tuple[ExtensionTheme, ...]:
        """Return loaded extension themes in deterministic numeric/name order."""
        return self.themes

    def get_theme(self, number: int) -> ExtensionTheme | None:
        """Return an extension theme by numeric id, or ``None``."""
        for theme in self.themes:
            if theme.number == number:
                return theme
        return None

    def get_theme_by_name(self, name: str) -> ExtensionTheme | None:
        """Return an extension theme by exact display name, or ``None``."""
        for theme in self.themes:
            if theme.name == name:
                return theme
        return None

    def list_diagnostics(self) -> tuple[RegistryDiagnostic, ...]:
        """Return deterministic diagnostics for missing/invalid themes."""
        return self.diagnostics

    def missing_target_names(self) -> tuple[str, ...]:
        """Return target professional themes absent from ``src/ecli/extensions``."""
        present = {theme.name for theme in self.themes}
        return tuple(name for name in TARGET_THEME_NAMES if name not in present)


def _diagnostic(
    level: str, message: str, manifest: str = _SOURCE
) -> RegistryDiagnostic:
    return RegistryDiagnostic(level, manifest, message)


def _append_string_char(out: list[str], char: str, escaped: bool) -> tuple[bool, bool]:
    """Append one JSON string character and return ``(in_string, escaped)``."""
    out.append(char)
    if escaped:
        return True, False
    if char == "\\":
        return True, True
    if char == '"':
        return False, False
    return True, False


def _skip_line_comment(text: str, index: int) -> int:
    """Return the index after a ``//`` comment body."""
    index += 2
    while index < len(text) and text[index] not in "\r\n":
        index += 1
    return index


def _skip_block_comment(text: str, index: int, out: list[str]) -> int:
    """Replace a ``/* ... */`` comment body with whitespace/newlines."""
    index += 2
    while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
        out.append("\n" if text[index] in "\r\n" else " ")
        index += 1
    return index + 2 if index + 1 < len(text) else index


def _strip_json_comments(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            in_string, escaped = _append_string_char(out, char, escaped)
            index += 1
        elif char == '"':
            in_string = True
            out.append(char)
            index += 1
        elif char == "/" and nxt == "/":
            index = _skip_line_comment(text, index)
        elif char == "/" and nxt == "*":
            index = _skip_block_comment(text, index, out)
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _next_nonspace_index(text: str, index: int) -> int:
    """Return the first non-space index at or after ``index``."""
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _is_trailing_comma(text: str, index: int) -> bool:
    """Return whether ``text[index]`` is followed by a closing JSON bracket."""
    lookahead = _next_nonspace_index(text, index + 1)
    return lookahead < len(text) and text[lookahead] in "}]"


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            in_string, escaped = _append_string_char(out, char, escaped)
        elif char == '"':
            in_string = True
            out.append(char)
        elif char != "," or not _is_trailing_comma(text, index):
            out.append(char)
        index += 1
    return "".join(out)


def _load_jsonc(
    path: Path, diagnostics: list[RegistryDiagnostic], source: str
) -> dict[str, object] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        diagnostics.append(
            _diagnostic("error", f"cannot read theme file: {error}", source)
        )
        return None
    try:
        data = json.loads(_strip_trailing_commas(_strip_json_comments(raw)))
    except json.JSONDecodeError as error:
        diagnostics.append(_diagnostic("error", f"invalid theme JSON: {error}", source))
        return None
    if not isinstance(data, dict):
        diagnostics.append(
            _diagnostic("error", "theme file is not a JSON object", source)
        )
        return None
    return data


def _dict_field(document: Mapping[str, object], key: str) -> dict[object, object]:
    value = document.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _list_field(document: Mapping[str, object], key: str) -> list[object]:
    value = document.get(key)
    return list(value) if isinstance(value, list) else []


def _merge_theme_documents(
    base: dict[str, object], override: dict[str, object]
) -> dict[str, object]:
    merged = dict(base)
    merged["colors"] = {
        **_dict_field(base, "colors"),
        **_dict_field(override, "colors"),
    }
    merged["semanticTokenColors"] = {
        **_dict_field(base, "semanticTokenColors"),
        **_dict_field(override, "semanticTokenColors"),
    }
    merged["tokenColors"] = [
        *_list_field(base, "tokenColors"),
        *_list_field(override, "tokenColors"),
    ]
    for key, value in override.items():
        if key not in {"colors", "semanticTokenColors", "tokenColors", "include"}:
            merged[key] = value
    return merged


def _load_theme_document(
    theme_file: Path,
    root: Path,
    diagnostics: list[RegistryDiagnostic],
    stack: tuple[Path, ...] = (),
) -> dict[str, object] | None:
    resolved = theme_file.resolve()
    source = paths.to_repo_relative(resolved, root)
    if resolved in stack:
        diagnostics.append(
            _diagnostic("error", f"theme include cycle at {source}", source)
        )
        return None
    data = _load_jsonc(resolved, diagnostics, source)
    if data is None:
        return None
    include = data.get("include")
    if not isinstance(include, str):
        return data
    included = (resolved.parent / include).resolve()
    if not paths.is_within_root(included, root):
        diagnostics.append(
            _diagnostic(
                "error", f"theme include escapes extension tree: {include!r}", source
            )
        )
        return data
    if not included.is_file():
        diagnostics.append(
            _diagnostic("warning", f"theme include missing: {include!r}", source)
        )
        return data
    base = _load_theme_document(included, root, diagnostics, (*stack, resolved))
    return _merge_theme_documents(base, data) if base is not None else data


def _repo_relative_to_path(repo_relative: str | None, root: Path) -> Path | None:
    if repo_relative is None:
        return None
    prefix = f"{paths.REPO_RELATIVE_PREFIX}/"
    if not repo_relative.startswith(prefix):
        return None
    candidate = (root / repo_relative[len(prefix) :]).resolve()
    return candidate if paths.is_within_root(candidate, root) else None


def _normalize_hex(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("#"):
        return None
    body = text[1:]
    if len(body) in {3, 4}:
        body = "".join(ch * 2 for ch in body[:3])
    elif len(body) in {6, 8}:
        body = body[:6]
    else:
        return None
    if re.fullmatch(r"[0-9a-fA-F]{6}", body) is None:
        return None
    return f"#{body.upper()}"


def _theme_type(ui_theme: str | None, data: Mapping[str, object]) -> str:
    declared = data.get("type")
    if isinstance(declared, str):
        normalized = declared.lower().replace("_", "-")
        if normalized in {"light", "dark", "high-contrast", "custom"}:
            return normalized
    ui = (ui_theme or "").lower()
    if ui in {"hc-black", "hc-light"}:
        return "high-contrast"
    if "dark" in ui or ui == "hc-black":
        return "dark"
    if ui == "vs" or "light" in ui:
        return "light"
    return "custom"


def _theme_name(contribution: ThemeContribution, data: Mapping[str, object]) -> str:
    raw_name = data.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    if contribution.theme_id:
        return contribution.theme_id
    if contribution.label and not contribution.label.startswith("%"):
        return contribution.label
    return contribution.path or "Unnamed Theme"


def _normalize_scope_selectors(raw_scope: object) -> tuple[str, ...]:
    raw_items: list[str] = []
    if isinstance(raw_scope, str):
        raw_items = raw_scope.split(",")
    elif isinstance(raw_scope, list):
        for item in raw_scope:
            if isinstance(item, str):
                raw_items.extend(item.split(","))
    return tuple(selector.strip() for selector in raw_items if selector.strip())


def _normalize_font_style(raw_style: object) -> tuple[str, ...]:
    if not isinstance(raw_style, str):
        return ()
    if raw_style.strip().lower() in {"", "none"}:
        return ()
    accepted = {"bold", "italic", "underline", "strikethrough"}
    return tuple(part for part in raw_style.strip().lower().split() if part in accepted)


def _parse_token_colors(raw: object) -> tuple[TextMateTokenColor, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[TextMateTokenColor] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        settings = entry.get("settings")
        if not isinstance(settings, dict):
            continue
        selectors = _normalize_scope_selectors(entry.get("scope"))
        foreground = _normalize_hex(settings.get("foreground"))
        font_style = _normalize_font_style(settings.get("fontStyle"))
        name = entry.get("name") if isinstance(entry.get("name"), str) else None
        result.append(
            TextMateTokenColor(
                scope_selectors=selectors,
                foreground=foreground,
                font_style=font_style,
                name=name,
                rule_index=index,
            )
        )
    return tuple(result)


def _normalize_color_mapping(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, dict):
        return ()
    pairs = []
    for key, value in raw.items():
        normalized = _normalize_hex(value)
        if isinstance(key, str) and normalized is not None:
            pairs.append((key, normalized))
    return tuple(sorted(pairs))


def _semantic_pairs(raw: object) -> tuple[tuple[str, object], ...]:
    if not isinstance(raw, dict):
        return ()
    return tuple(
        sorted((key, value) for key, value in raw.items() if isinstance(key, str))
    )


def _load_extension_theme(
    contribution: ThemeContribution,
    manifest_name: str | None,
    root: Path,
    diagnostics: list[RegistryDiagnostic],
) -> ExtensionTheme | None:
    theme_file = _repo_relative_to_path(contribution.path_repo_relative, root)
    if theme_file is None or not theme_file.is_file():
        diagnostics.append(
            _diagnostic(
                "warning",
                f"theme target file missing: {contribution.path_repo_relative}",
                manifest_name or _SOURCE,
            )
        )
        return None
    data = _load_theme_document(theme_file, root, diagnostics)
    if data is None:
        return None
    return ExtensionTheme(
        number=None,
        name=_theme_name(contribution, data),
        source_id=contribution.theme_id,
        theme_type=_theme_type(contribution.ui_theme, data),
        ui_theme=contribution.ui_theme,
        path_repo_relative=contribution.path_repo_relative
        or paths.to_repo_relative(theme_file, root),
        editor_colors=_normalize_color_mapping(data.get("colors")),
        token_colors=_parse_token_colors(data.get("tokenColors")),
        semantic_token_colors=_semantic_pairs(data.get("semanticTokenColors")),
        source_manifest=manifest_name,
    )


def _assign_numbers(themes: Sequence[ExtensionTheme]) -> tuple[ExtensionTheme, ...]:
    by_name: dict[str, ExtensionTheme] = {}
    for theme in themes:
        by_name.setdefault(theme.name, theme)
        if theme.source_id:
            by_name.setdefault(theme.source_id, theme)
    numbered: dict[int, ExtensionTheme] = {}
    used_paths: set[str] = set()
    for number, name in _TARGET_THEME_NUMBERS:
        candidate = by_name.get(name)
        if candidate is not None:
            numbered[number] = _with_number(candidate, number, name)
            used_paths.add(candidate.path_repo_relative)

    unnumbered: list[ExtensionTheme] = []
    for theme in sorted(themes, key=lambda item: (item.name, item.path_repo_relative)):
        if theme.path_repo_relative in used_paths:
            continue
        unnumbered.append(theme)
    return (*tuple(numbered[key] for key in sorted(numbered)), *tuple(unnumbered))


def _with_number(
    theme: ExtensionTheme, number: int, display_name: str | None = None
) -> ExtensionTheme:
    return ExtensionTheme(
        number=number,
        name=display_name or theme.name,
        source_id=theme.source_id,
        theme_type=theme.theme_type,
        ui_theme=theme.ui_theme,
        path_repo_relative=theme.path_repo_relative,
        editor_colors=theme.editor_colors,
        token_colors=theme.token_colors,
        semantic_token_colors=theme.semantic_token_colors,
        source_manifest=theme.source_manifest,
    )


def _scope_prefix_matches(scope: str, selector: str) -> bool:
    return scope == selector or scope.startswith(selector + ".")


def _selector_specificity(selector: str, scopes: Sequence[str]) -> int:
    selector = selector.strip()
    if not selector or selector.startswith("-"):
        return -1
    parts = tuple(
        part for part in selector.split() if part and not part.startswith("-")
    )
    if not parts:
        return -1
    search_start = 0
    score = 0
    for part in parts:
        matched_index = -1
        for index in range(search_start, len(scopes)):
            if _scope_prefix_matches(scopes[index], part):
                matched_index = index
                break
        if matched_index < 0:
            return -1
        search_start = matched_index + 1
        score += part.count(".") * 10 + len(part)
    return score + len(parts) * 100


def _default_token_foreground(theme: ExtensionTheme) -> str | None:
    colors = theme.colors
    if "editor.foreground" in colors:
        return colors["editor.foreground"]
    for rule in theme.token_colors:
        if not rule.scope_selectors and rule.foreground:
            return rule.foreground
    return None


def _missing_target_diagnostics(
    themes: Sequence[ExtensionTheme],
) -> tuple[RegistryDiagnostic, ...]:
    present = {theme.name for theme in themes if theme.number is not None}
    present.update(
        theme.source_id
        for theme in themes
        if theme.number is not None and theme.source_id
    )
    return tuple(
        _diagnostic("info", f"target theme missing from imported tree: {name}")
        for name in TARGET_THEME_NAMES
        if name not in present
    )


def _unnumbered_theme_diagnostics(
    themes: Sequence[ExtensionTheme],
) -> tuple[RegistryDiagnostic, ...]:
    return tuple(
        _diagnostic(
            "info",
            "imported theme has no canonical number and is left unassigned "
            f"until the reserved 800-899 custom/imported theme feature exists: "
            f"{theme.name} ({theme.path_repo_relative})",
        )
        for theme in themes
        if theme.number is None
    )


def build_theme_registry(
    registry: ExtensionRegistry | None = None, root: Path | None = None
) -> ThemeRegistry:
    """Build an extension-backed theme registry from ``contributes.themes``."""
    base = (root or paths.extensions_root()).resolve()
    source_registry = registry or build_registry(base)
    diagnostics: list[RegistryDiagnostic] = list(source_registry.list_diagnostics())
    loaded: list[ExtensionTheme] = []

    for manifest in source_registry.list_manifests():
        for contribution in manifest.themes:
            theme = _load_extension_theme(
                contribution, manifest.directory_name, base, diagnostics
            )
            if theme is not None:
                loaded.append(theme)

    numbered = _assign_numbers(loaded)
    diagnostics.extend(_missing_target_diagnostics(numbered))
    diagnostics.extend(_unnumbered_theme_diagnostics(numbered))
    return ThemeRegistry(themes=numbered, diagnostics=tuple(diagnostics))


@lru_cache(maxsize=1)
def cached_theme_registry() -> ThemeRegistry:
    """Return the cached registry for the real imported extension tree."""
    return build_theme_registry()
