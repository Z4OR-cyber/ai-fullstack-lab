"""Web 请求工具 — WebRequestTool.

基于 httpx 实现 HTTP 请求，支持 GET/POST/PUT/DELETE 方法.
内置 SSRF 防护，禁止访问内网 IP 段（10.x / 172.16-31.x / 192.168.x）.

设计原则：
- **权限内聚**：工具自描述风险画像（localhost → auto，内网 IP → block，其他 → confirm）.
- **SSRF 防护**：在 execute 和 assess_risk 两层做内网 IP 检测，纵深防御.
- **响应截断**：body 截断到 10000 字符，防止超长响应撑爆上下文.
"""

import ipaddress
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .base import AgentTool, ToolContext, ToolParameter, ToolResult


# ═══════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════

# 响应体最大长度（字符），防止超长响应撑爆上下文
MAX_BODY_LENGTH = 10000

# 支持的 HTTP 方法
SUPPORTED_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD")

# SSRF 防护：内网 IP 段（CIDR 表示法）
INTERNAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),       # 10.x.x.x
    ipaddress.ip_network("172.16.0.0/12"),    # 172.16.x.x - 172.31.x.x
    ipaddress.ip_network("192.168.0.0/16"),   # 192.168.x.x
]

# localhost 标识集合（允许访问本机服务）
LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


# ═══════════════════════════════════════════════════════════════
#  SSRF 防护辅助函数
# ═══════════════════════════════════════════════════════════════


def _is_internal_ip(ip_str: str) -> bool:
    """检查 IP 地址是否在内部网络段（SSRF 防护）.

    Args:
        ip_str: IP 地址字符串（IPv4 或 IPv6）.

    Returns:
        是否在 10.x / 172.16-31.x / 192.168.x 内网段.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for net in INTERNAL_NETWORKS:
        if ip in net:
            return True
    return False


def _is_localhost(hostname: str) -> bool:
    """检查主机名是否是 localhost.

    Args:
        hostname: 主机名（已小写化处理）.

    Returns:
        是否是 localhost / 127.0.0.1 / ::1 / 0.0.0.0.
    """
    return hostname.lower() in LOCALHOST_NAMES


def check_ssrf(url: str, resolve_dns: bool = True) -> Tuple[bool, str]:
    """检查 URL 是否存在 SSRF 风险.

    检查逻辑：
    1. 解析 URL 提取主机名.
    2. localhost → 允许（本机服务）.
    3. IP 字面量在内网段 → 阻止.
    4. 域名 DNS 解析到内网 IP → 阻止（可选）.

    Args:
        url: 待检查的 URL.
        resolve_dns: 是否做 DNS 解析检查（测试时可关闭以避免网络依赖）.

    Returns:
        (is_blocked, reason): 是否阻止及原因. is_blocked=True 表示存在
        SSRF 风险，应拒绝请求.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True, "无效的 URL"

    hostname = parsed.hostname
    if not hostname:
        return True, "URL 缺少主机名"

    # localhost 允许访问（本机服务）
    if _is_localhost(hostname):
        return False, ""

    # 检查 IP 字面量
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_internal_ip(str(ip)):
            return True, f"禁止访问内网 IP: {hostname}"
        # 公网 IP 字面量，允许
        return False, ""
    except ValueError:
        pass  # 不是 IP 字面量，是域名

    # DNS 解析检查（可选，测试时可关闭）
    if resolve_dns:
        try:
            addrs = socket.getaddrinfo(hostname, None)
            for addr in addrs:
                ip_str = addr[4][0]
                # 处理 IPv6 zone index（如 fe80::1%eth0）
                if "%" in ip_str:
                    ip_str = ip_str.split("%")[0]
                if _is_internal_ip(ip_str):
                    return True, f"域名 {hostname} 解析到内网 IP: {ip_str}"
        except socket.gaierror:
            # DNS 解析失败，不阻止（execute 时 httpx 会自然报错）
            pass

    return False, ""


# ═══════════════════════════════════════════════════════════════
#  WebRequestTool
# ═══════════════════════════════════════════════════════════════


