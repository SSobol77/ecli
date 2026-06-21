# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/utils/themes.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Editor colour theme resolution.

The editor no longer reads a free-form ``[colors]`` table from ``config.toml``.
Instead the user selects a deterministic numeric theme. Professional editor
themes are loaded from the imported VS Code extension tree via
``contributes.themes`` and theme JSON. The original eight ECLI palettes remain
available as immutable compatibility themes under reserved compatibility ids.

    theme = 207   # Dark+ from the imported VS Code theme assets

``resolve_theme()`` validates the configured value and always returns a concrete
``ThemePalette``. Missing target themes are not faked: invalid numbers preserve
the current palette when one is provided, or use the startup default with a
warning when no current palette exists.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Any, cast

from ecli.extensions.ecli_integration.theme_registry import cached_theme_registry


logger = logging.getLogger("ecli")


class ThemeId(IntEnum):
    """Stable integer identifiers for built-in compatibility themes."""

    PYSH_LIGHT = 181
    PYSH_CLASSIC = 182
    ECLI_LEGACY_LIGHT = 183
    PYSH_DARK = 281
    PYSH_CLASSIC_DARK = 282
    ECLI_LEGACY_DARK = 283
    ECLI_HIGH_CONTRAST_LIGHT = 381
    ECLI_HIGH_CONTRAST_DARK = 382


#: Professional default. Dark+ is present in the imported VS Code theme assets.
DEFAULT_THEME_ID: int = 207

#: Always-available fallback if the extension theme registry cannot be loaded.
COMPATIBILITY_FALLBACK_THEME_ID: int = int(ThemeId.PYSH_DARK)

STATUS_BAR_BACKGROUND_KEY = "statusBar.background"
STATUS_BAR_FOREGROUND_KEY = "statusBar.foreground"


