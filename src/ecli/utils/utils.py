# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/utils/utils.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""
ecli.utils.utils.py
===================

This module provides a collection of core utility functions for the ECLI editor.

Key functionalities include:
- Automatic User Configuration: Manages the creation and loading of user-specific
  configuration files (`config.toml`, `.env`) in `~/.config/ecli`, ensuring a
  seamless first-run experience.
- Robust Configuration Loading: Implements a multi-layered strategy that loads a
  hardcoded, built-in default configuration, then recursively merges it with
  user-defined settings from `~/.config/ecli/config.toml`.
- Safe Subprocess Execution: A wrapper around `subprocess.run` for safely
  executing external commands.
- File Icon Resolution: Determines the appropriate icon for files based on their
  name or extension.
- Helper Utilities: Includes functions for deep-merging dictionaries and color conversion.

This architecture ensures the application is always runnable, even if user
configuration files are missing or corrupted, by falling back to the
embedded defaults.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import toml

logger = logging.getLogger("ecli")

# --- Constants ---
CALM_BG_IDX = 236
WHITE_FG_IDX = 255

ENV_TEMPLATE = """# API Keys for AI Features
# Get your keys from the respective provider websites and add them here.
# XAI (Grok): from https://console.x.ai, format xa-...your-key-here
XAI_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
MISTRAL_API_KEY=
CLAUDE_API_KEY=
HUGGINGFACE_API_KEY=
"""

