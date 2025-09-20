# ecli/integrations/AI.py
"""AI.py
========================
This module defines asynchronous clients for interacting with various AI service providers,
including OpenAI, Google Gemini, Mistral, Hugging Face, Claude (Anthropic), and Grok (xAI).

It includes:
- A base class `BaseAiClient` that provides common async session handling.
- Specific subclasses that implement communication with each provider's chat API.
- Centralized error handling for each provider.
- A factory method `get_ai_client()` for dynamic client instantiation.

Supported providers: OpenAI, Gemini, Mistral, Hugging Face, Claude, Grok.
"""

import asyncio
import json
import os
from typing import Any, Optional, cast

import aiohttp

from ecli.utils.logging_config import logger


# Get logger to ensure messages match the general logging system
# ==================== BaseAiClient Class ====================
class BaseAiClient:
    """Base class for asynchronous AI clients.

    This class provides common functionality for all AI service clients, including
    session management and basic error handling patterns.

    Attributes:
        model (str): The AI model identifier.
        api_key (str): API key for authenticating requests.
        session (Optional[aiohttp.ClientSession]): AIOHTTP session for HTTP calls.
    """

    def __init__(self, model: str, api_key: str) -> None:
        """Initialize the base AI client.

        Args:
            model (str): The model identifier to use for requests.
            api_key (str): The API key for authentication.

        Raises:
            ValueError: If `model` or `api_key` is not provided or empty.
        """
        if not api_key:
            raise ValueError(f"API key for {self.__class__.__name__} is missing.")
        if not model:
            raise ValueError(f"Model for {self.__class__.__name__} is missing.")

        self.model = model
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"Initialized {self.__class__.__name__} for model {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get a valid aiohttp session, creating one if needed.

        Returns:
            aiohttp.ClientSession: An active session object for making HTTP requests.
        """
        if self.session is None or self.session.closed:
            logger.debug("Creating new aiohttp.ClientSession")
            self.session = aiohttp.ClientSession()
        # Small await to ensure this coroutine uses asynchronous features
        # (satisfies static analysis rules that require `async` functions to
        # perform at least one await). This yields control to the event loop
        # but does not change runtime behavior for the session creation.
        await asyncio.sleep(0)
        return self.session

    async def close(self) -> None:
        """Close the aiohttp session if it's currently open.

        This method should be called when the client is no longer needed
        to properly clean up resources.
        """
        if self.session and not self.session.closed:
            logger.debug("Closing aiohttp.ClientSession")
            await self.session.close()

    async def ask_async(self, prompt: str, system_msg: str) -> str:
        """Send a message and receive a response from the AI service.

        Args:
            prompt (str): The user's input prompt.
            system_msg (str): System message with instructions for the assistant.

        Returns:
            str: The AI model's generated response.

        Raises:
            NotImplementedError: This method must be implemented in subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method.")


