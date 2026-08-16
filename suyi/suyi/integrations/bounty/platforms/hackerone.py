"""
HackerOne platform adapter.

使用 HackerOne API v1 提交和查询漏洞报告。

API 文档: https://api.hackerone.com/hacker-resources/

认证方式: HTTP Basic Auth
    - username: API 用户名（在 HackerOne 设置中生成）
    - token: API Token

主要端点:
    - POST /v1/reports                  创建报告
    - GET  /v1/hackers/reports/{id}     查询报告
    - POST /v1/hackers/attachments      上传附件
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from ..base import BountyPlatformAdapter
from ..models import (
    BountyReport,
    PlatformConfig,
    SubmissionError,
    SubmissionResult,
)

logger = logging.getLogger(__name__)

# HackerOne API 默认基础 URL
HACKERONE_API_BASE = "https://api.hackerone.com/v1"


class HackerOneAdapter(BountyPlatformAdapter):
    """HackerOne 平台适配器.

    使用 HTTP Basic Auth 认证，通过 JSON API 格式提交漏洞报告。
    附件采用两阶段上传：先上传文件获得 attachment_id，
    再在创建报告时引用这些 ID。

    Args:
        config: 平台配置，credentials 需包含 username 和 token
        client: 可选的 httpx.AsyncClient（用于测试 mock）
    """

    PLATFORM_NAME = "hackerone"

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if config is None:
            config = PlatformConfig(
                platform_name=self.PLATFORM_NAME,
                api_base=HACKERONE_API_BASE,
                auth_type="basic_auth",
                credentials={
                    "username": os.environ.get("BOUNTY_H1_USER", ""),
                    "token": os.environ.get("BOUNTY_H1_TOKEN", ""),
                },
            )
        super().__init__(config, client)

    # ------------------------------------------------------------------
    #  配置校验
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """校验 HackerOne 配置.

        Raises:
            SubmissionError: 缺少 username 或 token 时
        """
        creds = self.config.credentials
        username = creds.get("username", "")
        token = creds.get("token", "")
        if not username:
            raise SubmissionError(
                "HackerOne 需要 username (API 用户名)，"
                "通过 credentials['username'] 或环境变量 BOUNTY_H1_USER 传入",
                platform=self.PLATFORM_NAME,
            )
        if not token:
            raise SubmissionError(
                "HackerOne 需要 token (API Token)，"
                "通过 credentials['token'] 或环境变量 BOUNTY_H1_TOKEN 传入",
                platform=self.PLATFORM_NAME,
            )

    # ------------------------------------------------------------------
    #  Payload 构建
    # ------------------------------------------------------------------

    def build_payload(self, report: BountyReport) -> Dict[str, Any]:
        """将 BountyReport 转换为 HackerOne JSON API 格式.

        Args:
            report: 统一漏洞报告

        Returns:
            HackerOne /v1/reports 请求体

        Raises:
            SubmissionError: 缺少 team_handle 时
        """
        team_handle = report.team_handle or report.metadata.get(
            "team_handle", ""
        )
        if not team_handle:
            raise SubmissionError(
                "HackerOne 报告需要 team_handle，"
                "请设置 BountyReport.team_handle 或 metadata['team_handle']",
                platform=self.PLATFORM_NAME,
            )

        attributes: Dict[str, Any] = {
            "team_handle": team_handle,
            "title": report.title,
            "vulnerability_information": report.vulnerability_information,
            "severity_rating": self.severity_to_h1(report.severity),
        }

        if report.impact:
            attributes["impact"] = report.impact

        if report.weakness_id:
            attributes["weakness_id"] = int(report.weakness_id) \
                if report.weakness_id.isdigit() else report.weakness_id

        if report.structured_scope_id:
            attributes["structured_scope_id"] = int(
                report.structured_scope_id
            ) if report.structured_scope_id.isdigit() \
                else report.structured_scope_id

        if report.cwe_id:
            attributes["cwe_id"] = report.cwe_id

        if report.endpoint_url:
            attributes["source"] = report.endpoint_url

        if report.attachments:
            # 附件 ID 需要在上传后填充，这里用占位符
            attributes["attachment_ids"] = []

        payload: Dict[str, Any] = {"data": {"type": "report", "attributes": attributes}}
        return payload

    # ------------------------------------------------------------------
    #  附件上传
    # ------------------------------------------------------------------

    async def _upload_attachment(self, file_path: str) -> int:
        """上传单个附件到 HackerOne.

        Args:
            file_path: 本地文件路径

        Returns:
            附件 ID

        Raises:
            SubmissionError: 上传失败时
        """
        if not os.path.isfile(file_path):
            raise SubmissionError(
                f"附件文件不存在: {file_path}",
                platform=self.PLATFORM_NAME,
            )

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"files": (filename, f)}
            response = await self._request(
                "POST",
                "/hackers/attachments",
                files=files,
            )

        data = self._safe_json(response)
        if isinstance(data, dict):
            attr = data.get("data", {}).get("attributes", {})
            attachment_id = attr.get("id") or data.get("data", {}).get("id")
            if attachment_id:
                return int(attachment_id)
        raise SubmissionError(
            f"附件上传响应格式异常: {data}",
            platform=self.PLATFORM_NAME,
        )

    async def _upload_attachments(self, file_paths: List[str]) -> List[int]:
        """批量上传附件.

        Args:
            file_paths: 本地文件路径列表

        Returns:
            附件 ID 列表
        """
        ids: List[int] = []
        for fp in file_paths:
            aid = await self._upload_attachment(fp)
            ids.append(aid)
        return ids

    # ------------------------------------------------------------------
    #  提交报告
    # ------------------------------------------------------------------

    async def submit_report(
        self,
        report: BountyReport,
        *,
        confirmed: bool = False,
        dry_run: bool = False,
    ) -> SubmissionResult:
        """提交漏洞报告到 HackerOne.

        安全机制:
            - ``confirmed=False`` (默认): 只构建 payload 返回草稿，不发送请求
            - ``dry_run=True``: 只构建 payload，不发送网络请求
            - ``confirmed=True + dry_run=False``: 真正提交到平台

        Args:
            report: 统一漏洞报告
            confirmed: 是否确认提交
            dry_run: 是否为演练模式

        Returns:
            提交结果（草稿模式 success=False，实际提交成功 success=True）
        """
        payload = self.build_payload(report)

        # dry_run 或未确认：返回草稿信息，不发送请求
        if dry_run or not confirmed:
            return SubmissionResult(
                success=False,
                platform=self.PLATFORM_NAME,
                status="draft",
                raw_response=payload,
            )

        # 真正提交前校验配置
        self.validate_config()

        # 上传附件
        attachment_ids: List[int] = []
        if report.attachments:
            attachment_ids = await self._upload_attachments(report.attachments)
            payload["data"]["attributes"]["attachment_ids"] = attachment_ids

        # 发送创建报告请求
        response = await self._request("POST", "/reports", json_body=payload)
        data = self._safe_json(response)

        report_id = ""
        report_url = ""
        status = ""

        if isinstance(data, dict):
            report_data = data.get("data", {})
            report_id = str(report_data.get("id", ""))
            links = data.get("links", {})
            report_url = links.get("self", "")
            attr = report_data.get("attributes", {})
            status = attr.get("state", "new")

        return SubmissionResult(
            success=True,
            platform=self.PLATFORM_NAME,
            report_id=report_id,
            url=report_url,
            status=status or "new",
            raw_response=data,
        )

    # ------------------------------------------------------------------
    #  查询报告
    # ------------------------------------------------------------------

    async def get_report(self, report_id: str) -> SubmissionResult:
        """查询 HackerOne 报告状态.

        Args:
            report_id: HackerOne 报告 ID

        Returns:
            包含最新状态的 SubmissionResult
        """
        self.validate_config()

        response = await self._request(
            "GET", f"/hackers/reports/{report_id}"
        )
        data = self._safe_json(response)

        report_url = ""
        status = ""

        if isinstance(data, dict):
            report_data = data.get("data", {})
            links = data.get("links", {})
            report_url = links.get("self", "")
            attr = report_data.get("attributes", {})
            status = attr.get("state", "")

        return SubmissionResult(
            success=True,
            platform=self.PLATFORM_NAME,
            report_id=report_id,
            url=report_url,
            status=status,
            raw_response=data,
        )