# This dictionary is a direct, hardcoded representation of `default_config.toml`.
# It serves as the ultimate fallback, ensuring the application can ALWAYS start.
DEFAULT_CONFIG: dict[str, Any] = {
    # Built-in colour theme (1-4 light, 5-8 dark). See ecli.utils.themes.
    "theme": 5,
    "colors": {"error": "red", "status": "bright_white", "green": "green"},
    "editor": {
        "use_system_clipboard": True, "default_new_filename": "new_file.py",
        "tab_size": 4, "use_spaces": True, "syntax_highlighting": True,
        # Opt-in mouse support (off by default to preserve native text selection).
        "mouse": False,
    },
    # Extensions Layer (data-only) switches. These mirror the [extensions] table
    # in config.toml and gate ONLY the deterministic metadata adapters under
    # src/ecli/extensions/ecli_integration/. They never enable an extension
    # runtime; syntax_engine = "legacy" preserves the regex highlighter until the
    # #102 extension-backed syntax service replaces it. See
    # docs/architecture/extensions-layer.md.
    "extensions": {
        "enabled": True, "metadata_registry": True, "grammar_catalog": True,
        "language_detection": True, "syntax_engine": "legacy",
    },
    "fonts": {"font_family": "monospace", "font_size": 12},
    "keybindings": {
        "delete": "del", "paste": "ctrl+v", "copy": "ctrl+c", "cut": "ctrl+x",
        "undo": "ctrl+z", "redo": "ctrl+y", "lint": "f4", "new_file": "f2",
        "open_file": "ctrl+o", "save_file": "ctrl+s", "save_as": "f5",
        "select_all": "ctrl+a", "quit": "ctrl+q", "goto_line": "ctrl+g",
        "git_menu": "f9", "cancel_operation": "esc", "find": "ctrl+f",
        "find_next": "f3", "search_and_replace": "f6", "help": "f1",
        "extend_selection_left": ["shift+left", "alt-h"],
        "extend_selection_right": ["shift+right", "alt-l"],
        "extend_selection_up": ["shift+up", "alt-k"],
        "extend_selection_down": ["shift+down", "alt-j"],
        "handle_up": ["up"], "handle_down": ["down"], "handle_left": ["left"],
        "handle_right": ["right"],
    },
    "ai": {"default_provider": "gemini"},
    "ai.keys": {
        "openai": "", "gemini": "", "mistral": "", "claude": "", "grok": "", "huggingface": ""
    },
    "ai.models": {
        "openai": "gpt-5-codex",
        "gemini": "gemini-2.5-pro",
        "mistral": "magistral-medium-1.2",
        "claude": "claude-4-opus",
        "grok": "grok-4-fast",
        "huggingface": "meta-llama/Meta-Llama-3.1-405B-Instruct",
    },
    "git": {"enabled": True},
    "settings": {"auto_save_interval": 5, "show_git_info": True},
    "file_icons": {
        "docs": "📘", "python": "🐍", "toml": "❄️", "javascript": "📜", "typescript": "📑",
        "php": "🐘", "ruby": "♦️", "css": "🎨", "html": "🌐", "json": "📊", "yaml": "⚙️",
        "xml": "📰", "markdown": "📗", "text": "📝", "shell": "💫", "dart": "🎯", "go": "🐹",
        "c": "🇨", "cpp": "🇨➕", "java": "☕", "julia": "🧮", "rust": "🦀", "csharp": "♯",
        "scala": "💎", "r": "📉", "swift": "🐦", "dockerfile": "🐳", "terraform": "🛠️",
        "jenkins": "🧑‍✈️", "puppet": "🎎", "saltstack": "🧂", "git": "🔖", "notebook": "📒",
        "diff": "↔️", "makefile": "🛠️", "ini": "🔩", "csv": "🗂️", "sql": "💾",
        "graphql": "📈", "kotlin": "📱", "lua": "🌙", "perl": "🐪", "powershell": "💻",
        "nix": "❄️", "image": "🖼️", "audio": "🎵", "video": "🎞️", "archive": "📦",
        "font": "🖋️", "binary": "⚙️", "document": "📄", "folder": "📁", "folder_open": "📂",
        "default": "❓",
    },
    "supported_formats": {
        "docs": ["readme", "docs", "todo", "changelog", "license", "contributing", "code_of_conduct"],
        "python": ["py", "pyw", "pyc", "pyd"], "toml": ["toml", "tml"],
        "javascript": ["js", "mjs", "cjs", "jsx"], "typescript": ["ts", "tsx", "mts", "cts"],
        "php": ["php", "php3", "php4", "php5", "phtml"], "ruby": ["rb", "erb", "rake", "rbw", "gemspec"],
        "css": ["css"], "html": ["html", "htm", "xhtml"], "json": ["json", "jsonc", "geojson", "webmanifest"],
        "yaml": ["yaml", "yml"], "xml": ["xml", "xsd", "xsl", "xslt", "plist", "rss", "atom", "csproj", "svg"],
        "markdown": ["md", "markdown", "mdown", "mkd"], "text": ["txt", "log", "rst", "srt", "sub", "me"],
        "shell": ["sh", "bash", "zsh", "fish", "ksh", "csh", "tcsh", "dash", "ash", "cmd", "command", "tool", "bat"],
        "dart": ["dart"], "go": ["go"], "c": ["c", "h"], "cpp": ["cpp", "cxx", "cc", "hpp", "hxx", "hh", "inl", "tpp"],
        "java": ["java", "jar", "class"], "julia": ["jl"], "rust": ["rs", "rlib"], "csharp": ["cs"],
        "scala": ["scala", "sc"], "r": ["r", "R", "rds", "rda"], "swift": ["swift"],
        "dockerfile": ["Dockerfile", "dockerfile"], "terraform": ["tf", "tfvars"],
        "jenkins": ["Jenkinsfile", "jenkinsfile", "groovy"], "puppet": ["pp"], "saltstack": ["sls"],
        "git": [".gitignore", ".gitattributes", ".gitmodules", ".gitkeep", "gitconfig", "config"],
        "notebook": ["ipynb"], "diff": ["diff", "patch"], "makefile": ["Makefile", "makefile", "mk", "mak"],
        "ini": ["ini", "cfg", "conf", "properties", "editorconfig"], "csv": ["csv", "tsv"], "sql": ["sql"],
        "graphql": ["graphql", "gql"], "kotlin": ["kt", "kts"], "lua": ["lua"], "perl": ["pl", "pm", "t", "pod"],
        "powershell": ["ps1", "psm1", "psd1"], "nix": ["nix"],
        "image": ["jpg", "jpeg", "png", "gif", "bmp", "ico", "webp", "tiff", "tif", "heic", "heif"],
        "audio": ["mp3", "wav", "ogg", "flac", "aac", "m4a", "wma"],
        "video": ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv"],
        "archive": ["zip", "tar", "gz", "tgz", "bz2", "rar", "7z", "xz", "iso", "deb", "rpm", "pkg"],
        "font": ["ttf", "otf", "woff", "woff2", "eot"],
        "binary": ["exe", "dll", "so", "o", "bin", "app", "com", "msi", "dmg"],
        "document": ["doc", "docx", "odt", "rtf", "pdf", "ppt", "pptx", "odp", "xls", "xlsx", "ods", "epub", "mobi"],
    },
    "comments": {
        "python": {"line_prefix": "# ", "docstring_delim": '"""'},
        "ruby": {"line_prefix": "# ", "block_delims": ["=begin", "=end"]},
        "perl": {"line_prefix": "# ", "block_delims": ["=pod", "=cut"]},
        "lua": {"line_prefix": "-- ", "block_delims": ["--[[", "]]"]},
        "javascript": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "typescript": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "php": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "html": {"block_delims": ["<!--", "-->"]}, "xml": {"block_delims": ["<!--", "-->"]},
        "css": {"block_delims": ["/*", "*/"]}, "scss": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "graphql": {"line_prefix": "# "}, "c": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "cpp": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "csharp": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "java": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "go": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "rust": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "swift": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "kotlin": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "scala": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "dart": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "haskell": {"line_prefix": "-- ", "block_delims": ["{-", "-}"]},
        "elixir": {"line_prefix": "# ", "docstring_delim": '"""'}, "erlang": {"line_prefix": "% "},
        "clojure": {"line_prefix": ";; "}, "fsharp": {"line_prefix": "// ", "block_delims": ["(*", "*)"]},
        "ocaml": {"block_delims": ["(*", "*)"]}, "shell": {"line_prefix": "# "},
        "powershell": {"line_prefix": "# ", "block_delims": ["<#", "#>"]},
        "dockerfile": {"line_prefix": "# "}, "makefile": {"line_prefix": "# "},
        "terraform": {"line_prefix": "# ", "block_delims": ["/*", "*/"]},
        "jenkins": {"line_prefix": "// ", "block_delims": ["/*", "*/"]},
        "puppet": {"line_prefix": "# "}, "saltstack": {"line_prefix": "# "},
        "nix": {"line_prefix": "# ", "block_delims": ["/*", "*/"]}, "vim": {"line_prefix": '" '},
        "assembly": {"line_prefix": "; "}, "sql": {"line_prefix": "-- ", "block_delims": ["/*", "*/"]},
        "yaml": {"line_prefix": "# "}, "toml": {"line_prefix": "# "}, "ini": {"line_prefix": "; "},
        "markdown": {"block_delims": ["<!--", "-->"]}, "latex": {"line_prefix": "% "},
        "r": {"line_prefix": "# "}, "julia": {"line_prefix": "# ", "block_delims": ["#=", "=#"]},
        "matlab": {"line_prefix": "% ", "block_delims": ["%{", "%}"]},
        "nim": {"line_prefix": "# ", "block_delims": ["#[", "]#"]},
        "crystal": {"line_prefix": "# "}, "zig": {"line_prefix": "// "}, "bat": {"line_prefix": "REM "},
    },
}