class WebRequestTool(AgentTool):
    """HTTP 请求工具.

    基于 httpx 实现，支持 GET/POST/PUT/DELETE/PATCH/HEAD 方法.
    内置 SSRF 防护，禁止访问内网 IP 段.

    **风险分级**：
    - localhost / 127.0.0.1 → ``'auto'``（本机服务，低风险）.
    - 内网 IP（10.x / 172.16-31.x / 192.168.x）→ ``'block'``（SSRF 防护）.
    - 其他域名 / 公网 IP → ``'confirm'``（默认，需用户确认）.

    **返回结构**::

        {
            "status_code": 200,
            "headers": {"Content-Type": "text/plain", ...},
            "body": "响应正文（截断到 10000 字符）",
            "elapsed_ms": 123,
            "truncated": False
        }

    Attributes:
        _transport: 可选的 httpx transport（测试时注入 MockTransport）.
        _resolve_dns: 是否在 SSRF 检查中做 DNS 解析（默认 True）.
    """

    def __init__(self, transport: Optional[httpx.BaseTransport] = None,
                 resolve_dns: bool = True):
        """
        Args:
            transport: 可选的 httpx transport，用于测试时注入 MockTransport.
            resolve_dns: 是否在 SSRF 检查中做 DNS 解析. 测试时可设为 False
                以避免网络依赖.
        """
        self._transport = transport
        self._resolve_dns = resolve_dns

    @property
    def name(self) -> str:
        return "web_request"

    @property
    def description(self) -> str:
        return (
            "Make an HTTP request to a URL. Supports GET/POST/PUT/DELETE. "
            "Input: {'url': str (required), 'method': str (default GET), "
            "'headers': dict, 'body': str, 'timeout': int (default 30), "
            "'params': dict}"
        )

    @property
    def default_permission(self) -> str:
        return "confirm"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="The URL to send the request to.",
                required=True,
            ),
            ToolParameter(
                name="method",
                type="string",
                description="HTTP method: GET, POST, PUT, or DELETE. Default: GET.",
                required=False,
                default="GET",
            ),
            ToolParameter(
                name="headers",
                type="object",
                description="Request headers as a key-value dict.",
                required=False,
                default={},
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Request body content (for POST/PUT).",
                required=False,
                default="",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Request timeout in seconds. Default: 30.",
                required=False,
                default=30,
            ),
            ToolParameter(
                name="params",
                type="object",
                description="Query parameters as a key-value dict.",
                required=False,
                default={},
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """执行 HTTP 请求.

        Args:
            input_data: 包含 ``url``（必填）、``method``、``headers``、
                ``body``、``timeout``、``params``（均可选）.
            context: 执行上下文.

        Returns:
            包含 ``status_code``、``headers``、``body``、``elapsed_ms``、
            ``truncated`` 的 ToolResult.
        """
        url = input_data.get("url", "")
        method = input_data.get("method", "GET").upper()
        headers = input_data.get("headers") or {}
        body = input_data.get("body", "")
        timeout = input_data.get("timeout", 30)
        params = input_data.get("params") or {}

        # 参数校验
        if not url:
            return ToolResult(success=False, error="未提供 URL")

        if method not in SUPPORTED_METHODS:
            return ToolResult(
                success=False,
                error=f"不支持的 HTTP 方法: {method}（支持: {', '.join(SUPPORTED_METHODS)}）",
            )

        # SSRF 防护检查
        blocked, reason = check_ssrf(url, resolve_dns=self._resolve_dns)
        if blocked:
            return ToolResult(success=False, error=f"SSRF 防护拦截: {reason}")

        # 执行请求
        start = time.perf_counter()
        try:
            client_kwargs: Dict[str, Any] = {"timeout": timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport

            with httpx.Client(**client_kwargs) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers if headers else None,
                    content=body if body else None,
                    params=params if params else None,
                )

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            # 截断响应体
            resp_body = response.text
            truncated = len(resp_body) > MAX_BODY_LENGTH
            if truncated:
                resp_body = resp_body[:MAX_BODY_LENGTH]

            return ToolResult(
                success=True,
                output={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": resp_body,
                    "elapsed_ms": elapsed_ms,
                    "truncated": truncated,
                },
            )

        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                success=False,
                error=f"请求超时（{timeout}s）",
                metadata={"elapsed_ms": elapsed_ms},
            )
        except httpx.ConnectError as e:
            return ToolResult(success=False, error=f"连接失败: {e}")
        except httpx.InvalidURL as e:
            return ToolResult(success=False, error=f"无效 URL: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"请求失败: {e}")

    def assess_risk(
        self, input_data: dict, context: ToolContext
    ) -> Optional[str]:
        """运行时风险评估.

        - localhost / 127.0.0.1 → ``'auto'``（本机服务，安全）.
        - 内网 IP 字面量（10.x / 172.16-31.x / 192.168.x）→ ``'block'``（SSRF 防护）.
        - 其他域名 / 公网 IP → ``None``（回退到 ``default_permission = 'confirm'``）.

        注意：本方法只做 IP 字面量检查（快速、确定性），不做 DNS 解析.
        DNS 解析级别的 SSRF 防护在 ``execute`` 中执行（纵深防御）.

        Args:
            input_data: 包含 ``url`` 字段.
            context: 执行上下文.

        Returns:
            风险级别字符串或 ``None``.
        """
        url = input_data.get("url", "")
        if not url:
            return None

        try:
            parsed = urlparse(url)
        except Exception:
            return "block"

        hostname = parsed.hostname
        if not hostname:
            return "block"

        # localhost → auto
        if _is_localhost(hostname):
            return "auto"

        # 内网 IP 字面量 → block（SSRF 防护）
        try:
            ip = ipaddress.ip_address(hostname)
            if _is_internal_ip(str(ip)):
                return "block"
        except ValueError:
            pass  # 不是 IP 字面量

        # 其他域名 / 公网 IP → confirm（回退到默认权限）
        return None

    def get_signature_key(self, input_data: dict) -> str:
        """提取 URL 的 scheme + host 作为签名键.

        粒度到主机级别，避免对每个不同路径都单独授权.

        Examples:
            >>> tool = WebRequestTool()
            >>> tool.get_signature_key({"url": "https://api.example.com/v1/users"})
            'https://api.example.com'
        """
        url = input_data.get("url", "")
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            if parsed.hostname:
                return f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            pass
        return url[:100]