@dataclass(frozen=True)
class ThemePalette:
    """An immutable colour palette.

    Every colour is an ``#rrggbb`` hex string. The renderer converts these to the
    closest terminal colour at start-up; the palette itself stays terminal-agnostic
    so it can be reasoned about and tested without curses.
    """

    theme_id: int
    name: str
    is_dark: bool
    # Editor surfaces.
    background: str
    foreground: str
    cursor: str
    selection: str
    status: str
    line_number: str
    current_line: str
    # Syntax tokens.
    comment: str
    keyword: str
    string: str
    number: str
    function: str
    klass: str
    constant: str
    type_: str
    operator: str
    decorator: str
    variable: str
    tag: str
    attribute: str
    builtin: str
    # Diagnostics.
    error: str
    warning: str
    # UI chrome roles. Default to "" and are filled deterministically in
    # __post_init__ from coherent palette fallbacks, so every theme always
    # defines a complete set of chrome colours even when not specified verbatim.
    dim: str = ""
    header_bg: str = ""
    header_fg: str = ""
    status_bg: str = ""
    status_fg: str = ""
    footer_bg: str = ""
    footer_fg: str = ""
    border: str = ""
    panel_title: str = ""
    info: str = ""
    success: str = ""
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Fill any unspecified chrome role from coherent palette fallbacks."""
        fallbacks = {
            "dim": self.comment,
            "header_bg": self.current_line,
            "header_fg": self.foreground,
            "status_bg": self.current_line,
            "status_fg": self.foreground,
            "footer_bg": self.current_line,
            "footer_fg": self.foreground,
            "border": self.comment,
            "panel_title": self.function,
            "info": self.number,
            "success": self.tag,
        }
        for name, value in fallbacks.items():
            if not getattr(self, name):
                object.__setattr__(self, name, value)

    def syntax_color_hex(self) -> dict[str, str]:
        """Return the semantic-name -> hex map consumed by ``Ecli.init_colors``.

        The keys here are exactly the colour names the renderer and the syntax
        highlighter look up in ``self.colors`` so the active palette fully drives
        the on-screen appearance.
        """
        return {
            "default": self.foreground,
            "comment": self.comment,
            "keyword": self.keyword,
            "string": self.string,
            "number": self.number,
            "function": self.function,
            "class": self.klass,
            "constant": self.constant,
            "type": self.type_,
            "operator": self.operator,
            "decorator": self.decorator,
            "variable": self.variable,
            "tag": self.tag,
            "attribute": self.attribute,
            "builtin": self.builtin,
            "error": self.error,
            "status": self.status,
            "status_error": self.error,
            "line_number": self.line_number,
            # Git status colours are derived from the palette so they stay coherent.
            "git_info": self.comment,
            "git_dirty": self.warning,
            "git_added": self.string,
            "git_deleted": self.error,
            "search_highlight": self.background,
        }

    @property
    def search_background(self) -> str:
        """Background colour used behind highlighted search matches."""
        return self.warning

    def chrome_color_pairs(self) -> dict[str, tuple[str, str]]:
        """Return UI-chrome colour pairs as ``name -> (fg_hex, bg_hex)``.

        These drive the header bar, status bar, footer shortcut strip, panel
        borders/titles and the current-line highlight. Keys are namespaced with
        ``ui_`` so they never collide with syntax-token colour names.
        """
        return {
            "ui_header": (self.header_fg, self.header_bg),
            "ui_header_accent": (self.panel_title, self.header_bg),
            "ui_header_dim": (self.dim, self.header_bg),
            "ui_status": (self.status_fg, self.status_bg),
            "ui_status_dim": (self.dim, self.status_bg),
            "ui_status_accent": (self.panel_title, self.status_bg),
            "ui_footer": (self.footer_fg, self.footer_bg),
            "ui_footer_key": (self.panel_title, self.footer_bg),
            "ui_border": (self.border, self.background),
            "ui_current_line": (self.foreground, self.current_line),
            "ui_current_line_number": (self.panel_title, self.current_line),
            "ui_selection": (self.foreground, self.selection),
            "ui_info": (self.info, self.background),
            "ui_success": (self.success, self.background),
            "ui_warning": (self.warning, self.background),
            "ui_error": (self.error, self.background),
            "ui_dim": (self.dim, self.background),
            # Solid panel surface (header-bar colour) so modals are opaque.
            "ui_panel": (self.foreground, self.header_bg),
            "ui_panel_dim": (self.dim, self.header_bg),
            "ui_panel_title": (self.panel_title, self.header_bg),
            "ui_panel_border": (self.border, self.header_bg),
            "ui_panel_warning": (self.warning, self.header_bg),
            "ui_panel_error": (self.error, self.header_bg),
            "ui_panel_selected": (self.header_bg, self.panel_title),
        }


_THEMES: dict[int, ThemePalette] = {
    1: ThemePalette(
        theme_id=1,
        name="Light Classic",
        is_dark=False,
        background="#FFFFFF",
        foreground="#1F2328",
        cursor="#1F2328",
        selection="#B6E3FF",
        status="#1F2328",
        line_number="#8C959F",
        current_line="#F6F8FA",
        comment="#6E7781",
        keyword="#CF222E",
        string="#0A3069",
        number="#0550AE",
        function="#8250DF",
        klass="#953800",
        constant="#0550AE",
        type_="#953800",
        operator="#CF222E",
        decorator="#8250DF",
        variable="#1F2328",
        tag="#116329",
        attribute="#0550AE",
        builtin="#6639BA",
        error="#CF222E",
        warning="#9A6700",
    ),
    2: ThemePalette(
        theme_id=2,
        name="Light Soft",
        is_dark=False,
        background="#FBF1C7",
        foreground="#3C3836",
        cursor="#3C3836",
        selection="#EBDBB2",
        status="#3C3836",
        line_number="#A89984",
        current_line="#F2E5BC",
        comment="#928374",
        keyword="#9D0006",
        string="#79740E",
        number="#8F3F71",
        function="#B57614",
        klass="#B57614",
        constant="#8F3F71",
        type_="#B57614",
        operator="#9D0006",
        decorator="#AF3A03",
        variable="#3C3836",
        tag="#427B58",
        attribute="#076678",
        builtin="#8F3F71",
        error="#9D0006",
        warning="#B57614",
    ),
    3: ThemePalette(
        theme_id=3,
        name="Light High Contrast",
        is_dark=False,
        background="#FFFFFF",
        foreground="#000000",
        cursor="#000000",
        selection="#FFE000",
        status="#000000",
        line_number="#333333",
        current_line="#F0F0F0",
        comment="#4B4B4B",
        keyword="#B30000",
        string="#006400",
        number="#00008B",
        function="#6A0DAD",
        klass="#8B4500",
        constant="#00008B",
        type_="#8B4500",
        operator="#B30000",
        decorator="#6A0DAD",
        variable="#000000",
        tag="#006400",
        attribute="#00008B",
        builtin="#6A0DAD",
        error="#B30000",
        warning="#8B4500",
    ),
    4: ThemePalette(
        theme_id=4,
        name="Light Solar",
        is_dark=False,
        background="#FDF6E3",
        foreground="#657B83",
        cursor="#586E75",
        selection="#EEE8D5",
        status="#586E75",
        line_number="#93A1A1",
        current_line="#EEE8D5",
        comment="#93A1A1",
        keyword="#859900",
        string="#2AA198",
        number="#D33682",
        function="#268BD2",
        klass="#B58900",
        constant="#6C71C4",
        type_="#B58900",
        operator="#859900",
        decorator="#6C71C4",
        variable="#657B83",
        tag="#268BD2",
        attribute="#268BD2",
        builtin="#CB4B16",
        error="#DC322F",
        warning="#B58900",
    ),
    5: ThemePalette(
        theme_id=5,
        name="Dark Classic",
        is_dark=True,
        background="#0D1117",
        foreground="#C9D1D9",
        cursor="#C9D1D9",
        selection="#264F78",
        status="#C9D1D9",
        line_number="#6E7681",
        current_line="#161B22",
        comment="#8B949E",
        keyword="#FF7B72",
        string="#A5D6FF",
        number="#79C0FF",
        function="#D2A8FF",
        klass="#F2CC60",
        constant="#79C0FF",
        type_="#F2CC60",
        operator="#FF7B72",
        decorator="#D2A8FF",
        variable="#C9D1D9",
        tag="#7EE787",
        attribute="#79C0FF",
        builtin="#FFA657",
        error="#F85149",
        warning="#D29922",
    ),
    6: ThemePalette(
        theme_id=6,
        name="Dark Soft",
        is_dark=True,
        background="#282828",
        foreground="#EBDBB2",
        cursor="#EBDBB2",
        selection="#504945",
        status="#EBDBB2",
        line_number="#7C6F64",
        current_line="#3C3836",
        comment="#928374",
        keyword="#FB4934",
        string="#B8BB26",
        number="#D3869B",
        function="#FABD2F",
        klass="#FABD2F",
        constant="#D3869B",
        type_="#FABD2F",
        operator="#FE8019",
        decorator="#8EC07C",
        variable="#EBDBB2",
        tag="#8EC07C",
        attribute="#83A598",
        builtin="#FE8019",
        error="#FB4934",
        warning="#FABD2F",
    ),
    7: ThemePalette(
        theme_id=7,
        name="Dark High Contrast",
        is_dark=True,
        background="#000000",
        foreground="#FFFFFF",
        cursor="#FFFFFF",
        selection="#44475A",
        status="#FFFFFF",
        line_number="#BBBBBB",
        current_line="#1A1A1A",
        comment="#9E9E9E",
        keyword="#FF5555",
        string="#50FA7B",
        number="#8BE9FD",
        function="#BD93F9",
        klass="#FFB86C",
        constant="#8BE9FD",
        type_="#FFB86C",
        operator="#FF79C6",
        decorator="#BD93F9",
        variable="#FFFFFF",
        tag="#50FA7B",
        attribute="#8BE9FD",
        builtin="#FFB86C",
        error="#FF5555",
        warning="#F1FA8C",
    ),
    8: ThemePalette(
        theme_id=8,
        name="Dark Neon",
        is_dark=True,
        background="#0A0E14",
        foreground="#B3B1AD",
        cursor="#FFCC66",
        selection="#1F2430",
        status="#B3B1AD",
        line_number="#3D4751",
        current_line="#131721",
        comment="#5C6773",
        keyword="#FF8F40",
        string="#C2D94C",
        number="#FFEE99",
        function="#59C2FF",
        klass="#FFB454",
        constant="#E6B450",
        type_="#FFB454",
        operator="#F29668",
        decorator="#FFB454",
        variable="#B3B1AD",
        tag="#95E6CB",
        attribute="#59C2FF",
        builtin="#FFB454",
        error="#FF3333",
        warning="#E6B450",
    ),
}


def _chrome(
    bar: tuple[str, str],
    border: str,
    panel_title: str,
    info: str,
    success: str,
) -> dict[str, str]:
    """Expand a compact chrome seed into explicit header/status/footer roles.

    ``bar`` is the shared ``(bg, fg)`` colour used by the header, status and
    footer bars for a coherent, btop-style look while still populating every
    individually-required chrome field.
    """
    bar_bg, bar_fg = bar
    return {
        "header_bg": bar_bg,
        "header_fg": bar_fg,
        "status_bg": bar_bg,
        "status_fg": bar_fg,
        "footer_bg": bar_bg,
        "footer_fg": bar_fg,
        "border": border,
        "panel_title": panel_title,
        "info": info,
        "success": success,
    }


# Distinctive, professional chrome bars per theme (id -> chrome overrides).
_CHROME_OVERRIDES: dict[int, dict[str, str]] = {
    1: _chrome(("#EAEEF2", "#1F2328"), "#D0D7DE", "#0969DA", "#0969DA", "#1A7F37"),
    2: _chrome(("#EBDBB2", "#3C3836"), "#D5C4A1", "#B57614", "#076678", "#79740E"),
    3: _chrome(("#000000", "#FFFFFF"), "#000000", "#B30000", "#00008B", "#006400"),
    4: _chrome(("#EEE8D5", "#586E75"), "#93A1A1", "#268BD2", "#268BD2", "#859900"),
    5: _chrome(("#161B22", "#C9D1D9"), "#30363D", "#58A6FF", "#58A6FF", "#3FB950"),
    6: _chrome(("#3C3836", "#EBDBB2"), "#504945", "#83A598", "#83A598", "#B8BB26"),
    7: _chrome(("#1A1A1A", "#FFFFFF"), "#5A5A5A", "#8BE9FD", "#8BE9FD", "#50FA7B"),
    8: _chrome(("#131721", "#B3B1AD"), "#1F2430", "#59C2FF", "#59C2FF", "#C2D94C"),
}

# Apply the chrome overrides, keeping the palettes immutable.
_THEMES = {
    tid: replace(palette, **cast("dict[str, Any]", _CHROME_OVERRIDES.get(tid, {})))
    for tid, palette in _THEMES.items()
}

_COMPATIBILITY_THEME_IDS: dict[int, tuple[int, str]] = {
    1: (int(ThemeId.PYSH_LIGHT), "PySH Light"),
    2: (int(ThemeId.PYSH_CLASSIC), "PySH Classic"),
    4: (int(ThemeId.ECLI_LEGACY_LIGHT), "ECLI Legacy Light"),
    5: (int(ThemeId.PYSH_DARK), "PySH Dark"),
    6: (int(ThemeId.PYSH_CLASSIC_DARK), "PySH Classic Dark"),
    8: (int(ThemeId.ECLI_LEGACY_DARK), "ECLI Legacy Dark"),
    3: (int(ThemeId.ECLI_HIGH_CONTRAST_LIGHT), "ECLI High Contrast Light"),
    7: (int(ThemeId.ECLI_HIGH_CONTRAST_DARK), "ECLI High Contrast Dark"),
}

_LEGACY_THEME_ID_TO_COMPATIBILITY_ID = {
    old_id: new_id for old_id, (new_id, _name) in _COMPATIBILITY_THEME_IDS.items()
}

_THEMES = {
    new_id: replace(_THEMES[old_id], theme_id=new_id, name=name)
    for old_id, (new_id, name) in _COMPATIBILITY_THEME_IDS.items()
}


def _theme_exists(theme_id: int) -> bool:
    if theme_id in _THEMES:
        return True
    try:
        return cached_theme_registry().get_theme(theme_id) is not None
    except Exception:
        return False


def _first_color(
    colors: Mapping[str, str], names: tuple[str, ...], default: str
) -> str:
    for name in names:
        value = colors.get(name)
        if value:
            return value
    return default


def _resolved_token_color(theme: Any, scope_stack: str, default: str) -> str:
    try:
        value = theme.resolve_token_style(scope_stack).foreground
    except Exception:
        value = None
    return value or default


def _resolved_first_token_color(
    theme: Any, scope_stacks: tuple[str, ...], default: str
) -> str:
    for scope_stack in scope_stacks:
        color = _resolved_token_color(theme, scope_stack, "")
        if color:
            return color
    return default


def _extension_theme_to_palette(theme: Any) -> ThemePalette:
    colors = theme.colors
    is_dark = theme.theme_type == "dark" or theme.ui_theme == "hc-black"
    default_bg = "#1E1E1E" if is_dark else "#FFFFFF"
    default_fg = "#D4D4D4" if is_dark else "#000000"
    background = _first_color(colors, ("editor.background",), default_bg)
    foreground = _first_color(colors, ("editor.foreground",), default_fg)
    current_line = _first_color(
        colors,
        ("editor.lineHighlightBackground", "editorLineNumber.activeBackground"),
        background,
    )
    selection = _first_color(
        colors,
        ("editor.selectionBackground", "selection.background"),
        "#264F78" if is_dark else "#ADD6FF",
    )
    return ThemePalette(
        theme_id=int(theme.number),
        name=theme.name,
        is_dark=is_dark,
        background=background,
        foreground=foreground,
        cursor=_first_color(colors, ("editorCursor.foreground",), foreground),
        selection=selection,
        status=_first_color(colors, (STATUS_BAR_FOREGROUND_KEY,), foreground),
        line_number=_first_color(colors, ("editorLineNumber.foreground",), foreground),
        current_line=current_line,
        comment=_resolved_first_token_color(
            theme,
            ("source comment", "text.html.markdown markup.quote"),
            foreground,
        ),
        keyword=_resolved_first_token_color(
            theme,
            ("source keyword.control", "source keyword"),
            foreground,
        ),
        string=_resolved_first_token_color(
            theme,
            (
                "source string.quoted",
                "text.html.markdown markup.inline.raw",
                "text.html.markdown markup.fenced_code",
            ),
            foreground,
        ),
        number=_resolved_first_token_color(
            theme,
            ("source constant.numeric", "source constant.numeric.integer"),
            foreground,
        ),
        function=_resolved_first_token_color(
            theme,
            (
                "text.html.markdown markup.heading",
                "text.html.markdown entity.name.section",
                "source entity.name.function",
            ),
            foreground,
        ),
        klass=_resolved_token_color(theme, "source entity.name.class", foreground),
        constant=_resolved_token_color(theme, "source constant.language", foreground),
        type_=_resolved_first_token_color(
            theme,
            ("source entity.name.type", "text.html.markdown markup.bold"),
            foreground,
        ),
        operator=_resolved_first_token_color(
            theme,
            ("source keyword.operator", "text.html.markdown markup.list"),
            foreground,
        ),
        decorator=_resolved_token_color(
            theme,
            "source meta.function.decorator entity.name.function.decorator",
            foreground,
        ),
        variable=_resolved_token_color(theme, "source variable.other", foreground),
        tag=_resolved_token_color(theme, "text.html entity.name.tag", foreground),
        attribute=_resolved_token_color(
            theme, "text.html entity.other.attribute-name", foreground
        ),
        builtin=_resolved_token_color(theme, "source support.function", foreground),
        error=_resolved_token_color(theme, "source invalid", "#F44747"),
        warning=_first_color(
            colors,
            ("editorWarning.foreground", "problemsWarningIcon.foreground"),
            "#CCA700",
        ),
        dim=_first_color(colors, ("descriptionForeground",), foreground),
        header_bg=_first_color(
            colors,
            ("titleBar.activeBackground", STATUS_BAR_BACKGROUND_KEY),
            current_line,
        ),
        header_fg=_first_color(
            colors,
            ("titleBar.activeForeground", STATUS_BAR_FOREGROUND_KEY),
            foreground,
        ),
        status_bg=_first_color(colors, (STATUS_BAR_BACKGROUND_KEY,), current_line),
        status_fg=_first_color(colors, (STATUS_BAR_FOREGROUND_KEY,), foreground),
        footer_bg=_first_color(colors, (STATUS_BAR_BACKGROUND_KEY,), current_line),
        footer_fg=_first_color(colors, (STATUS_BAR_FOREGROUND_KEY,), foreground),
        border=_first_color(colors, ("panel.border", "contrastBorder"), foreground),
        panel_title=_first_color(
            colors,
            ("panelTitle.activeForeground", "list.highlightForeground"),
            _resolved_token_color(theme, "source entity.name.function", foreground),
        ),
        info=_first_color(
            colors,
            ("editorInfo.foreground", "problemsInfoIcon.foreground"),
            _resolved_token_color(theme, "source constant.numeric", foreground),
        ),
        success=_resolved_token_color(theme, "source string", foreground),
    )


def _extension_theme(theme_id: int) -> ThemePalette | None:
    try:
        theme = cached_theme_registry().get_theme(theme_id)
    except Exception:
        return None
    return _extension_theme_to_palette(theme) if theme is not None else None


def find_theme(theme_id: int) -> ThemePalette | None:
    """Return an extension or compatibility palette, or ``None`` if missing."""
    candidate = int(theme_id)
    if candidate in _THEMES:
        return _THEMES[candidate]
    return _extension_theme(candidate)


def get_theme(theme_id: int) -> ThemePalette:
    """Return an extension or compatibility palette for ``theme_id``.

    Missing ids are a contract violation for direct callers. Config resolution
    uses :func:`resolve_theme`, which reports diagnostics and preserves the
    current palette when possible.
    """
    palette = find_theme(theme_id)
    if palette is None:
        raise KeyError(f"theme id is not available: {theme_id}")
    return palette


def _startup_default_theme() -> ThemePalette:
    return find_theme(DEFAULT_THEME_ID) or _THEMES[COMPATIBILITY_FALLBACK_THEME_ID]


#: Environment variable that overrides the configured theme (highest precedence).
THEME_ENV_VAR = "ECLI_THEME"


def _legacy_theme_id(table: Mapping[str, Any]) -> int | None:
    """Resolve a theme id from a legacy ``[theme]`` table (id wins, then name)."""
    table_id = table.get("id")
    if isinstance(table_id, int) and not isinstance(table_id, bool):
        if table_id in _LEGACY_THEME_ID_TO_COMPATIBILITY_ID:
            return _LEGACY_THEME_ID_TO_COMPATIBILITY_ID[table_id]
        if table_id in _THEMES:
            return table_id
    name = table.get("name")
    if isinstance(name, str):
        lowered = name.strip().lower()
        if "dark" in lowered:
            return int(ThemeId.PYSH_DARK)
        if "light" in lowered:
            return int(ThemeId.PYSH_LIGHT)
    return None


def _coerce_theme_id(raw: Any) -> int | None:
    """Parse a raw theme value into a known theme id, or ``None`` if unusable.

    Returns ``None`` (rather than the default) when the value cannot be
    interpreted, so callers can try the next source in the precedence chain.

    * ``int`` / integer-like ``str`` (``"207"``) -> that id when present in the
      extension-backed or compatibility registry.
    * legacy ``[theme]`` table (``Mapping``) -> old ``id`` (1-8) mapped to
      compatibility ids, or ``name`` (``"dark"`` -> 281,
      ``"light"`` -> 181) for backward compatibility.
    * ``bool`` / out-of-range / unparseable -> ``None``.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if _theme_exists(raw) else None
    if isinstance(raw, str):
        try:
            candidate = int(raw.strip())
        except ValueError:
            return None
        return candidate if _theme_exists(candidate) else None
    if isinstance(raw, Mapping):
        return _legacy_theme_id(raw)
    return None


