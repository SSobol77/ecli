# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/utils/logging_config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ecli.utils.logging_config
===========================

This module provides a robust and flexible logging configuration utility for the ECLI application.
It defines global logger objects and a single setup function, `setup_logging`, which configures
application-wide logging handlers and log levels based on a supplied configuration dictionary.

Features:
    - Rotating file logging for general application events (editor.log).
    - Runtime logging is file-backed; curses sessions do not attach console handlers.
    - Optional separate error log file (error.log) for ERROR and CRITICAL events.
    - Optional key event tracing (keytrace.log) enabled via the MOOPS2_KEYTRACE environment variable.
    - Automatic creation of log directories, with fallback to the system temp directory on failure.
    - Safe reconfiguration: clears existing handlers to avoid duplicate logs when called multiple times.
    - Never raises exceptions; setup-time failures use explicit stderr fallback before curses takes ownership.

Usage:
    Import the module and call `setup_logging()` early in your application's startup sequence,
    optionally passing a configuration dictionary to customize log levels and handlers.

    >>> from ecli.utils import logging_config
    >>> logging_config.setup_logging({
    ... })

Globals:
    logger: Main application logger ("ecli").
    KEY_LOGGER: Logger for raw key-press trace events ("ecli.keyevents").

Functions:
    setup_logging(config: Optional[Dict[str, Any]] = None) -> None
        Configures logging handlers and log levels for the application.
