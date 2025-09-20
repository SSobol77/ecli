# ecli/utils/logging_config.py
"""ecli.utils.logging_config
===========================

This module provides a robust and flexible logging configuration utility for the ECLI application.
It defines global logger objects and a single setup function, `setup_logging`, which configures
application-wide logging handlers and log levels based on a supplied configuration dictionary.

Features:
    - Rotating file logging for general application events (editor.log).
    - Optional console logging to stderr with configurable log level.
    - Optional separate error log file (error.log) for ERROR and CRITICAL events.
    - Optional key event tracing (keytrace.log) enabled via the MOOPS2_KEYTRACE environment variable.
    - Automatic creation of log directories, with fallback to the system temp directory on failure.
    - Safe reconfiguration: clears existing handlers to avoid duplicate logs when called multiple times.
    - Never raises exceptions; all errors are reported to stderr and logging continues with best-effort.

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
from typing import Any, Optional


# ======================== Global loggers ========================
# These logger objects are created at import-time but remain unconfigured
# until ``setup_logging()`` attaches appropriate handlers.
logger = logging.getLogger("ecli")  # main application logger
KEY_LOGGER = logging.getLogger("ecli.keyevents")  # raw key-press trace


# --- Enhanced Logging Setup Function ---
def setup_logging(config: Optional[dict[str, Any]] = None) -> None:
    """Configures application-wide logging handlers and log levels.

    This function sets up a flexible logging system with support for file logging,
    console logging, error-only file logging, and optional key event tracing.
    It clears existing root logger handlers to avoid duplicate logs and applies
    settings from the provided configuration dictionary.

    The routine sets up a flexible logging stack with up to four
    independent handlers:

    1. File handler – rotating editor.log capturing everything from
       the configured `file_level` (default DEBUG) upward.
    2. Console handler – optional `stderr` output whose threshold is
       `console_level` (default WARNING).
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
            - ``console_level`` (str): Log-level for console output.
              Default: ``"WARNING"``.
            - ``log_to_console`` (bool): Disable/enable console handler.
              Default: ``True``.
            - ``separate_error_log`` (bool): Whether to create error.log.
              Default: ``False``.

    Side Effects:
        - Creates directories for log files if they don’t exist; falls
          back to the system temp directory on failure.
        - Replaces all handlers on the root logger.
        - Configures the namespace logger ``ecli.keyevents`` to not
          propagate and attaches/clears its handlers independently.

    Notes:
        The function never raises; all I/O or permission errors are
        reported to stderr and the logging subsystem continues with a
        best-effort configuration.

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
    # Main Application Logger (e.g., for editor.log)
    log_filename = "editor.log"
    # Use .get safely for nested dictionaries
    logging_config = config.get("logging", {})
    log_file_level_str = logging_config.get("file_level", "DEBUG").upper()
    log_file_level = getattr(logging, log_file_level_str, logging.DEBUG)

    log_dir = os.path.dirname(log_filename)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
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

    # Console Handler
    log_to_console_enabled = logging_config.get("log_to_console", True)
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
        error_log_filename = "error.log"
        try:
            error_log_dir = os.path.dirname(error_log_filename)
            if error_log_dir and not os.path.exists(error_log_dir):
                os.makedirs(error_log_dir)

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

    root_logger.setLevel(
        log_file_level
    )  # Set root to the most verbose level needed by file handlers

    # Key Event Logger
    key_event_logger = logging.getLogger("ecli.keyevents")
    key_event_logger.propagate = False
    key_event_logger.setLevel(logging.DEBUG)
    # Clear any handlers that might have been added if setup_logging is called multiple times
    key_event_logger.handlers = []

    if os.environ.get("MOOPS2_KEYTRACE", "").lower() in {"1", "true", "yes"}:
        try:
            key_trace_filename = "keytrace.log"
            key_trace_log_dir = os.path.dirname(key_trace_filename)
            if key_trace_log_dir and not os.path.exists(key_trace_log_dir):
                os.makedirs(key_trace_log_dir)

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
