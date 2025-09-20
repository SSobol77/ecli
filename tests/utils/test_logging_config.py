# tests/utils/test_logging_config.py
"""Unit tests for logging configuration utility.
=================================================

Tests for the logging setup utility in `ecli.utils.logging_config`.

This module verifies that `setup_logging`:
- Creates rotating file handlers for the main log and a separate error log
  when `separate_error_log` is enabled.
- Honors the configured levels for each handler.
- Can disable console logging when `log_to_console` is set to False.

The test runs in a temporary working directory to avoid touching real files.
"""

import logging

from ecli.utils import logging_config


def test_setup_logging_creates_handlers(tmp_path, monkeypatch) -> None:
    """`setup_logging` should add rotating file handlers with proper levels.

    Scenario:
    - Console logging is disabled.
    - Separate error log is requested.
    - File handler level is INFO.
    - Error file handler level is ERROR.

    Assertions:
    - Both a main rotating file handler (e.g., `editor.log`) and a separate
      error rotating file handler (e.g., `error.log`) are attached to the
      root logger.
    - The total number of handlers equals 2 (main + error).
    - Handler levels match the configuration.
    """
    # Ensure any log files created by the test go into a temporary directory
    monkeypatch.chdir(tmp_path)

    # Configure logging: no console, separate error log, specific levels
    logging_config.setup_logging(
        {
            "logging": {
                "file_level": "INFO",
                "console_level": "ERROR",
                "log_to_console": False,
                "separate_error_log": True,
            }
        }
    )

    # Inspect the root logger's handlers
    root = logging.getLogger()
    names = {type(h).__name__ for h in root.handlers}

    # A rotating file handler should be present for the main log
    assert "RotatingFileHandler" in names

    # Exactly two handlers: main file + error file
    assert len(root.handlers) == 2

    # Verify the configured levels were applied:
    # - First handler: INFO (main log)
    # - Second handler: ERROR (error log)
    assert root.handlers[0].level == logging.INFO
    assert root.handlers[1].level == logging.ERROR
