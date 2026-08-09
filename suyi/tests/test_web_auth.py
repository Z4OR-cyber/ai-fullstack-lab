"""
Suyi Web 认证与安全层测试.

覆盖范围:
    - AuthConfig 配置默认值与自定义
    - API Key 认证: 有效 key、无效 key、无 key、空 key、多个有效 key
    - JWT 认证: 生成、验证、过期、篡改、无 token、错误密钥
    - CORS: 预检请求、正常请求 CORS 头、自定义 origins
    - 端点豁免: /health 和 /auth/token 不需要认证
    - 认证优先级: JWT 优先于 API Key
    - 错误响应格式: 401 JSON {error, message}
    - 服务器集成: 认证开关、带/不带凭证的请求
    - 实时 HTTP 服务器: 真实 socket 请求验证认证与 CORS
"""

import json
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from suyi.core.loop import LLMResponse, MockLLM
from suyi.memory import MemoryManager
from suyi.persistence import SessionManager
from suyi.web import SuyiServer, AuthConfig, AuthManager


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_llm():
    """返回友好的 MockLLM."""
    return MockLLM([LLMResponse.text("Hello from Suyi!", tokens=20)])


@pytest.fixture
def auth_config():
    """标准认证配置: 2 个 API Key + JWT 密钥."""
    return AuthConfig(
        auth_enabled=True,
        api_keys=["test-key-1", "test-key-2"],
        jwt_secret="test-jwt-secret",
        jwt_expiry=3600,
        cors_origins=["*"],
    )


@pytest.fixture
def auth_manager(auth_config):
    """认证管理器实例."""
    return AuthManager(auth_config)


@pytest.fixture
def auth_server(mock_llm, auth_config, tmp_path):
    """带认证的服务器实例."""
    return SuyiServer(
        llm=mock_llm,
        auth_config=auth_config,
        memory_manager=MemoryManager(storage_dir=str(tmp_path / "memory")),
        session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
    )


@pytest.fixture
def no_auth_server(mock_llm, tmp_path):
    """不带认证的服务器实例（向后兼容）."""
    return SuyiServer(
        llm=mock_llm,
        memory_manager=MemoryManager(storage_dir=str(tmp_path / "memory")),
        session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
    )


# ═══════════════════════════════════════════════════════════════
#  AuthConfig 配置测试
# ═══════════════════════════════════════════════════════════════


class TestAuthConfig:
    """AuthConfig 配置测试."""

    def test_default_config(self):
        """默认配置: auth_enabled=True, 无 api_keys, 无 jwt_secret."""
        config = AuthConfig()
        assert config.auth_enabled is True
        assert config.api_keys == []
        assert config.jwt_secret == ""
        assert config.jwt_expiry == 3600
        assert config.cors_origins == ["*"]

    def test_custom_config(self):
        """自定义配置."""
        config = AuthConfig(
            auth_enabled=False,
            api_keys=["key-a", "key-b"],
            jwt_secret="my-secret",
            jwt_expiry=7200,
            cors_origins=["https://example.com"],
        )
        assert config.auth_enabled is False
        assert config.api_keys == ["key-a", "key-b"]
        assert config.jwt_secret == "my-secret"
        assert config.jwt_expiry == 7200
        assert config.cors_origins == ["https://example.com"]

    def test_auth_not_active_without_credentials(self):
        """无凭证时认证不生效（即使 auth_enabled=True）."""
        config = AuthConfig(auth_enabled=True)
        manager = AuthManager(config)
        assert manager.is_auth_active() is False

    def test_auth_not_active_when_disabled(self):
        """auth_enabled=False 时认证不生效."""
        config = AuthConfig(auth_enabled=False, api_keys=["key"])
        manager = AuthManager(config)
        assert manager.is_auth_active() is False

    def test_auth_active_with_api_keys(self):
        """仅配置 api_keys 时认证生效."""
        config = AuthConfig(api_keys=["key"])
        manager = AuthManager(config)
        assert manager.is_auth_active() is True

    def test_auth_active_with_jwt_secret(self):
        """仅配置 jwt_secret 时认证生效."""
        config = AuthConfig(jwt_secret="secret")
        manager = AuthManager(config)
        assert manager.is_auth_active() is True


