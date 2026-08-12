"""
OmniRoute 适配器测试 — 全部使用 Mock，不依赖真实 OmniRoute 服务。

测试覆盖：
    - 适配器创建（默认参数 + 自定义参数）
    - 请求体构建（model="auto" 特殊处理）
    - 响应解析（标准 OpenAI 格式 + OmniRoute 扩展字段）
    - 健康检查（mock httpx 响应）
    - 模型列表（mock httpx 响应）
    - Provider 状态获取（mock httpx 响应）
    - 连接重试逻辑（首次失败后重试成功）
    - chat() 完整流程（mock httpx 响应）
    - chat_stream() 流式输出（mock httpx 响应）
    - fallback 信息提取
    - 工厂注册测试（create_llm("omniroute") 返回 OmniRouteAdapter）
    - 协议兼容性测试
"""

import asyncio
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from suyi.llm import OmniRouteAdapter, create_llm, create_llm_from_config, list_providers
from suyi.llm.factory import register_provider, _PROVIDER_REGISTRY, _PROVIDER_ALIASES
from suyi.core.loop import LLMResponse, ToolCall, LLMInterface


# ═══════════════════════════════════════════════════════════════
#  适配器创建测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteAdapterInit:
    """测试 OmniRouteAdapter 初始化。"""

    def test_init_with_defaults(self):
        """使用全部默认参数创建适配器。"""
        adapter = OmniRouteAdapter()
        assert adapter.base_url == "http://localhost:20128/v1"
        assert adapter.model == "auto/best-free"
        assert adapter.api_key == "sk-ac3f703f89a3c4a7-e18773-1c0655db"
        assert adapter.temperature == 0.7
        assert adapter.max_tokens == 4096
        assert adapter.max_retries == 3
        assert adapter.retry_interval == 2.0

    def test_init_with_custom_api_key(self):
        """使用自定义 API key 创建适配器。"""
        adapter = OmniRouteAdapter(api_key="my-secret-key")
        assert adapter.api_key == "my-secret-key"

    def test_init_with_custom_base_url(self):
        """使用自定义 base_url 创建适配器。"""
        adapter = OmniRouteAdapter(base_url="http://192.168.1.100:3000/v1")
        assert adapter.base_url == "http://192.168.1.100:3000/v1"

    def test_init_with_custom_model(self):
        """指定具体模型而非 auto。"""
        adapter = OmniRouteAdapter(model="gpt-4o")
        assert adapter.model == "gpt-4o"

    def test_init_with_custom_retry_params(self):
        """自定义重试参数。"""
        adapter = OmniRouteAdapter(max_retries=5, retry_interval=0.5)
        assert adapter.max_retries == 5
        assert adapter.retry_interval == 0.5

    def test_init_strips_trailing_slash(self):
        """base_url 尾部斜杠应被去除。"""
        adapter = OmniRouteAdapter(base_url="http://localhost:20128/v1/")
        assert adapter.base_url == "http://localhost:20128/v1"

    def test_init_no_api_key_required(self):
        """OmniRoute 不强制要求 API key（与 OpenAIAdapter 不同）。"""
        # 不传 api_key 不应报错，使用配置的默认 key
        adapter = OmniRouteAdapter()
        assert adapter.api_key == "sk-ac3f703f89a3c4a7-e18773-1c0655db"

    def test_init_is_subclass_of_openai(self):
        """OmniRouteAdapter 应继承 OpenAIAdapter。"""
        from suyi.llm import OpenAIAdapter
        adapter = OmniRouteAdapter()
        assert isinstance(adapter, OpenAIAdapter)