# --- Helper Functions ---

def get_project_root() -> Path:
    """Determines the project's root directory for finding template files."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parents[3]


def ensure_user_config_exists() -> None:
    """Checks for user config files in `~/.config/ecli` and creates them if missing."""
    try:
        config_dir = Path.home() / ".config" / "ecli"
        user_config_path = config_dir / "config.toml"
        user_env_path = config_dir / ".env"

        config_dir.mkdir(parents=True, exist_ok=True)

        if not user_config_path.exists():
            project_root = get_project_root()
            source_config_path = project_root / "config.toml"
            if source_config_path.exists():
                shutil.copy(source_config_path, user_config_path)
                logger.info(f"Created user config template at: {user_config_path}")

        if not user_env_path.exists():
            user_env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
            logger.info(f"Created user .env template at: {user_env_path}")

        migrate_legacy_theme_config(user_config_path)

    except Exception as e:
        logger.critical(f"Could not create user configuration files: {e}", exc_info=True)


def migrate_legacy_theme_config(user_config_path: Path) -> bool:
    """Upgrade a legacy ``[theme]``-table config to a root ``theme = N`` key.

    Old configs used ``[theme]``/``[theme.ui]``/``[colors]`` tables that the
    editor no longer reads, leaving users unable to switch themes by editing the
    file. This is a one-time, backed-up, conservative migration: the dead tables
    are commented out (never deleted) and a single editable ``theme = N`` line is
    inserted, derived from the legacy ``name``/``id``. No-op when the config
    already has a root ``theme`` key, has no legacy ``[theme]`` table, or cannot
    be read. Returns True when a migration was written.
    """
    try:
        text = user_config_path.read_text(encoding="utf-8")
    except Exception:
        return False

    if re.search(r"(?m)^\s*theme\s*=\s*\d", text):
        return False  # already has a root theme = N
    if not re.search(r"(?m)^\s*\[theme\]", text):
        return False  # no legacy table to migrate

    theme_id = _derive_legacy_theme_id(text)

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    commenting = False
    for line in lines:
        stripped = line.lstrip()
        if re.match(r"\[(colors|theme(\.ui)?)\]", stripped):
            commenting = True
        elif stripped.startswith("["):
            commenting = False
        if commenting and stripped and not stripped.startswith("#"):
            out.append("# " + line)
        else:
            out.append(line)
    migrated = "".join(out)

    insertion = (
        "# Active colour theme (1-4 light, 5-8 dark). Edit this number to switch.\n"
        f"theme = {theme_id}\n\n"
    )
    first_table = re.search(r"(?m)^\s*\[", migrated)
    if first_table:
        migrated = migrated[: first_table.start()] + insertion + migrated[first_table.start() :]
    else:
        migrated = insertion + migrated

    try:
        backup = user_config_path.with_name(user_config_path.name + ".bak")
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        user_config_path.write_text(migrated, encoding="utf-8")
        logger.warning(
            "Migrated legacy [theme] config to 'theme = %d' at %s (backup: %s).",
            theme_id,
            user_config_path,
            backup,
        )
        return True
    except Exception:
        logger.exception("Legacy theme config migration failed; left config unchanged.")
        return False


def _derive_legacy_theme_id(text: str) -> int:
    """Best-effort theme id from a legacy ``[theme]`` table's id/name."""
    id_match = re.search(r"(?ms)^\s*\[theme\].*?^\s*id\s*=\s*(\d+)", text)
    if id_match:
        candidate = int(id_match.group(1))
        if 1 <= candidate <= 8:
            return candidate
    name_match = re.search(
        r"(?ms)^\s*\[theme\].*?^\s*name\s*=\s*[\"']([^\"']+)[\"']", text
    )
    if name_match and "light" in name_match.group(1).lower():
        return 1
    return 5




