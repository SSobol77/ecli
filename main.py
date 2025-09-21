#!/usr/bin/env python3
# /ecli/main.py
"""ECLI Main Entry Point

This script serves as the primary entry point for launching the ECLI editor.
It orchestrates the entire application startup sequence in a safe and
structured manner:

1.  Environment Loading: Immediately loads environment variables from a `.env`
    file using `dotenv`. This ensures API keys and other secrets are available
    to all subsequent modules.
2.  Path Setup: Modifies `sys.path` to ensure the `ecli` package is correctly
    located and importable.
3.  Configuration and Logging: Loads the `config.toml` file and initializes
    the logging system based on its settings. This is done before any major
    imports to ensure all startup activities are logged.
4.  Core Application Import: Imports the main `Ecli` class.
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

from dotenv import load_dotenv

# 1. Load Environment Variables First
# This is the most critical step. By loading .env here, we ensure that all
# environment variables (like API keys) are available globally before any
# other part of the application, including configuration loading and module
# imports, is executed.
load_dotenv()


# 2. Set up the path
# This must follow environment loading so that Python can find the 'ecli' package.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 3. Immediate logging setup
# We import ONLY what is needed for logging and set it up right away.
# This ensures that ANY subsequent error, including import errors, will be logged.
try:
    from ecli.utils.logging_config import setup_logging
    from ecli.utils.utils import load_config

    # Load config and set up logging immediately.
    config = load_config()
    setup_logging(config)

    # Now, obtain the logger for this module.
    logger = logging.getLogger("ecli")

except Exception as e:
    # If logging setup itself fails, there's no choice but to print to stderr.
    print(f"FATAL: Could not initialize logging system: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc()
    sys.exit(1)

# 4. Import the rest of the application
# Now that logging is configured, it's safe to import the main Ecli class.
try:
    from ecli.core.Ecli import Ecli
except ImportError as e:
    logger.critical(f"Failed to import a critical component: {e}", exc_info=True)
    sys.exit(1)


# 5. Curses Application Runner
def main_app_runner(stdscr, config, file_to_open):
    """This function is the target for `curses.wrapper`. It sets up and runs the editor."""
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


def start():
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
        # `curses.wrapper` handles all the setup and teardown of the curses environment,
        # ensuring the terminal is restored to a usable state on exit or crash.
        curses.wrapper(main_app_runner, config, file_to_open)
        logger.info("ECLI editor shut down gracefully.")
    except Exception:
        # Catch any unhandled exception that bubbles up to the top.
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