# ═══════════════════════════════════════════════════════════════
#  请求头构建测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteHeaders:
    """测试 OmniRouteAdapter 的请求头构建。"""

    def test_headers_without_api_key(self):
        """使用 'omniroute-local'（无认证模式）时不应包含 Authorization 头。"""
        adapter = OmniRouteAdapter(api_key="omniroute-local")
        headers = adapter._build_headers()
        assert "Content-Type" in headers
        assert "Authorization" not in headers

    def test_headers_default_with_api_key(self):
        """默认配置应包含 Authorization 头（使用配置的 API key）。"""
        adapter = OmniRouteAdapter()
        headers = adapter._build_headers()
        assert "Content-Type" in headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer sk-ac3f703f89a3c4a7-e18773-1c0655db"

    def test_headers_with_api_key(self):
        """传入真实 API key 时应包含 Bearer 认证头。"""
        adapter = OmniRouteAdapter(api_key="real-key-123")
        headers = adapter._build_headers()
        assert headers["Authorization"] == "Bearer real-key-123"


# ═══════════════════════════════════════════════════════════════
#  请求体构建测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteRequestBuilding:
    """测试 OmniRouteAdapter 请求体构建。"""

    def test_build_body_model_auto(self):
        """model="auto/best-free"（默认）应正确写入请求体。"""
        adapter = OmniRouteAdapter()
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
            system_prompt="You are helpful.",
        )
        assert body["model"] == "auto/best-free"
        assert body["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert body["messages"][1] == {"role": "user", "content": "Hello"}

    def test_build_body_with_tools(self):
        """带工具的请求体应包含 tools 字段。"""
        adapter = OmniRouteAdapter()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "search"}],
            tools=tools,
            system_prompt="",
        )
        assert body["tools"] == tools

    def test_build_body_stream(self):
        """流式请求应包含 stream=True。"""
        adapter = OmniRouteAdapter()
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
            stream=True,
        )
        assert body["stream"] is True

    def test_build_body_inherits_from_openai(self):
        """请求体构建逻辑应与父类 OpenAIAdapter 一致。"""
        adapter = OmniRouteAdapter()
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
            system_prompt="System prompt",
        )
        # 验证标准 OpenAI 格式字段
        assert "model" in body
        assert "messages" in body
        assert "temperature" in body
        assert "max_tokens" in body
        # 验证 system prompt 被正确注入
        assert body["messages"][0]["role"] == "system"