def load_config() -> dict[str, Any]:
    """
    Loads and merges configurations, ensuring the application can always run.
    """
    final_config = deep_merge({}, DEFAULT_CONFIG)
    logger.debug("Loaded embedded default configuration.")

    ensure_user_config_exists()

    user_config_path = Path.home() / ".config" / "ecli" / "config.toml"
    loaded_from = "(built-in defaults only)"
    if user_config_path.is_file():
        try:
            user_config = toml.load(user_config_path)
            final_config = deep_merge(final_config, user_config)
            loaded_from = str(user_config_path)
            logger.info("Loaded user config from %s", user_config_path)
            if isinstance(user_config.get("theme"), dict):
                logger.warning(
                    "User config %s uses the legacy [theme] table. Set a root-level "
                    "'theme = 1..8' (or [theme] id = N), or run with ECLI_THEME=N.",
                    user_config_path,
                )
        except Exception as e:
            logger.error(
                "Could not parse user config '%s': %s. Using defaults.",
                user_config_path,
                e,
            )
            loaded_from = f"{user_config_path} (parse error; using defaults)"

    # Record the effective config path so the runtime/UI can report which file
    # was actually loaded (root-cause aid for "my config changes do nothing").
    final_config["_loaded_config_path"] = loaded_from
    return final_config


