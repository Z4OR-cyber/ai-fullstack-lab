"""
Intigriti platform adapter.

使用 Intigriti Core Researcher API 提交和查询漏洞报告。

API 文档: https://api.intigriti.com/core/researcher

认证方式: Bearer Token (OAuth Personal Access Token)
    - Authorization: Bearer {pat}

主要端点:
    - POST /submissions          创建报告
    - GET  /submissions/{id}     查询报告
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

# Intigriti API 默认基础 URL
INTIGRITI_API_BASE = "https://api.intigriti.com/core/researcher"


class IntigritiAdapter(BountyPlatformAdapter):
    """Intigriti 平台适配器.

    使用 Bearer Token 认证，需要 program_id 和 asset_id 来定位目标。
    支持 CVSS 向量字符串传递严重度信息。

    Args:
        config: 平台配置，credentials 需包含 token
        client: 可选的 httpx.AsyncClient（用于测试 mock）
    """

    PLATFORM_NAME = "intigriti"

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if config is None:
            config = PlatformConfig(
                platform_name=self.PLATFORM_NAME,
                api_base=INTIGRITI_API_BASE,
                auth_type="bearer_token",
                credentials={
                    "token": os.environ.get("BOUNTY_INT_TOKEN", ""),
                },
            )
        super().__init__(config, client)

    # ------------------------------------------------------------------
    #  配置校验
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """校验 Intigriti 配置.

        Raises:
            SubmissionError: 缺少 token 时
        """
        token = self.config.credentials.get("token", "")
        if not token:
            raise SubmissionError(
                "Intigriti 需要 token (PAT)，"
                "通过 credentials['token'] 或环境变量 BOUNTY_INT_TOKEN 传入",
                platform=self.PLATFORM_NAME,
            )

    # ------------------------------------------------------------------
    #  Payload 构建
    # ------------------------------------------------------------------

    def build_payload(self, report: BountyReport) -> Dict[str, Any]:
        """将 BountyReport 转换为 Intigriti submission 格式.

        Intigriti submission 需要:
            - programId: 目标项目 ID
            - assetId: 目标资产 ID（可选但推荐）
            - title: 报告标题
            - description: 漏洞描述
            - impact: 影响描述
            - severity: 严重度 (1-5)
            - cvss: CVSS 向量（可选）

        Args:
            report: 统一漏洞报告

        Returns:
            Intigriti /submissions 请求体

        Raises:
            SubmissionError: 缺少 program_id 时
        """
        program_id = report.program_id or report.metadata.get(
            "program_id", ""
        )
        if not program_id:
            raise SubmissionError(
                "Intigriti 报告需要 program_id，"
                "请设置 BountyReport.program_id 或 metadata['program_id']",
                platform=self.PLATFORM_NAME,
            )

        severity_int = self.severity_to_intigriti(report.severity)

        # 构建描述
        description_parts: List[str] = []
        if report.vulnerability_information:
            description_parts.append(report.vulnerability_information)
        if report.endpoint_url:
            description_parts.append(
                f"\n## Endpoint\n\n{report.endpoint_url}"
            )
        if report.cwe_id:
            description_parts.append(f"\n## CWE\n\n{report.cwe_id}")
        description = "\n".join(description_parts) if description_parts \
            else report.title

        payload: Dict[str, Any] = {
            "programId": program_id,
            "title": report.title,
            "description": description,
            "impact": report.impact or report.vulnerability_information,
            "severity": severity_int,
        }

        if report.asset_id:
            payload["assetId"] = report.asset_id

        if report.cvss_vector:
            payload["cvss"] = {"vector": report.cvss_vector}

        if report.endpoint_url:
            payload["endpoint"] = report.endpoint_url

        if report.attachments:
            payload["attachments"] = [
                {"fileName": os.path.basename(fp)}
                for fp in report.attachments
            ]

        return payload

    # ------------------------------------------------------------------
    #  附件上传
    # ------------------------------------------------------------------

    async def _upload_attachment(
        self, submission_id: str, file_path: str
    ) -> str:
        """上传附件到 Intigriti submission.

        Intigriti 使用两阶段上传：先获取上传 URL，再上传文件内容。
        这里简化为直接 POST 文件到 submissions/{id}/attachments。

        Args:
            submission_id: submission ID
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
                f"/submissions/{submission_id}/attachments",
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
        """提交漏洞报告到 Intigriti.

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

        response = await self._request(
            "POST", "/submissions", json_body=payload
        )
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
                        "Intigriti 附件上传失败 %s: %s", fp, e
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
        """查询 Intigriti submission 状态.

        Args:
            report_id: Intigriti submission ID

        Returns:
            包含最新状态的 SubmissionResult
        """
        self.validate_config()

        response = await self._request(
            "GET", f"/submissions/{report_id}"
        )
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

    # ------------------------------------------------------------------
    #  CVSS 计算器辅助
    # ------------------------------------------------------------------

    @staticmethod
    def cvss_to_severity(cvss_score: float) -> int:
        """将 CVSS 分数转换为 Intigriti 严重度整数.

        CVSS v3 评级:
            9.0-10.0 → 1 (Critical)
            7.0-8.9  → 2 (High)
            4.0-6.9  → 3 (Medium)
            0.1-3.9  → 4 (Low)
            0.0      → 5 (Info)

        Args:
            cvss_score: CVSS 分数 (0.0-10.0)

        Returns:
            Intigriti 严重度 (1-5)
        """
        if cvss_score >= 9.0:
            return 1
        elif cvss_score >= 7.0:
            return 2
        elif cvss_score >= 4.0:
            return 3
        elif cvss_score > 0.0:
            return 4
        else:
            return 5