# ═══════════════════════════════════════════════════════════════
#  响应解析与 fallback 信息提取测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteResponseParsing:
    """测试 OmniRoute 响应解析和 fallback 信息提取。"""

    def test_extract_provider_info_standard_response(self):
        """标准 OpenAI 响应（无扩展字段）应返回空 provider 信息。"""
        data = {
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        info = OmniRouteAdapter._extract_provider_info(data)
        # 没有扩展字段，fallback_triggered 默认 False 会被过滤掉吗？
        # 不，fallback_triggered 默认为 False，不是 None，所以会保留
        assert info.get("fallback_triggered") is False

    def test_extract_provider_info_with_provider(self):
        """包含 provider 字段的 OmniRoute 扩展响应。"""
        data = {
            "choices": [{"message": {"content": "Hello"}}],
            "provider": "openai",
            "model_used": "gpt-4o",
            "fallback_triggered": False,
        }
        info = OmniRouteAdapter._extract_provider_info(data)
        assert info["provider"] == "openai"
        assert info["model_used"] == "gpt-4o"
        assert info["fallback_triggered"] is False

    def test_extract_provider_info_with_fallback(self):
        """触发了 fallback 的响应。"""
        data = {
            "choices": [{"message": {"content": "Hello"}}],
            "provider": "anthropic",
            "model_used": "claude-sonnet-4-20250514",
            "fallback_triggered": True,
            "original_provider": "openai",
        }
        info = OmniRouteAdapter._extract_provider_info(data)
        assert info["provider"] == "anthropic"
        assert info["model_used"] == "claude-sonnet-4-20250514"
        assert info["fallback_triggered"] is True
        assert info["original_provider"] == "openai"

    def test_extract_provider_info_omni_prefix_fields(self):
        """支持 omni_ 前缀的扩展字段。"""
        data = {
            "choices": [{"message": {"content": "Hi"}}],
            "omni_provider": "groq",
            "omni_model": "llama-3-70b",
            "omni_fallback": True,
        }
        info = OmniRouteAdapter._extract_provider_info(data)
        assert info.get("provider") == "groq"
        assert info.get("model") == "llama-3-70b"
        assert info.get("fallback") is True

    def test_parse_tool_calls_inherited(self):
        """工具调用解析应继承父类逻辑。"""
        adapter = OmniRouteAdapter()
        data = {
            "choices": [
                {
                    "message": {
                        "content": "Let me search.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "test"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        tool_calls = adapter._parse_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "search"
        assert tool_calls[0].arguments == {"query": "test"}


# ═══════════════════════════════════════════════════════════════
#  健康检查测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteHealthCheck:
    """测试 OmniRouteAdapter.health_check()。"""

    async def test_health_check_via_health_endpoint(self):
        """通过 /health 端点成功获取健康状态。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "providers": 3}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            result = await adapter.health_check()

        assert result["status"] == "ok"
        assert result["providers"] == 3
        # 第一次应请求 /health
        first_call_url = mock_client.get.call_args_list[0][0][0]
        assert "/health" in first_call_url

    async def test_health_check_fallback_to_models_endpoint(self):
        """/health 失败时回退到 /models 端点。"""
        adapter = OmniRouteAdapter()

        mock_health_response = MagicMock()
        mock_health_response.status_code = 404

        mock_models_response = MagicMock()
        mock_models_response.status_code = 200
        mock_models_response.json.return_value = {
            "object": "list",
            "data": [{"id": "gpt-4o"}],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[mock_health_response, mock_models_response]
        )

        with patch.object(adapter, "_get_client", return_value=mock_client):
            result = await adapter.health_check()

        assert "data" in result
        assert result["data"][0]["id"] == "gpt-4o"

    async def test_health_check_all_endpoints_fail(self):
        """所有端点都不可用时应抛出 RuntimeError。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="健康检查失败"):
                await adapter.health_check()


# ═══════════════════════════════════════════════════════════════
#  模型列表测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteListModels:
    """测试 OmniRouteAdapter.list_models()。"""

    async def test_list_models_standard_format(self):
        """标准 OpenAI 格式的模型列表。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [
                {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
                {"id": "claude-sonnet-4-20250514", "object": "model", "owned_by": "anthropic"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            models = await adapter.list_models()

        assert len(models) == 2
        assert models[0]["id"] == "gpt-4o"
        assert models[1]["id"] == "claude-sonnet-4-20250514"

    async def test_list_models_plain_list_format(self):
        """直接返回列表格式的模型列表。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "llama-3-70b"},
            {"id": "gpt-4o-mini"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            models = await adapter.list_models()

        assert len(models) == 2
        assert models[0]["id"] == "llama-3-70b"

    async def test_list_models_http_error(self):
        """HTTP 错误时应抛出 RuntimeError。"""
        import httpx

        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.raise_for_status.side_effect = http_error

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="获取模型列表失败"):
                await adapter.list_models()


# ═══════════════════════════════════════════════════════════════
#  Provider 状态测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteProviderStatus:
    """测试 OmniRouteAdapter.get_provider_status()。"""

    async def test_get_provider_status_success(self):
        """成功获取 Provider 状态。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "providers": [
                {"name": "openai", "status": "active", "models": 5},
                {"name": "anthropic", "status": "standby", "models": 3},
            ],
            "fallback_chain": ["openai", "anthropic", "local"],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            result = await adapter.get_provider_status()

        assert len(result["providers"]) == 2
        assert result["providers"][0]["name"] == "openai"
        assert result["fallback_chain"] == ["openai", "anthropic", "local"]

    async def test_get_provider_status_fallback_to_health(self):
        """/providers 不可用时回退到 /health。"""
        adapter = OmniRouteAdapter()

        # /providers 返回 404
        mock_providers_response = MagicMock()
        mock_providers_response.status_code = 404

        # /health 返回 200
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[mock_providers_response, mock_health_response, mock_health_response]
        )

        with patch.object(adapter, "_get_client", return_value=mock_client):
            result = await adapter.get_provider_status()

        assert "health" in result
        assert result["health"]["status"] == "ok"
        assert "note" in result

    async def test_get_provider_status_all_fail(self):
        """所有端点不可用时应抛出 RuntimeError。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Provider 状态获取失败"):
                await adapter.get_provider_status()


# ═══════════════════════════════════════════════════════════════
#  chat() 完整流程测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteChat:
    """测试 OmniRouteAdapter.chat() 完整流程。"""

    async def test_chat_text_response(self):
        """标准文本响应。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello from OmniRoute!"}}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="Be helpful.",
            )

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from OmniRoute!"
        assert response.tool_calls == []
        assert response.usage["total_tokens"] == 8

        # 验证请求 URL
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:20128/v1/chat/completions"
        body = call_args[1]["json"]
        assert body["model"] == "auto/best-free"

    async def test_chat_with_tool_calls(self):
        """带工具调用的响应。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Let me search.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "weather"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Search weather"}],
                tools=[{"type": "function", "function": {"name": "search"}}],
                system_prompt="",
            )

        assert response.content == "Let me search."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments == {"query": "weather"}

    async def test_chat_with_provider_info_injected(self):
        """OmniRoute 扩展字段应被注入 usage["omniroute"]。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Hello!"}}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            "provider": "openai",
            "model_used": "gpt-4o",
            "fallback_triggered": False,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert "omniroute" in response.usage
        assert response.usage["omniroute"]["provider"] == "openai"
        assert response.usage["omniroute"]["model_used"] == "gpt-4o"

    async def test_chat_http_error(self):
        """HTTP 错误应抛出 RuntimeError。"""
        import httpx

        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.raise_for_status.side_effect = http_error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="OmniRoute API error 500"):
                await adapter.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    tools=[],
                    system_prompt="",
                )


# ═══════════════════════════════════════════════════════════════
#  连接重试测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteRetry:
    """测试 OmniRouteAdapter 的连接重试逻辑。"""

    async def test_chat_retry_then_success(self):
        """首次连接失败后重试成功。"""
        adapter = OmniRouteAdapter(max_retries=3, retry_interval=0.01)
        # httpx 已在文件顶部导入

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success on retry!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        # 第一次抛 ConnectError，第二次成功
        mock_client.post = AsyncMock(
            side_effect=[httpx.ConnectError("Connection refused"), mock_response]
        )

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert response.content == "Success on retry!"
        assert mock_client.post.call_count == 2

    async def test_chat_all_retries_exhausted(self):
        """所有重试都失败应抛出 RuntimeError。"""
        import httpx

        adapter = OmniRouteAdapter(max_retries=2, retry_interval=0.01)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="连接失败，已重试 2 次"):
                await adapter.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    tools=[],
                    system_prompt="",
                )

        assert mock_client.post.call_count == 2

    async def test_chat_http_error_no_retry(self):
        """HTTP 状态码错误不应重试。"""
        import httpx

        adapter = OmniRouteAdapter(max_retries=3, retry_interval=0.01)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        http_error = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.raise_for_status.side_effect = http_error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="OmniRoute API error 400"):
                await adapter.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    tools=[],
                    system_prompt="",
                )

        # HTTP 错误不重试，只调用一次
        assert mock_client.post.call_count == 1


# ═══════════════════════════════════════════════════════════════
#  chat_with_fallback_info 测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteChatWithFallbackInfo:
    """测试 OmniRouteAdapter.chat_with_fallback_info()。"""

    async def test_chat_with_fallback_info_no_fallback(self):
        """正常响应（无 fallback）的 fallback 信息。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            "provider": "openai",
            "model_used": "gpt-4o",
            "fallback_triggered": False,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            llm_resp, info = await adapter.chat_with_fallback_info(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert isinstance(llm_resp, LLMResponse)
        assert llm_resp.content == "Hello!"
        assert info["provider"] == "openai"
        assert info["model_used"] == "gpt-4o"
        assert info["fallback_triggered"] is False

    async def test_chat_with_fallback_info_triggered(self):
        """触发 fallback 时的信息。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from fallback!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            "provider": "anthropic",
            "model_used": "claude-sonnet-4-20250514",
            "fallback_triggered": True,
            "original_provider": "openai",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            llm_resp, info = await adapter.chat_with_fallback_info(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert llm_resp.content == "Hello from fallback!"
        assert info["provider"] == "anthropic"
        assert info["fallback_triggered"] is True
        assert info["original_provider"] == "openai"

    async def test_chat_with_fallback_info_no_extension_fields(self):
        """响应中无 OmniRoute 扩展字段时，info 仅含默认值。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Plain response."}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            llm_resp, info = await adapter.chat_with_fallback_info(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert llm_resp.content == "Plain response."
        # fallback_triggered 默认 False
        assert info.get("fallback_triggered") is False


# ═══════════════════════════════════════════════════════════════
#  流式输出测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteStreaming:
    """测试 OmniRouteAdapter.chat_stream()。"""

    async def test_chat_stream_basic(self):
        """基本流式输出。"""
        adapter = OmniRouteAdapter()

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" from"}}]}',
            'data: {"choices":[{"delta":{"content":" OmniRoute!"}}]}',
            'data: [DONE]',
        ]

        class MockStreamResponse:
            def raise_for_status(self):
                pass

            async def aiter_lines(self):
                for line in sse_lines:
                    yield line

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=MockStreamResponse())

        with patch.object(adapter, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in adapter.chat_stream(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " from", " OmniRoute!"]

    async def test_chat_stream_with_retry(self):
        """流式输出首次连接失败后重试成功。"""
        import httpx

        adapter = OmniRouteAdapter(max_retries=3, retry_interval=0.01)

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Retry OK"}}]}',
            'data: [DONE]',
        ]

        class MockStreamResponse:
            def raise_for_status(self):
                pass

            async def aiter_lines(self):
                for line in sse_lines:
                    yield line

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        mock_client = AsyncMock()
        # 第一次 stream 抛 ConnectError，第二次成功
        call_count = 0

        def stream_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 需要返回一个在 __aenter__ 时抛异常的 context manager
                class FailingStream:
                    async def __aenter__(self):
                        raise httpx.ConnectError("Connection refused")
                    async def __aexit__(self, *a):
                        pass
                return FailingStream()
            return MockStreamResponse()

        mock_client.stream = MagicMock(side_effect=stream_side_effect)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in adapter.chat_stream(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            ):
                chunks.append(chunk)

        assert chunks == ["Retry OK"]


