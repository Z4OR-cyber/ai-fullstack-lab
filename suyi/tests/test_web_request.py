"""WebRequestTool 测试.

覆盖范围：
- CRUD 各方法（GET / POST / PUT / DELETE）
- 自定义 headers / query params
- 超时处理
- SSRF 防护（内网 IP 段拦截）
- 风险分级（localhost → auto，内网 → block，域名 → confirm）
- 错误处理（无 URL、无效方法、连接失败）
- 大响应截断
- 签名键 / schema 生成
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from suyi.tools import WebRequestTool, ToolContext
from suyi.tools.web_request import (
    check_ssrf,
    _is_internal_ip,
    _is_localhost,
    MAX_BODY_LENGTH,
)


# ═══════════════════════════════════════════════════════════════
#  本地 HTTP 测试服务器
# ═══════════════════════════════════════════════════════════════


class _TestHandler(BaseHTTPRequestHandler):
    """测试用 HTTP 请求处理器.

    支持记录请求方法、路径、headers、body，并返回可预测的响应.
    """

    # 类级别变量，用于跨请求记录数据
    last_request = None

    def _handle(self):
        # 读取请求体
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""

        _TestHandler.last_request = {
            "method": self.command,
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        }

        # 根据路径返回不同响应
        if self.path.startswith("/echo"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("X-Custom-Header", "test-value")
            self.end_headers()
            self.wfile.write(body.encode("utf-8") if body else b"GET OK")
        elif self.path.startswith("/json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"method": self.command, "body": body}).encode())
        elif self.path.startswith("/large"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            # 返回超过 MAX_BODY_LENGTH 的内容
            self.wfile.write(b"A" * (MAX_BODY_LENGTH + 5000))
        elif self.path.startswith("/created"):
            self.send_response(201)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Created")
        elif self.path.startswith("/slow"):
            import time as _time
            _time.sleep(5)  # 模拟慢响应
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"slow")
        elif self.path.startswith("/notfound"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"{self.command} response".encode())

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def log_message(self, format, *args):
        pass  # 静默日志


@pytest.fixture
def local_server():
    """启动本地 HTTP 测试服务器，返回 (base_url, server)."""
    _TestHandler.last_request = None
    server = HTTPServer(("127.0.0.1", 0), _TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def ctx():
    """工具执行上下文."""
    return ToolContext()


@pytest.fixture
def tool():
    """WebRequestTool 实例（关闭 DNS 解析以避免网络依赖）."""
    return WebRequestTool(resolve_dns=False)


# ═══════════════════════════════════════════════════════════════
#  基础属性测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestToolBasic:
    """基础属性测试."""

    def test_name(self, tool):
        """工具名称为 web_request."""
        assert tool.name == "web_request"

    def test_description(self, tool):
        """工具描述非空且包含关键信息."""
        desc = tool.description
        assert "HTTP" in desc or "http" in desc.lower()
        assert "url" in desc.lower()

    def test_default_permission(self, tool):
        """默认权限为 confirm."""
        assert tool.default_permission == "confirm"

    def test_parameters(self, tool):
        """参数列表包含 url, method, headers, body, timeout, params."""
        param_names = [p.name for p in tool.parameters]
        assert "url" in param_names
        assert "method" in param_names
        assert "headers" in param_names
        assert "body" in param_names
        assert "timeout" in param_names
        assert "params" in param_names

    def test_url_required(self, tool):
        """url 参数为必填."""
        url_param = [p for p in tool.parameters if p.name == "url"][0]
        assert url_param.required is True

    def test_method_default_get(self, tool):
        """method 默认值为 GET."""
        method_param = [p for p in tool.parameters if p.name == "method"][0]
        assert method_param.default == "GET"

    def test_timeout_default_30(self, tool):
        """timeout 默认值为 30."""
        timeout_param = [p for p in tool.parameters if p.name == "timeout"][0]
        assert timeout_param.default == 30

    def test_to_schema(self, tool):
        """schema 生成正确."""
        schema = tool.to_schema()
        assert schema["name"] == "web_request"
        assert "parameters" in schema
        assert "url" in schema["parameters"]["properties"]


# ═══════════════════════════════════════════════════════════════
#  HTTP 方法测试（使用本地服务器）
# ═══════════════════════════════════════════════════════════════


class TestWebRequestMethods:
    """HTTP 方法测试."""

    def test_get_request(self, tool, ctx, local_server):
        """GET 请求返回 200 和正确 body."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        assert result.output["status_code"] == 200

    def test_post_request(self, tool, ctx, local_server):
        """POST 请求发送 body 并返回响应."""
        result = tool.execute(
            {"url": f"{local_server}/echo", "method": "POST", "body": "post data"},
            ctx,
        )
        assert result.success is True
        assert result.output["status_code"] == 200

    def test_put_request(self, tool, ctx, local_server):
        """PUT 请求正常执行."""
        result = tool.execute(
            {"url": f"{local_server}/echo", "method": "PUT", "body": "put data"},
            ctx,
        )
        assert result.success is True
        assert result.output["status_code"] == 200

    def test_delete_request(self, tool, ctx, local_server):
        """DELETE 请求正常执行."""
        result = tool.execute(
            {"url": f"{local_server}/echo", "method": "DELETE"},
            ctx,
        )
        assert result.success is True
        assert result.output["status_code"] == 200

    def test_default_method_is_get(self, tool, ctx, local_server):
        """不指定 method 时默认使用 GET."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        assert _TestHandler.last_request["method"] == "GET"

    def test_post_body_echoed(self, tool, ctx, local_server):
        """POST 请求的 body 被服务器正确接收."""
        result = tool.execute(
            {"url": f"{local_server}/echo", "method": "POST", "body": "hello world"},
            ctx,
        )
        assert result.success is True
        assert result.output["body"] == "hello world"

    def test_get_with_params(self, tool, ctx, local_server):
        """GET 请求带 query params."""
        result = tool.execute(
            {
                "url": f"{local_server}/echo",
                "params": {"key": "value", "num": "42"},
            },
            ctx,
        )
        assert result.success is True
        # 服务器记录的路径应包含 query string
        assert "key=value" in _TestHandler.last_request["path"]

    def test_custom_headers_sent(self, tool, ctx, local_server):
        """自定义 headers 被发送到服务器."""
        result = tool.execute(
            {
                "url": f"{local_server}/echo",
                "headers": {"X-Test-Header": "my-value"},
            },
            ctx,
        )
        assert result.success is True
        assert _TestHandler.last_request["headers"].get("X-Test-Header") == "my-value"

    def test_response_headers_captured(self, tool, ctx, local_server):
        """响应 headers 被正确捕获（httpx 会将 header 名小写化）."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        # httpx 将 header 名统一为小写
        assert "x-custom-header" in result.output["headers"]
        assert result.output["headers"]["x-custom-header"] == "test-value"

    def test_json_response(self, tool, ctx, local_server):
        """JSON 响应正确返回."""
        result = tool.execute({"url": f"{local_server}/json", "method": "POST", "body": "test"}, ctx)
        assert result.success is True
        data = json.loads(result.output["body"])
        assert data["method"] == "POST"

    def test_404_status_code(self, tool, ctx, local_server):
        """404 响应的 status_code 正确返回."""
        result = tool.execute({"url": f"{local_server}/notfound"}, ctx)
        assert result.success is True
        assert result.output["status_code"] == 404

    def test_201_status_code(self, tool, ctx, local_server):
        """201 响应的 status_code 正确返回."""
        result = tool.execute({"url": f"{local_server}/created"}, ctx)
        assert result.success is True
        assert result.output["status_code"] == 201