# ==================== OpenAiClient Class ====================
class OpenAiClient(BaseAiClient):
    """Client for the OpenAI Chat Completion API (v1).

    This client supports asynchronous requests with robust error handling
    for various OpenAI API scenarios including quota limits, rate limiting,
    and authentication issues.
    """

    API_URL = "https://api.openai.com/v1/chat/completions"

    def _handle_openai_error(self, status_code: int, response_text: str) -> str:
        """Handle OpenAI-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()

        if status_code == 401:
            return "Error: Invalid OpenAI API key. Please check OPENAI_API_KEY."
        if status_code == 403:
            return "Error: Access forbidden. Please check your OpenAI API permissions."
        if status_code == 429:
            if "quota" in response_lower or "billing" in response_lower:
                return "Error: OpenAI quota exceeded or billing issues. Check your balance at https://platform.openai.com/usage"
            if "rate limit" in response_lower:
                return "Error: OpenAI rate limit exceeded. Please try again later."
        elif status_code == 400:
            if "model" in response_lower:
                return f"Error: Unsupported OpenAI model: {self.model}"
            if "context_length" in response_lower:
                return "Error: Request too long for OpenAI. Please shorten your text."
        elif status_code == 500:
            return "Error: OpenAI internal server error. Please try again later."

        return f"OpenAI Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a chat completion request to OpenAI API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to set assistant behavior.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The assistant's response text, or an error message if the request failed.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        }

        logger.debug("Sending request to OpenAI API...")
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=90)
            async with session.post(
                self.API_URL, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from OpenAI with status: {response.status}"
                )

                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"OpenAI API Error {response.status}: {response_text}")
                    return self._handle_openai_error(response.status, response_text)

                data = await response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "Empty response")
                )
                return content.strip()

        except TimeoutError:
            logger.error("Request to OpenAI API timed out.")
            return "Error: OpenAI request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(f"Network or connection error to OpenAI: {e}", exc_info=True)
            return f"Error: Network error connecting to OpenAI: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in OpenAiClient: {e}", exc_info=True
            )
            return f"Error: Unexpected OpenAI error: {e}"


# ==================== GeminiClient Class ====================
class GeminiClient(BaseAiClient):
    """Client for Google Gemini API.

    This client handles requests to Google's Gemini generative AI models,
    including proper error handling for safety filters, quota limits,
    and authentication issues.
    """

    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def _handle_gemini_error(self, status_code: int, response_text: str) -> str:
        """Handle Gemini-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()

        if status_code == 400:
            if "api_key" in response_lower:
                return (
                    "Error: Invalid Google Gemini API key. Please check GEMINI_API_KEY."
                )
            if "quota" in response_lower:
                return "Error: Gemini quota exceeded. Check your limits at https://makersuite.google.com/"
            if "safety" in response_lower:
                return "Error: Request blocked by Gemini safety filters."
        elif status_code == 403:
            return "Error: Access to Gemini API forbidden. Please check your API key and permissions."
        elif status_code == 404:
            return f"Error: Gemini model not found: {self.model}"
        elif status_code == 429:
            return "Error: Gemini rate limit exceeded. Please try again later."
        elif status_code == 500:
            return "Error: Gemini internal server error. Please try again later."

        return f"Gemini Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a content generation request to Gemini API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to provide context.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The generated response text, or an error message if the request failed.
        """
        url = self.API_URL_TEMPLATE.format(model=self.model, api_key=self.api_key)
        headers = {"Content-Type": "application/json"}
        body = {"contents": [{"parts": [{"text": f"{system_msg}\n\n{prompt}"}]}]}

        logger.debug(f"Sending request to Gemini API: {url}")

        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=90)
            async with session.post(
                url, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from Gemini with status: {response.status}"
                )
                response_text = await response.text()

                if response.status != 200:
                    logger.error(f"Gemini API Error {response.status}: {response_text}")
                    return self._handle_gemini_error(response.status, response_text)

                data = json.loads(response_text)

                candidates = data.get("candidates")
                if not candidates:
                    if "error" in data:
                        return f"Gemini API Error: {data['error'].get('message', 'Unknown error')}"
                    return "Error: Gemini response blocked by safety filters."

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    return "Error: Empty response from Gemini or content blocked."

                return parts[0].get("text", "Empty text in Gemini response.").strip()

        except TimeoutError:
            logger.error("Request to Gemini API timed out.")
            return "Error: Gemini request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(f"Network or connection error to Gemini: {e}", exc_info=True)
            return f"Error: Network error connecting to Gemini: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in GeminiClient: {e}", exc_info=True
            )
            return f"Error: Unexpected Gemini error: {e}"


# ==================== MistralClient Class ====================
class MistralClient(BaseAiClient):
    """Client for Mistral AI API.

    This client handles chat completion requests to Mistral AI models,
    with comprehensive error handling for authentication, quota, and
    rate limiting scenarios.
    """

    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def _handle_mistral_error(self, status_code: int, response_text: str) -> str:
        """Handle Mistral-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()
        error_messages = {
            401: "Error: Invalid Mistral API key. Please check MISTRAL_API_KEY.",
            403: "Error: Access to Mistral API forbidden. Please check your permissions.",
            429: (
                "Error: Mistral quota exceeded. Check your balance at https://console.mistral.ai/"
                if "quota" in response_lower
                else "Error: Mistral rate limit exceeded. Please try again later."
            ),
            400: (
                f"Error: Unsupported Mistral model: {self.model}"
                if "model" in response_lower
                else None
            ),
            500: "Error: Mistral internal server error. Please try again later.",
        }

        message = error_messages.get(status_code)
        if message is not None:
            return message

        return f"Mistral Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a chat completion request to Mistral API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to set assistant behavior.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The assistant's response text, or an error message if the request failed.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        }

        logger.debug("Sending request to Mistral API...")
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=90)
            async with session.post(
                self.API_URL, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from Mistral with status: {response.status}"
                )
                response_text = await response.text()

                if response.status != 200:
                    logger.error(
                        f"Mistral API Error {response.status}: {response_text}"
                    )
                    return self._handle_mistral_error(response.status, response_text)

                data = json.loads(response_text)
                return (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "Empty response")
                    .strip()
                )

        except TimeoutError:
            logger.error("Request to Mistral API timed out.")
            return "Error: Mistral request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(f"Network or connection error to Mistral: {e}", exc_info=True)
            return f"Error: Network error connecting to Mistral: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in MistralClient: {e}", exc_info=True
            )
            return f"Error: Unexpected Mistral error: {e}"


