# tests/integrations/test_ai.py
"""ecli.integrations.AI test suite.
===================================

Integration and unit tests for AI client implementations in `ecli.integrations.AI`.

This test suite covers the following areas:

1. **BaseAiClient**
   - Initialization and validation of required fields.
   - Session lifecycle management with `aiohttp`.
   - Enforcement of abstract methods (`ask_async`).

2. **AI client factory (`get_ai_client`)**
   - Correct instantiation of provider-specific clients.
   - Reading API keys from configuration and environment variables.
   - Validation of error handling for invalid or incomplete configurations.

3. **Provider-specific clients**
   - `OpenAiClient`, `GeminiClient`, `HuggingFaceClient`, and others.
   - Success scenarios with mocked HTTP responses.
   - Error scenarios with various HTTP status codes.
   - Retry logic (e.g., HuggingFace client retry on 503 “Model is loading”).

4. **Testing methodology**
   - Uses `pytest` and `pytest-asyncio` for async test support.
   - Heavy reliance on `unittest.mock` (`patch`, `MagicMock`) to simulate
     `aiohttp.ClientSession` behavior without making real network calls.
   - Parametrized tests for broad coverage of different error conditions.

These tests ensure correctness, resilience, and consistent error handling
across all supported AI provider clients in the ECLI integration layer.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import everything under test
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


# === Tests for BaseAiClient ===


@pytest.mark.asyncio
async def test_base_client_initialization() -> None:
    """Test: successful initialization of BaseAiClient."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    assert client.model == "base-model"
    assert client.api_key == "test_key"
    assert client.session is None


def test_base_client_missing_credentials() -> None:
    """Test: BaseAiClient raises when API key or model is missing."""
    with pytest.raises(ValueError, match="API key for BaseAiClient is missing"):
        BaseAiClient(model="base-model", api_key="")
    with pytest.raises(ValueError, match="Model for BaseAiClient is missing"):
        BaseAiClient(model="", api_key="test_key")


@pytest.mark.asyncio
async def test_base_client_session_management() -> None:
    """Test: BaseAiClient manages the aiohttp session lifecycle."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    session1 = await client._get_session()  # noqa: SLF001 type: ignore[attr-defined]
    assert session1 is not None and not session1.closed

    session2 = await client._get_session()  # noqa: SLF001 type: ignore[attr-defined]
    assert session1 is session2

    await client.close()
    assert session1.closed


@pytest.mark.asyncio
async def test_base_client_ask_async_not_implemented() -> None:
    """Test: calling ask_async on the base class raises NotImplementedError."""
    client = BaseAiClient(model="base-model", api_key="test_key")
    with pytest.raises(NotImplementedError):
        await client.ask_async("prompt", "system")


# === Tests for the get_ai_client factory ===


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Fixture: typical configuration for AI providers and models."""
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
    """Test: factory creates an instance of the correct client class."""
    client = get_ai_client(provider, mock_config)
    assert isinstance(client, client_class)


def test_get_ai_client_factory_from_env(
    mock_config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test: factory reads API key from environment variables when present."""
    monkeypatch.setenv("OPENAI_API_KEY", "key_from_env")
    client = get_ai_client("openai", mock_config)
    assert client.api_key == "key_from_env"


def test_get_ai_client_factory_failures(mock_config: dict[str, Any]) -> None:
    """Test: factory raises meaningful errors for invalid inputs."""
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


# === Tests for concrete clients (with aiohttp mocking) ===


@pytest.fixture
def aiohttp_mock() -> Any:
    """Factory for creating mocked HTTP responses usable with `async with`.

    Returns:
        Callable[..., MagicMock]: A factory that returns a mock object emulating
        an aiohttp POST call context manager, yielding a mocked response with
        configurable `status`, `json()` and `text()` behaviors.
    """

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

        # Emulate `async with session.post(...) as resp:`
        mock_session_post = MagicMock()
        mock_session_post.__aenter__.return_value = mock_response
        mock_session_post.__aexit__.return_value = None
        return mock_session_post

    return _mock_response


@pytest.mark.asyncio
async def test_openai_client_success(aiohttp_mock: Any) -> None:
    """Test: successful request flow for OpenAI client."""
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
    """Test: handling of various OpenAI API error responses."""
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
    """Test: successful request flow for Gemini client."""
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
    """Test: retry logic for HuggingFace client when HTTP 503 is returned.

    The client should wait and retry after receiving a 503 with
    `"Model is loading"`, then succeed on the subsequent attempt.
    """
    client = HuggingFaceClient(model="test-model", api_key="key")

    mock_503 = aiohttp_mock(status=503, text_data='{"error": "Model is loading"}')
    mock_200 = aiohttp_mock(status=200, json_data=[{"generated_text": "Success!"}])

    # FIXED: Patch `sleep` only in the module where it is used
    # to avoid affecting sleeps that might be used in the fixture itself.
    with (
        patch.object(client, "_get_session") as mock_get_session,
        patch("ecli.integrations.AI.asyncio.sleep", return_value=None) as mock_sleep,
    ):
        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_503, mock_200]
        mock_get_session.return_value = mock_session

        response = await client.ask_async("prompt", "system")

        assert response == "Success!"
        assert mock_session.post.call_count == 2
        mock_sleep.assert_awaited_once_with(10)
        await client.close()
