#!/usr/bin/env python3
# /ecli/main.py
"""
ECLI Main Entry Point
=====================

This script serves as the primary entry point for launching the ECLI editor.
It orchestrates the entire application startup sequence in a safe and structured manner:

1.  Environment Loading: Immediately loads environment variables from the user's
    personal configuration directory (`~/.config/ecli/.env`). This ensures that
    user-specific API keys and secrets are available globally before any other
    part of the application runs.

2.  Path Setup: Modifies `sys.path` to ensure the `ecli` package is correctly
    located and importable, which is crucial for both source and bundled execution.

3.  Configuration and Logging: Loads the application's configuration files and
    initializes the logging system based on those settings. This is done before
    any core imports to ensure all startup activities are properly logged.

4.  Core Application Import: After basic setup, it imports the main `Ecli` class.

5.  Curses Wrapper: Uses `curses.wrapper` to safely initialize and tear down
    the curses environment, preventing terminal corruption on exit or crash.

6.  Application Run: Instantiates the `Ecli` class and starts its main event loop.
"""

import curses
import locale
import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- Step 1: Load Environment Variables from User's Config Directory ---
# This is a critical step. We explicitly load the .env file from a consistent,
# user-specific location. This prevents the application's behavior from changing
# based on the current working directory and ensures it always uses the
# intended secrets file.
# The `utils.py` module will handle the creation of this file if it doesn't exist.
try:
    user_config_dir = Path.home() / ".config" / "ecli"
    dotenv_path = user_config_dir / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except Exception:
    # This might fail in unusual environments (e.g., no home directory).
    # Silently ignore, as logging is not yet configured. The app will later
    # fail gracefully if an API key is required but not found.
    pass


# --- Step 2: Set up the Python Path ---
# This ensures that Python can find the 'ecli' package modules.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Step 3: Immediate Logging and Configuration Setup ---
# We import only what is necessary for this step to set up logging ASAP.
# This ensures that ANY subsequent error, including import failures, will be logged.
try:
    from ecli.utils.logging_config import setup_logging
    from ecli.utils.utils import load_config

    # Load config and set up logging immediately.
    config = load_config()
    setup_logging(config)

    # Now, obtain the logger for this module.
    logger = logging.getLogger("ecli")

except Exception as e:
    # If the logging/config system itself fails, there's no choice but to print
    # to stderr and exit, as we cannot log the failure.
    print(f"FATAL: Could not initialize configuration or logging system: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# --- Step 4: Import the Core Application ---
# Now that logging is configured, it's safe to import the main Ecli class.
try:
    from ecli.core.Ecli import Ecli
except ImportError as e:
    logger.critical(f"Failed to import a critical application component: {e}", exc_info=True)
    sys.exit(1)


# --- Step 5: Curses Application Runner ---
def main_app_runner(stdscr: 'curses._CursesWindow', config: dict, file_to_open: str | None) -> None:
    """
    This function is the target for `curses.wrapper`. It sets up and runs the editor.
    """
    # Set a short escape delay for better responsiveness (e.g., for Alt key combos).
    try:
        curses.set_escdelay(25)
    except Exception:
        os.environ.setdefault("ESCDELAY", "25")

    # Instantiate the main editor class.
    editor = Ecli(stdscr, config=config)

    # Ignore the terminal suspension signal (Ctrl+Z) to prevent the editor from
    # being backgrounded accidentally by the user's shell.
    if hasattr(signal, "SIGTSTP"):
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)

    # If a file was passed as a command-line argument, open it.
    if file_to_open and os.path.exists(file_to_open):
        editor.open_file(file_to_open)

    # Start the editor's main event loop. This will run until editor.running is False.
    editor.run()


def start() -> None:
    """Initializes the environment and launches the curses application."""
    logger.info("ECLI editor starting up...")

    # Set the locale to the user's default to ensure correct character handling.
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        logger.warning(
            "Could not set system locale. Character rendering may be affected."
        )

    # Get the filename from command-line arguments, if provided.
    file_to_open = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        # `curses.wrapper` handles all the setup and teardown of the curses
        # environment, ensuring the terminal is restored to a usable state on
        # exit or crash.
        curses.wrapper(main_app_runner, config, file_to_open)
        logger.info("ECLI editor shut down gracefully.")
    except Exception:
        # Catch any unhandled exception that bubbles up to the top level.
        logger.critical("Unhandled exception at the top level.", exc_info=True)
        sys.exit(1)
    finally:
        # A final, best-effort attempt to clear the screen after curses has finished.
        if sys.platform != "win32":
            print("\033c", end="")  # ANSI reset for Unix-like systems
        else:
            os.system("cls")


if __name__ == "__main__":
    start()