# ==================== HuggingFaceClient Class ====================
class HuggingFaceClient(BaseAiClient):
    """Client for Hugging Face Inference API.

    This client handles text generation requests to Hugging Face models,
    including model loading detection, retry logic, and comprehensive
    error handling for various API scenarios.
    """

    API_URL_TEMPLATE = "https://api-inference.huggingface.co/models/{model}"

    def _handle_huggingface_error(self, status_code: int, response_text: str) -> str:
        """Handle Hugging Face-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()

        if status_code == 401:
            return "Error: Invalid Hugging Face API token. Please check HUGGINGFACE_API_KEY."
        if status_code == 403:
            return "Error: Access to Hugging Face model forbidden. Please check your permissions."
        if status_code == 404:
            return f"Error: Hugging Face model not found: {self.model}"
        if status_code == 429:
            return "Error: Hugging Face rate limit exceeded. Please try again later."
        if status_code == 503:
            if "loading" in response_lower:
                return "Error: Hugging Face model is loading. Please try again in a few minutes."
            return "Error: Hugging Face service unavailable. Please try again later."
        if status_code == 500:
            return "Error: Hugging Face internal server error. Please try again later."

        return f"Hugging Face Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a text generation request to Hugging Face API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to provide context.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The generated response text, or an error message if the request failed.
        """
        url = self.API_URL_TEMPLATE.format(model=self.model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        full_prompt = f"{system_msg}\n\nUser: {prompt}\nAssistant:"

        body = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 2048,
                "temperature": 0.7,
                "do_sample": True,
                "return_full_text": False,
            },
        }

        logger.debug(f"Sending request to Hugging Face API: {url}")

        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=120)
            async with session.post(
                url, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from Hugging Face with status: {response.status}"
                )
                response_text = await response.text()

                if response.status == 503:
                    logger.warning("Hugging Face model is loading, retrying...")
                    await asyncio.sleep(10)
                    retry_timeout = aiohttp.ClientTimeout(total=120)
                    async with session.post(
                        url, headers=headers, json=body, timeout=retry_timeout
                    ) as retry_response:
                        response_text = await retry_response.text()
                        if retry_response.status != 200:
                            logger.error(
                                f"Hugging Face API Error {retry_response.status}: {response_text}"
                            )
                            return self._handle_huggingface_error(
                                retry_response.status, response_text
                            )
                        response = retry_response

                elif response.status != 200:
                    logger.error(
                        f"Hugging Face API Error {response.status}: {response_text}"
                    )
                    return self._handle_huggingface_error(
                        response.status, response_text
                    )

                # Narrow the parsed JSON type for the type checker
                data_raw = cast(list[Any] | dict[str, Any], json.loads(response_text))
                logger.debug(f"Hugging Face response data: {data_raw}")

                # Handle different response formats with explicit narrowing
                if isinstance(data_raw, list):
                    data_list = data_raw
                    if data_list:
                        first = data_list[0]
                        if isinstance(first, dict):
                            first_dict = cast(dict[str, Any], first)
                            gen = first_dict.get("generated_text")
                            if isinstance(gen, str):
                                return gen.strip()
                            resp = first_dict.get("response")
                            if isinstance(resp, str):
                                return resp.strip()
                        elif isinstance(first, str):
                            return first.strip()

                else:
                    data_dict = data_raw  # type: ignore[assignment]
                    gen = data_dict.get("generated_text")
                    if isinstance(gen, str):
                        return gen.strip()
                    resp = data_dict.get("response")
                    if isinstance(resp, str):
                        return resp.strip()
                    if "error" in data_dict:
                        return f"Hugging Face API Error: {data_dict['error']}"

                # Use json.dumps to create a stable preview of the unexpected payload
                try:
                    preview = json.dumps(data_raw)[:200]
                except Exception:
                    preview = str(data_raw)[:200]
                return f"Error: Unexpected Hugging Face response format: {preview}..."

        except TimeoutError:
            logger.error("Request to Hugging Face API timed out.")
            return "Error: Hugging Face request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(
                f"Network or connection error to Hugging Face: {e}", exc_info=True
            )
            return f"Error: Network error connecting to Hugging Face: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in HuggingFaceClient: {e}", exc_info=True
            )
            return f"Error: Unexpected Hugging Face error: {e}"


