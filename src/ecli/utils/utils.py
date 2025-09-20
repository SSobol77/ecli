# --- utils.py ---
"""ecli.utils.utils.py
===========================
utils.py - Utility Functions for ECLI Editor
This module provides a collection of utility functions and constants used throughout the ECLI editor project.
It includes:
- Color index constants for terminal UI customization.
- File icon retrieval logic based on file names and extensions, supporting flexible configuration.
- Robust configuration loading and deep merging of default and user-specific TOML files.
- Safe execution of external commands with error handling and output capture.
- Recursive dictionary merging utility for configuration management.
- Conversion of hexadecimal RGB colors to the nearest xterm-256 color index for terminal compatibility.
These utilities are designed to enhance the flexibility, reliability, and user experience of the ECLI editor,
while ensuring maintainable and reusable code.
"""

import logging
import os
import subprocess
import sys
from typing import Any, Optional

import toml


# --- Constants for Color Indices ---
# These constants represent xterm-256 color indices for various purposes.
# They are used to define colors for text and backgrounds in the terminal.
CALM_BG_IDX = 236  # xterm-256 “graphite” ≈ #303030
WHITE_FG_IDX = 255  # full white


# --- File Icon Retrieval Function ---
def get_file_icon(filename: Optional[str], config: dict[str, Any]) -> str:
    """Returns an icon string representing the file type based on its name and extension, using the provided
    configuration.

    This function prioritizes exact filename matches (such as "Makefile" or "Dockerfile") before checking
    file extensions to determine the appropriate icon. If no match is found, a default or text icon is returned.


        str: The icon string corresponding to the file type.

    Raises:
        None
    Example:
        >>> config = {
        ...     "file_icons": {"default": "❓", "text": "📝", "python": "🐍"},
        ...     "supported_formats": {"python": [".py"], "text": [".txt", ".md", "README"]}
        ... }
        >>> get_file_icon("example.py", config)
        '🐍'
    """
    if not config or not isinstance(config, dict):
        logging.error(
            "get_file_icon: Invalid configuration provided. Using default icon."
        )
        return "❓"  # Default icon if config is invalid

    # Extract file icons and default icon from the configuration
    file_icons = config.get("file_icons", {})
    default_icon = file_icons.get(
        "default", "❓"
    )  # Default if no specific icon is found
    text_icon = file_icons.get(
        "text", "📝 "
    )  # Specific default for text-like or new files

    if not filename:  # Handles new, unsaved files or None input
        return default_icon

        # Normalize filename for matching (lowercase)
    filename_lower = filename.lower()
    base_name_lower = os.path.basename(
        filename_lower
    )  # e.g., "myfile.txt" from "/path/to/myfile.txt"

    supported_formats: dict[str, list[str]] = config.get("supported_formats", {})

    if not file_icons or not supported_formats:
        logging.warning(
            "get_file_icon: 'file_icons' or 'supported_formats' missing in config. Using default icon."
        )
        return default_icon

    # CHECK FOR DIRECT FILENAME MATCHES
    # Check for direct filename matches (e.g., "Makefile", "Dockerfile", ".gitignore")
    # These often don't have typical extensions but are specific file types.
    # The extensions list for these in `supported_formats` might contain the full name.
    for icon_key, extensions_or_names in supported_formats.items():
        if isinstance(extensions_or_names, list):
            for ext_or_name in extensions_or_names:
                # If the "extension" is actually a full filename (e.g., "makefile", "dockerfile")
                # or a name starting with a dot (e.g., ".gitignore")
                if (
                    not ext_or_name.startswith(".")
                    and base_name_lower == ext_or_name.lower()
                ):
                    return file_icons.get(icon_key, default_icon)
                if (
                    ext_or_name.startswith(".")
                    and base_name_lower == ext_or_name.lower()
                ):  # Handles .gitignore, .gitattributes
                    return file_icons.get(icon_key, default_icon)

    # CHECK FOR EXTENSION MATCHES
    # Handle complex extensions like ".tar.gz" by checking parts of the extension.
    # We can get all "extensions" by splitting by dot.
    # Example: "myfile.tar.gz" -> parts ["myfile", "tar", "gz"]
    # We want to check for ".gz", ".tar.gz"
    name_parts = base_name_lower.split(".")
    if len(name_parts) > 1:  # If there is at least one dot
        # Iterate from the longest possible extension to the shortest
        # e.g., for "file.tar.gz", check ".tar.gz", then ".gz"
        for i in range(1, len(name_parts)):
            # Construct extension like ".gz", ".tar.gz"
            current_extension_to_check = "." + ".".join(name_parts[i:])

            for icon_key, defined_extensions in supported_formats.items():
                if isinstance(defined_extensions, list):
                    # Convert defined extensions to lowercase for comparison
                    lower_defined_extensions = [
                        ext.lower() for ext in defined_extensions
                    ]
                    ext_to_match = current_extension_to_check[1:]  # Remove leading dot

                    if ext_to_match in lower_defined_extensions:
                        return file_icons.get(icon_key, default_icon)

    # If no specific match by full name or extension, return the generic text icon
    # or a more generic default if text icon is also not found (though unlikely).
    # The problem description implied returning text_icon as a final fallback.
    # Using `default_icon` might be more appropriate if truly nothing matched.
    # Let's stick to text_icon as the ultimate fallback if other logic fails.
    logging.debug(
        f"get_file_icon: No specific icon found for '{filename}'. Falling back to text icon."
    )
    return text_icon


