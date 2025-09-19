import json
from typing import Any, Dict, Type
from unittest.mock import MagicMock, patch

import pytest

# Импортируем все, что нужно протестировать
from ecli.integrations.AI import (
    BaseAiClient,
    ClaudeClient,
    GeminiClient,
    GrokClient,
    HuggingFaceClient,
    MistralClient,
    OpenAiClient,
    get_ai_client,
)


# === Тесты для BaseAiClient ===


@pytest.mark.asyncio
async def test_base_client_initialization() -> None:
    """Тест: успешная инициализация BaseAiClient."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    assert client.model == "base-model"
    assert client.api_key == "test_key"
    assert client.session is None


def test_base_client_missing_credentials() -> None:
    """Тест: BaseAiClient выбрасывает ошибку при отсутствии ключа или модели."""
    with pytest.raises(ValueError, match="API key for BaseAiClient is missing"):
        BaseAiClient(model="base-model", api_key="")
    with pytest.raises(ValueError, match="Model for BaseAiClient is missing"):
        BaseAiClient(model="", api_key="test_key")


@pytest.mark.asyncio
async def test_base_client_session_management() -> None:
    """Тест: BaseAiClient управляет сессией aiohttp."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    session1 = await client._get_session()
    assert session1 is not None and not session1.closed

    session2 = await client._get_session()
    assert session1 is session2

    await client.close()
    assert session1.closed


@pytest.mark.asyncio
async def test_base_client_ask_async_not_implemented() -> None:
    """Тест: вызов ask_async у базового класса вызывает ошибку."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    with pytest.raises(NotImplementedError):
        await client.ask_async("prompt", "system")


# === Тесты для фабрики get_ai_client ===


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Фикстура с типовой конфигурацией."""
    return {
        "ai": {
            "keys": {
                "openai": "openai-key",
                "gemini": "gemini-key",
                "mistral": "mistral-key",
                "claude": "claude-key",
                "huggingface": "hf-key",
                "grok": "grok-key",
            },
            "models": {
                "openai": "gpt-4",
                "gemini": "gemini-pro",
                "mistral": "mistral-large",
                "claude": "claude-3-opus",
                "huggingface": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "grok": "grok-1",
            },
        }
    }


@pytest.mark.parametrize(
    "provider, client_class",
    [
        ("openai", OpenAiClient),
        ("gemini", GeminiClient),
        ("mistral", MistralClient),
        ("claude", ClaudeClient),
        ("huggingface", HuggingFaceClient),
        ("grok", GrokClient),
    ],
)
def test_get_ai_client_factory_success(
    provider: str, client_class: type[BaseAiClient], mock_config: dict[str, Any]
) -> None:
    """Тест: фабрика создает правильный экземпляр клиента."""
    client = get_ai_client(provider, mock_config)
    assert isinstance(client, client_class)