# ==================== ClaudeClient Class ====================
class ClaudeClient(BaseAiClient):
    """Client for Anthropic Claude API.

    This client handles message requests to Claude models using Anthropic's
    Messages API, with proper error handling for quota limits, model
    availability, and content filtering.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def _handle_claude_error(self, status_code: int, response_text: str) -> str:
        """Handle Claude-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()

        if status_code == 401:
            return "Error: Invalid Claude API key. Please check CLAUDE_API_KEY."
        if status_code == 403:
            return (
                "Error: Access to Claude API forbidden. Please check your permissions."
            )
        if status_code == 429:
            if "credits" in response_lower or "usage" in response_lower:
                return "Error: Claude quota exceeded. Check your balance at https://console.anthropic.com/"
            return "Error: Claude rate limit exceeded. Please try again later."
        if status_code == 400:
            if "model" in response_lower:
                return f"Error: Unsupported Claude model: {self.model}"
            if "max_tokens" in response_lower:
                return "Error: Request too long for Claude. Please shorten your text."
        elif status_code == 500:
            return "Error: Claude internal server error. Please try again later."

        return f"Claude Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a message request to Claude API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to set assistant behavior.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The assistant's response text, or an error message if the request failed.
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_msg,
            "messages": [{"role": "user", "content": prompt}],
        }

        logger.debug("Sending request to Claude API...")
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=90)
            async with session.post(
                self.API_URL, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from Claude with status: {response.status}"
                )
                response_text = await response.text()

                if response.status != 200:
                    logger.error(f"Claude API Error {response.status}: {response_text}")
                    return self._handle_claude_error(response.status, response_text)

                data = json.loads(response_text)

                if "content" not in data:
                    if "error" in data:
                        return f"Claude API Error: {data['error'].get('message', 'Unknown error')}"
                    return "Error: Empty response from Claude."

                content = data.get("content", [])
                if not content:
                    return "Error: Empty content in Claude response."

                for content_block in content:
                    if content_block.get("type") == "text":
                        return content_block.get(
                            "text", "Empty text in Claude response."
                        ).strip()

                return "Error: No text content found in Claude response."

        except TimeoutError:
            logger.error("Request to Claude API timed out.")
            return "Error: Claude request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(f"Network or connection error to Claude: {e}", exc_info=True)
            return f"Error: Network error connecting to Claude: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in ClaudeClient: {e}", exc_info=True
            )
            return f"Error: Unexpected Claude error: {e}"


# ==================== GrokClient Class ====================