# ═══════════════════════════════════════════════════════════════
#  响应字段测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestResponseFields:
    """响应字段测试."""

    def test_elapsed_ms_present(self, tool, ctx, local_server):
        """响应包含 elapsed_ms 字段."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        assert "elapsed_ms" in result.output
        assert isinstance(result.output["elapsed_ms"], int)
        assert result.output["elapsed_ms"] >= 0

    def test_truncated_field_present(self, tool, ctx, local_server):
        """响应包含 truncated 字段."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        assert "truncated" in result.output
        assert result.output["truncated"] is False

    def test_body_truncation(self, tool, ctx, local_server):
        """超过 MAX_BODY_LENGTH 的响应被截断."""
        result = tool.execute({"url": f"{local_server}/large"}, ctx)
        assert result.success is True
        assert result.output["truncated"] is True
        assert len(result.output["body"]) == MAX_BODY_LENGTH

    def test_body_not_truncated_for_small(self, tool, ctx, local_server):
        """小响应不被截断."""
        result = tool.execute({"url": f"{local_server}/echo"}, ctx)
        assert result.success is True
        assert result.output["truncated"] is False


# ═══════════════════════════════════════════════════════════════
#  超时测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestTimeout:
    """超时测试."""

    def test_timeout_error(self, tool, ctx, local_server):
        """超时返回失败结果."""
        result = tool.execute(
            {"url": f"{local_server}/slow", "timeout": 1},
            ctx,
        )
        assert result.success is False
        assert "超时" in result.error

    def test_timeout_metadata_elapsed(self, tool, ctx, local_server):
        """超时结果包含 elapsed_ms 元数据."""
        result = tool.execute(
            {"url": f"{local_server}/slow", "timeout": 1},
            ctx,
        )
        assert result.success is False
        assert "elapsed_ms" in result.metadata


