"""
Bounty submission data models.

定义漏洞赏金报告提交过程中使用的核心数据结构:
    - :class:`BountyReport`: 统一漏洞报告数据类
    - :class:`SubmissionResult`: 提交结果
    - :class:`PlatformConfig`: 平台连接配置
    - :class:`DraftReport`: 草稿（包含已构建的 payload）
    - :class:`SubmissionError`: 自定义异常
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# 合法的严重性等级
VALID_SEVERITIES = ("critical", "high", "medium", "low", "none")


class SubmissionError(Exception):
    """提交过程中的自定义异常.

    封装平台名、HTTP 状态码和响应体，便于上层统一错误处理。

    Attributes:
        platform: 发生错误的平台名称
        status_code: HTTP 状态码（网络层错误时可为 None）
        error_body: 平台返回的错误响应体（字符串或字典）
    """

    def __init__(
        self,
        message: str,
        platform: str = "",
        status_code: Optional[int] = None,
        error_body: Any = None,
    ):
        super().__init__(message)
        self.platform = platform
        self.status_code = status_code
        self.error_body = error_body

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.platform:
            parts.append(f"platform={self.platform}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " | ".join(parts)


@dataclass
class BountyReport:
    """统一漏洞报告数据类.

    各平台适配器将此结构转换为平台特定的 API payload。

    Attributes:
        title: 漏洞标题
        vulnerability_information: 漏洞详情（Markdown 格式）
        impact: 安全影响描述
        severity: 严重性等级 (critical/high/medium/low/none)
        weakness: CWE 名称（如 "Cross-site Scripting (XSS)"）
        cwe_id: CWE 编号（如 "CWE-79"）
        asset: 目标资产标识
        endpoint_url: 受影响的端点 URL
        attachments: 本地附件文件路径列表
        researcher_handle: 研究员用户名
        team_handle: HackerOne 团队 handle
        program_id: Intigriti 项目 ID
        program_slug: YesWeHack 项目 slug
        program_code: Bugcrowd 项目 code
        structured_scope_id: HackerOne scope ID
        weakness_id: HackerOne weakness ID
        asset_id: Intigriti 资产 ID
        cvss_vector: CVSS 向量字符串
        metadata: 平台特定的额外元数据
    """

    title: str
    vulnerability_information: str = ""
    impact: str = ""
    severity: str = "medium"
    weakness: str = ""
    cwe_id: str = ""
    asset: str = ""
    endpoint_url: str = ""
    attachments: List[str] = field(default_factory=list)
    researcher_handle: str = ""
    # 平台特定字段
    team_handle: str = ""
    program_id: str = ""
    program_slug: str = ""
    program_code: str = ""
    structured_scope_id: str = ""
    weakness_id: str = ""
    asset_id: str = ""
    cvss_vector: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验必填字段和 severity 合法性."""
        if not self.title or not self.title.strip():
            raise ValueError("BountyReport.title 不能为空")
        # 先规范化 severity 为小写
        self.severity = self.severity.lower()
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"severity 必须是 {VALID_SEVERITIES} 之一，得到: {self.severity!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "title": self.title,
            "vulnerability_information": self.vulnerability_information,
            "impact": self.impact,
            "severity": self.severity,
            "weakness": self.weakness,
            "cwe_id": self.cwe_id,
            "asset": self.asset,
            "endpoint_url": self.endpoint_url,
            "attachments": list(self.attachments),
            "researcher_handle": self.researcher_handle,
            "team_handle": self.team_handle,
            "program_id": self.program_id,
            "program_slug": self.program_slug,
            "program_code": self.program_code,
            "structured_scope_id": self.structured_scope_id,
            "weakness_id": self.weakness_id,
            "asset_id": self.asset_id,
            "cvss_vector": self.cvss_vector,
            "metadata": dict(self.metadata),
        }


@dataclass
class PlatformConfig:
    """平台连接配置.

    Attributes:
        platform_name: 平台标识名 (hackerone/bugcrowd/intigriti/yeswehack)
        api_base: API 基础 URL
        auth_type: 认证类型 (basic_auth/bearer_token/api_key_header)
        credentials: 凭证字典（不同 auth_type 使用不同 key）
        timeout: HTTP 请求超时秒数（最低 30 秒）
        extra_headers: 额外 HTTP 请求头
    """

    platform_name: str
    api_base: str
    auth_type: str = "bearer_token"
    credentials: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    extra_headers: Dict[str, str] = field(default_factory=dict)

    VALID_AUTH_TYPES = ("basic_auth", "bearer_token", "api_key_header")

    def __post_init__(self) -> None:
        """校验配置."""
        self.platform_name = self.platform_name.strip().lower()
        if not self.platform_name:
            raise ValueError("platform_name 不能为空")
        if self.auth_type not in self.VALID_AUTH_TYPES:
            raise ValueError(
                f"auth_type 必须是 {self.VALID_AUTH_TYPES} 之一，"
                f"得到: {self.auth_type!r}"
            )
        if self.timeout < 30.0:
            self.timeout = 30.0
        # 去除尾部斜杠
        self.api_base = self.api_base.rstrip("/")

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（脱敏凭证）."""
        return {
            "platform_name": self.platform_name,
            "api_base": self.api_base,
            "auth_type": self.auth_type,
            "credentials_keys": list(self.credentials.keys()),
            "timeout": self.timeout,
            "extra_headers": dict(self.extra_headers),
        }


@dataclass
class SubmissionResult:
    """提交结果.

    Attributes:
        success: 是否提交成功
        platform: 平台名称
        report_id: 平台返回的报告 ID
        url: 报告在平台上的查看 URL
        status: 报告状态（如 new/triaged/resolved）
        raw_response: 平台原始响应
        submitted_at: 提交时间戳
    """

    success: bool
    platform: str = ""
    report_id: str = ""
    url: str = ""
    status: str = ""
    raw_response: Any = None
    submitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "success": self.success,
            "platform": self.platform,
            "report_id": self.report_id,
            "url": self.url,
            "status": self.status,
            "raw_response": self.raw_response,
            "submitted_at": self.submitted_at,
        }


@dataclass
class DraftReport:
    """草稿报告，包含原始报告、目标平台和已构建的 payload.

    Attributes:
        report: 原始 BountyReport
        target_platform: 目标平台名称
        built_payload: 适配器构建的平台特定 payload
        created_at: 创建时间戳
        draft_id: 草稿唯一标识
        reviewed: 是否已审查
    """

    report: BountyReport
    target_platform: str
    built_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    draft_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    reviewed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "draft_id": self.draft_id,
            "target_platform": self.target_platform,
            "report": self.report.to_dict(),
            "built_payload": self.built_payload,
            "created_at": self.created_at,
            "reviewed": self.reviewed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DraftReport:
        """从字典反序列化."""
        report = BountyReport(**data["report"])
        return cls(
            report=report,
            target_platform=data["target_platform"],
            built_payload=data.get("built_payload", {}),
            created_at=data.get("created_at", time.time()),
            draft_id=data.get("draft_id", uuid.uuid4().hex[:12]),
            reviewed=data.get("reviewed", False),
        )
