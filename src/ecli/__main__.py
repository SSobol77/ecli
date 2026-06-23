#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/__main__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""
ECLI Main Entry Point
=====================

This script is the primary entry point for launching the ECLI editor. It performs:
1) Environment Loading: reads the dev-checkout <repo>/.env or the installed
   ~/.config/ecli/.env early, so secrets are available.
2) Path Setup: ensures the ecli package is importable.
3) Configuration & Logging: loads config and initializes logging ASAP.
4) Core Import: imports the Ecli class after logging is ready.
5) Curses Wrapper: safely initializes/tears down curses to avoid terminal corruption.
6) Application Run: instantiates Ecli and starts its main loop.
"""

from __future__ import annotations

import curses
import locale
import logging
import os
import signal
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

from ecli import __version__

# --- Step 2: Set up the Python Path ---
# Ensure the 'ecli' package is importable for both source and bundled runs.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def _default_log_path() -> Path:
    # Follow the same dev-checkout vs installed-user resolution as runtime
    # logging. Falls back to the installed-user path if the resolver cannot be
    # imported yet (very early startup failures).
    try:
        from ecli.utils.utils import resolve_log_dir  # noqa: PLC0415

        return resolve_log_dir() / "editor.log"
    except Exception:
        return Path.home() / ".config" / "ecli" / "logs" / "editor.log"


def _write_unconfigured_startup_traceback(message: str, exc: BaseException) -> None:
    """Best-effort traceback logging before configured logging is available."""
    try:
        log_path = _default_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"CRITICAL - ecli - {message}: {exc}\n")
            log_file.writelines(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
    except Exception:
        return


def _print_startup_failure(message: str, exc: BaseException) -> None:
    print(f"ECLI startup failure: {message}: {exc}", file=sys.stderr)
    print(f"Full traceback logged to: {_default_log_path()}", file=sys.stderr)


def _exit_startup_failure(message: str, exc: BaseException) -> None:
    logger.critical("%s: %s", message, exc, exc_info=True)
    _print_startup_failure(message, exc)
    sys.exit(1)


def _print_help() -> None:
    print(
        "Usage: ecli [OPTIONS] [FILE]\n"
        "\n"
        "ECLI terminal-first engineering operations workbench.\n"
        "\n"
        "Options:\n"
        "  -h, --help       Show this help and exit.\n"
        "  --version        Show version and exit.\n"
        "  --services       Print ServiceRegistry service status.\n"
        "  --doctor         Run read-only SystemDoctor diagnostics.\n"
        "  --plan-preview   Print a draft CommandPlan preview.\n"
    )


def _print_version() -> None:
    print(f"ecli {__version__}")


# --- Step 2.5: Explicit read-only service CLI dispatch ---
# Preserve the default editor path for `python -m ecli [file]`. Only explicit
# Phase 1 service flags are handled here before curses/editor initialization.
try:
    if sys.argv[1:] in (["--help"], ["-h"]):
        _print_help()
        sys.exit(0)
    if sys.argv[1:] == ["--version"]:
        _print_version()
        sys.exit(0)

    from ecli.cli import is_service_cli, run_service_cli

    if is_service_cli(sys.argv[1:]):
        sys.exit(run_service_cli(sys.argv[1:]))
except SystemExit:
    raise
except Exception as e:
    print(f"ECLI service CLI error: {e}", file=sys.stderr)
    sys.exit(1)

# --- Step 1: Load Environment Variables ---
# In a development checkout, load <repo>/.env; when installed, load
# ~/.config/ecli/.env. The development checkout never reads ~/.config/ecli/.env.
# Loaded before runtime imports so secrets/overrides are available early.
try:
    from dotenv import load_dotenv

    try:
        from ecli.utils.utils import resolve_env_file

        dotenv_path = resolve_env_file()
    except Exception:
        dotenv_path = Path.home() / ".config" / "ecli" / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
except ImportError as e:
    print(f"Warning: Could not load dotenv support: {e}", file=sys.stderr)
except (RuntimeError, PermissionError, OSError) as e:
    print(f"Warning: Could not load .env file: {e}", file=sys.stderr)
except Exception as e:
    print(
        f"Warning: Unexpected error loading .env, continuing with defaults: {e}",
        file=sys.stderr,
    )

# --- Step 3: Immediate Logging and Configuration Setup ---
try:
    from ecli.utils.logging_config import setup_logging
    from ecli.utils.utils import load_config

    config: dict[str, Any] = load_config()
    setup_logging(config)
    logger = logging.getLogger("ecli")
except Exception as e:
    message = "Could not initialize configuration or logging system"
    _write_unconfigured_startup_traceback(message, e)
    _print_startup_failure(message, e)
    traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
    sys.exit(1)

# --- Step 4: Import the Core Application ---
try:
    from ecli.core.Ecli import Ecli
except Exception as e:
    _exit_startup_failure(
        "Failed to import a critical application component",
        e,
    )


def _resolve_cli_path(argv: list[str]) -> Optional[Path]:
    """
    Resolve an optional CLI path from argv[1], expanded to a user path.
    The file does NOT need to exist on disk; we pass the intended path
    to the editor so Save/Write defaults to that name.
    """
    if len(argv) <= 1:
        return None
    raw = argv[1].strip()
    if not raw:
        return None
    try:
        candidate = Path(raw).expanduser()
        path_str = str(candidate)
        if len(path_str) > 4096:
            logger.warning("Provided path is too long: %r", raw)
            return None
        return candidate
    except (RuntimeError, ValueError) as e:
        logger.warning("Invalid path provided: %r - %s", raw, e)
        return None
    except Exception as e:
        logger.error("Unexpected error resolving path %r: %s", raw, e)
        return None


def _preload_cli_document(editor: Ecli, candidate: Path) -> None:
    """
    Tell the editor to open/create a buffer named after 'candidate'.
    This function is robust across possible editor APIs:

    Priority:
      1) editor.preload_cli_document(Path)           # preferred if available
      2) editor.open_or_create(str|Path)             # open if exists, else create empty buffer with path
      3) editor.open_file(str|Path) if exists else   # open if on disk
         editor.create_empty_buffer_with_name(str)   # create empty buffer with that name
      4) LAST RESORT: touch the file on disk and open it (ensures correct default path on Save).
    """
    # Normalize to absolute string path for broadest API compatibility
    abs_path = str(candidate.resolve())

    # 1) Preferred explicit API
    if hasattr(editor, "preload_cli_document"):
        try:
            editor.preload_cli_document(candidate)  # type: ignore[attr-defined]
            return
        except Exception:
            logger.debug(
                "preload_cli_document(Path) failed, trying fallbacks.", exc_info=True
            )

    # 2) Generic open-or-create
    if hasattr(editor, "open_or_create"):
        try:
            editor.open_or_create(abs_path)  # type: ignore[attr-defined]
            return
        except Exception:
            logger.debug(
                "open_or_create(path) failed, trying fallbacks.", exc_info=True
            )

    # 3) Open if exists, else create in-memory buffer with this name
    if os.path.exists(abs_path):
        try:
            editor.open_file(abs_path)
            return
        except Exception:
            logger.debug(
                "open_file(existing path) failed, trying buffer creation.",
                exc_info=True,
            )
    else:
        # Try a few common method names to set a new-named buffer without touching disk
        for meth_name in (
            "create_empty_buffer_with_name",
            "new_buffer_named",
            "new_file_with_name",
            "new_file",
        ):
            if hasattr(editor, meth_name):
                try:
                    meth = getattr(editor, meth_name)
                    # Try with a kw if method supports it, otherwise positional
                    try:
                        meth(initial_path=abs_path)  # type: ignore[call-arg]
                    except TypeError:
                        meth(abs_path)  # type: ignore[misc]
                    return
                except Exception:
                    logger.debug(
                        "%s(...) failed, continue fallbacks.", meth_name, exc_info=True
                    )
                    continue

    # 4) Last resort: create an empty file on disk so open_file() succeeds.
    # This guarantees the buffer is named as requested when all nicer APIs are absent.
    try:
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        Path(abs_path).touch(exist_ok=True)
        editor.open_file(abs_path)
        return
    except Exception:
        logger.warning(
            "Fallback touch+open failed for %s; starting unnamed buffer.",
            abs_path,
            exc_info=True,
        )


# --- Step 5: Curses Application Runner ---
def main_app_runner(
    stdscr: curses.window, config: dict[str, Any], file_to_open: Optional[str]
) -> None:
    """
    Target for `curses.wrapper`. Initializes terminal responsiveness and runs the editor.

    Args:
        stdscr: Curses standard screen window provided by wrapper.
        config: Application configuration dict.
        file_to_open: Optional CLI path (may or may not exist on disk).

    Behavior:
        - Sets a short ESC delay for snappy Alt/Meta combos.
        - Instantiates Ecli with (stdscr, config).
        - Blocks terminal suspension (SIGTSTP) to avoid accidental backgrounding.
        - If CLI path provided, opens or preloads buffer with that name (even if not on disk).
        - Starts the editor main loop.
    """
    # Keep Alt/ESC combos responsive on TTY (especially FreeBSD consoles).
    try:
        curses.set_escdelay(25)
    except Exception:
        os.environ.setdefault("ESCDELAY", "25")

    editor = Ecli(stdscr, config=config)

    # Ignore terminal suspension (Ctrl+Z), typical for full-screen TUIs.
    if hasattr(signal, "SIGTSTP"):
        try:
            signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        except Exception:
            # Some restricted environments may disallow changing signal handlers.
            pass

    # Preload CLI document name: open if exists, otherwise create an empty buffer with that path.
    if file_to_open:
        try:
            _preload_cli_document(editor, Path(file_to_open).expanduser())
        except Exception:
            logger.warning(
                "Failed to preload CLI document: %s", file_to_open, exc_info=True
            )

    # Start the editor main event loop (runs until editor.running is False).
    editor.run()


def start() -> None:
    """
    Initializes locale and runs the curses application via wrapper.
    Also toggles application keypad mode around the curses lifecycle to ensure
    arrow keys (and their modifiers) are delivered to the app instead of the terminal.
    """
    logger.info("ECLI editor starting up...")

    # Locale is important for proper character width/encoding behavior in curses.
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        logger.warning(
            "Could not set system locale. Character rendering may be affected."
        )

    file_to_open = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        # Enable "Application Cursor Keys" + keypad mode *before* curses starts.
        # \x1b[?1h → DECCKM (application cursor keys), \x1b= → DECKPAM (keypad application mode)
        if sys.platform != "win32":
            sys.stdout.write("\x1b[?1h\x1b=")
            sys.stdout.flush()

        # wrapper() will set up/tear down curses safely.
        curses.wrapper(main_app_runner, config, file_to_open)

        logger.info("ECLI editor shut down gracefully.")
    except Exception as e:
        logger.critical("Unhandled exception at the top level.", exc_info=True)
        _print_startup_failure("Unhandled exception at the top level", e)
        sys.exit(1)
    finally:
        # Disable application modes after curses finishes:
        # \x1b[?1l → normal cursor keys, \x1b> → keypad numeric mode
        if sys.platform != "win32":
            try:
                sys.stdout.write("\x1b[?1l\x1b>")
                sys.stdout.flush()
            except Exception:
                pass

        # Best-effort final clear to avoid artifacts after exit.
        if sys.platform != "win32":
            try:
                print("\033c", end="")
            except Exception:
                pass
        else:
            # On Windows, do a standard clear.
            os.system("cls")


def main() -> int:
    """Run the ECLI application entry point."""
    start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