# ═══════════════════════════════════════════════════════════════
#  SSRF 防护测试
# ═══════════════════════════════════════════════════════════════


class TestSSRFProtection:
    """SSRF 防护测试."""

    def test_is_internal_ip_10(self):
        """10.x.x.x 是内网 IP."""
        assert _is_internal_ip("10.0.0.1") is True

    def test_is_internal_ip_192_168(self):
        """192.168.x.x 是内网 IP."""
        assert _is_internal_ip("192.168.1.1") is True

    def test_is_internal_ip_172_16(self):
        """172.16.x.x 是内网 IP."""
        assert _is_internal_ip("172.16.0.1") is True

    def test_is_internal_ip_172_31(self):
        """172.31.x.x 是内网 IP（上界）."""
        assert _is_internal_ip("172.31.255.255") is True

    def test_is_internal_ip_172_32_not_internal(self):
        """172.32.x.x 不是内网 IP（超出范围）."""
        assert _is_internal_ip("172.32.0.1") is False

    def test_is_internal_ip_public(self):
        """公网 IP 不是内网."""
        assert _is_internal_ip("8.8.8.8") is False

    def test_is_internal_ip_invalid(self):
        """无效 IP 字符串返回 False."""
        assert _is_internal_ip("not-an-ip") is False

    def test_check_ssrf_blocks_192_168(self, tool):
        """check_ssrf 阻止 192.168.x.x."""
        blocked, reason = check_ssrf("http://192.168.1.1/test", resolve_dns=False)
        assert blocked is True
        assert "内网" in reason

    def test_check_ssrf_blocks_10(self, tool):
        """check_ssrf 阻止 10.x.x.x."""
        blocked, _ = check_ssrf("http://10.0.0.1/test", resolve_dns=False)
        assert blocked is True

    def test_check_ssrf_allows_localhost(self, tool):
        """check_ssrf 允许 localhost."""
        blocked, _ = check_ssrf("http://127.0.0.1/test", resolve_dns=False)
        assert blocked is False

    def test_check_ssrf_allows_public_ip(self, tool):
        """check_ssrf 允许公网 IP."""
        blocked, _ = check_ssrf("http://8.8.8.8/test", resolve_dns=False)
        assert blocked is False

    def test_execute_blocks_internal_ip_192(self, tool, ctx):
        """execute 拦截 192.168.x.x 请求."""
        result = tool.execute({"url": "http://192.168.1.1/secret"}, ctx)
        assert result.success is False
        assert "SSRF" in result.error

    def test_execute_blocks_internal_ip_10(self, tool, ctx):
        """execute 拦截 10.x.x.x 请求."""
        result = tool.execute({"url": "http://10.0.0.1/admin"}, ctx)
        assert result.success is False
        assert "SSRF" in result.error

    def test_execute_blocks_internal_ip_172(self, tool, ctx):
        """execute 拦截 172.16.x.x 请求."""
        result = tool.execute({"url": "http://172.16.0.1/internal"}, ctx)
        assert result.success is False
        assert "SSRF" in result.error

    def test_execute_blocks_internal_ip_172_31(self, tool, ctx):
        """execute 拦截 172.31.x.x 请求（上界）."""
        result = tool.execute({"url": "http://172.31.255.255/internal"}, ctx)
        assert result.success is False
        assert "SSRF" in result.error


