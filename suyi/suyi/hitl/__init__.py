"""Suyi Human-in-the-loop 模块 — 人工确认交互.

提供确认请求管理、策略引擎和中间件集成:

    HITLManager      — 管理需要人工确认的操作（队列/回调/超时/批量确认）
    HITLPolicy       — 确认策略（工具名/参数内容/风险评分/学习模式）
    HITLMiddleware   — 中间件集成（priority=35，循环检测之后，澄清之前）

使用示例::

    from suyi.hitl import HITLManager, HITLPolicy, HITLMiddleware

    manager = HITLManager()
    policy = HITLPolicy()
    mw = HITLMiddleware(manager=manager, policy=policy)

    # 注册确认回调
    async def on_confirm(operation_id: str, approved: bool):
        ...

    manager.register_callback("op-123", on_confirm)

    # 创建确认请求
    req = manager.create_request(
        operation="bash:rm -rf /tmp",
        arguments={"command": "rm -rf /tmp"},
        risk_level="high",
        description="Delete temporary directory",
    )

    # 用户确认
    manager.approve(req.id)
"""

from .manager import HITLManager, ConfirmationRequest, ConfirmationStatus
from .policy import HITLPolicy, RiskScore
from .middleware import HITLMiddleware

__all__ = [
    "HITLManager",
    "ConfirmationRequest",
    "ConfirmationStatus",
    "HITLPolicy",
    "RiskScore",
    "HITLMiddleware",
]