# ═══════════════════════════════════════════════════════════════
#  工厂注册测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteFactory:
    """测试 OmniRoute 在工厂中的注册。"""

    def test_create_omniroute_default(self):
        """工厂创建 OmniRouteAdapter（默认参数）。"""
        llm = create_llm("omniroute")
        assert isinstance(llm, OmniRouteAdapter)
        assert llm.base_url == "http://localhost:20128/v1"
        assert llm.model == "auto/best-free"

    def test_create_omniroute_with_custom_params(self):
        """工厂创建 OmniRouteAdapter（自定义参数）。"""
        llm = create_llm(
            "omniroute",
            base_url="http://10.0.0.1:9999/v1",
            model="gpt-4o",
            api_key="custom-key",
        )
        assert isinstance(llm, OmniRouteAdapter)
        assert llm.base_url == "http://10.0.0.1:9999/v1"
        assert llm.model == "gpt-4o"
        assert llm.api_key == "custom-key"

    def test_create_omniroute_via_alias(self):
        """通过别名 "omni" 创建。"""
        llm = create_llm("omni")
        assert isinstance(llm, OmniRouteAdapter)

    def test_omniroute_in_provider_registry(self):
        """_PROVIDER_REGISTRY 中应包含 omniroute。"""
        assert "omniroute" in _PROVIDER_REGISTRY
        assert _PROVIDER_REGISTRY["omniroute"] is OmniRouteAdapter

    def test_omni_alias_in_aliases(self):
        """_PROVIDER_ALIASES 中应包含 omni → omniroute。"""
        assert _PROVIDER_ALIASES.get("omni") == "omniroute"

    def test_omniroute_in_list_providers(self):
        """list_providers() 应包含 omniroute 和 omni。"""
        providers = list_providers()
        assert "omniroute" in providers
        assert "omni" in providers

    def test_create_from_config(self):
        """通过 LLMConfig 创建 OmniRouteAdapter。"""
        from suyi.config import LLMConfig

        config = LLMConfig(
            provider="omniroute",
            model="gpt-4o",
            base_url="http://localhost:20128/v1",
        )
        llm = create_llm_from_config(config)
        assert isinstance(llm, OmniRouteAdapter)
        assert llm.model == "gpt-4o"


