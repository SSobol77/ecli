# ecli/utils/utils.py
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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml

logger = logging.getLogger("ecli")

# --- Constants ---
CALM_BG_IDX = 236
WHITE_FG_IDX = 255

ENV_TEMPLATE = """# API Keys for AI Features
# Get your keys from the respective provider websites and add them here.
OPENAI_API_KEY=
GEMINI_API_KEY=
MISTRAL_API_KEY=
CLAUDE_API_KEY=
HUGGINGFACE_API_KEY=
XAI_API_KEY=
"""

# This dictionary is a direct, hardcoded representation of `default_config.toml`.
# It serves as the ultimate fallback, ensuring the application can ALWAYS start.
DEFAULT_CONFIG: Dict[str, Any] = {
    "colors": {"error": "red", "status": "bright_white", "green": "green"},
    "editor": {
        "use_system_clipboard": True, "default_new_filename": "new_file.py",
        "tab_size": 4, "use_spaces": True,
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
        "openai": "gpt-4o", "gemini": "gemini-2.5-pro", "mistral": "mistral-large-latest",
        "claude": "claude-3-opus-20240229", "grok": "grok-1.5", "huggingface": "microsoft/DialoGPT-large",
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

    except Exception as e:
        logger.critical(f"Could not create user configuration files: {e}", exc_info=True)




def load_config() -> Dict[str, Any]:
    """
    Loads and merges configurations, ensuring the application can always run.
    """
    final_config = deep_merge({}, DEFAULT_CONFIG)
    logger.debug("Loaded embedded default configuration.")

    ensure_user_config_exists()

    user_config_path = Path.home() / ".config" / "ecli" / "config.toml"
    if user_config_path.is_file():
        try:
            user_config = toml.load(user_config_path)
            final_config = deep_merge(final_config, user_config)
            logger.info(f"Successfully loaded and merged user config from {user_config_path}")
        except Exception as e:
            logger.error(f"Could not parse user config '{user_config_path}': {e}. Using defaults.")

    return final_config


def get_file_icon(filename: Optional[str], config: Dict[str, Any]) -> str:
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


def safe_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """
    Executes a command safely, capturing output and handling common exceptions.
    """
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", **kwargs,
        )
    except FileNotFoundError as e:
        logger.error(f"Command not found: {cmd[0]!r}", exc_info=True)
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(e))
    except subprocess.TimeoutExpired as e:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -9, stdout=e.stdout or "", stderr=e.stderr or "")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while running command: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=str(e))


def deep_merge(base: Dict, override: Dict) -> Dict:
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


def hex_to_xterm(hex_color: str) -> int:
    """
    Converts a hexadecimal color string to the nearest xterm-256 color index.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return WHITE_FG_IDX
    try:
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return WHITE_FG_IDX

    if r == g == b:
        if r < 8: return 16
        if r > 248: return 231
        return round(((r - 8) / 247) * 24) + 232

    return int(
        16
        + (36 * round(r / 255 * 5))
        + (6 * round(g / 255 * 5))
        + round(b / 255 * 5)
    )