class GrokClient(BaseAiClient):
    """Client for Grok API from xAI.

    This client handles chat completion requests to xAI's Grok models,
    with comprehensive error handling for authentication, credit limits,
    and rate limiting scenarios.
    """

    API_URL = "https://api.x.ai/v1/chat/completions"

    def _handle_grok_error(self, status_code: int, response_text: str) -> str:
        """Handle Grok-specific error responses.

        Args:
            status_code (int): HTTP status code from the API response.
            response_text (str): Raw response text from the API.

        Returns:
            str: A user-friendly error message describing the issue.
        """
        response_lower = response_text.lower()

        if status_code == 401:
            return "Error: Invalid xAI API key. Please check XAI_API_KEY."
        if status_code == 403:
            if "credits" in response_lower:
                return "Error: Your xAI team is out of credits. Please top up your balance at https://console.x.ai/"
            return "Error: Access to Grok API forbidden. Please check your permissions."
        if status_code == 429:
            return "Error: Grok rate limit exceeded. Please try again later."
        if status_code == 400:
            if "model" in response_lower:
                return f"Error: Unsupported Grok model: {self.model}"
        elif status_code == 500:
            return "Error: Grok internal server error. Please try again later."

        return f"Grok Error {status_code}: {response_text[:200]}..."

    async def ask_async(
        self, prompt: str, system_msg: str = "You are a helpful assistant."
    ) -> str:
        """Send a chat completion request to Grok API.

        Args:
            prompt (str): The user's input message.
            system_msg (str, optional): System message to set assistant behavior.
                Defaults to "You are a helpful assistant.".

        Returns:
            str: The assistant's response text, or an error message if the request failed.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
        }

        logger.debug("Sending request to Grok API...")
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=90)
            async with session.post(
                self.API_URL, headers=headers, json=body, timeout=timeout
            ) as response:
                logger.info(
                    f"Received response from Grok with status: {response.status}"
                )

                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Grok API Error {response.status}: {response_text}")
                    return self._handle_grok_error(response.status, response_text)

                data = await response.json()

                choices = data.get("choices", [])
                if not choices:
                    if "error" in data:
                        return f"Grok API Error: {data['error'].get('message', 'Unknown error')}"
                    return "Error: Empty response from Grok."

                content = choices[0].get("message", {}).get("content", "Empty response")
                return content.strip()

        except TimeoutError:
            logger.error("Request to Grok API timed out.")
            return "Error: Grok request timeout. Please try again later."
        except aiohttp.ClientError as e:
            logger.error(f"Network or connection error to Grok: {e}", exc_info=True)
            return f"Error: Network error connecting to Grok: {e}"
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in GrokClient: {e}", exc_info=True
            )
            return f"Error: Unexpected Grok error: {e}"


def get_ai_client(provider: str, config: dict[str, Any]) -> BaseAiClient:
    """Factory function for creating the appropriate AI client.

    This function creates and returns an AI client instance based on the
    specified provider. It handles API key retrieval from environment
    variables or configuration, and validates required parameters.

    Args:
        provider (str): The AI service provider name (case-insensitive).
            Supported values: "openai", "gemini", "mistral", "claude",
            "huggingface", "grok".
        config (Dict[str, Any]): Configuration dictionary containing API keys
            and model specifications. Expected structure:
            {
                "ai": {
                    "keys": {"provider_name": "api_key"},
                    "models": {"provider_name": "model_name"}
                }
            }

    Returns:
        BaseAiClient: An instance of the appropriate client class for the
        specified provider.

    Raises:
        ValueError: If the provider is unknown, or if the required API key
            or model configuration is missing.

    Example:
        >>> config = {
        ...     "ai": {
        ...         "keys": {"openai": "sk-..."},
        ...         "models": {"openai": "gpt-3.5-turbo"}
        ...     }
        ... }
        >>> client = get_ai_client("openai", config)
        >>> response = await client.ask_async("Hello!", "You are helpful.")
    """
    provider = provider.lower()

    api_key_env_var = f"{provider.upper()}_API_KEY"
    if provider == "huggingface":
        api_key_env_var = "HUGGINGFACE_API_KEY"
    elif provider == "grok":
        api_key_env_var = "XAI_API_KEY"

    api_key = os.environ.get(api_key_env_var) or config.get("ai", {}).get(
        "keys", {}
    ).get(provider)

    model = config.get("ai", {}).get("models", {}).get(provider)

    if not api_key:
        raise ValueError(
            f"API key for {provider} not found in config or environment variable {api_key_env_var}"
        )
    if not model:
        raise ValueError(f"Model for {provider} not found in config")

    if provider == "openai":
        return OpenAiClient(model=model, api_key=api_key)
    if provider == "gemini":
        return GeminiClient(model=model, api_key=api_key)
    if provider == "mistral":
        return MistralClient(model=model, api_key=api_key)
    if provider == "claude":
        return ClaudeClient(model=model, api_key=api_key)
    if provider == "huggingface":
        return HuggingFaceClient(model=model, api_key=api_key)
    if provider == "grok":
        return GrokClient(model=model, api_key=api_key)
    raise ValueError(f"Unknown AI provider: {provider}")
