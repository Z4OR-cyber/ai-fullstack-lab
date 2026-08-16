"""
Bounty Submission Adapter — 多平台漏洞赏金报告统一提交适配器.

支持的平台:
    - HackerOne (Basic Auth)
    - Bugcrowd (Token Header)
    - Intigriti (Bearer Token / OAuth PAT)
    - YesWeHack (Bearer Token / PAT)

核心设计:
    - :class:`BountyReport` 是统一的报告数据模型
    - 各平台适配器负责将 BountyReport 转换为平台特定 payload
    - :class:`BountyRouter` 统一管理多平台注册和路由
    - :class:`DraftStore` 提供草稿持久化，支持提交前审查
    - ``confirmed=True`` 才真正提交，``confirmed=False`` 只返回草稿
    - ``dry_run=True`` 只构建 payload 不发送网络请求

安全约束:
    - API Token 只能通过参数或环境变量传入，不能硬编码
    - 默认 ``confirmed=False``，防止误提交
    - 所有网络请求通过 httpx，timeout 不低于 30 秒

Usage::

    from suyi.integrations.bounty import (
        BountyReport, BountyRouter, PlatformConfig,
    )

    router = BountyRouter()
    router.register_platform(PlatformConfig(
        platform_name="hackerone",
        api_base="https://api.hackerone.com/v1",
        auth_type="basic_auth",
        credentials={"username": "user", "token": "tok"},
    ))

    report = BountyReport(
        title="XSS in search endpoint",
        vulnerability_information="Reflected XSS via q parameter...",
        impact="Session hijacking possible",
        severity="high",
        asset="example.com",
        endpoint_url="https://example.com/search?q=",
    )

    # 构建草稿审查
    draft = router.build_draft(report, "hackerone")
    print(draft.built_payload)

    # 确认后真正提交
    result = router.submit(report, "hackerone", confirmed=True)
"""

from .models import (
    BountyReport,
    SubmissionResult,
    PlatformConfig,
    DraftReport,
    SubmissionError,
)
from .base import BountyPlatformAdapter
from .platforms import (
    HackerOneAdapter,
    BugcrowdAdapter,
    IntigritiAdapter,
    YesWeHackAdapter,
)
from .router import BountyRouter
from .draft_store import DraftStore

__all__ = [
    # Models
    "BountyReport",
    "SubmissionResult",
    "PlatformConfig",
    "DraftReport",
    "SubmissionError",
    # Base
    "BountyPlatformAdapter",
    # Platform adapters
    "HackerOneAdapter",
    "BugcrowdAdapter",
    "IntigritiAdapter",
    "YesWeHackAdapter",
    # Router
    "BountyRouter",
    # Draft store
    "DraftStore",
]