# ═══════════════════════════════════════════════════════════════
#  风险分级测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestRiskAssessment:
    """风险分级测试."""

    def test_risk_localhost_auto(self, tool):
        """localhost → auto."""
        risk = tool.assess_risk({"url": "http://localhost:8080/test"}, ToolContext())
        assert risk == "auto"

    def test_risk_127_auto(self, tool):
        """127.0.0.1 → auto."""
        risk = tool.assess_risk({"url": "http://127.0.0.1:8080/test"}, ToolContext())
        assert risk == "auto"

    def test_risk_internal_192_block(self, tool):
        """192.168.x.x → block."""
        risk = tool.assess_risk({"url": "http://192.168.1.1/test"}, ToolContext())
        assert risk == "block"

    def test_risk_internal_10_block(self, tool):
        """10.x.x.x → block."""
        risk = tool.assess_risk({"url": "http://10.0.0.1/test"}, ToolContext())
        assert risk == "block"

    def test_risk_internal_172_block(self, tool):
        """172.16.x.x → block."""
        risk = tool.assess_risk({"url": "http://172.16.0.1/test"}, ToolContext())
        assert risk == "block"

    def test_risk_public_ip_none(self, tool):
        """公网 IP → None（回退到 confirm）."""
        risk = tool.assess_risk({"url": "http://8.8.8.8/test"}, ToolContext())
        assert risk is None

    def test_risk_domain_none(self, tool):
        """域名 → None（回退到 confirm）."""
        risk = tool.assess_risk({"url": "https://example.com/test"}, ToolContext())
        assert risk is None

    def test_risk_no_url_none(self, tool):
        """无 URL → None."""
        risk = tool.assess_risk({}, ToolContext())
        assert risk is None

    def test_risk_no_hostname_block(self, tool):
        """无主机名的 URL → block."""
        risk = tool.assess_risk({"url": "not-a-url"}, ToolContext())
        assert risk == "block"


# ═══════════════════════════════════════════════════════════════
#  错误处理测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestErrors:
    """错误处理测试."""

    def test_no_url_error(self, tool, ctx):
        """无 URL 返回错误."""
        result = tool.execute({}, ctx)
        assert result.success is False
        assert "URL" in result.error

    def test_empty_url_error(self, tool, ctx):
        """空 URL 返回错误."""
        result = tool.execute({"url": ""}, ctx)
        assert result.success is False

    def test_invalid_method_error(self, tool, ctx, local_server):
        """不支持的 HTTP 方法返回错误."""
        result = tool.execute(
            {"url": f"{local_server}/echo", "method": "INVALID"},
            ctx,
        )
        assert result.success is False
        assert "不支持" in result.error or "INVALID" in result.error

    def test_connection_error(self, tool, ctx):
        """连接不存在的端口返回错误."""
        # 使用一个几乎不可能开放的端口
        result = tool.execute(
            {"url": "http://127.0.0.1:19999/test", "timeout": 2},
            ctx,
        )
        assert result.success is False

    def test_invalid_url_error(self, tool, ctx):
        """无效 URL 格式返回错误."""
        result = tool.execute(
            {"url": "http://192.168.1.1/test", "method": "GET"},
            ctx,
        )
        assert result.success is False
        assert "SSRF" in result.error


# ═══════════════════════════════════════════════════════════════
#  签名键测试
# ═══════════════════════════════════════════════════════════════


class TestWebRequestSignature:
    """签名键测试."""

    def test_signature_key_normal_url(self, tool):
        """正常 URL 的签名键为 scheme://hostname."""
        key = tool.get_signature_key({"url": "https://api.example.com/v1/users"})
        assert key == "https://api.example.com"

    def test_signature_key_empty_url(self, tool):
        """空 URL 的签名键为空字符串."""
        key = tool.get_signature_key({"url": ""})
        assert key == ""

    def test_signature_key_no_url(self, tool):
        """无 url 字段的签名键为空字符串."""
        key = tool.get_signature_key({})
        assert key == ""

    def test_signature_key_with_port(self, tool):
        """带端口的 URL 签名键不含端口."""
        key = tool.get_signature_key({"url": "http://localhost:8080/test"})
        assert key == "http://localhost"
