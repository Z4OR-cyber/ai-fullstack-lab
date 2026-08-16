"""
Bounty platform adapter abstract base class.

定义所有平台适配器必须实现的接口，并提供通用的 HTTP 请求封装、
错误处理、重试逻辑和 severity 映射辅助方法。

新平台适配器只需继承 :class:`BountyPlatformAdapter` 并实现:
    - :meth:`build_payload` — 将 BountyReport 转换为平台特定 payload
    - :meth:`submit_report` — 提交报告到平台
    - :meth:`get_report` — 查询已有报告状态
    - :meth:`validate_config` — 校验平台配置
"""

from __future__ import annotations

import asyncio
import base64
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from .models import (
    BountyReport,
    DraftReport,
    PlatformConfig,
    SubmissionError,
    SubmissionResult,
)

logger = logging.getLogger(__name__)

# 默认重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0

# 可重试的 HTTP 状态码
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class BountyPlatformAdapter(ABC):
    """漏洞赏金平台适配器抽象基类.

    封装通用的 HTTP 请求、认证头构建、重试和错误处理逻辑。
    子类必须实现平台特定的 payload 构建、提交和查询方法。

    Attributes:
        config: 平台连接配置
        _client: 可选的外部 httpx.AsyncClient（用于测试注入）
    """

    # 子类覆盖：平台名称
    PLATFORM_NAME: str = ""

    def __init__(
        self,
        config: PlatformConfig,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.config = config
        self._client = client
        self._owns_client = client is None

    # ------------------------------------------------------------------
    #  抽象方法
    # ------------------------------------------------------------------

    @abstractmethod
    def build_payload(self, report: BountyReport) -> Dict[str, Any]:
        """将统一 BountyReport 转换为平台特定的请求 payload.

        Args:
            report: 统一漏洞报告

        Returns:
            平台 API 所需的请求体字典
        """

    @abstractmethod
    async def submit_report(
        self,
        report: BountyReport,
        *,
        confirmed: bool = False,
        dry_run: bool = False,
    ) -> SubmissionResult:
        """提交漏洞报告到平台.

        Args:
            report: 统一漏洞报告
            confirmed: 是否真正提交。False 时只构建草稿
            dry_run: 为 True 时只构建 payload 不发送网络请求

        Returns:
            提交结果
        """

    @abstractmethod
    async def get_report(self, report_id: str) -> SubmissionResult:
        """查询已有报告状态.

        Args:
            report_id: 平台报告 ID

        Returns:
            包含最新状态的 SubmissionResult
        """

    @abstractmethod
    def validate_config(self) -> None:
        """校验平台配置是否完整.

        Raises:
            SubmissionError: 配置缺失或无效时
        """

    # ------------------------------------------------------------------
    #  通用 HTTP 方法
    # ------------------------------------------------------------------

    def _get_auth_headers(self) -> Dict[str, str]:
        """根据 auth_type 构建认证请求头.

        Returns:
            包含认证信息的 HTTP 头字典
        """
        headers: Dict[str, str] = {}
        creds = self.config.credentials
        auth_type = self.config.auth_type

        if auth_type == "basic_auth":
            username = creds.get("username", "")
            token = creds.get("token", "")
            raw = f"{username}:{token}".encode("utf-8")
            encoded = base64.b64encode(raw).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_type == "bearer_token":
            token = creds.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key_header":
            header_name = creds.get("header_name", "Authorization")
            token = creds.get("token", "")
            prefix = creds.get("prefix", "Token")
            if prefix:
                headers[header_name] = f"{prefix} {token}"
            else:
                headers[header_name] = token

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> httpx.Response:
        """发送 HTTP 请求，带重试和错误处理.

        Args:
            method: HTTP 方法 (GET/POST/PUT/DELETE)
            path: API 路径（相对于 api_base）
            json_body: JSON 请求体
            data: 表单数据
            files: 上传文件
            params: 查询参数
            extra_headers: 额外请求头
            max_retries: 最大重试次数

        Returns:
            httpx.Response 对象

        Raises:
            SubmissionError: HTTP 错误或网络异常时
        """
        url = f"{self.config.api_base}{path}"
        headers = self._get_auth_headers()
        headers.update(self.config.extra_headers)
        if extra_headers:
            headers.update(extra_headers)

        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                client = self._get_client()
                response = await client.request(
                    method,
                    url,
                    json=json_body,
                    data=data,
                    files=files,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )

                if response.status_code < 400:
                    return response

                # 可重试的服务端错误
                if (
                    response.status_code in RETRYABLE_STATUS_CODES
                    and attempt < max_retries
                ):
                    delay = DEFAULT_RETRY_DELAY * (
                        DEFAULT_RETRY_BACKOFF ** attempt
                    )
                    logger.warning(
                        "[%s] %s %s 返回 %d，%.1f 秒后重试 (%d/%d)",
                        self.PLATFORM_NAME,
                        method,
                        path,
                        response.status_code,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

                # 不可重试的错误
                error_body = self._safe_json(response)
                raise SubmissionError(
                    f"HTTP {response.status_code} from {self.PLATFORM_NAME}: "
                    f"{method} {path}",
                    platform=self.PLATFORM_NAME,
                    status_code=response.status_code,
                    error_body=error_body,
                )

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = DEFAULT_RETRY_DELAY * (
                        DEFAULT_RETRY_BACKOFF ** attempt
                    )
                    logger.warning(
                        "[%s] %s %s 网络错误: %s，%.1f 秒后重试 (%d/%d)",
                        self.PLATFORM_NAME,
                        method,
                        path,
                        exc,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise SubmissionError(
                    f"Network error connecting to {self.PLATFORM_NAME}: {exc}",
                    platform=self.PLATFORM_NAME,
                ) from exc

        # 理论上不会到达，但为类型安全
        if last_exc:
            raise SubmissionError(
                f"Max retries exceeded for {self.PLATFORM_NAME}: {last_exc}",
                platform=self.PLATFORM_NAME,
            ) from last_exc
        raise SubmissionError(
            f"Unknown error from {self.PLATFORM_NAME}",
            platform=self.PLATFORM_NAME,
        )

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx.AsyncClient."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
        """关闭自有的 HTTP client."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BountyPlatformAdapter:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        """安全地解析 JSON 响应，失败时返回文本."""
        try:
            return response.json()
        except Exception:
            return response.text[:2000]

    @staticmethod
    def severity_to_h1(severity: str) -> str:
        """将统一 severity 映射为 HackerOne severity_rating.

        HackerOne 直接使用 critical/high/medium/low/none，
        所以这里是恒等映射，但保留方法以确保一致性。
        """
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "none": "none",
        }
        return mapping.get(severity.lower(), "medium")

    @staticmethod
    def severity_to_bugcrowd(severity: str) -> int:
        """将统一 severity 映射为 Bugcrowd P1-P5.

        P1 = Critical, P2 = High, P3 = Medium, P4 = Low, P5 = Info/None
        """
        mapping = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
            "none": 5,
        }
        return mapping.get(severity.lower(), 3)

    @staticmethod
    def severity_to_intigriti(severity: str) -> int:
        """将统一 severity 映射为 Intigriti 严重度整数 (1-5).

        Intigriti: 1=Critical, 2=High, 3=Medium, 4=Low, 5=Info
        """
        mapping = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
            "none": 5,
        }
        return mapping.get(severity.lower(), 3)

    @staticmethod
    def severity_to_ywh(severity: str) -> str:
        """将统一 severity 映射为 YesWeHack severity 字符串."""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "none": "info",
        }
        return mapping.get(severity.lower(), "medium")

    def build_draft(self, report: BountyReport) -> DraftReport:
        """构建草稿（不发送网络请求）.

        Args:
            report: 统一漏洞报告

        Returns:
            包含已构建 payload 的 DraftReport
        """
        payload = self.build_payload(report)
        return DraftReport(
            report=report,
            target_platform=self.PLATFORM_NAME,
            built_payload=payload,
        )
