import queue
import time
from typing import Any, Dict, Generator, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ecli.core.AsyncEngine import AsyncEngine
from ecli.integrations.AI import BaseAiClient


QueueItem = dict[str, Any]

@pytest.fixture
def engine_instance() -> Generator[tuple[AsyncEngine, queue.Queue[QueueItem]], None, None]:
    """Создает и предоставляет экземпляр AsyncEngine с мок-зависимостями.
    """
    mock_to_ui_queue: queue.Queue[QueueItem] = queue.Queue()
    mock_config = {
        "ai": {
            "keys": {"some_provider": "fake_key", "p": "p_key"},
            "models": {"some_provider": "model-x", "p": "p-model"},
        }
    }
    engine = AsyncEngine(to_ui_queue=mock_to_ui_queue, config=mock_config)
    yield engine, mock_to_ui_queue
    if engine.thread and engine.thread.is_alive():
        engine.stop()


class TestAsyncEngine:
    """Группирует тесты для класса AsyncEngine."""

    EngineFixture = tuple[AsyncEngine, queue.Queue[QueueItem]]

    def test_initialization(self, engine_instance: EngineFixture) -> None:
        """Тест: Проверяем, что движок правильно инициализируется."""
        engine, mock_to_ui_queue = engine_instance
        assert engine.to_ui_queue is mock_to_ui_queue
        assert isinstance(engine.from_ui_queue, queue.Queue)

    def test_start_and_stop(self, engine_instance: EngineFixture) -> None:
        """Тест: Проверяем запуск и остановку фонового потока."""
        engine, _ = engine_instance
        engine.start()
        time.sleep(0.1)
        assert engine.thread is not None and engine.thread.is_alive()
        assert engine.loop is not None and engine.loop.is_running()
        engine.stop()
        assert not engine.thread.is_alive()

    @pytest.mark.asyncio
    @patch("ecli.core.AsyncEngine.get_ai_client")
    async def test_submit_and_process_ai_chat_task_success(
        self, mock_get_ai_client: MagicMock, engine_instance: EngineFixture
    ) -> None:
        """Тест: Успешная обработка задачи 'ai_chat'."""
        engine, to_ui_queue = engine_instance
        mock_ai_client = MagicMock(spec=BaseAiClient)
        mock_ai_client.ask_async = AsyncMock(return_value="Mocked AI response")
        mock_ai_client.close = AsyncMock()

        mock_get_ai_client.return_value = mock_ai_client
        engine.start()

        task_data = {
            "type": "ai_chat",
            "provider": "some_provider",
            "prompt": "Hello, world!",
            "config": engine.config,
        }
        engine.submit_task(task_data)
        result = to_ui_queue.get(timeout=2)

        mock_get_ai_client.assert_called_once_with("some_provider", task_data["config"])

        # ИСПРАВЛЕНО: Добавляем второй аргумент, чтобы соответствовать реальному вызову
        mock_ai_client.ask_async.assert_awaited_once_with(
            "Hello, world!", system_msg="You are a helpful assistant."
        )
        mock_ai_client.close.assert_awaited_once()

        assert result["type"] == "ai_reply"
        assert result["text"] == "Mocked AI response"

    @pytest.mark.asyncio
    @patch("ecli.core.AsyncEngine.get_ai_client")
    async def test_task_execution_error(
        self, mock_get_ai_client: MagicMock, engine_instance: EngineFixture
    ) -> None:
        """Тест: Обработка ошибки во время выполнения задачи."""
        engine, to_ui_queue = engine_instance
        mock_ai_client = MagicMock(spec=BaseAiClient)
        mock_ai_client.ask_async.side_effect = Exception("API connection failed")
        mock_ai_client.close = AsyncMock()

        mock_get_ai_client.return_value = mock_ai_client
        engine.start()

        task_data = {
            "type": "ai_chat",
            "provider": "p",
            "prompt": "p",
            "config": engine.config,
        }
        engine.submit_task(task_data)
        result = to_ui_queue.get(timeout=2)

        assert result["type"] == "task_error"
        assert result["task_type"] == "ai_chat"
        assert "API connection failed" in result["error"]
        mock_ai_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_invalid_task_data(self, engine_instance: EngineFixture) -> None:
        """Тест: Отправка задачи с неполными данными."""
        engine, to_ui_queue = engine_instance
        engine.start()

        invalid_task_data = {
            "type": "ai_chat",
            "provider": "some_provider",
            "config": {},
        }
        engine.submit_task(invalid_task_data)
        result = to_ui_queue.get(timeout=2)

        # ИСПРАВЛЕНО: Текст ошибки должен точно совпадать с тем, что в коде
        expected_error = "Missing or invalid 'provider', 'prompt', or 'config' for ai_chat task."
        assert result["type"] == "task_error"
        assert expected_error in result["error"]