"""

import logging
import logging.handlers
import os
import sys
import tempfile
from types import TracebackType
from typing import Any, Optional


# ======================== Global loggers ========================
# These logger objects are created at import-time but remain unconfigured
# until ``setup_logging()`` attaches appropriate handlers.
logger = logging.getLogger("ecli")  # main application logger
KEY_LOGGER = logging.getLogger("ecli.keyevents")  # raw key-press trace


def log_exception_to_file_handlers(
    message: str,
    exc: BaseException,
    *,
    logger_name: str = "ecli",
) -> None:
    """Log an exception through file-backed handlers without writing to stderr."""
    root_logger = logging.getLogger()
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None] = (
        type(exc),
        exc,
        exc.__traceback__,
    )
    record = root_logger.makeRecord(
        logger_name,
        logging.ERROR,
        __file__,
        0,
        message,
        (),
        exc_info,
        None,
    )

    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler) and record.levelno >= handler.level:
            handler.handle(record)


def log_record_to_file_handlers(
    level: int,
    message: str,
    *args: Any,
    logger_name: str = "ecli",
) -> None:
    """Log a non-exception record through file-backed handlers only."""
    root_logger = logging.getLogger()
    record = root_logger.makeRecord(
        logger_name,
        level,
        __file__,
        0,
        message,
        args,
        None,
        None,
    )

    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler) and record.levelno >= handler.level:
            handler.handle(record)


# --- Enhanced Logging Setup Function ---
def setup_logging(config: Optional[dict[str, Any]] = None) -> None:
    """Configures application-wide logging handlers and log levels.

    This function sets up a flexible logging system with support for file logging,
    error-only file logging, and optional key event tracing.
    It clears existing root logger handlers to avoid duplicate logs and applies
    settings from the provided configuration dictionary.

    The routine sets up a flexible logging stack with up to four
    independent handlers:

    1. File handler – rotating editor.log capturing everything from
       the configured `file_level` (default DEBUG) upward.
    2. Console handler – intentionally disabled for runtime logging so log
       records cannot corrupt the curses screen.
    3. Error-file handler – optional rotating error.log that stores
       only ERROR and CRITICAL events.
    4. Key-event handler – optional rotating keytrace.log enabled
       when the environment variable ``MOOPS2_KEYTRACE`` is set to
       ``1/true/yes``; attached to the ``ecli.keyevents`` logger.

    Existing handlers on the root logger are cleared to avoid duplicate
    records when the function is invoked multiple times (e.g. in unit
    tests).

    Args:
        config (dict | None): Optional application configuration blob.
            Only the ``["logging"]`` sub-section is consulted; recognised
            keys are:

            - ``file_level`` (str): Log-level for editor.log
              (DEBUG, INFO, …).  Default: ``"DEBUG"``.
            - ``console_level`` (str): Retained for configuration
              compatibility; runtime console logging is disabled.
            - ``log_to_console`` (bool): Retained for configuration
              compatibility; runtime console logging is disabled.
            - ``separate_error_log`` (bool): Whether to create error.log.
              Default: ``False``.

    Side Effects:
        - Creates directories for log files if they don’t exist; falls
          back to the system temp directory on failure.
        - Replaces all handlers on the root logger.
        - Configures the namespace logger ``ecli.keyevents`` to not
          propagate and attaches/clears its handlers independently.

    Notes:
        The function never raises; setup-time I/O or permission errors use
        explicit stderr fallback before curses starts, and the logging subsystem
        continues with a best-effort configuration.

    Example:
        >>> config = {
        ...     "logging": {
        ...         "file_level": "INFO",
        ...         "console_level": "ERROR",
        ...         "log_to_console": True,
        ...         "separate_error_log": True
        ...     }
        ... }
        >>> setup_logging(config)
    """
    if config is None:
        config = {}
    # Main Application Logger (e.g., for editor.log). The log directory follows
    # the same precedence as config: ECLI_LOG_DIR override, then a development
    # checkout (<repo>/logs), then the installed-user ~/.config/ecli/logs path.
    # A source checkout never writes logs into ~/.config/ecli.
    from ecli.utils.utils import resolve_log_dir

    log_dir = str(resolve_log_dir())
    log_filename = os.path.join(log_dir, "editor.log")
    # Use .get safely for nested dictionaries
    logging_config = config.get("logging", {})
    log_file_level_str = logging_config.get("file_level", "DEBUG").upper()
    log_file_level = getattr(logging, log_file_level_str, logging.DEBUG)

    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e_mkdir:
            print(
                f"Error creating log directory '{log_dir}': {e_mkdir}", file=sys.stderr
            )
            log_filename = os.path.join(tempfile.gettempdir(), "ecli.log")
            print(f"Logging to temporary file: '{log_filename}'", file=sys.stderr)

    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(name)-15s - %(message)s (%(filename)s:%(lineno)d)"
    )
    file_handler = None
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_filename, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_file_level)
    except Exception as e_fh:
        print(
            f"Error setting up file logger for '{log_filename}': {e_fh}. File logging may be impaired.",
            file=sys.stderr,
        )

    # Console logging is unsafe once curses owns the terminal. Startup failures
    # that must be visible use explicit stderr printing in __main__.py instead.
    log_to_console_enabled = False
    console_handler = None
    if log_to_console_enabled:
        console_level_str = logging_config.get("console_level", "WARNING").upper()
        console_log_level = getattr(logging, console_level_str, logging.WARNING)

        console_formatter = logging.Formatter(
            "%(levelname)-8s - %(name)-12s - %(message)s"
        )  # Slightly shorter name field
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_log_level)

    # Optional Separate Error Log File
    separate_error_log_enabled = logging_config.get("separate_error_log", False)
    error_file_handler = None
    if separate_error_log_enabled:
        error_log_filename = os.path.join(log_dir, "error.log")
        try:
            error_log_dir = os.path.dirname(error_log_filename)
            if error_log_dir and not os.path.exists(error_log_dir):
                os.makedirs(error_log_dir, exist_ok=True)

            error_file_handler = logging.handlers.RotatingFileHandler(
                error_log_filename,
                maxBytes=1 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            error_file_handler.setFormatter(file_formatter)
            error_file_handler.setLevel(logging.ERROR)
        except Exception as e_efh:
            print(
                f"Error setting up separate error log '{error_log_filename}': {e_efh}.",
                file=sys.stderr,
            )

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Clear existing root handlers to avoid duplicates

    if file_handler:
        root_logger.addHandler(file_handler)
    if console_handler:
        root_logger.addHandler(console_handler)
    if error_file_handler:
        root_logger.addHandler(error_file_handler)
    if not root_logger.handlers:
        # Prevent logging.lastResort from writing warnings/errors to stderr if
        # file logging could not be initialized. Setup-time stderr diagnostics
        # above are intentional; runtime logging records must stay off curses.
        root_logger.addHandler(logging.NullHandler())

    root_logger.setLevel(
        log_file_level
    )  # Set root to the most verbose level needed by file handlers
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    # Key Event Logger
    key_event_logger = logging.getLogger("ecli.keyevents")
    key_event_logger.propagate = False
    key_event_logger.setLevel(logging.DEBUG)
    # Clear any handlers that might have been added if setup_logging is called multiple times
    key_event_logger.handlers = []

    if os.environ.get("MOOPS2_KEYTRACE", "").lower() in {"1", "true", "yes"}:
        try:
            key_trace_filename = os.path.join(log_dir, "keytrace.log")
            key_trace_log_dir = os.path.dirname(key_trace_filename)
            if key_trace_log_dir and not os.path.exists(key_trace_log_dir):
                os.makedirs(key_trace_log_dir, exist_ok=True)

            key_trace_handler = logging.handlers.RotatingFileHandler(
                key_trace_filename,
                maxBytes=1 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            key_trace_formatter = logging.Formatter("%(asctime)s - %(message)s")
            key_trace_handler.setFormatter(key_trace_formatter)
            key_event_logger.addHandler(key_trace_handler)
            # Do not enable propagate for key_event_logger unless you want key traces in the main log too.
            logging.info(
                "Key event tracing enabled, logging to '%s'.", key_trace_filename
            )  # Use root logger for this info
        except Exception as e_keytrace:
            logging.error(
                f"Failed to set up key trace logging: {e_keytrace}", exc_info=True
            )  # Use root logger
            key_event_logger.disabled = True
    else:
        key_event_logger.addHandler(logging.NullHandler())
        key_event_logger.disabled = True
        logging.debug("Key event tracing is disabled.")  # Use root logger

    logging.info(
        "Logging setup complete. Root logger level: %s.",
        logging.getLevelName(root_logger.level),
    )
    if file_handler:
        logging.info(
            f"File logging to '{log_filename}' at level: {logging.getLevelName(file_handler.level)}."
        )
    if console_handler:
        logging.info(
            f"Console logging to stderr at level: {logging.getLevelName(console_handler.level)}."
        )
    if error_file_handler:
        logging.info("Error logging to 'error.log' at level: ERROR.")
