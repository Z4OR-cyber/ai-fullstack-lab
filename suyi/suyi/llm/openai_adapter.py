"""
OpenAI-Compatible LLM Adapter.

Implements the LLMInterface protocol using raw HTTP requests (httpx),
supporting OpenAI API format and any compatible provider:
DeepSeek, Moonshot, Together, Groq, OpenRouter, local vLLM, etc.

Key design:
    - No dependency on the openai SDK — pure httpx async calls
    - Converts Suyi's messages/tools format → OpenAI API format
    - Converts OpenAI response → LLMResponse (with tool_calls parsing)
    - Supports streaming (stream=True yields content chunks)
    - API key from constructor, env var, or config

Usage::

    from suyi.llm import OpenAIAdapter

    llm = OpenAIAdapter(
        api_key="sk-...",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
    )
    response = await llm.chat(messages, tools, system_prompt)
    print(response.content)

    # Streaming
    async for chunk in llm.chat_stream(messages, tools, system_prompt):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Optional

import httpx

from ..core.loop import LLMResponse, ToolCall


class OpenAIAdapter:
    """
    LLM adapter for OpenAI-compatible APIs.

    Compatible providers (set base_url accordingly):
        - OpenAI:    https://api.openai.com/v1
        - DeepSeek:  https://api.deepseek.com/v1
        - Moonshot:  https://api.moonshot.cn/v1
        - Together:  https://api.together.xyz/v1
        - Groq:      https://api.groq.com/openai/v1
        - OpenRouter:https://openrouter.ai/api/v1
        - Local:     http://localhost:8000/v1
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        **extra_kwargs: Any,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_kwargs = extra_kwargs

        if not self.api_key:
            raise ValueError(
                "API key required: pass api_key= or set OPENAI_API_KEY env var"
            )

        self._client: Optional[httpx.AsyncClient] = None

    # ── HTTP Client Management ─────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and reuse the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for the API request."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        return headers

    # ── Format Conversion ──────────────────────────────────────

    def _build_request_body(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Convert Suyi format → OpenAI API request body.

        Suyi messages: [{"role": "user", "content": "..."}, ...]
        Suyi tools:    [{"type": "function", "function": {"name": ..., ...}}]
        OpenAI expects the same format, so conversion is mostly passthrough
        with system prompt injection.
        """
        # Build messages: system prompt first, then conversation history
        api_messages: list[dict] = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            # Deep copy to avoid mutating caller's list
            api_msg = dict(msg)

            # Handle tool result messages — OpenAI expects specific format
            if msg.get("role") == "tool":
                # Already in OpenAI format: {role: tool, content, tool_call_id}
                api_messages.append(api_msg)
            elif msg.get("role") == "assistant" and "tool_calls" in msg:
                # Assistant message with tool calls — ensure correct format
                api_messages.append({
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": msg["tool_calls"],
                })
            else:
                api_messages.append(api_msg)

        body: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add tools if provided (OpenAI function calling format)
        if tools:
            body["tools"] = tools

        # Merge any extra kwargs (e.g., top_p, frequency_penalty)
        body.update(self.extra_kwargs)

        if stream:
            body["stream"] = True

        return body

    @staticmethod
    def _parse_tool_calls(response_data: dict) -> list[ToolCall]:
        """
        Parse OpenAI tool_calls from response.

        OpenAI format:
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": "{\"city\": \"Tokyo\"}"  # JSON string!
                    }
                }
            ]
        """
        tool_calls: list[ToolCall] = []
        message = response_data.get("choices", [{}])[0].get("message", {})

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            # OpenAI returns arguments as a JSON string — parse it
            raw_args = func.get("arguments", "{}")
            try:
                if isinstance(raw_args, str):
                    arguments = json.loads(raw_args) if raw_args.strip() else {}
                else:
                    arguments = raw_args
            except (json.JSONDecodeError, TypeError):
                arguments = {"_raw": raw_args}

            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=arguments,
                )
            )

        return tool_calls

    @staticmethod
    def _parse_usage(response_data: dict) -> dict:
        """Extract usage stats from OpenAI response."""
        usage = response_data.get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    # ── LLMInterface Implementation ────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """
        Send a chat completion request and return an LLMResponse.

        Implements the LLMInterface protocol.
        """
        body = self._build_request_body(messages, tools, system_prompt, stream=False)
        url = f"{self.base_url}/chat/completions"

        client = await self._get_client()

        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else "unknown"
            raise RuntimeError(
                f"OpenAI API error {e.response.status_code}: {error_body}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}") from e

        data = resp.json()

        # Extract content
        choices = data.get("choices", [])
        content: Optional[str] = None
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")

        # Parse tool calls
        tool_calls = self._parse_tool_calls(data)

        # Parse usage
        usage = self._parse_usage(data)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion, yielding content chunks as they arrive.

        This is NOT part of the LLMInterface protocol — it's an optional
        enhancement for real-time output display.
        """
        body = self._build_request_body(messages, tools, system_prompt, stream=True)
        url = f"{self.base_url}/chat/completions"

        client = await self._get_client()

        try:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else "unknown"
            raise RuntimeError(
                f"OpenAI API streaming error {e.response.status_code}: {error_body}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Streaming request failed: {e}") from e

    # ── Lifecycle ──────────────────────────────────────────────

    async def close(self) -> None:
        """Close the HTTP client. Call when done to free resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OpenAIAdapter":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