# -------- Configuration Loading (if defined in this file) ---------
def load_config() -> dict[str, Any]:
    """Loads, merges, and validates the application configuration.

    This function implements a robust, multi-layered configuration strategy:
    1.  Loads Built-in Defaults: It first loads the base configuration
        from `default_config.toml`, which is shipped with the application.
        This file ensures that the editor has a complete and functional set of
        defaults to operate correctly. This step is critical; if the default
        config is missing or corrupt, the application will exit.

    2.  Overrides with User Settings: It then looks for a `config.toml` file
        in the current working directory. If found, it loads the user's settings
        and recursively merges them on top of the defaults. This allows users to
        customize any part of the configuration without needing to replicate
        the entire default file.

    3.  Ensures Integrity: The merging process is "deep", meaning nested
        dictionaries (like `[colors]` or `[keybindings]`) are merged key-by-key,
        rather than being replaced entirely.

    This approach provides both stability through built-in defaults and
    flexibility through user-specific overrides. All file I/O and parsing
    errors for the *user* config are gracefully handled and logged, allowing
    the application to fall back to the default settings.

    Returns:
        Dict[str, Any]: A dictionary representing the final, merged configuration.

    Raises:
        SystemExit: If the critical `default_config.toml` file cannot be loaded.
    """
    # Load Built-in Default Configuration
    default_config: dict[str, Any] = {}
    try:
        # Define the absolute path to the defaults file relative to the current file (utils.py)
        # This ensures that it will be found regardless of where the editor is launched from.
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(current_script_dir, "default_config.toml")

        with open(default_config_path, encoding="utf-8") as f:
            default_config = toml.load(f)
        logging.debug(
            f"Successfully loaded default configuration from {default_config_path}"
        )

    except FileNotFoundError:
        # This is a critical error - the application cannot run without basic configuration.
        logging.critical(
            "FATAL: Default configuration file 'default_config.toml' not found. Application cannot start."
        )
        sys.exit(
            "Error: Default configuration is missing. Please restore the application files."
        )
    except Exception as e:
        logging.critical(
            f"FATAL: Could not parse 'default_config.toml': {e}. Application cannot start.",
            exc_info=True,
        )
        sys.exit(
            "Error: Default configuration is corrupt. Please restore the application files."
        )

    # Load and Merge User-Specific Configuration
    user_config_path = "config.toml"  # Look for it in the current working directory
    user_config: dict[str, Any] = {}
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, encoding="utf-8") as f_user:
                user_config = toml.load(f_user)
            logging.debug(f"Loaded user overrides from {user_config_path}")
        except toml.TomlDecodeError as e_toml:
            logging.error(
                f"TOML parse error in user config '{user_config_path}': {e_toml}. User settings will be ignored."
            )
        except Exception as e_user:
            logging.error(
                f"Could not read user config '{user_config_path}': {e_user}. User settings will be ignored.",
                exc_info=True,
            )
    else:
        logging.debug(
            f"No user config file found at '{user_config_path}'. Using default settings."
        )

    # Perform Deep Merge
    # User settings override defaults.
    final_config = deep_merge(default_config, user_config)

    logging.info("Configuration loaded and merged successfully.")
    return final_config


