# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_ai_configuration_errors.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for graceful AI Assistant configuration error handling."""

from __future__ import annotations

import asyncio
import queue
import shutil
from pathlib import Path
from typing import Iterator

import pytest

from ecli.core.AsyncEngine import AsyncEngine
from ecli.core.Ecli import Ecli
from ecli.integrations.AI import (
    AiConfigurationError,
    ai_configuration_panel_message,
    get_ai_client,
)


class FakeEditor:
    def __init__(self) -> None:
        """Initialize the minimal queue-processing editor double."""
        self.is_lightweight = False
        self.status_message = "Ready"
        self._shell_cmd_q: queue.Queue[str] = queue.Queue()
        self._async_results_q: queue.Queue[dict[str, object]] = queue.Queue()
        self.git = None
        self.linter_bridge = None
        self.async_engine = object()
        self.lint_panel_active = False
        self.lint_panel_message = ""
        self.ai_panels: list[tuple[str, str]] = []

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def show_ai_panel(self, title: str, content: str) -> bool:
        self.ai_panels.append((title, content))
        return True


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-ai-configuration-errors"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_missing_ai_key_raises_typed_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AiConfigurationError) as exc_info:
        get_ai_client(
            "openai",
            {"ai": {"models": {"openai": "gpt-5-codex"}, "keys": {}}},
        )

    assert exc_info.value.provider == "openai"
    assert exc_info.value.env_var == "OPENAI_API_KEY"
    assert "Traceback" not in str(exc_info.value)


def test_ai_configuration_panel_message_is_user_friendly() -> None:
    message = ai_configuration_panel_message("openai", env_var="OPENAI_API_KEY")

    assert "AI provider is not configured" in message
    assert "Selected provider: openai" in message
    assert "Missing environment variable: OPENAI_API_KEY" in message
    assert "AI features require a user-provided API key" in message
    assert "~/.config/ecli/.env" in message
    assert "config.toml" in message
    assert "Traceback" not in message
    assert "ValueError" not in message


def test_async_engine_converts_missing_ai_key_to_configuration_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    to_ui_queue: queue.Queue[dict[str, object]] = queue.Queue()
    engine = AsyncEngine(
        to_ui_queue,
        config={},
    )

    asyncio.run(
        engine.dispatch_task(
            {
                "type": "ai_chat",
                "provider": "openai",
                "prompt": "explain this",
                "config": {"ai": {"models": {"openai": "gpt-5-codex"}, "keys": {}}},
            }
        )
    )

    result = to_ui_queue.get_nowait()
    assert result["type"] == "ai_configuration_error"
    assert result["provider"] == "openai"
    assert result["env_var"] == "OPENAI_API_KEY"
    assert result["title"] == "AI provider is not configured"
    text = str(result["text"])
    assert "~/.config/ecli/.env" in text
    assert "config.toml" in text
    assert "Traceback" not in text
    assert "ValueError" not in text


def test_editor_queue_renders_ai_configuration_panel_without_traceback() -> None:
    editor = FakeEditor()
    editor._async_results_q.put(
        {
            "type": "ai_configuration_error",
            "provider": "openai",
            "env_var": "OPENAI_API_KEY",
            "title": "AI provider is not configured",
            "text": ai_configuration_panel_message(
                "openai",
                env_var="OPENAI_API_KEY",
            ),
        }
    )

    changed = Ecli._process_all_queues(editor)  # type: ignore[arg-type]

    assert changed is True
    assert editor.status_message == "AI provider is not configured: openai"
    assert editor.ai_panels
    title, content = editor.ai_panels[-1]
    assert title == "AI provider is not configured"
    assert "Selected provider: openai" in content
    assert "OPENAI_API_KEY" in content
    assert "~/.config/ecli/.env" in content
    assert "config.toml" in content
    assert "Traceback" not in content
    assert "ValueError" not in content


def test_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)
