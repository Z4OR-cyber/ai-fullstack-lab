"""
Bugcrowd platform adapter.

使用 Bugcrowd API 提交和查询漏洞报告。

API 文档: https://docs.bugcrowd.com/api/usage/

认证方式: HTTP Header
    - Authorization: Token {api_token}
    - Accept: application/vnd.bugcrowd+json

主要端点:
    - POST /submissions        创建报告（JSON API 规范）
    - GET  /submissions/{id}   查询报告
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

# Bugcrowd API 默认基础 URL
BUGCROWD_API_BASE = "https://api.bugcrowd.com"

# Bugcrowd severity 映射: P1=Critical, P2=High, P3=Medium, P4=Low, P5=Info
BUGCROWD_SEVERITY_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


class BugcrowdAdapter(BountyPlatformAdapter):
    """Bugcrowd 平台适配器.

    使用 Token 认证头，遵循 JSON API 规范
    （type/attributes/relationships 结构）提交漏洞报告。

    Args:
        config: 平台配置，credentials 需包含 token
        client: 可选的 httpx.AsyncClient（用于测试 mock）
    """

    PLATFORM_NAME = "bugcrowd"

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if config is None:
            config = PlatformConfig(
                platform_name=self.PLATFORM_NAME,
                api_base=BUGCROWD_API_BASE,
                auth_type="api_key_header",
                credentials={
                    "header_name": "Authorization",
                    "prefix": "Token",
                    "token": os.environ.get("BOUNTY_BC_TOKEN", ""),
                },
                extra_headers={
                    "Accept": "application/vnd.bugcrowd+json",
                    "Content-Type": "application/vnd.api+json",
                },
            )
        super().__init__(config, client)

    # ------------------------------------------------------------------
    #  配置校验
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """校验 Bugcrowd 配置.

        Raises:
            SubmissionError: 缺少 api_token 时
        """
        token = self.config.credentials.get("token", "")
        if not token:
            raise SubmissionError(
                "Bugcrowd 需要 api_token，"
                "通过 credentials['token'] 或环境变量 BOUNTY_BC_TOKEN 传入",
                platform=self.PLATFORM_NAME,
            )

    # ------------------------------------------------------------------
    #  Payload 构建
    # ------------------------------------------------------------------

    def build_payload(self, report: BountyReport) -> Dict[str, Any]:
        """将 BountyReport 转换为 Bugcrowd JSON API 格式.

        Bugcrowd submissions 使用 JSON API 规范:
        data.type = "submission"
        data.attributes 包含标题、描述等
        data.relationships.program 关联目标项目

        Args:
            report: 统一漏洞报告

        Returns:
            Bugcrowd /submissions 请求体

        Raises:
            SubmissionError: 缺少 program_code 时
        """
        program_code = report.program_code or report.metadata.get(
            "program_code", ""
        )
        if not program_code:
            raise SubmissionError(
                "Bugcrowd 报告需要 program_code，"
                "请设置 BountyReport.program_code 或 metadata['program_code']",
                platform=self.PLATFORM_NAME,
            )

        severity_p = self.severity_to_bugcrowd(report.severity)

        # 构建描述字段：Bugcrowd 使用一个 description 字段，
        # 我们将漏洞详情、影响和端点信息合并为 Markdown
        desc_parts: List[str] = []
        if report.vulnerability_information:
            desc_parts.append(report.vulnerability_information)
        if report.impact:
            desc_parts.append(f"\n## Impact\n\n{report.impact}")
        if report.endpoint_url:
            desc_parts.append(f"\n## Affected URL\n\n{report.endpoint_url}")
        if report.cwe_id:
            desc_parts.append(f"\n## CWE\n\n{report.cwe_id}")
        description = "\n".join(desc_parts) if desc_parts else report.title

        # 构建 v3 标记（Bugcrowd 使用 severity 和 vrt 版本）
        attributes: Dict[str, Any] = {
            "title": report.title,
            "description": description,
            "severity": severity_p,
            "extra_info": report.metadata.get("extra_info", ""),
        }

        if report.cwe_id:
            attributes["vrt_id"] = report.cwe_id
        if report.endpoint_url:
            attributes["vulnerability_url"] = report.endpoint_url

        payload: Dict[str, Any] = {
            "data": {
                "type": "submission",
                "attributes": attributes,
                "relationships": {
                    "program": {
                        "data": {
                            "type": "program",
                            "id": program_code,
                        }
                    }
                },
            }
        }

        return payload

    # ------------------------------------------------------------------
    #  附件上传
    # ------------------------------------------------------------------

    async def _upload_attachment(
        self, submission_id: str, file_path: str
    ) -> str:
        """上传附件到 Bugcrowd submission.

        Bugcrowd 的附件通过 /submissions/{id}/attachments 端点上传。

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
            # Bugcrowd 附件上传不使用 JSON API content-type
            response = await self._request(
                "POST",
                f"/submissions/{submission_id}/attachments",
                files=files,
                extra_headers={
                    "Content-Type": None,  # 让 httpx 自动设置 multipart
                    "Accept": "application/vnd.bugcrowd+json",
                },
            )

        data = self._safe_json(response)
        if isinstance(data, dict):
            att_data = data.get("data", {})
            return str(att_data.get("id", ""))
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
        """提交漏洞报告到 Bugcrowd.

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

        response = await self._request("POST", "/submissions", json_body=payload)
        data = self._safe_json(response)

        report_id = ""
        report_url = ""
        status = ""

        if isinstance(data, dict):
            sub_data = data.get("data", {})
            report_id = str(sub_data.get("id", ""))
            links = data.get("links", {})
            report_url = links.get("self", "")
            attr = sub_data.get("attributes", {})
            status = attr.get("state", "new")

        # 上传附件（Bugcrowd 在创建 submission 后追加附件）
        if report.attachments and report_id:
            for fp in report.attachments:
                try:
                    await self._upload_attachment(report_id, fp)
                except SubmissionError as e:
                    logger.warning(
                        "Bugcrowd 附件上传失败 %s: %s", fp, e
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
        """查询 Bugcrowd submission 状态.

        Args:
            report_id: Bugcrowd submission UUID

        Returns:
            包含最新状态的 SubmissionResult
        """
        self.validate_config()

        response = await self._request("GET", f"/submissions/{report_id}")
        data = self._safe_json(response)

        report_url = ""
        status = ""

        if isinstance(data, dict):
            sub_data = data.get("data", {})
            links = data.get("links", {})
            report_url = links.get("self", "")
            attr = sub_data.get("attributes", {})
            status = attr.get("state", "")

        return SubmissionResult(
            success=True,
            platform=self.PLATFORM_NAME,
            report_id=report_id,
            url=report_url,
            status=status,
            raw_response=data,
        )
