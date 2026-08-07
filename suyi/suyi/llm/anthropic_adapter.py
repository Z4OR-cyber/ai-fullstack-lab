"""
Anthropic Claude LLM Adapter.

Implements the LLMInterface protocol using raw HTTP requests (httpx),
supporting the Anthropic Messages API (Claude models).

Key design:
    - No dependency on the anthropic SDK — pure httpx async calls
    - Converts Suyi's messages/tools format → Anthropic API format
      (system is passed separately; tools use input_schema)
    - Converts Anthropic response (content blocks) → LLMResponse
      (parses text blocks + tool_use blocks)
    - API key from constructor, env var, or config

Anthropic API format differences from OpenAI:
    - System prompt is a top-level parameter, not a message
    - Tools use "input_schema" instead of "parameters"
    - Response is an array of content blocks (text / tool_use)
    - Tool call arguments are already dict, not JSON strings

Usage::

    from suyi.llm import AnthropicAdapter

    llm = AnthropicAdapter(
        api_key="sk-ant-...",
        model="claude-sonnet-4-20250514",
    )
    response = await llm.chat(messages, tools, system_prompt)
    print(response.content)
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

from ..core.loop import LLMResponse, ToolCall


class AnthropicAdapter:
    """
    LLM adapter for Anthropic Claude models.

    Uses the Messages API (POST /v1/messages).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        base_url: str = "https://api.anthropic.com",
        temperature: float = 0.7,
        timeout: float = 120.0,
        anthropic_version: str = "2023-06-01",
        **extra_kwargs: Any,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.anthropic_version = anthropic_version
        self.extra_kwargs = extra_kwargs

        if not self.api_key:
            raise ValueError(
                "API key required: pass api_key= or set ANTHROPIC_API_KEY env var"
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
        """Build HTTP headers for Anthropic API."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
        }
        return headers

    # ── Format Conversion ──────────────────────────────────────

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """
        Convert OpenAI-format tools → Anthropic format.

        OpenAI format:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}

        Anthropic format:
            {"name": ..., "description": ..., "input_schema": {...}}
        """
        anthropic_tools: list[dict] = []
        for tool in tools:
            # If already in Anthropic format (has name + input_schema), pass through
            if "name" in tool and "input_schema" in tool:
                anthropic_tools.append(tool)
                continue

            # OpenAI format: {"type": "function", "function": {...}}
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """
        Convert Suyi/OpenAI messages → Anthropic messages format.

        Key differences:
        - Anthropic doesn't use "system" role in messages (it's top-level)
        - Tool results use "role": "user" with "content": [{"type": "tool_result", ...}]
        - Assistant tool calls use "content": [{"type": "tool_use", ...}]
        """
        anthropic_messages: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Skip system messages (handled separately as top-level system param)
            if role == "system":
                continue

            if role == "tool":
                # Convert OpenAI tool result → Anthropic tool_result block
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content if isinstance(content, str) else json.dumps(content),
                    }],
                })

            elif role == "assistant" and "tool_calls" in msg:
                # Convert assistant message with tool calls
                blocks: list[dict] = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in msg["tool_calls"]:
                    func = tc.get("function", tc)
                    args = func.get("arguments", {})
                    # Anthropic expects arguments as dict, not JSON string
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"_raw": args}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args,
                    })
                anthropic_messages.append({"role": "assistant", "content": blocks})

            else:
                # Regular user/assistant message
                anthropic_messages.append({"role": role, "content": content})

        return anthropic_messages

    def _build_request_body(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> dict[str, Any]:
        """Build the Anthropic Messages API request body."""
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": self._convert_messages(messages),
        }

        if system_prompt:
            body["system"] = system_prompt

        if tools:
            body["tools"] = self._convert_tools(tools)

        # Merge extra kwargs
        body.update(self.extra_kwargs)

        return body

    @staticmethod
    def _parse_response(response_data: dict) -> tuple[Optional[str], list[ToolCall]]:
        """
        Parse Anthropic content blocks → (content, tool_calls).

        Anthropic response format:
            "content": [
                {"type": "text", "text": "Let me search for that."},
                {"type": "tool_use", "id": "toolu_01...", "name": "search", "input": {"query": "..."}},
            ]
        """
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response_data.get("content", []):
            block_type = block.get("type", "")

            if block_type == "text":
                content_parts.append(block.get("text", ""))

            elif block_type == "tool_use":
                # Anthropic returns input as a dict already (no JSON parsing needed)
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        content = "\n".join(content_parts) if content_parts else None
        return content, tool_calls

    @staticmethod
    def _parse_usage(response_data: dict) -> dict:
        """Extract usage stats from Anthropic response."""
        usage = response_data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    # ── LLMInterface Implementation ────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """
        Send a Messages API request and return an LLMResponse.

        Implements the LLMInterface protocol.
        """
        body = self._build_request_body(messages, tools, system_prompt)
        url = f"{self.base_url}/v1/messages"

        client = await self._get_client()

        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else "unknown"
            raise RuntimeError(
                f"Anthropic API error {e.response.status_code}: {error_body}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}") from e

        data = resp.json()

        content, tool_calls = self._parse_response(data)
        usage = self._parse_usage(data)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        )

    # ── Lifecycle ──────────────────────────────────────────────

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AnthropicAdapter":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