# ═══════════════════════════════════════════════════════════════
#  协议兼容性测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteProtocolCompliance:
    """测试 OmniRouteAdapter 是否满足 LLMInterface 协议。"""

    def test_is_llm_interface(self):
        """OmniRouteAdapter 应满足 LLMInterface 协议。"""
        adapter = OmniRouteAdapter()
        assert isinstance(adapter, LLMInterface)

    def test_has_chat_method(self):
        """应有 async chat 方法。"""
        adapter = OmniRouteAdapter()
        assert hasattr(adapter, "chat")
        assert asyncio.iscoroutinefunction(adapter.chat)

    def test_has_chat_stream_method(self):
        """应有 chat_stream 方法。"""
        adapter = OmniRouteAdapter()
        assert hasattr(adapter, "chat_stream")

    def test_has_close_method(self):
        """应有 close 方法（继承自父类）。"""
        adapter = OmniRouteAdapter()
        assert hasattr(adapter, "close")
        assert asyncio.iscoroutinefunction(adapter.close)

    async def test_context_manager(self):
        """应支持 async with 上下文管理器。"""
        adapter = OmniRouteAdapter()
        async with adapter as a:
            assert a is adapter
        assert adapter._client is None


# ═══════════════════════════════════════════════════════════════
#  生命周期测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteLifecycle:
    """测试 OmniRouteAdapter 生命周期方法。"""

    async def test_close(self):
        """close() 应关闭 HTTP 客户端。"""
        adapter = OmniRouteAdapter()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        adapter._client = mock_client

        await adapter.close()
        mock_client.aclose.assert_called_once()
        assert adapter._client is None

    async def test_close_already_closed(self):
        """对已关闭的客户端调用 close() 不应报错。"""
        adapter = OmniRouteAdapter()
        adapter._client = None
        await adapter.close()  # 不应抛出异常

