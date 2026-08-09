"""
Suyi Web 认证与安全层 — API Key 认证、JWT Token 认证、CORS 支持.

纯 Python 标准库实现（hmac / hashlib / json / base64），不引入 PyJWT.

功能概述
--------

1. **API Key 认证**
   - 请求头 ``Authorization: Bearer <api_key>`` 或 ``X-API-Key: <key>``
   - 支持多个有效 key
   - ``/health`` 和 ``/auth/token`` 端点豁免

2. **JWT Token 认证**
   - 手动实现 HS256（HMAC-SHA256），不依赖 PyJWT
   - ``POST /auth/token``：用 API Key 换取 JWT（有效期 1 小时）
   - JWT payload: ``{sub, exp, iat}``
   - 验证：检查签名 + 过期时间

3. **CORS 支持**
   - OPTIONS 预检请求处理
   - 响应头可配置（默认 ``*``）

4. **认证优先级**
   - JWT > API Key，任一通过即可

使用示例::

    from suyi.web.auth import AuthConfig, AuthManager

    config = AuthConfig(
        api_keys=["my-secret-key"],
        jwt_secret="jwt-signing-secret",
        cors_origins=["https://example.com"],
    )
    auth = AuthManager(config)

    # 生成 JWT
    token = auth.generate_jwt("user-1")

    # 验证请求
    ok, err = auth.authenticate({"Authorization": f"Bearer {token}"})
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════════════════


@dataclass
class AuthConfig:
    """认证与安全配置.

    Attributes:
        auth_enabled: 是否启用认证（默认 True）.
                      若为 False，所有请求均放行.
        api_keys:     有效的 API Key 列表，支持多个.
        jwt_secret:   JWT 签名密钥（HS256），为空则不启用 JWT.
        jwt_expiry:   JWT 有效期（秒），默认 3600（1 小时）.
        cors_origins: 允许的 CORS 来源列表，默认 ``["*"]``.
    """

    auth_enabled: bool = True
    api_keys: list[str] = field(default_factory=list)
    jwt_secret: str = ""
    jwt_expiry: int = 3600
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


# ═══════════════════════════════════════════════════════════════
#  Base64URL 编解码工具（JWT 规范要求 URL-safe Base64，无填充）
# ═══════════════════════════════════════════════════════════════


def _b64url_encode(data: bytes) -> str:
    """Base64URL 编码（去除 ``=`` 填充）.

    Args:
        data: 原始字节数据.

    Returns:
        URL-safe Base64 字符串（无填充）.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Base64URL 解码（自动补 ``=`` 填充）.

    Args:
        data: URL-safe Base64 字符串（可能无填充）.

    Returns:
        原始字节数据.

    Raises:
        ValueError: 如果输入不是合法的 Base64.
    """
    # 补齐填充
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


# ═══════════════════════════════════════════════════════════════
#  认证管理器
# ═══════════════════════════════════════════════════════════════


class AuthManager:
    """认证管理器 — 统一处理 API Key、JWT 和 CORS.

    认证优先级: JWT > API Key，任一通过即可.
    豁免路径: ``/health`` (GET)、``/auth/token`` (POST).

    Args:
        config: 认证配置，为 None 时使用默认配置（auth_enabled=True 但无凭证 → 不生效）.
    """

    # 不需要认证的路径集合: (method, path)
    EXEMPT_PATHS: set[tuple[str, str]] = {
        ("GET", "/health"),
        ("POST", "/auth/token"),
    }

    def __init__(self, config: Optional[AuthConfig] = None) -> None:
        self.config: AuthConfig = config or AuthConfig()

    # ───────────────────────────────────────────────────────
    #  JWT 生成与验证
    # ───────────────────────────────────────────────────────

    def generate_jwt(self, subject: str) -> str:
        """生成 HS256 JWT 令牌.

        使用 ``hmac`` + ``hashlib`` 手动实现 HS256 签名，
        不依赖 PyJWT 等第三方库.

        Args:
            subject: 令牌主体标识（如 API Key 或用户 ID）.

        Returns:
            JWT 字符串，格式为 ``header.payload.signature``.

        Raises:
            ValueError: 如果未配置 ``jwt_secret``.
        """
        if not self.config.jwt_secret:
            raise ValueError("未配置 jwt_secret，无法生成 JWT")

        # JWT Header
        header = {"alg": "HS256", "typ": "JWT"}
        # JWT Payload
        now = int(time.time())
        payload = {
            "sub": subject,       # 主体
            "iat": now,           # 签发时间
            "exp": now + self.config.jwt_expiry,  # 过期时间
        }

        # Base64URL 编码
        header_b64 = _b64url_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        payload_b64 = _b64url_encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )

        # 签名: HMAC-SHA256(header_b64 + "." + payload_b64, secret)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = hmac.new(
            self.config.jwt_secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        sig_b64 = _b64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{sig_b64}"

    def verify_jwt(self, token: str) -> Optional[dict[str, Any]]:
        """验证 HS256 JWT 令牌.

        验证步骤:
            1. 检查格式（三段式）
            2. 重新计算签名并常量时间比较
            3. 解析 payload
            4. 检查过期时间

        Args:
            token: JWT 字符串.

        Returns:
            验证成功返回 payload 字典，失败返回 ``None``.
        """
        if not self.config.jwt_secret:
            return None

        # 格式检查: 必须是三段式
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # 重新计算签名
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(
            self.config.jwt_secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = _b64url_encode(expected_sig)

        # 常量时间比较签名（防止时序攻击）
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None

        # 解析 payload
        try:
            payload: dict[str, Any] = json.loads(_b64url_decode(payload_b64))
        except (json.JSONDecodeError, ValueError):
            return None

        # 检查过期时间
        exp = payload.get("exp")
        if exp is None or not isinstance(exp, (int, float)):
            return None
        if time.time() >= exp:
            return None

        return payload

    # ───────────────────────────────────────────────────────
    #  API Key 验证
    # ───────────────────────────────────────────────────────

    def verify_api_key(self, key: str) -> bool:
        """验证 API Key 是否有效.

        使用常量时间比较，防止时序攻击.

        Args:
            key: 待验证的 API Key.

        Returns:
            ``True`` 如果 key 在有效列表中.
        """
        if not self.config.api_keys or not key:
            return False
        for valid_key in self.config.api_keys:
            if hmac.compare_digest(key, valid_key):
                return True
        return False

    # ───────────────────────────────────────────────────────
    #  请求头提取
    # ───────────────────────────────────────────────────────

    @staticmethod
    def extract_bearer_token(headers: dict[str, str]) -> Optional[str]:
        """从 ``Authorization`` 头提取 Bearer token.

        支持 ``Authorization: Bearer <token>`` 格式.
        大小写不敏感地查找头名称.

        Args:
            headers: 请求头字典.

        Returns:
            Bearer token 字符串，若不存在返回 ``None``.
        """
        # 大小写不敏感查找 Authorization 头
        auth_header = ""
        for k, v in headers.items():
            if k.lower() == "authorization":
                auth_header = v
                break
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        return None

    @staticmethod
    def extract_api_key_header(headers: dict[str, str]) -> Optional[str]:
        """从 ``X-API-Key`` 头提取 API Key.

        大小写不敏感地查找头名称.

        Args:
            headers: 请求头字典.

        Returns:
            API Key 字符串，若不存在返回 ``None``.
        """
        # 大小写不敏感查找 X-API-Key 头
        for k, v in headers.items():
            if k.lower() == "x-api-key":
                return v
        return None

    # ───────────────────────────────────────────────────────
    #  统一认证
    # ───────────────────────────────────────────────────────

    def is_auth_active(self) -> bool:
        """认证是否实际生效.

        认证生效条件:
            - ``auth_enabled=True``
            - 且 ``api_keys`` 非空 **或** ``jwt_secret`` 非空

        若未配置任何凭证（两者均为空），认证不生效，放行所有请求.
        这确保了向后兼容：未配置认证的服务器不会拒绝请求.

        Returns:
            ``True`` 如果认证生效.
        """
        if not self.config.auth_enabled:
            return False
        if not self.config.api_keys and not self.config.jwt_secret:
            return False
        return True

    def is_exempt(self, method: str, path: str) -> bool:
        """检查请求是否豁免认证.

        豁免路径: ``GET /health``、``POST /auth/token``.

        Args:
            method: HTTP 方法（大写）.
            path:   请求路径.

        Returns:
            ``True`` 如果该路径不需要认证.
        """
        return (method.upper(), path) in self.EXEMPT_PATHS

    def authenticate(
        self, headers: dict[str, str]
    ) -> tuple[bool, Optional[dict[str, Any]]]:
        """统一认证入口.

        认证优先级: **JWT > API Key**，任一通过即可.

        提取顺序:
            1. ``Authorization: Bearer <token>`` — 先尝试 JWT 验证，
               失败后再尝试作为 API Key 验证
            2. ``X-API-Key: <key>`` — 仅作为 API Key 验证

        Args:
            headers: 请求头字典.

        Returns:
            ``(True, None)`` — 认证成功.
            ``(False, error_dict)`` — 认证失败，``error_dict`` 为 401 JSON 响应体.
        """
        # 1. 尝试从 Authorization: Bearer 头提取 token
        bearer = self.extract_bearer_token(headers)
        if bearer:
            # 优先尝试 JWT 验证
            if self.config.jwt_secret:
                payload = self.verify_jwt(bearer)
                if payload is not None:
                    return True, None
            # JWT 验证失败，尝试作为 API Key
            if self.verify_api_key(bearer):
                return True, None

        # 2. 尝试 X-API-Key 头
        api_key = self.extract_api_key_header(headers)
        if api_key and self.verify_api_key(api_key):
            return True, None

        # 3. 所有方式均失败
        return False, {
            "error": "Unauthorized",
            "message": "缺少有效的认证凭证或凭证无效",
        }

    # ───────────────────────────────────────────────────────
    #  CORS
    # ───────────────────────────────────────────────────────

    def get_cors_headers(
        self, origin: Optional[str] = None
    ) -> dict[str, str]:
        """获取 CORS 响应头.

        根据配置的 ``cors_origins`` 决定 ``Access-Control-Allow-Origin``:
            - 如果配置了 ``"*"``，则返回 ``"*"``
            - 如果请求的 Origin 在允许列表中，则返回该 Origin
            - 否则返回列表中第一个来源

        Args:
            origin: 请求的 ``Origin`` 头（可选）.

        Returns:
            CORS 响应头字典.
        """
        origins = self.config.cors_origins

        # 确定 Access-Control-Allow-Origin
        if "*" in origins:
            allow_origin = "*"
        elif origin and origin in origins:
            allow_origin = origin
        else:
            allow_origin = origins[0] if origins else "*"

        return {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
            "Access-Control-Max-Age": "3600",
        }

    # ───────────────────────────────────────────────────────
    #  令牌端点
    # ───────────────────────────────────────────────────────

    def create_token_response(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        """处理 ``POST /auth/token`` — 用 API Key 换取 JWT.

        从以下位置提取 API Key（按优先级）:
            1. ``X-API-Key`` 头
            2. ``Authorization: Bearer <key>`` 头
            3. 请求体 ``api_key`` 字段

        Args:
            headers: 请求头字典.
            body:    请求体字典.

        Returns:
            ``(status_code, response_dict)``:
                - 200: ``{"token", "token_type", "expires_in"}``
                - 400: 缺少 API Key
                - 401: API Key 无效
                - 503: 未配置 JWT 密钥
        """
        # 从头或体中提取 API Key
        api_key = self.extract_api_key_header(headers)
        if not api_key:
            bearer = self.extract_bearer_token(headers)
            if bearer:
                api_key = bearer
        if not api_key:
            api_key = body.get("api_key", "")

        if not api_key:
            return 400, {
                "error": "Bad Request",
                "message": "缺少 API Key，请通过 Authorization、X-API-Key 头或 api_key 字段提供",
            }

        if not self.verify_api_key(api_key):
            return 401, {
                "error": "Unauthorized",
                "message": "无效的 API Key",
            }

        if not self.config.jwt_secret:
            return 503, {
                "error": "Service Unavailable",
                "message": "未配置 JWT 密钥，无法生成令牌",
            }

        # 生成 JWT
        token = self.generate_jwt(api_key)

        return 200, {
            "token": token,
            "token_type": "Bearer",
            "expires_in": self.config.jwt_expiry,
        }

    # ───────────────────────────────────────────────────────
    #  辅助
    # ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"AuthManager(auth_enabled={self.config.auth_enabled}, "
            f"api_keys={len(self.config.api_keys)}, "
            f"jwt_secret={'set' if self.config.jwt_secret else 'unset'})"
        )
