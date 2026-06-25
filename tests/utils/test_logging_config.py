# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/utils/test_logging_config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ecli.utils.logging_config import SafeRotatingFileHandler, setup_logging


@pytest.fixture(autouse=True)
def isolated_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    root_logger = logging.getLogger()
    key_logger = logging.getLogger("ecli.keyevents")

    old_root_handlers = root_logger.handlers[:]
    old_root_level = root_logger.level
    old_key_handlers = key_logger.handlers[:]
    old_key_level = key_logger.level
    old_key_propagate = key_logger.propagate
    old_key_disabled = key_logger.disabled
    old_raise_exceptions = logging.raiseExceptions

    for handler in old_root_handlers:
        root_logger.removeHandler(handler)
    for handler in old_key_handlers:
        key_logger.removeHandler(handler)

    monkeypatch.delenv("ECLI_LOG_DIR", raising=False)
    monkeypatch.delenv("MOOPS2_KEYTRACE", raising=False)

    yield

    _close_attached_handlers(root_logger)
    _close_attached_handlers(key_logger)

    root_logger.setLevel(old_root_level)
    key_logger.setLevel(old_key_level)
    key_logger.propagate = old_key_propagate
    key_logger.disabled = old_key_disabled
    logging.raiseExceptions = old_raise_exceptions

    for handler in old_root_handlers:
        root_logger.addHandler(handler)
    for handler in old_key_handlers:
        key_logger.addHandler(handler)


def _close_attached_handlers(target_logger: logging.Logger) -> None:
    for handler in target_logger.handlers[:]:
        target_logger.removeHandler(handler)
        handler.close()


def _is_closed(handler: logging.Handler) -> bool:
    if isinstance(handler, logging.FileHandler):
        return handler.stream is None
    return bool(getattr(handler, "_closed", False))


def test_setup_logging_twice_does_not_duplicate_handlers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECLI_LOG_DIR", str(tmp_path / "logs"))
    config = {"logging": {"file_level": "DEBUG", "separate_error_log": True}}

    setup_logging(config)
    first_handlers = logging.getLogger().handlers[:]

    setup_logging(config)
    second_handlers = logging.getLogger().handlers[:]

    assert len(second_handlers) == 2
    assert all(
        isinstance(handler, SafeRotatingFileHandler) for handler in second_handlers
    )
    assert {Path(handler.baseFilename).name for handler in second_handlers} == {
        "editor.log",
        "error.log",
    }
    assert {id(handler) for handler in first_handlers}.isdisjoint(
        {id(handler) for handler in second_handlers}
    )


def test_old_handlers_are_closed_on_reconfiguration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_logger = logging.getLogger()
    key_logger = logging.getLogger("ecli.keyevents")
    old_root_handler = logging.FileHandler(tmp_path / "old-root.log", encoding="utf-8")
    old_key_handler = logging.FileHandler(tmp_path / "old-key.log", encoding="utf-8")
    root_logger.addHandler(old_root_handler)
    key_logger.addHandler(old_key_handler)

    monkeypatch.setenv("ECLI_LOG_DIR", str(tmp_path / "logs"))

    setup_logging()

    assert _is_closed(old_root_handler)
    assert _is_closed(old_key_handler)


def test_repeated_setup_closes_replaced_file_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECLI_LOG_DIR", str(tmp_path / "logs"))

    setup_logging()
    first_handlers = logging.getLogger().handlers[:]

    setup_logging()

    assert first_handlers
    assert all(_is_closed(handler) for handler in first_handlers)


def test_rollover_file_not_found_does_not_raise_or_write_to_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_file = tmp_path / "editor.log"
    log_file.write_text("seed\n", encoding="utf-8")
    calls = 0

    def fail_rollover(_handler: logging.handlers.RotatingFileHandler) -> None:
        nonlocal calls
        calls += 1
        raise FileNotFoundError(
            "[Errno 2] No such file or directory: 'editor.log.3' -> 'editor.log.4'"
        )

    monkeypatch.setattr(
        logging.handlers.RotatingFileHandler, "doRollover", fail_rollover
    )
    old_raise_exceptions = logging.raiseExceptions
    logging.raiseExceptions = True
    logger = logging.getLogger("ecli.test.rollover")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    _close_attached_handlers(logger)
    handler = SafeRotatingFileHandler(
        log_file, maxBytes=1, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    try:
        logger.info("after rollover failure")
        handler.flush()
    finally:
        logging.raiseExceptions = old_raise_exceptions
        _close_attached_handlers(logger)

    captured = capsys.readouterr()
    assert calls == 1
    assert captured.err == ""
    assert captured.out == ""
    assert "after rollover failure" in log_file.read_text(encoding="utf-8")


def test_safe_handler_preserves_successful_rotation(tmp_path: Path) -> None:
    log_file = tmp_path / "editor.log"
    logger = logging.getLogger("ecli.test.rotation-success")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    _close_attached_handlers(logger)
    handler = SafeRotatingFileHandler(
        log_file, maxBytes=24, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    try:
        logger.info("first message that fills the file")
        logger.info("second message that rotates it")
        handler.flush()
    finally:
        _close_attached_handlers(logger)

    assert log_file.exists()
    assert (tmp_path / "editor.log.1").exists()


def test_normal_runtime_attaches_no_stdout_or_stderr_stream_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECLI_LOG_DIR", str(tmp_path / "logs"))

    setup_logging({"logging": {"log_to_console": True, "file_level": "DEBUG"}})

    handlers = (
        logging.getLogger().handlers + logging.getLogger("ecli.keyevents").handlers
    )
    terminal_streams = {sys.stdout, sys.stderr}
    assert all(
        getattr(handler, "stream", None) not in terminal_streams for handler in handlers
    )
    assert logging.raiseExceptions is False


def test_keytrace_uses_safe_rotating_handler_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECLI_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("MOOPS2_KEYTRACE", "1")

    setup_logging()

    key_logger = logging.getLogger("ecli.keyevents")
    assert key_logger.disabled is False
    assert len(key_logger.handlers) == 1
    keytrace_handler = key_logger.handlers[0]
    assert isinstance(keytrace_handler, SafeRotatingFileHandler)
    assert Path(keytrace_handler.baseFilename).name == "keytrace.log"