# ═══════════════════════════════════════════════════════════════
#  API Key 认证测试
# ═══════════════════════════════════════════════════════════════


class TestAPIKeyAuth:
    """API Key 认证测试."""

    def test_verify_valid_api_key(self, auth_manager):
        """有效 API Key 验证通过."""
        assert auth_manager.verify_api_key("test-key-1") is True

    def test_verify_second_valid_api_key(self, auth_manager):
        """第二个有效 API Key 也验证通过."""
        assert auth_manager.verify_api_key("test-key-2") is True

    def test_verify_invalid_api_key(self, auth_manager):
        """无效 API Key 验证失败."""
        assert auth_manager.verify_api_key("invalid-key") is False

    def test_verify_empty_api_key(self, auth_manager):
        """空 API Key 验证失败."""
        assert auth_manager.verify_api_key("") is False

    def test_verify_none_like_api_key(self, auth_manager):
        """空字符串 API Key 验证失败."""
        assert auth_manager.verify_api_key("   ") is False

    def test_authenticate_with_bearer_api_key(self, auth_manager):
        """通过 Authorization: Bearer 头传递 API Key 认证成功."""
        headers = {"Authorization": "Bearer test-key-1"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is True
        assert err is None

    def test_authenticate_with_x_api_key_header(self, auth_manager):
        """通过 X-API-Key 头传递 API Key 认证成功."""
        headers = {"X-API-Key": "test-key-2"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is True
        assert err is None

    def test_authenticate_invalid_bearer_key(self, auth_manager):
        """无效 Bearer API Key 认证失败."""
        headers = {"Authorization": "Bearer wrong-key"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is False
        assert err is not None
        assert err["error"] == "Unauthorized"

    def test_authenticate_invalid_x_api_key(self, auth_manager):
        """无效 X-API-Key 认证失败."""
        headers = {"X-API-Key": "wrong-key"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is False
        assert err is not None

    def test_authenticate_no_credentials(self, auth_manager):
        """无任何凭证认证失败."""
        ok, err = auth_manager.authenticate({})
        assert ok is False
        assert err is not None
        assert "error" in err
        assert "message" in err

    def test_authenticate_empty_bearer(self, auth_manager):
        """空的 Bearer token 认证失败."""
        headers = {"Authorization": "Bearer "}
        ok, err = auth_manager.authenticate(headers)
        assert ok is False

    def test_authenticate_no_bearer_prefix(self, auth_manager):
        """非 Bearer 前缀的 Authorization 头不提取 token."""
        headers = {"Authorization": "test-key-1"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is False

    def test_multiple_valid_keys_all_work(self):
        """多个有效 key 都能认证成功."""
        config = AuthConfig(api_keys=["k1", "k2", "k3"])
        manager = AuthManager(config)
        for key in ["k1", "k2", "k3"]:
            ok, _ = manager.authenticate({"X-API-Key": key})
            assert ok is True, f"Key {key} 应该有效"


# ═══════════════════════════════════════════════════════════════
#  JWT 认证测试
# ═══════════════════════════════════════════════════════════════


class TestJWTAuth:
    """JWT Token 认证测试."""

    def test_generate_jwt_returns_string(self, auth_manager):
        """生成的 JWT 是非空字符串."""
        token = auth_manager.generate_jwt("user-1")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_has_three_parts(self, auth_manager):
        """JWT 由三段组成（header.payload.signature）."""
        token = auth_manager.generate_jwt("user-1")
        parts = token.split(".")
        assert len(parts) == 3

    def test_verify_valid_jwt(self, auth_manager):
        """验证有效 JWT 返回 payload."""
        token = auth_manager.generate_jwt("user-1")
        payload = auth_manager.verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "user-1"
        assert "exp" in payload
        assert "iat" in payload

    def test_jwt_expiry_in_future(self, auth_manager):
        """JWT 的 exp 在未来."""
        token = auth_manager.generate_jwt("user-1")
        payload = auth_manager.verify_jwt(token)
        assert payload is not None
        assert payload["exp"] > time.time()

    def test_verify_expired_jwt(self):
        """过期的 JWT 验证失败."""
        config = AuthConfig(
            api_keys=["key"],
            jwt_secret="secret",
            jwt_expiry=-10,  # 已过期
        )
        manager = AuthManager(config)
        token = manager.generate_jwt("user-1")
        assert manager.verify_jwt(token) is None

    def test_verify_tampered_payload(self, auth_manager):
        """篡改 payload 后 JWT 验证失败."""
        token = auth_manager.generate_jwt("user-1")
        parts = token.split(".")
        # 篡改 payload（第二段）
        parts[1] = parts[1][:-2] + "AA"
        tampered = ".".join(parts)
        assert auth_manager.verify_jwt(tampered) is None

    def test_verify_tampered_signature(self, auth_manager):
        """篡改签名后 JWT 验证失败."""
        token = auth_manager.generate_jwt("user-1")
        parts = token.split(".")
        # 篡改签名（第三段）
        parts[2] = parts[2][:-2] + "AA"
        tampered = ".".join(parts)
        assert auth_manager.verify_jwt(tampered) is None

    def test_verify_invalid_format(self, auth_manager):
        """格式不合法的 token 验证失败."""
        assert auth_manager.verify_jwt("not.a.valid.jwt.token") is None
        assert auth_manager.verify_jwt("onlyonepart") is None
        assert auth_manager.verify_jwt("") is None

    def test_verify_jwt_wrong_secret(self):
        """用错误密钥生成的 JWT 验证失败."""
        manager1 = AuthManager(AuthConfig(jwt_secret="secret-1"))
        manager2 = AuthManager(AuthConfig(jwt_secret="secret-2"))
        token = manager1.generate_jwt("user-1")
        assert manager2.verify_jwt(token) is None

    def test_generate_jwt_without_secret_raises(self):
        """未配置 jwt_secret 时生成 JWT 抛出 ValueError."""
        manager = AuthManager(AuthConfig(api_keys=["key"]))
        with pytest.raises(ValueError, match="jwt_secret"):
            manager.generate_jwt("user-1")

    def test_authenticate_with_jwt_bearer(self, auth_manager):
        """通过 Bearer 头传递 JWT 认证成功."""
        token = auth_manager.generate_jwt("user-1")
        headers = {"Authorization": f"Bearer {token}"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is True
        assert err is None

    def test_jwt_token_endpoint(self, auth_manager):
        """POST /auth/token 用 API Key 换取 JWT."""
        headers = {"X-API-Key": "test-key-1"}
        status, body = auth_manager.create_token_response(headers, {})
        assert status == 200
        assert "token" in body
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 3600
        # 验证返回的 token 有效
        assert auth_manager.verify_jwt(body["token"]) is not None

    def test_jwt_token_endpoint_via_bearer(self, auth_manager):
        """通过 Authorization: Bearer 头传 API Key 换取 JWT."""
        headers = {"Authorization": "Bearer test-key-1"}
        status, body = auth_manager.create_token_response(headers, {})
        assert status == 200
        assert "token" in body

    def test_jwt_token_endpoint_via_body(self, auth_manager):
        """通过请求体 api_key 字段换取 JWT."""
        status, body = auth_manager.create_token_response({}, {"api_key": "test-key-1"})
        assert status == 200
        assert "token" in body

    def test_jwt_token_endpoint_invalid_key(self, auth_manager):
        """无效 API Key 换取 JWT 返回 401."""
        headers = {"X-API-Key": "wrong-key"}
        status, body = auth_manager.create_token_response(headers, {})
        assert status == 401
        assert body["error"] == "Unauthorized"

    def test_jwt_token_endpoint_no_key(self, auth_manager):
        """无 API Key 换取 JWT 返回 400."""
        status, body = auth_manager.create_token_response({}, {})
        assert status == 400
        assert body["error"] == "Bad Request"

    def test_jwt_token_endpoint_no_jwt_secret(self):
        """未配置 jwt_secret 时 /auth/token 返回 503."""
        manager = AuthManager(AuthConfig(api_keys=["key"]))
        status, body = manager.create_token_response({"X-API-Key": "key"}, {})
        assert status == 503
        assert body["error"] == "Service Unavailable"


# ═══════════════════════════════════════════════════════════════
#  认证优先级测试
# ═══════════════════════════════════════════════════════════════


class TestAuthPriority:
    """认证优先级测试: JWT > API Key."""

    def test_jwt_takes_priority_over_api_key(self, auth_manager):
        """JWT 优先于 API Key 验证."""
        token = auth_manager.generate_jwt("test-key-1")
        # 同时提供 JWT 和无效 API Key，应通过 JWT
        headers = {
            "Authorization": f"Bearer {token}",
            "X-API-Key": "invalid-key",
        }
        ok, err = auth_manager.authenticate(headers)
        assert ok is True

    def test_invalid_jwt_falls_back_to_api_key(self, auth_manager):
        """JWT 无效时回退到 API Key 验证."""
        # 提供无效 JWT 但有效 API Key（通过 Bearer）
        headers = {"Authorization": "Bearer test-key-1"}
        ok, err = auth_manager.authenticate(headers)
        assert ok is True

    def test_both_invalid_fails(self, auth_manager):
        """JWT 和 API Key 都无效时认证失败."""
        headers = {
            "Authorization": "Bearer invalid-token",
            "X-API-Key": "invalid-key",
        }
        ok, err = auth_manager.authenticate(headers)
        assert ok is False


# ═══════════════════════════════════════════════════════════════
#  CORS 测试
# ═══════════════════════════════════════════════════════════════


class TestCORS:
    """CORS 支持测试."""

    def test_default_cors_headers(self, auth_manager):
        """默认 CORS 配置允许所有来源."""
        headers = auth_manager.get_cors_headers()
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "GET" in headers["Access-Control-Allow-Methods"]
        assert "POST" in headers["Access-Control-Allow-Methods"]
        assert "OPTIONS" in headers["Access-Control-Allow-Methods"]
        assert headers["Access-Control-Max-Age"] == "3600"

    def test_cors_headers_include_auth_headers(self, auth_manager):
        """CORS 允许头包含 Authorization 和 X-API-Key."""
        headers = auth_manager.get_cors_headers()
        assert "Authorization" in headers["Access-Control-Allow-Headers"]
        assert "X-API-Key" in headers["Access-Control-Allow-Headers"]
        assert "Content-Type" in headers["Access-Control-Allow-Headers"]

    def test_custom_cors_origins(self):
        """自定义 CORS origins."""
        config = AuthConfig(cors_origins=["https://example.com", "https://app.example.com"])
        manager = AuthManager(config)
        headers = manager.get_cors_headers("https://example.com")
        assert headers["Access-Control-Allow-Origin"] == "https://example.com"

    def test_cors_origin_not_in_list(self):
        """请求的 Origin 不在允许列表中."""
        config = AuthConfig(cors_origins=["https://example.com"])
        manager = AuthManager(config)
        headers = manager.get_cors_headers("https://evil.com")
        # 不在列表中时返回列表第一个
        assert headers["Access-Control-Allow-Origin"] == "https://example.com"

    def test_cors_wildcard_overrides_specific(self):
        """配置了 * 时始终返回 *."""
        config = AuthConfig(cors_origins=["*", "https://example.com"])
        manager = AuthManager(config)
        headers = manager.get_cors_headers("https://example.com")
        assert headers["Access-Control-Allow-Origin"] == "*"

    def test_cors_no_origin_header(self, auth_manager):
        """无 Origin 头时仍返回 CORS 头."""
        headers = auth_manager.get_cors_headers(None)
        assert "Access-Control-Allow-Origin" in headers


# ═══════════════════════════════════════════════════════════════
#  端点豁免测试
# ═══════════════════════════════════════════════════════════════


class TestExemptEndpoints:
    """端点豁免测试."""

    def test_health_is_exempt(self, auth_manager):
        """GET /health 豁免认证."""
        assert auth_manager.is_exempt("GET", "/health") is True

    def test_auth_token_is_exempt(self, auth_manager):
        """POST /auth/token 豁免认证."""
        assert auth_manager.is_exempt("POST", "/auth/token") is True

    def test_chat_not_exempt(self, auth_manager):
        """POST /chat 不豁免."""
        assert auth_manager.is_exempt("POST", "/chat") is False

    def test_memory_not_exempt(self, auth_manager):
        """GET /memory 不豁免."""
        assert auth_manager.is_exempt("GET", "/memory") is False

    def test_health_post_not_exempt(self, auth_manager):
        """POST /health 不豁免（只有 GET 豁免）."""
        assert auth_manager.is_exempt("POST", "/health") is False

    def test_health_accessible_without_auth(self, auth_server):
        """带认证的服务器，/health 无需凭证即可访问."""
        import asyncio
        status, body = asyncio.run(auth_server.handle_request("GET", "/health"))
        assert status == 200
        assert body["status"] == "ok"

    def test_auth_token_accessible_without_auth(self, auth_server):
        """带认证的服务器，/auth/token 无需凭证即可访问."""
        import asyncio
        # 无 API Key → 400（可访问但不完整），不是 401
        status, body = asyncio.run(
            auth_server.handle_request("POST", "/auth/token", {}, {})
        )
        assert status == 400  # 缺少 API Key，不是 401 认证错误


# ═══════════════════════════════════════════════════════════════
#  错误响应格式测试
# ═══════════════════════════════════════════════════════════════


class TestErrorResponseFormat:
    """认证错误响应格式测试."""

    def test_401_has_error_and_message(self, auth_manager):
        """401 响应包含 error 和 message 字段."""
        ok, err = auth_manager.authenticate({})
        assert err is not None
        assert "error" in err
        assert "message" in err
        assert err["error"] == "Unauthorized"

    def test_401_message_is_descriptive(self, auth_manager):
        """401 错误消息具有描述性."""
        ok, err = auth_manager.authenticate({})
        assert err is not None
        assert len(err["message"]) > 0

    def test_server_returns_401_without_credentials(self, auth_server):
        """带认证的服务器，无凭证访问受保护端点返回 401."""
        import asyncio
        status, body = asyncio.run(
            auth_server.handle_request("GET", "/tools", headers={})
        )
        assert status == 401
        assert body["error"] == "Unauthorized"

    def test_server_returns_401_with_invalid_key(self, auth_server):
        """带认证的服务器，无效 key 返回 401."""
        import asyncio
        status, body = asyncio.run(
            auth_server.handle_request(
                "GET", "/tools", headers={"X-API-Key": "bad-key"}
            )
        )
        assert status == 401


# ═══════════════════════════════════════════════════════════════
#  服务器集成测试
# ═══════════════════════════════════════════════════════════════


class TestServerAuthIntegration:
    """服务器认证集成测试."""

    @pytest.mark.asyncio
    async def test_no_auth_server_allows_all(self, no_auth_server):
        """无认证配置的服务器允许所有请求（向后兼容）."""
        status, body = await no_auth_server.handle_request("GET", "/tools")
        assert status == 200

    @pytest.mark.asyncio
    async def test_auth_server_blocks_without_credentials(self, auth_server):
        """带认证的服务器拒绝无凭证请求."""
        status, body = await auth_server.handle_request("GET", "/tools")
        assert status == 401

    @pytest.mark.asyncio
    async def test_auth_server_allows_with_api_key(self, auth_server):
        """带认证的服务器，有效 API Key 放行."""
        status, body = await auth_server.handle_request(
            "GET", "/tools", headers={"X-API-Key": "test-key-1"}
        )
        assert status == 200

    @pytest.mark.asyncio
    async def test_auth_server_allows_with_jwt(self, auth_server):
        """带认证的服务器，有效 JWT 放行."""
        token = auth_server.auth_manager.generate_jwt("test-key-1")
        status, body = await auth_server.handle_request(
            "GET", "/tools", headers={"Authorization": f"Bearer {token}"}
        )
        assert status == 200

    @pytest.mark.asyncio
    async def test_auth_server_chat_with_api_key(self, auth_server):
        """带认证的服务器，用 API Key 访问 /chat."""
        status, body = await auth_server.handle_request(
            "POST", "/chat",
            body={"message": "Hi"},
            headers={"X-API-Key": "test-key-1"},
        )
        assert status == 200
        assert body["reply"] == "Hello from Suyi!"

    @pytest.mark.asyncio
    async def test_auth_server_chat_without_credentials(self, auth_server):
        """带认证的服务器，无凭证访问 /chat 返回 401."""
        status, body = await auth_server.handle_request(
            "POST", "/chat", body={"message": "Hi"}
        )
        assert status == 401

    @pytest.mark.asyncio
    async def test_auth_token_endpoint_via_server(self, auth_server):
        """通过服务器 /auth/token 端点换取 JWT."""
        status, body = await auth_server.handle_request(
            "POST", "/auth/token",
            body={},
            headers={"X-API-Key": "test-key-1"},
        )
        assert status == 200
        assert "token" in body

    @pytest.mark.asyncio
    async def test_disabled_auth_allows_all(self, mock_llm, tmp_path):
        """auth_enabled=False 时所有请求放行."""
        config = AuthConfig(auth_enabled=False, api_keys=["key"])
        server = SuyiServer(
            llm=mock_llm,
            auth_config=config,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "m")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "d")),
        )
        status, body = await server.handle_request("GET", "/tools")
        assert status == 200

    @pytest.mark.asyncio
    async def test_jwt_then_use_token(self, auth_server):
        """先获取 JWT，再用 JWT 访问受保护端点."""
        # 步骤 1: 获取 JWT
        status, token_body = await auth_server.handle_request(
            "POST", "/auth/token",
            body={},
            headers={"X-API-Key": "test-key-1"},
        )
        assert status == 200
        token = token_body["token"]

        # 步骤 2: 用 JWT 访问 /tools
        status, body = await auth_server.handle_request(
            "GET", "/tools",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200

    @pytest.mark.asyncio
    async def test_all_endpoints_require_auth(self, auth_server):
        """所有非豁免端点都需要认证."""
        protected_endpoints = [
            ("POST", "/chat", {"message": "hi"}),
            ("GET", "/memory", None),
            ("GET", "/tools", None),
            ("GET", "/sessions", None),
        ]
        for method, path, body in protected_endpoints:
            status, _ = await auth_server.handle_request(
                method, path, body=body, headers={}
            )
            assert status == 401, f"{method} {path} 应该返回 401"


# ═══════════════════════════════════════════════════════════════
#  实时 HTTP 服务器测试
# ═══════════════════════════════════════════════════════════════


class TestLiveServerWithAuth:
    """实时 HTTP 服务器认证测试."""

    def _start_server(self, server, port=0):
        """启动服务器并返回 (httpd, port)."""
        server_ref = server

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _headers_to_dict(self):
                return {k: v for k, v in self.headers.items()}

            def _set_cors_headers(self):
                origin = self.headers.get("Origin")
                cors = server_ref.auth_manager.get_cors_headers(origin)
                for k, v in cors.items():
                    self.send_header(k, v)

            def _send_json(self, status, payload):
                body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body_bytes)

            def _read_body(self):
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {}

            def do_OPTIONS(self):
                self.send_response(204)
                self._set_cors_headers()
                self.end_headers()

            def do_GET(self):
                import asyncio
                status, payload = asyncio.run(
                    server_ref.handle_request("GET", self.path, headers=self._headers_to_dict())
                )
                self._send_json(status, payload)

            def do_POST(self):
                import asyncio
                body = self._read_body()
                status, payload = asyncio.run(
                    server_ref.handle_request("POST", self.path, body, self._headers_to_dict())
                )
                self._send_json(status, payload)

        httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        actual_port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd, actual_port

    def test_live_health_no_auth_needed(self, auth_server):
        """实时服务器 /health 无需认证."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["status"] == "ok"
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_protected_without_key_401(self, auth_server):
        """实时服务器，无凭证访问受保护端点返回 401."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/tools"
            try:
                urllib.request.urlopen(url, timeout=5)
                assert False, "应该抛出 HTTPError"
            except urllib.error.HTTPError as e:
                assert e.code == 401
                data = json.loads(e.read())
                assert data["error"] == "Unauthorized"
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_protected_with_api_key(self, auth_server):
        """实时服务器，带 API Key 访问受保护端点成功."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/tools"
            req = urllib.request.Request(url, headers={"X-API-Key": "test-key-1"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert "tools" in data
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_auth_token_endpoint(self, auth_server):
        """实时服务器 /auth/token 换取 JWT."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/auth/token"
            req = urllib.request.Request(
                url,
                data=json.dumps({}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": "test-key-1",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert "token" in data
                assert data["token_type"] == "Bearer"
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_cors_headers(self, auth_server):
        """实时服务器响应包含 CORS 头."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.headers.get("Access-Control-Allow-Origin") == "*"
                assert "GET" in resp.headers.get("Access-Control-Allow-Methods", "")
                assert "3600" == resp.headers.get("Access-Control-Max-Age")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_options_preflight(self, auth_server):
        """实时服务器 OPTIONS 预检请求返回 204 + CORS 头."""
        httpd, port = self._start_server(auth_server)
        try:
            url = f"http://127.0.0.1:{port}/chat"
            req = urllib.request.Request(url, method="OPTIONS")
            try:
                resp = urllib.request.urlopen(req, timeout=5)
                assert resp.status == 204
            except urllib.error.HTTPError as e:
                # 某些 Python 版本对 204 可能处理不同
                assert e.code in (204, 200)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_jwt_flow(self, auth_server):
        """实时服务器完整 JWT 流程: 换 token → 用 token 访问."""
        httpd, port = self._start_server(auth_server)
        try:
            # 步骤 1: 换取 JWT
            url = f"http://127.0.0.1:{port}/auth/token"
            req = urllib.request.Request(
                url,
                data=json.dumps({}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": "test-key-2",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                token_data = json.loads(resp.read())
                token = token_data["token"]

            # 步骤 2: 用 JWT 访问 /tools
            url2 = f"http://127.0.0.1:{port}/tools"
            req2 = urllib.request.Request(
                url2, headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req2, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert "tools" in data
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_custom_cors_origins(self, mock_llm, tmp_path):
        """实时服务器自定义 CORS origins."""
        config = AuthConfig(
            api_keys=["key"],
            jwt_secret="secret",
            cors_origins=["https://myapp.com"],
        )
        server = SuyiServer(
            llm=mock_llm,
            auth_config=config,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "m")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "d")),
        )
        httpd, port = self._start_server(server)
        try:
            url = f"http://127.0.0.1:{port}/health"
            req = urllib.request.Request(
                url, headers={"Origin": "https://myapp.com"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                origin = resp.headers.get("Access-Control-Allow-Origin")
                assert origin == "https://myapp.com"
        finally:
            httpd.shutdown()
            httpd.server_close()


# ═══════════════════════════════════════════════════════════════
#  请求头提取测试
# ═══════════════════════════════════════════════════════════════


class TestHeaderExtraction:
    """请求头提取测试."""

    def test_extract_bearer_token(self, auth_manager):
        """从 Authorization 头提取 Bearer token."""
        headers = {"Authorization": "Bearer my-token"}
        assert auth_manager.extract_bearer_token(headers) == "my-token"

    def test_extract_bearer_token_lowercase(self, auth_manager):
        """小写 authorization 头也能提取."""
        headers = {"authorization": "Bearer my-token"}
        assert auth_manager.extract_bearer_token(headers) == "my-token"

    def test_extract_bearer_token_no_prefix(self, auth_manager):
        """无 Bearer 前缀返回 None."""
        headers = {"Authorization": "my-token"}
        assert auth_manager.extract_bearer_token(headers) is None

    def test_extract_bearer_token_missing(self, auth_manager):
        """无 Authorization 头返回 None."""
        assert auth_manager.extract_bearer_token({}) is None

    def test_extract_api_key_header(self, auth_manager):
        """从 X-API-Key 头提取 API Key."""
        headers = {"X-API-Key": "my-key"}
        assert auth_manager.extract_api_key_header(headers) == "my-key"

    def test_extract_api_key_header_lowercase(self, auth_manager):
        """小写 x-api-key 头也能提取."""
        headers = {"x-api-key": "my-key"}
        assert auth_manager.extract_api_key_header(headers) == "my-key"

    def test_extract_api_key_header_missing(self, auth_manager):
        """无 X-API-Key 头返回 None."""
        assert auth_manager.extract_api_key_header({}) is None

    def test_extract_bearer_token_with_spaces(self, auth_manager):
        """Bearer token 前后有空格时正确提取."""
        headers = {"Authorization": "Bearer  my-token  "}
        assert auth_manager.extract_bearer_token(headers) == "my-token"
