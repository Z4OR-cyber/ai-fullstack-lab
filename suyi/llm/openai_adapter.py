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
    def _parse_content_tool_calls(content: Optional[str]) -> list[ToolCall]:
        """
        Parse tool calls embedded in content text (Ollama / local model fallback).

        Some OpenAI-compatible endpoints (notably Ollama with qwen2.5-coder)
        do not populate the ``tool_calls`` array; instead they emit a JSON
        object (or multiple newline-separated JSON objects) directly in
        ``content``::

            {"name": "get_weather", "arguments": {"city": "Beijing"}}
            {"name": "calculate", "arguments": {"expression": "1+1"}}

        This method detects and parses such payloads so the agent loop can
        still execute tools.  Returns an empty list when content does not
        look like a tool-call payload.
        """
        if not content or not content.strip():
            return []
        text = content.strip()
        # Quick rejection: must contain "name" and look like JSON
        if '"name"' not in text:
            return []
        import uuid as _uuid
        results: list[ToolCall] = []

        def _try_parse_obj(obj: Any) -> Optional[ToolCall]:
            if not isinstance(obj, dict):
                return None
            name = obj.get("name")
            if not name or not isinstance(name, str):
                return None
            raw_args = obj.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args) if raw_args.strip() else {}
                except (json.JSONDecodeError, TypeError):
                    arguments = {"_raw": raw_args}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = {"_raw": raw_args}
            return ToolCall(
                id=obj.get("id") or f"call_{_uuid.uuid4().hex[:12]}",
                name=name,
                arguments=arguments,
            )

        # Try single JSON object
        try:
            parsed = json.loads(text)
            tc = _try_parse_obj(parsed)
            if tc:
                results.append(tc)
                return results
        except (json.JSONDecodeError, TypeError):
            pass

        # Try multiple JSON objects (one per line, possibly wrapped in ```json fences)
        cleaned = text
        if cleaned.startswith("```"):
            # Strip code fences
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        for line in cleaned.split("\n"):
            line = line.strip().rstrip(",")
            if not line or '"name"' not in line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            tc = _try_parse_obj(obj)
            if tc:
                results.append(tc)
        return results

    @staticmethod
    def _parse_tool_calls(response_data: dict) -> list[ToolCall]:
        """
        Parse OpenAI tool_calls from response.

        Primary path: standard ``tool_calls`` array::

            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": "{\\"city\\": \\"Tokyo\\"}"
                    }
                }
            ]

        Fallback path: if the array is absent but ``content`` contains an
        embedded JSON tool-call (Ollama / local model behaviour), parse it
        via :meth:`_parse_content_tool_calls`.
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

        # Fallback: Ollama-style tool calls embedded in content
        if not tool_calls:
            content = message.get("content")
            content_calls = OpenAIAdapter._parse_content_tool_calls(content)
            tool_calls.extend(content_calls)

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

        # Parse tool calls (may also be parsed from content fallback)
        tool_calls = self._parse_tool_calls(data)

        # If tool calls were extracted from content (Ollama-style fallback),
        # clear content so the agent loop treats this as a pure tool-call turn
        if tool_calls and content:
            content_text = content.strip()
            if '"name"' in content_text:
                try:
                    parsed = json.loads(content_text)
                    if isinstance(parsed, dict) and "name" in parsed:
                        content = None
                except (json.JSONDecodeError, TypeError):
                    pass

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