# --------- Utility Functions ---------
# --- Safe Command Execution Utility ---
def safe_run(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """This function wraps subprocess.run to execute a command with enhanced safety:
    - Always captures stdout and stderr.
    - Always returns a CompletedProcess, even on error.
    - Handles common exceptions (command not found, timeout, OS errors) gracefully.
    - Logs warnings if the 'check' argument is provided, but always disables it internally.

    Args:
        cmd (list[str]): The command and arguments to execute.
        cwd (Optional[str], optional): Working directory to run the command in. Defaults to None.
        timeout (Optional[float], optional): Timeout in seconds for command execution. Defaults to None.
        **kwargs (Any): Additional keyword arguments passed to subprocess.run.

    Returns:
        subprocess.CompletedProcess: The result of the executed command, with stdout and stderr as strings.

    Raises:
        Does not raise; always returns a CompletedProcess. Logs errors and warnings as appropriate.
    """
    if "check" in kwargs:
        logging.warning("...")

    effective_kwargs = {
        "capture_output": True,
        "text": True,
        "check": False,
        "encoding": "utf-8",
        "errors": "replace",
        **kwargs,
    }

    if cwd is not None:
        effective_kwargs["cwd"] = cwd
    if timeout is not None:
        effective_kwargs["timeout"] = timeout

    try:
        return subprocess.run(cmd, **effective_kwargs)
    except FileNotFoundError as e:
        logging.error(f"safe_run: Command not found: {cmd[0]!r}", exc_info=True)
        return subprocess.CompletedProcess(
            cmd, returncode=127, stdout="", stderr=str(e)
        )
    except subprocess.TimeoutExpired as e:
        logging.warning(
            f"safe_run: Command timed out after {timeout}s: {' '.join(cmd)}"
        )
        return subprocess.CompletedProcess(
            cmd,
            returncode=-9,
            stdout=(e.stdout.decode("utf-8", "replace") if e.stdout else ""),
            stderr=(
                e.stderr.decode("utf-8", "replace")
                if e.stderr
                else "Process timed out."
            ),
        )
    except OSError as e:
        logging.error(f"safe_run: OS error while running {cmd}: {e}", exc_info=True)
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr=str(e))
    except Exception as _:
        logging.exception(
            f"safe_run: Unexpected error while executing: {' '.join(cmd)}"
        )
        return subprocess.CompletedProcess(
            cmd, returncode=-1, stdout="", stderr="Unexpected error occurred."
        )


# --- Dictionary Deep Merge Utility ---
def deep_merge(base: dict[Any, Any], override: dict[Any, Any]) -> dict[Any, Any]:
    """Recursively merges the `override` dictionary into the `base` dictionary.

    If a key exists in both dictionaries and both values are dictionaries,
    the merge is performed recursively. Otherwise, the value from `override`
    replaces the value from `base`. The original `base` dictionary is not modified;
    a new merged dictionary is returned.

    Args:
        base (Dict[Any, Any]): The base dictionary.
        override (Dict[Any, Any]): The dictionary whose values will override those in `base`.

    Returns:
        Dict[Any, Any]: A new dictionary containing the merged result.

    Example:
        >>> base = {'a': 1, 'b': {'x': 10, 'y': 20}}
        >>> override = {'b': {'y': 99, 'z': 100}, 'c': 3}
        >>> deep_merge(base, override)
        {'a': 1, 'b': {'x': 10, 'y': 99, 'z': 100}, 'c': 3}
    """
    result = dict(base)  # Start with a shallow copy of the base
    for key, override_value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            # If both values are dictionaries, recurse
            result[key] = deep_merge(base_value, override_value)
        else:
            # Otherwise, the override value takes precedence
            result[key] = override_value
    return result


# --- Hexadecimal to xterm-256 Color Conversion ---
def hex_to_xterm(hex_color: str) -> int:
    """Converts a hexadecimal RGB color to the nearest xterm-256 color index.

    This function maps a standard 24-bit hex color (e.g., "#RRGGBB") to the closest
    color in the xterm-256 color palette, which includes:
    - A 6×6×6 RGB color cube (indexes 16–231),
    - A grayscale ramp (indexes 232–255),
    - Basic ANSI colors (indexes 0–15).

    If the input is invalid (e.g. wrong format or contains non-hex characters),
    the function returns 255 (defaulting to white in most terminal color schemes).

    Args:
        hex_color (str): A 6-digit hexadecimal RGB color string, with or without leading '#'.

    Returns:
        int: The closest xterm-256 color index in the range [0, 255].
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return 255  # Default to white on error

    try:
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
    except ValueError:
        return 255

    # Simple grayscale check
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round(((r - 8) / 247) * 24) + 232

    # Color cube
    color_index = 16
    color_index += 36 * round(r / 255 * 5)
    color_index += 6 * round(g / 255 * 5)
    color_index += round(b / 255 * 5)
    return int(color_index)