def _with_theme_diagnostic(palette: ThemePalette, message: str) -> ThemePalette:
    updated = replace(palette, diagnostics=(*palette.diagnostics, message))
    return cast(ThemePalette, updated)


def resolve_theme(
    config: Mapping[str, Any] | None,
    current_theme: ThemePalette | None = None,
) -> ThemePalette:
    """Resolve the active palette from env + application config.

    Precedence (highest first): ``ECLI_THEME`` env var, the root-level ``theme``
    key in the effective config, then the deterministic default. Never raises;
    invalid values are logged and the next source is tried. If no explicit source
    is valid, the current palette is preserved when supplied; otherwise the
    startup default professional theme is returned with a diagnostic.
    """
    sources: list[tuple[str, Any]] = []
    env_value = os.environ.get(THEME_ENV_VAR)
    if env_value is not None and env_value.strip():
        sources.append((f"{THEME_ENV_VAR} env", env_value))
    if isinstance(config, Mapping):
        sources.append(("config 'theme'", config.get("theme")))

    for label, raw in sources:
        if raw is None:
            continue
        theme_id = _coerce_theme_id(raw)
        if theme_id is not None:
            return get_theme(theme_id)
        logger.warning("Ignoring invalid theme from %s (%r).", label, raw)

    invalid_sources = [(label, raw) for label, raw in sources if raw is not None]
    if invalid_sources:
        label, raw = invalid_sources[-1]
        if current_theme is not None:
            return _with_theme_diagnostic(
                current_theme,
                f"Invalid theme from {label}: {raw!r}; keeping current theme "
                f"{current_theme.theme_id} ({current_theme.name})",
            )
        palette = _startup_default_theme()
        return _with_theme_diagnostic(
            palette,
            f"Invalid theme from {label}: {raw!r}; using theme {palette.theme_id} ({palette.name})",
        )
    return _startup_default_theme()
