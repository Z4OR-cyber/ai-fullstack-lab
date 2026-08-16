"""
YesWeHack platform adapter.

使用 YesWeHack API 提交和查询漏洞报告。

API 文档 (OpenAPI): https://api.yeswehack.com/doc

认证方式: Bearer Token (Personal Access Token)
    - Authorization: Bearer {pat}

主要端点:
    - POST /reports          创建报告
    - GET  /reports/{id}     查询报告
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

# YesWeHack API 默认基础 URL
YWH_API_BASE = "https://api.yeswehack.com"


class YesWeHackAdapter(BountyPlatformAdapter):
    """YesWeHack 平台适配器.

    使用 Bearer Token 认证，需要 program_slug 来定位目标项目。

    Args:
        config: 平台配置，credentials 需包含 token
        client: 可选的 httpx.AsyncClient（用于测试 mock）
    """

    PLATFORM_NAME = "yeswehack"

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if config is None:
            config = PlatformConfig(
                platform_name=self.PLATFORM_NAME,
                api_base=YWH_API_BASE,
                auth_type="bearer_token",
                credentials={
                    "token": os.environ.get("BOUNTY_YWH_TOKEN", ""),
                },
                extra_headers={
                    "Accept": "application/json",
                },
            )
        super().__init__(config, client)

    # ------------------------------------------------------------------
    #  配置校验
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """校验 YesWeHack 配置.

        Raises:
            SubmissionError: 缺少 PAT 时
        """
        token = self.config.credentials.get("token", "")
        if not token:
            raise SubmissionError(
                "YesWeHack 需要 token (PAT)，"
                "通过 credentials['token'] 或环境变量 BOUNTY_YWH_TOKEN 传入",
                platform=self.PLATFORM_NAME,
            )

    # ------------------------------------------------------------------
    #  Payload 构建
    # ------------------------------------------------------------------

    def build_payload(self, report: BountyReport) -> Dict[str, Any]:
        """将 BountyReport 转换为 YesWeHack report 格式.

        YesWeHack reports 需要:
            - program_slug: 目标项目 slug
            - title: 报告标题
            - description: 漏洞详情（Markdown）
            - impact: 影响描述
            - severity: 严重度 (critical/high/medium/low/info)
            - cwe: CWE ID（可选）

        Args:
            report: 统一漏洞报告

        Returns:
            YesWeHack /reports 请求体

        Raises:
            SubmissionError: 缺少 program_slug 时
        """
        program_slug = report.program_slug or report.metadata.get(
            "program_slug", ""
        )
        if not program_slug:
            raise SubmissionError(
                "YesWeHack 报告需要 program_slug，"
                "请设置 BountyReport.program_slug 或 metadata['program_slug']",
                platform=self.PLATFORM_NAME,
            )

        severity_str = self.severity_to_ywh(report.severity)

        # 构建描述
        description_parts: List[str] = []
        if report.vulnerability_information:
            description_parts.append(report.vulnerability_information)
        if report.endpoint_url:
            description_parts.append(
                f"\n## Affected Endpoint\n\n{report.endpoint_url}"
            )
        if report.cwe_id:
            description_parts.append(f"\n## CWE\n\n{report.cwe_id}")
        description = "\n".join(description_parts) if description_parts \
            else report.title

        payload: Dict[str, Any] = {
            "program_slug": program_slug,
            "title": report.title,
            "description": description,
            "impact": report.impact or report.vulnerability_information,
            "severity": severity_str,
        }

        if report.cvss_vector:
            payload["cvss_vector"] = report.cvss_vector

        if report.attachments:
            # YesWeHack 附件在创建报告后通过单独端点上传
            payload["attachment_ids"] = []

        return payload

    # ------------------------------------------------------------------
    #  附件上传
    # ------------------------------------------------------------------

    async def _upload_attachment(
        self, report_id: str, file_path: str
    ) -> str:
        """上传附件到 YesWeHack report.

        Args:
            report_id: report ID
            file_path: 本地文件路径

        Returns:
            附件 ID
        """
        if not os.path.isfile(file_path):
            raise SubmissionError(
                f"附件文件不存在: {file_path}",
                platform=self.PLATFORM_NAME,
            )

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            response = await self._request(
                "POST",
                f"/reports/{report_id}/attachments",
                files=files,
            )

        data = self._safe_json(response)
        if isinstance(data, dict):
            return str(data.get("id", ""))
        return ""

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
        """提交漏洞报告到 YesWeHack.

        Args:
            report: 统一漏洞报告
            confirmed: 是否确认提交
            dry_run: 是否为演练模式

        Returns:
            提交结果
        """
        payload = self.build_payload(report)

        if dry_run or not confirmed:
            return SubmissionResult(
                success=False,
                platform=self.PLATFORM_NAME,
                status="draft",
                raw_response=payload,
            )

        self.validate_config()

        response = await self._request("POST", "/reports", json_body=payload)
        data = self._safe_json(response)

        report_id = ""
        report_url = ""
        status = ""

        if isinstance(data, dict):
            report_id = str(data.get("id", ""))
            report_url = data.get("url", "")
            status = data.get("status", "new")

        # 上传附件
        if report.attachments and report_id:
            for fp in report.attachments:
                try:
                    await self._upload_attachment(report_id, fp)
                except SubmissionError as e:
                    logger.warning(
                        "YesWeHack 附件上传失败 %s: %s", fp, e
                    )

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
        """查询 YesWeHack report 状态.

        Args:
            report_id: YesWeHack report ID

        Returns:
            包含最新状态的 SubmissionResult
        """
        self.validate_config()

        response = await self._request("GET", f"/reports/{report_id}")
        data = self._safe_json(response)

        report_url = ""
        status = ""

        if isinstance(data, dict):
            report_url = data.get("url", "")
            status = data.get("status", "")

        return SubmissionResult(
            success=True,
            platform=self.PLATFORM_NAME,
            report_id=report_id,
            url=report_url,
            status=status,
            raw_response=data,
        )
