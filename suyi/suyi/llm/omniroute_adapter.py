"""
OmniRoute LLM 适配器 — 本地 AI Gateway 专用适配器。

OmniRoute 是本地部署的 AI Gateway，暴露 OpenAI 兼容端点
（默认 http://localhost:20128/v1），提供多 Provider 路由、
自动 fallback、成本优化等增强功能。

本适配器继承 OpenAIAdapter，复用其请求构建、响应解析、
流式输出等全部核心能力，并在此基础上增加 OmniRoute 特有功能：

    - 健康检查（health_check）：查询 Gateway 运行状态
    - 模型列表（list_models）：获取可用模型清单
    - Provider 状态（get_provider_status）：查看路由链 / fallback 状态
    - 带 fallback 信息的对话（chat_with_fallback_info）：
      返回 LLMResponse + 实际使用 Provider 的元数据
    - 连接重试：OmniRoute 启动中时自动重试 3 次（间隔 2s）

设计要点：
    - API key 可选（本地部署可能不需要认证）
    - 默认 model="auto"，由 OmniRoute 自动选择最优模型
    - 认证方式灵活：有 key 则用 Bearer，无 key 则不发送 Authorization 头
    - 全部使用 httpx 异步调用，不引入新依赖

Usage::

    from suyi.llm import OmniRouteAdapter

    adapter = OmniRouteAdapter()                      # 使用全部默认值
    adapter = OmniRouteAdapter(api_key="my-key")      # 带认证
    adapter = OmniRouteAdapter(model="gpt-4o")        # 指定模型

    # 健康检查
    status = await adapter.health_check()

    # 对话（与 OpenAIAdapter 接口完全一致）
    resp = await adapter.chat(messages, tools, system_prompt)

    # 带 fallback 信息的对话
    resp, info = await adapter.chat_with_fallback_info(messages, tools, system_prompt)
    print(info)  # {"provider": "openai", "model": "gpt-4o", ...}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

import httpx

from ..core.loop import LLMResponse, ToolCall
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class OmniRouteAdapter(OpenAIAdapter):
    """
    OmniRoute AI Gateway 适配器。

    继承 OpenAIAdapter，复用 OpenAI 兼容 API 的全部能力，
    并增加 OmniRoute 特有的健康检查、模型列表、Provider 状态
    以及 fallback 信息提取等功能。

    Attributes:
        base_url:       OmniRoute 服务地址，默认 http://localhost:20128/v1
        model:          默认 "auto"，由 OmniRoute 自动路由
        api_key:        可选，默认 "omniroute-local"
        max_retries:    连接重试次数，默认 3
        retry_interval: 重试间隔（秒），默认 2
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:20128/v1",
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_interval: float = 2.0,
        **extra_kwargs: Any,
    ):
        # OmniRoute 本地部署可能不需要 API key，给一个默认占位值
        # 父类 OpenAIAdapter.__init__ 会在 api_key 为空时报 ValueError，
        # 所以这里在调用 super().__init__ 前就处理好默认值
        resolved_key = api_key or "omniroute-local"

        super().__init__(
            api_key=resolved_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **extra_kwargs,
        )

        # OmniRoute 特有配置
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    # ── 认证与请求头 ────────────────────────────────────────────

    def _build_headers(self) -> dict[str, str]:
        """
        构建 HTTP 请求头。

        OmniRoute 的认证方式与 OpenAI 不同：
        - 如果 api_key 为 "omniroute-local"（默认占位值），则不发送
          Authorization 头，表示无认证模式
        - 如果用户显式传入了真实 api_key，则使用 Bearer 认证
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        # 仅在有真实 key 时添加认证头
        if self.api_key and self.api_key != "omniroute-local":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ── 连接重试封装 ────────────────────────────────────────────

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[dict] = None,
        use_stream: bool = False,
    ) -> httpx.Response:
        """
        带连接重试的 HTTP 请求。

        OmniRoute 可能在启动过程中，首次连接失败时自动重试。
        仅对连接级错误（ConnectError、ConnectTimeout）重试，
        HTTP 状态码错误不重试（由调用方处理）。

        Args:
            method:       HTTP 方法（GET / POST）
            url:          请求 URL
            json_body:    请求体（POST 时使用）
            use_stream:   是否使用流式响应

        Returns:
            httpx.Response 对象

        Raises:
            RuntimeError: 所有重试耗尽后仍然失败
        """
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if use_stream:
                    # 流式请求由调用方通过 client.stream 处理，这里不直接返回
                    # 此方法主要用于非流式请求
                    raise ValueError("流式请求请直接使用 client.stream")
                else:
                    resp = await client.request(method, url, json=json_body)
                    resp.raise_for_status()
                    return resp
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                # 仅对连接级错误重试
                last_error = e
                logger.warning(
                    "OmniRoute 连接失败（第 %d/%d 次）: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_interval)
            except httpx.HTTPStatusError:
                # HTTP 状态码错误直接向上抛出，不重试
                raise
            except httpx.RequestError as e:
                # 其他请求错误也不重试
                raise RuntimeError(f"OmniRoute 请求失败: {e}") from e

        # 所有重试耗尽
        raise RuntimeError(
            f"OmniRoute 连接失败，已重试 {self.max_retries} 次: {last_error}"
        )

    # ── OmniRoute 特有方法 ─────────────────────────────────────

    async def health_check(self) -> dict:
        """
        检查 OmniRoute 健康状态。

        依次尝试 GET /health 和 GET /v1/models，
        返回第一个成功的响应。两者都失败则抛出异常。

        Returns:
            健康状态字典，例如：
            {"status": "ok"} 或 {"status": "healthy", "providers": 3}
        """
        client = await self._get_client()

        # 优先尝试 /health 端点（OmniRoute 自定义端点）
        for url in [f"{self.base_url}/health", f"{self.base_url}/models"]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
            except (httpx.RequestError, json.JSONDecodeError):
                continue

        raise RuntimeError("OmniRoute 健康检查失败：所有端点均不可用")

    async def list_models(self) -> list[dict]:
        """
        获取 OmniRoute 可用模型列表。

        调用 GET /v1/models，返回模型清单。
        OmniRoute 会聚合所有已配置 Provider 的模型。

        Returns:
            模型字典列表，例如：
            [{"id": "gpt-4o", "object": "model", "owned_by": "openai"}, ...]
        """
        client = await self._get_client()
        url = f"{self.base_url}/models"

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else "unknown"
            raise RuntimeError(
                f"OmniRoute 获取模型列表失败 {e.response.status_code}: {error_body}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"OmniRoute 请求失败: {e}") from e

        data = resp.json()
        # OpenAI 标准格式: {"object": "list", "data": [...]}
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        # 兼容直接返回列表的情况
        if isinstance(data, list):
            return data
        return []

    async def get_provider_status(self) -> dict:
        """
        获取当前 Provider / fallback 链状态。

        调用 GET /v1/providers（OmniRoute 扩展端点），
        返回各 Provider 的健康状态和 fallback 配置。

        如果该端点不可用，尝试从 /health 推断状态。

        Returns:
            Provider 状态字典，例如：
            {
                "providers": [
                    {"name": "openai", "status": "active", "models": 5},
                    {"name": "anthropic", "status": "standby", "models": 3},
                ],
                "fallback_chain": ["openai", "anthropic", "local"]
            }
        """
        client = await self._get_client()
        url = f"{self.base_url}/providers"

        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except (httpx.RequestError, json.JSONDecodeError):
            pass

        # 回退：尝试从 /health 推断
        try:
            health = await self.health_check()
            return {
                "providers": [],
                "fallback_chain": [],
                "health": health,
                "note": "providers 端点不可用，仅返回健康状态",
            }
        except RuntimeError:
            raise RuntimeError("OmniRoute Provider 状态获取失败：所有端点均不可用")

    @staticmethod
    def _extract_provider_info(response_data: dict) -> dict:
        """
        从 OmniRoute 响应中提取 Provider / fallback 元数据。

        OmniRoute 在标准 OpenAI 响应基础上可能附加以下字段：
        - response.provider: 实际使用的 Provider 名称
        - response.model_used: 实际使用的模型名称
        - response.fallback_triggered: 是否触发了 fallback
        - response.original_provider: fallback 前的原始 Provider

        这些字段是可选的，不存在时返回空字典中的默认值。

        Args:
            response_data: OmniRoute 返回的完整 JSON 响应

        Returns:
            Provider 信息字典
        """
        info: dict[str, Any] = {
            "provider": response_data.get("provider"),
            "model_used": response_data.get("model_used"),
            "fallback_triggered": response_data.get("fallback_triggered", False),
            "original_provider": response_data.get("original_provider"),
        }

        # OmniRoute 可能把扩展信息放在顶层或嵌套在某个字段中
        # 检查是否有 omni 前缀的字段
        for key in ("omni_provider", "omni_model", "omni_fallback"):
            if key in response_data:
                short_key = key.replace("omni_", "")
                info[short_key] = response_data[key]

        # 清理 None 值（保留 False 等有效假值）
        return {k: v for k, v in info.items() if v is not None}

    async def chat_with_fallback_info(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> tuple[LLMResponse, dict]:
        """
        发送对话请求，同时返回 fallback 元数据。

        与 chat() 功能一致，但额外提取 OmniRoute 返回的
        Provider 路由信息（哪个 Provider 被实际使用、是否触发 fallback）。

        Args:
            messages:      对话消息列表
            tools:         工具定义列表
            system_prompt: 系统提示词

        Returns:
            (LLMResponse, provider_info) 元组
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
                f"OmniRoute API error {e.response.status_code}: {error_body}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"OmniRoute 请求失败: {e}") from e

        data = resp.json()

        # 提取内容、工具调用、用量（复用父类方法）
        choices = data.get("choices", [])
        content: Optional[str] = None
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")

        tool_calls = self._parse_tool_calls(data)
        usage = self._parse_usage(data)

        llm_response = LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        )

        # 提取 OmniRoute 特有的 Provider 信息
        provider_info = self._extract_provider_info(data)

        return llm_response, provider_info

    # ── 覆写父类方法 ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """
        发送对话请求并返回 LLMResponse。

        覆写父类方法，在标准 OpenAI 响应解析基础上，
        将 OmniRoute 返回的 Provider 元数据注入 usage 字段，
        以便调用方无需使用 chat_with_fallback_info 也能获取路由信息。

        OmniRoute 可能在启动中，首次请求失败时会自动重试。
        """
        body = self._build_request_body(messages, tools, system_prompt, stream=False)
        url = f"{self.base_url}/chat/completions"

        client = await self._get_client()
        last_error: Optional[Exception] = None

        # 带连接重试的请求
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                logger.warning(
                    "OmniRoute 连接失败（第 %d/%d 次）: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_interval)
                    # 重试时重建 client（可能需要重新连接）
                    client = await self._get_client()
                else:
                    raise RuntimeError(
                        f"OmniRoute 连接失败，已重试 {self.max_retries} 次: {last_error}"
                    ) from last_error
            except httpx.HTTPStatusError as e:
                error_body = e.response.text if e.response else "unknown"
                raise RuntimeError(
                    f"OmniRoute API error {e.response.status_code}: {error_body}"
                ) from e
            except httpx.RequestError as e:
                raise RuntimeError(f"OmniRoute 请求失败: {e}") from e

        data = resp.json()

        # 提取内容
        choices = data.get("choices", [])
        content: Optional[str] = None
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")

        # 解析工具调用和用量（复用父类方法）
        tool_calls = self._parse_tool_calls(data)
        usage = self._parse_usage(data)

        # 将 OmniRoute Provider 元数据注入 usage（如果有）
        provider_info = self._extract_provider_info(data)
        if provider_info:
            usage["omniroute"] = provider_info

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
        流式对话输出。

        继承父类的流式实现。OmniRoute 完全兼容 OpenAI SSE 格式，
        因此直接使用父类的 chat_stream 逻辑即可。

        如果首次连接失败，会自动重试。
        """
        body = self._build_request_body(messages, tools, system_prompt, stream=True)
        url = f"{self.base_url}/chat/completions"

        client = await self._get_client()

        for attempt in range(1, self.max_retries + 1):
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
                # 流式成功完成，退出重试循环
                return
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                logger.warning(
                    "OmniRoute 流式连接失败（第 %d/%d 次）: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_interval)
                    client = await self._get_client()
                else:
                    raise RuntimeError(
                        f"OmniRoute 流式连接失败，已重试 {self.max_retries} 次: {e}"
                    ) from e
            except httpx.HTTPStatusError as e:
                error_body = e.response.text if e.response else "unknown"
                raise RuntimeError(
                    f"OmniRoute 流式 API error {e.response.status_code}: {error_body}"
                ) from e
            except httpx.RequestError as e:
                raise RuntimeError(f"OmniRoute 流式请求失败: {e}") from e
