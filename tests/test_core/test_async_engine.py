# tests/test_core/test_async_engine.py
"""`tests/test_core/test_async_engine.py`
=========================================

Unit tests for the AsyncEngine class.

This test suite validates the following aspects of AsyncEngine:

1. **Initialization**
   - Proper setup of internal queues and configuration.

2. **Thread and event loop management**
   - Starting the engine launches a background thread with an active event loop.
   - Stopping the engine shuts down the thread cleanly.

3. **AI task processing**
   - Successful execution of `ai_chat` tasks via mocked AI clients.
   - Proper handling of exceptions raised during task execution.
   - Dispatching invalid or incomplete task data results in meaningful errors.

4. **Testing methodology**
   - Uses `pytest` and `pytest-asyncio` for async test support.
   - Patches `get_ai_client` to inject mocked AI clients instead of real ones.
   - Employs `AsyncMock` to simulate async calls to AI client methods.
"""

import queue
import time
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ecli.core.AsyncEngine import AsyncEngine
from ecli.integrations.AI import BaseAiClient


QueueItem = dict[str, Any]


@pytest.fixture
def engine_instance() -> Generator[
    tuple[AsyncEngine, queue.Queue[QueueItem]], None, None
]:
    """Create and provide an AsyncEngine instance with mocked dependencies.

    Yields:
        tuple[AsyncEngine, queue.Queue[QueueItem]]:
            - The AsyncEngine instance configured with fake AI credentials.
            - A mocked UI queue for capturing engine output messages.
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

    # Ensure proper cleanup after each test
    if engine.thread and engine.thread.is_alive():
        engine.stop()


class TestAsyncEngine:
    """Group of tests for the AsyncEngine class."""

    EngineFixture = tuple[AsyncEngine, queue.Queue[QueueItem]]

    def test_initialization(self, engine_instance: EngineFixture) -> None:
        """Test: Verify that AsyncEngine initializes correctly."""
        engine, mock_to_ui_queue = engine_instance
        assert engine.to_ui_queue is mock_to_ui_queue
        assert isinstance(engine.from_ui_queue, queue.Queue)

    def test_start_and_stop(self, engine_instance: EngineFixture) -> None:
        """Test: Verify starting and stopping of the background thread."""
        engine, _ = engine_instance
        engine.start()
        time.sleep(0.1)

        # The thread and event loop should now be active
        assert engine.thread is not None and engine.thread.is_alive()
        assert engine.loop is not None and engine.loop.is_running()

        engine.stop()
        assert not engine.thread.is_alive()

    @pytest.mark.asyncio
    @patch("ecli.core.AsyncEngine.get_ai_client")
    async def test_submit_and_process_ai_chat_task_success(
        self, mock_get_ai_client: MagicMock, engine_instance: EngineFixture
    ) -> None:
        """Test: Successful processing of an `ai_chat` task."""
        engine, to_ui_queue = engine_instance

        # Mock the AI client with async methods
        mock_ai_client = MagicMock(spec=BaseAiClient)
        mock_ai_client.ask_async = AsyncMock(return_value="Mocked AI response")
        mock_ai_client.close = AsyncMock()

        mock_get_ai_client.return_value = mock_ai_client
        engine.start()

        # Submit a valid ai_chat task
        task_data = {
            "type": "ai_chat",
            "provider": "some_provider",
            "prompt": "Hello, world!",
            "config": engine.config,
        }
        engine.submit_task(task_data)
        result = to_ui_queue.get(timeout=2)

        # Verify the AI client was called correctly
        mock_get_ai_client.assert_called_once_with("some_provider", task_data["config"])
        mock_ai_client.ask_async.assert_awaited_once_with(
            "Hello, world!", system_msg="You are a helpful assistant."
        )
        mock_ai_client.close.assert_awaited_once()

        # Verify the result was dispatched correctly
        assert result["type"] == "ai_reply"
        assert result["text"] == "Mocked AI response"

    @pytest.mark.asyncio
    @patch("ecli.core.AsyncEngine.get_ai_client")
    async def test_task_execution_error(
        self, mock_get_ai_client: MagicMock, engine_instance: EngineFixture
    ) -> None:
        """Test: Error handling during task execution."""
        engine, to_ui_queue = engine_instance

        # Simulate an exception raised by the AI client
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

        # Verify error details are included in the output
        assert result["type"] == "task_error"
        assert result["task_type"] == "ai_chat"
        assert "API connection failed" in result["error"]
        mock_ai_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_invalid_task_data(
        self, engine_instance: EngineFixture
    ) -> None:
        """Test: Submitting incomplete or invalid task data produces an error."""
        engine, to_ui_queue = engine_instance
        engine.start()

        invalid_task_data = {
            "type": "ai_chat",
            "provider": "some_provider",
            "config": {},
        }
        engine.submit_task(invalid_task_data)
        result = to_ui_queue.get(timeout=2)

        expected_error = (
            "Missing or invalid 'provider', 'prompt', or 'config' for ai_chat task."
        )
        assert result["type"] == "task_error"
        assert expected_error in result["error"]
