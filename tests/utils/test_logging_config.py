# tests/utils/test_logging_config.py
import logging

from ecli.utils import logging_config


def test_setup_logging_creates_handlers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # лог‑файлы летят в tmp

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

    root = logging.getLogger()
    names = {type(h).__name__ for h in root.handlers}
    assert "RotatingFileHandler" in names  # editor.log
    assert len(root.handlers) == 2  # editor.log + error.log
    assert root.handlers[0].level == logging.INFO
    assert root.handlers[1].level == logging.ERROR  # error.log
