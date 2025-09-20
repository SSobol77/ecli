#!/usr/bin/env python3
# /ecli/main.py

import curses
import locale
import logging
import os
import signal
import sys


# 1. Set up the path
# This must be the very first action so that Python can find the 'ecli' package.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. Immediate logging setup
# We import ONLY what is needed for logging and set it up right away.
# This ensures that ANY subsequent error will be logged.
try:
    from ecli.utils.logging_config import setup_logging
    from ecli.utils.utils import load_config

    # Load config and set up logging immediately.
    config = load_config()
    setup_logging(config)

    # Now you can use the logger
    logger = logging.getLogger("ecli")

except Exception as e:
    # If even logging setup failed, print to console and exit.
    print(f"FATAL: Could not initialize logging system: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc()
    sys.exit(1)

# 3. Import everything else
# Now that logging works, it's safe to import the main class.
try:
    from ecli.core.Ecli import Ecli
except ImportError as e:
    logger.critical(f"Failed to import a critical component: {e}", exc_info=True)
    sys.exit(1)


# 4. Main application logic
def main_app_runner(stdscr, config, file_to_open):
    try:
        curses.set_escdelay(25)
    except Exception:
        os.environ.setdefault("ESCDELAY", "25")

    editor = Ecli(stdscr, config=config)

    if hasattr(signal, "SIGTSTP"):
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)

    if file_to_open and os.path.exists(file_to_open):
        editor.open_file(file_to_open)

    editor.run()


def start():
    logger.info("ECLI editor starting up...")

    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        logger.warning("Could not set system locale.")

    file_to_open = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        curses.wrapper(main_app_runner, config, file_to_open)
        logger.info("ECLI editor shut down gracefully.")
    except Exception:
        logger.critical("Unhandled exception at the top level.", exc_info=True)
        sys.exit(1)
    finally:
        if sys.platform != "win32":
            print("\033c", end="")
        else:
            os.system("cls")


if __name__ == "__main__":
    start()