def get_file_icon(filename: Optional[str], config: dict[str, Any]) -> str:
    """
    Returns an icon string for a given filename based on the configuration.

    This function uses a two-pass strategy for reliability:
    1.  **Exact Match First**: It checks for an exact, case-insensitive match of the
        entire filename (e.g., "Makefile", ".gitignore"). This is the highest priority.
    2.  **Extension Match Second**: If no exact match is found, it checks the file's
        extension (e.g., "py", "js") against the configuration lists.

    If neither pass finds a match, it returns a generic text icon as a fallback.

    Args:
        filename: The name of the file (e.g., "my_script.py").
        config: The application configuration dictionary.

    Returns:
        A string containing the corresponding icon.
    """
    if not isinstance(config, dict):
        return "❓"

    file_icons = config.get("file_icons", {})
    supported_formats = config.get("supported_formats", {})
    default_icon = file_icons.get("default", "❓")
    text_icon = file_icons.get("text", "📝")

    if not filename:
        return default_icon  # For new, unsaved buffers.

    base_name_lower = os.path.basename(filename.lower())

    # Pass 1: Check for an exact filename match (e.g., "makefile", ".gitignore").
    for icon_key, names_list in supported_formats.items():
        if isinstance(names_list, list):
            # Normalize list items for safe comparison
            lower_names_list = [str(name).lower() for name in names_list]
            if base_name_lower in lower_names_list:
                return file_icons.get(icon_key, default_icon)

    # Pass 2: If no exact match, check by file extension.
    # We use splitext to correctly handle names like 'archive.tar.gz' -> '.gz'
    _, extension = os.path.splitext(base_name_lower)
    if extension:
        # Remove the leading dot for comparison, e.g., '.py' -> 'py'
        ext_without_dot = extension[1:]
        for icon_key, extensions_list in supported_formats.items():
            if isinstance(extensions_list, list):
                if ext_without_dot in extensions_list:
                    return file_icons.get(icon_key, default_icon)

    # If no match was found in either pass, return the generic text icon.
    return text_icon


def safe_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """
    Executes a command safely, capturing output and handling common exceptions.
    """
    timeout = kwargs.pop("timeout", None)
    if timeout is not None and not isinstance(timeout, int | float):
        logger.warning("Invalid timeout type %s; running without timeout.", type(timeout).__name__)
        timeout = None
    elif timeout is not None and timeout <= 0:
        logger.warning("Invalid timeout value %s; using default 30s.", timeout)
        timeout = 30

    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", timeout=timeout, **kwargs,
        )
    except FileNotFoundError as e:
        logger.error(f"Command not found: {cmd[0]!r}", exc_info=True)
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(e))
    except subprocess.TimeoutExpired as e:
        logger.warning(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -15, stdout=e.stdout or "", stderr=e.stderr or "")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while running command: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=str(e))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merges the `override` dictionary into the `base` dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# xterm-256 colour-cube channel levels (indices 16..231).
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)


def _xterm_index_rgb(index: int) -> tuple[int, int, int]:
    """Return the approximate RGB of an xterm-256 colour index (16..255)."""
    if index < 16:
        return (0, 0, 0)
    if index < 232:
        i = index - 16
        return (
            _CUBE_LEVELS[(i // 36) % 6],
            _CUBE_LEVELS[(i // 6) % 6],
            _CUBE_LEVELS[i % 6],
        )
    gray = 8 + 10 * (index - 232)
    return (gray, gray, gray)


def hex_to_xterm(hex_color: str) -> int:
    """Convert a hex colour to the nearest xterm-256 index.

    Considers both the 6x6x6 colour cube *and* the 24-step grayscale ramp (plus
    pure black/white), returning whichever is closest in RGB space. This keeps
    dark, near-neutral colours (e.g. ``#161B22``) on the grey ramp instead of
    snapping them to a saturated cube cell.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return WHITE_FG_IDX
    try:
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return WHITE_FG_IDX

    def _nearest_level(value: int) -> int:
        return min(range(6), key=lambda i: abs(_CUBE_LEVELS[i] - value))

    candidates = [
        16
        + 36 * _nearest_level(r)
        + 6 * _nearest_level(g)
        + _nearest_level(b),  # colour cube
        16,  # black
        231,  # white
    ]
    # Nearest grayscale-ramp step (indices 232..255).
    gray_step = round((((r + g + b) / 3) - 8) / 10)
    candidates.append(232 + max(0, min(23, gray_step)))

    def _distance(index: int) -> int:
        cr, cg, cb = _xterm_index_rgb(index)
        return (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2

    return min(candidates, key=_distance)