# ═══════════════════════════════════════════════════════════════
#  Cost 监控测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteCostHeaders:
    """测试 OmniRouteAdapter._extract_cost_headers()。"""

    def test_extract_cost_headers_full(self):
        """完整的 cost 响应头应被正确解析。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0.00234",
            "x-omniroute-provider": "openai",
            "x-omniroute-model": "gpt-4o",
            "x-omniroute-tokens-in": "1234",
            "x-omniroute-tokens-out": "567",
        }

        info = adapter._extract_cost_headers(mock_response)
        assert info["cost"] == 0.00234
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o"
        assert info["tokens_in"] == 1234
        assert info["tokens_out"] == 567

    def test_extract_cost_headers_empty(self):
        """无 cost 头时所有字段应为 None。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.headers = {}

        info = adapter._extract_cost_headers(mock_response)
        assert info["cost"] is None
        assert info["provider"] is None
        assert info["model"] is None
        assert info["tokens_in"] is None
        assert info["tokens_out"] is None

    def test_extract_cost_headers_partial(self):
        """部分 cost 头存在时只解析存在的字段。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0.0",
            "x-omniroute-provider": "groq",
        }

        info = adapter._extract_cost_headers(mock_response)
        assert info["cost"] == 0.0
        assert info["provider"] == "groq"
        assert info["model"] is None
        assert info["tokens_in"] is None
        assert info["tokens_out"] is None

    def test_extract_cost_headers_invalid_values(self):
        """无效的数值格式应返回 None 而非报错。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "not-a-number",
            "x-omniroute-tokens-in": "abc",
            "x-omniroute-tokens-out": "",
        }

        info = adapter._extract_cost_headers(mock_response)
        assert info["cost"] is None
        assert info["tokens_in"] is None
        assert info["tokens_out"] is None

    def test_extract_cost_headers_zero_cost(self):
        """零成本应被正确解析（auto/best-free 场景）。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0",
            "x-omniroute-provider": "free-provider",
            "x-omniroute-model": "gemini-flash",
            "x-omniroute-tokens-in": "100",
            "x-omniroute-tokens-out": "50",
        }

        info = adapter._extract_cost_headers(mock_response)
        assert info["cost"] == 0.0
        assert info["provider"] == "free-provider"


class TestOmniRouteCostRecording:
    """测试 OmniRouteAdapter._record_cost() 和 cost 查询。"""

    def test_record_cost_caches_to_memory(self):
        """cost 信息应被缓存到 _cost_log。"""
        adapter = OmniRouteAdapter()
        cost_info = {
            "cost": 0.001,
            "provider": "openai",
            "model": "gpt-4o",
            "tokens_in": 100,
            "tokens_out": 50,
        }
        adapter._record_cost(cost_info)
        assert len(adapter._cost_log) == 1
        entry = adapter._cost_log[0]
        assert entry["cost"] == 0.001
        assert entry["provider"] == "openai"
        assert entry["request_model"] == "auto/best-free"
        assert "timestamp" in entry

    def test_record_cost_with_backend(self):
        """cost_backend 存在时应调用 set 方法持久化。"""
        adapter = OmniRouteAdapter()
        mock_backend = MagicMock()
        mock_backend.set = MagicMock()
        adapter.cost_backend = mock_backend

        cost_info = {
            "cost": 0.002,
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "tokens_in": 200,
            "tokens_out": 100,
        }
        adapter._record_cost(cost_info)

        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        assert key.startswith("cost_log:")
        assert value["cost"] == 0.002
        assert value["provider"] == "anthropic"

    def test_record_cost_backend_failure_no_crash(self):
        """cost_backend 出错时不应崩溃，仅记录警告。"""
        adapter = OmniRouteAdapter()
        mock_backend = MagicMock()
        mock_backend.set = MagicMock(side_effect=RuntimeError("DB error"))
        adapter.cost_backend = mock_backend

        cost_info = {"cost": 0.001, "provider": "test", "model": "test",
                     "tokens_in": 10, "tokens_out": 5}
        # 不应抛出异常
        adapter._record_cost(cost_info)
        assert len(adapter._cost_log) == 1  # 仍然缓存到内存

    def test_record_cost_none_values(self):
        """所有 cost 值为 None 时也应正常记录。"""
        adapter = OmniRouteAdapter()
        cost_info = {"cost": None, "provider": None, "model": None,
                     "tokens_in": None, "tokens_out": None}
        adapter._record_cost(cost_info)
        assert len(adapter._cost_log) == 1

    def test_cost_history_property(self):
        """cost_history 属性返回所有记录的副本。"""
        adapter = OmniRouteAdapter()
        for i in range(3):
            adapter._record_cost({
                "cost": 0.001 * (i + 1),
                "provider": f"provider_{i}",
                "model": f"model_{i}",
                "tokens_in": 100,
                "tokens_out": 50,
            })
        history = adapter.cost_history
        assert len(history) == 3
        assert history[0]["cost"] == 0.001
        assert history[2]["cost"] == 0.003
        # 确认是副本（修改不影响内部状态）
        history.append({"fake": True})
        assert len(adapter._cost_log) == 3

    def test_get_total_cost(self):
        """get_total_cost 返回累计成本。"""
        adapter = OmniRouteAdapter()
        adapter._record_cost({"cost": 0.001, "provider": "a", "model": "m",
                              "tokens_in": 10, "tokens_out": 5})
        adapter._record_cost({"cost": 0.002, "provider": "b", "model": "m",
                              "tokens_in": 10, "tokens_out": 5})
        adapter._record_cost({"cost": None, "provider": "c", "model": "m",
                              "tokens_in": 10, "tokens_out": 5})
        assert adapter.get_total_cost() == 0.003

    def test_get_total_cost_empty(self):
        """无记录时累计成本为 0。"""
        adapter = OmniRouteAdapter()
        assert adapter.get_total_cost() == 0.0


class TestOmniRouteCostInChat:
    """测试 cost 监控在 chat() 和 chat_with_fallback_info() 中的集成。"""

    async def test_chat_injects_cost_into_usage(self):
        """chat() 应将 cost 信息注入 usage。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0.0001",
            "x-omniroute-provider": "groq",
            "x-omniroute-model": "llama-3-70b",
            "x-omniroute-tokens-in": "5",
            "x-omniroute-tokens-out": "3",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert "cost" in response.usage
        assert response.usage["cost"]["cost"] == 0.0001
        assert response.usage["cost"]["provider"] == "groq"
        assert response.usage["cost"]["model"] == "llama-3-70b"
        assert response.usage["cost"]["tokens_in"] == 5
        assert response.usage["cost"]["tokens_out"] == 3
        assert len(adapter.cost_history) == 1

    async def test_chat_no_cost_headers(self):
        """无 cost 头时 usage 不包含 cost 键。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert "cost" not in response.usage
        assert len(adapter.cost_history) == 1
        assert adapter.get_total_cost() == 0.0

    async def test_chat_with_fallback_info_includes_cost(self):
        """chat_with_fallback_info 应在 info 中包含 cost。"""
        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            "provider": "openai",
            "model_used": "gpt-4o",
            "fallback_triggered": False,
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0.005",
            "x-omniroute-provider": "openai",
            "x-omniroute-model": "gpt-4o",
            "x-omniroute-tokens-in": "5",
            "x-omniroute-tokens-out": "3",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            llm_resp, info = await adapter.chat_with_fallback_info(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        assert info["provider"] == "openai"
        assert "cost" in info
        assert info["cost"]["cost"] == 0.005

    async def test_chat_cost_with_backend_persistence(self):
        """chat() 配合 cost_backend 时应持久化 cost 记录。"""
        adapter = OmniRouteAdapter()
        mock_backend = MagicMock()
        mock_backend.set = MagicMock()
        adapter.cost_backend = mock_backend

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {
            "x-omniroute-response-cost": "0.001",
            "x-omniroute-provider": "deepseek",
            "x-omniroute-model": "deepseek-chat",
            "x-omniroute-tokens-in": "10",
            "x-omniroute-tokens-out": "5",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

        mock_backend.set.assert_called_once()
        persisted = mock_backend.set.call_args[0][1]
        assert persisted["cost"] == 0.001
        assert persisted["provider"] == "deepseek"