def test_get_ai_client_factory_from_env(
    mock_config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Тест: фабрика правильно читает ключ из переменной окружения."""
    monkeypatch.setenv("OPENAI_API_KEY", "key_from_env")
    client = get_ai_client("openai", mock_config)
    assert client.api_key == "key_from_env"


def test_get_ai_client_factory_failures(mock_config: dict[str, Any]) -> None:
    """Тест: фабрика выбрасывает ошибки при неверных данных."""
    invalid_provider_config = mock_config.copy()
    invalid_provider_config["ai"]["keys"]["invalid"] = "fake-key"
    invalid_provider_config["ai"]["models"]["invalid"] = "fake-model"
    with pytest.raises(ValueError, match="Unknown AI provider: invalid"):
        get_ai_client("invalid", invalid_provider_config)

    bad_config = {"ai": {"models": {"openai": "gpt-4"}}}
    with pytest.raises(ValueError, match="API key for openai not found"):
        get_ai_client("openai", bad_config)

    bad_config = {"ai": {"keys": {"openai": "key"}}}
    with pytest.raises(ValueError, match="Model for openai not found"):
        get_ai_client("openai", bad_config)


# === Тесты для конкретных клиентов (с мокингом aiohttp) ===


@pytest.fixture
def aiohttp_mock() -> Any:
    """Фабрика для создания моков HTTP-ответов."""

    def _mock_response(
        status: int = 200, json_data: Any = None, text_data: str | None = None
    ) -> MagicMock:
        mock_response = MagicMock()
        mock_response.status = status

        async def json_func() -> Any:  # noqa: S7503
            return json_data

        async def text_func() -> str:  # noqa: S7503
            if text_data is not None:
                return text_data
            return json.dumps(json_data)

        mock_response.json = MagicMock(side_effect=json_func)
        mock_response.text = MagicMock(side_effect=text_func)

        mock_session_post = MagicMock()
        mock_session_post.__aenter__.return_value = mock_response
        mock_session_post.__aexit__.return_value = None
        return mock_session_post

    return _mock_response


@pytest.mark.asyncio
async def test_openai_client_success(aiohttp_mock: Any) -> None:
    """Тест: успешный запрос к OpenAI."""
    client = OpenAiClient(model="gpt-4", api_key="key")
    mock_response_data = {
        "choices": [{"message": {"content": "  Hello from OpenAI!  "}}]
    }
    mock_post = aiohttp_mock(status=200, json_data=mock_response_data)

    with patch.object(client, "_get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post
        mock_get_session.return_value = mock_session

        response = await client.ask_async("prompt", "system")

        assert response == "Hello from OpenAI!"
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, response_text, expected_error_msg",
    [
        (401, "invalid key", "Error: Invalid OpenAI API key."),
        (429, "rate limit", "Error: OpenAI rate limit exceeded."),
        (429, "quota", "Error: OpenAI quota exceeded or billing issues."),
        (500, "server error", "Error: OpenAI internal server error."),
    ],
)
async def test_openai_client_api_errors(
    aiohttp_mock: Any, status_code: int, response_text: str, expected_error_msg: str
) -> None:
    """Тест: обработка различных API ошибок OpenAI."""
    client = OpenAiClient(model="gpt-4", api_key="key")
    mock_post = aiohttp_mock(status=status_code, text_data=response_text)

    with patch.object(client, "_get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post
        mock_get_session.return_value = mock_session

        response = await client.ask_async("prompt", "system")
        assert expected_error_msg in response
        await client.close()


@pytest.mark.asyncio
async def test_gemini_client_success(aiohttp_mock: Any) -> None:
    """Тест: успешный запрос к Gemini."""
    client = GeminiClient(model="gemini-pro", api_key="key")
    mock_response_data = {
        "candidates": [{"content": {"parts": [{"text": "  Hello from Gemini!  "}]}}]
    }
    mock_post = aiohttp_mock(status=200, json_data=mock_response_data)

    with patch.object(client, "_get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post
        mock_get_session.return_value = mock_session

        response = await client.ask_async("prompt", "system")
        assert response == "Hello from Gemini!"
        await client.close()


@pytest.mark.asyncio
async def test_huggingface_client_retry_logic(aiohttp_mock: Any) -> None:
    """Тест: проверка логики повторного запроса для HuggingFace при статусе 503."""
    client = HuggingFaceClient(model="test-model", api_key="key")

    mock_503 = aiohttp_mock(status=503, text_data='{"error": "Model is loading"}')
    mock_200 = aiohttp_mock(status=200, json_data=[{"generated_text": "Success!"}])

    # ИСПРАВЛЕНО: Патчим sleep только в том модуле, где он используется,
    # чтобы не затрагивать вызовы sleep в нашей фикстуре.
    with patch.object(client, "_get_session") as mock_get_session, patch(
        "ecli.integrations.AI.asyncio.sleep", return_value=None
    ) as mock_sleep:
        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_503, mock_200]
        mock_get_session.return_value = mock_session

        response = await client.ask_async("prompt", "system")

        assert response == "Success!"
        assert mock_session.post.call_count == 2
        mock_sleep.assert_awaited_once_with(10)
        await client.close()
