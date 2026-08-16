"""
Bounty submission router — 统一多平台提交路由器.

:class:`BountyRouter` 管理多个平台适配器实例，提供统一的提交、草稿构建
和状态查询接口。支持通过环境变量自动加载平台配置。

环境变量约定:
    - HackerOne: BOUNTY_H1_USER, BOUNTY_H1_TOKEN
    - Bugcrowd:  BOUNTY_BC_TOKEN
    - Intigriti: BOUNTY_INT_TOKEN
    - YesWeHack: BOUNTY_YWH_TOKEN
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from .base import BountyPlatformAdapter
from .models import (
    BountyReport,
    DraftReport,
    PlatformConfig,
    SubmissionError,
    SubmissionResult,
)
from .platforms.bugcrowd import BugcrowdAdapter
from .platforms.hackerone import HackerOneAdapter
from .platforms.intigriti import IntigritiAdapter
from .platforms.yeswehack import YesWeHackAdapter

logger = logging.getLogger(__name__)

# 平台名称到适配器类的映射
PLATFORM_REGISTRY: Dict[str, type] = {
    "hackerone": HackerOneAdapter,
    "bugcrowd": BugcrowdAdapter,
    "intigriti": IntigritiAdapter,
    "yeswehack": YesWeHackAdapter,
}

# 环境变量自动加载配置
ENV_CONFIG_MAP: Dict[str, Dict[str, Any]] = {
    "hackerone": {
        "api_base": "https://api.hackerone.com/v1",
        "auth_type": "basic_auth",
        "credential_env": {
            "username": "BOUNTY_H1_USER",
            "token": "BOUNTY_H1_TOKEN",
        },
    },
    "bugcrowd": {
        "api_base": "https://api.bugcrowd.com",
        "auth_type": "api_key_header",
        "credential_env": {
            "token": "BOUNTY_BC_TOKEN",
        },
        "extra_headers": {
            "Accept": "application/vnd.bugcrowd+json",
        },
    },
    "intigriti": {
        "api_base": "https://api.intigriti.com/core/researcher",
        "auth_type": "bearer_token",
        "credential_env": {
            "token": "BOUNTY_INT_TOKEN",
        },
    },
    "yeswehack": {
        "api_base": "https://api.yeswehack.com",
        "auth_type": "bearer_token",
        "credential_env": {
            "token": "BOUNTY_YWH_TOKEN",
        },
    },
}


class BountyRouter:
    """多平台漏洞赏金提交路由器.

    管理多个平台适配器实例，提供统一接口:
        - :meth:`register_platform` 注册平台
        - :meth:`submit` 统一提交
        - :meth:`build_draft` 构建草稿
        - :meth:`get_status` 查询状态
        - :meth:`list_platforms` 列出已注册平台

    支持从环境变量自动加载配置。

    Args:
        auto_load_env: 是否在初始化时自动从环境变量加载平台
        client: 可选的共享 httpx.AsyncClient
    """

    def __init__(
        self,
        auto_load_env: bool = False,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self._adapters: Dict[str, BountyPlatformAdapter] = {}
        self._client = client
        if auto_load_env:
            self.load_from_env()

    # ------------------------------------------------------------------
    #  平台注册
    # ------------------------------------------------------------------

    def register_platform(self, config: PlatformConfig) -> None:
        """注册一个平台适配器.

        Args:
            config: 平台配置

        Raises:
            SubmissionError: 未知平台名称时
        """
        name = config.platform_name
        adapter_cls = PLATFORM_REGISTRY.get(name)
        if adapter_cls is None:
            raise SubmissionError(
                f"未知平台: {name!r}，支持的平台: "
                f"{list(PLATFORM_REGISTRY.keys())}",
            )
        adapter = adapter_cls(config=config, client=self._client)
        self._adapters[name] = adapter
        logger.info("已注册平台适配器: %s", name)

    def unregister_platform(self, platform: str) -> None:
        """注销平台适配器.

        Args:
            platform: 平台名称
        """
        platform = platform.strip().lower()
        if platform in self._adapters:
            del self._adapters[platform]
            logger.info("已注销平台适配器: %s", platform)

    def load_from_env(self) -> List[str]:
        """从环境变量自动加载平台配置.

        只加载有完整凭证的平台。

        Returns:
            成功加载的平台名称列表
        """
        loaded: List[str] = []
        for name, env_info in ENV_CONFIG_MAP.items():
            cred_env = env_info.get("credential_env", {})
            credentials: Dict[str, str] = {}
            has_all = True

            for key, env_var in cred_env.items():
                value = os.environ.get(env_var, "")
                if not value:
                    has_all = False
                    break
                credentials[key] = value

            if not has_all:
                continue

            config = PlatformConfig(
                platform_name=name,
                api_base=env_info["api_base"],
                auth_type=env_info["auth_type"],
                credentials=credentials,
                extra_headers=env_info.get("extra_headers", {}),
            )
            self.register_platform(config)
            loaded.append(name)

        return loaded

    # ------------------------------------------------------------------
    #  适配器访问
    # ------------------------------------------------------------------

    def get_adapter(self, platform: str) -> BountyPlatformAdapter:
        """获取指定平台的适配器.

        Args:
            platform: 平台名称

        Returns:
            平台适配器实例

        Raises:
            SubmissionError: 平台未注册时
        """
        platform = platform.strip().lower()
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise SubmissionError(
                f"平台 {platform!r} 未注册，"
                f"已注册: {self.list_platforms()}",
            )
        return adapter

    def list_platforms(self) -> List[str]:
        """列出已注册的平台名称."""
        return list(self._adapters.keys())

    # ------------------------------------------------------------------
    #  统一操作
    # ------------------------------------------------------------------

    async def submit(
        self,
        report: BountyReport,
        platform: str,
        *,
        confirmed: bool = False,
        dry_run: bool = False,
    ) -> SubmissionResult:
        """统一提交漏洞报告.

        Args:
            report: 统一漏洞报告
            platform: 目标平台名称
            confirmed: 是否确认提交（默认 False，只返回草稿）
            dry_run: 是否为演练模式

        Returns:
            提交结果
        """
        adapter = self.get_adapter(platform)
        return await adapter.submit_report(
            report, confirmed=confirmed, dry_run=dry_run
        )

    def build_draft(self, report: BountyReport, platform: str) -> DraftReport:
        """构建草稿（不发送网络请求）.

        Args:
            report: 统一漏洞报告
            platform: 目标平台名称

        Returns:
            包含已构建 payload 的草稿
        """
        adapter = self.get_adapter(platform)
        return adapter.build_draft(report)

    async def get_status(
        self, report_id: str, platform: str
    ) -> SubmissionResult:
        """查询报告状态.

        Args:
            report_id: 平台报告 ID
            platform: 平台名称

        Returns:
            包含最新状态的 SubmissionResult
        """
        adapter = self.get_adapter(platform)
        return await adapter.get_report(report_id)

    # ------------------------------------------------------------------
    #  生命周期
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """关闭所有适配器（仅关闭路由器自有的 client）."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BountyRouter:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()
