"""HITL 中间件 — 在中间件链中集成人工确认交互.

钩子点:
    - before_tool_call: 检查工具调用是否需要确认
        根据 HITLPolicy 决策:
          - auto:   放行
          - confirm: 创建确认请求，暂停执行
          - block:   拒绝工具调用

    与现有 PermissionManager 集成:
        - 工具权限为 PERMISSION_CONFIRM 时，触发 HITL 确认流程
        - 用户确认 → 继续执行
        - 用户拒绝 → 跳过工具调用
        - 超时 → 自动拒绝

排序优先级: 35（在循环检测之后，澄清之前）.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.loop import LoopState
from ..middleware.base import MiddlewareBase
from ..tools.permissions import (
    PERMISSION_AUTO,
    PERMISSION_CONFIRM,
    PERMISSION_BLOCK,
)
from .manager import (
    HITLManager,
    ConfirmationRequest,
    ConfirmationStatus,
    RiskLevel,
)
from .policy import HITLPolicy, PolicyDecision

__all__ = ["HITLMiddleware"]


class HITLMiddleware(MiddlewareBase):
    """Human-in-the-loop 中间件.

    在 before_tool_call 钩子中检查工具调用是否需要人工确认.
    如果需要确认:
        1. 通过 HITLPolicy 评估操作
        2. 通过 HITLManager 创建确认请求
        3. 如果配置了 permission_callback，等待用户确认
        4. 用户确认 → 继续执行
        5. 用户拒绝 → 通过修改 tool_name 为空阻止执行

    Args:
        manager: 可选的 HITLManager 实例（不提供则创建默认）.
        policy:  可选的 HITLPolicy 实例（不提供则创建默认）.
        permission_manager: 可选的 PermissionManager 引用.

    使用示例::

        manager = HITLManager()
        policy = HITLPolicy()
        mw = HITLMiddleware(manager=manager, policy=policy)

        # 用户确认回调
        async def confirm_callback(tool_name, arguments) -> bool:
            req = manager.create_request(
                operation=tool_name,
                arguments=arguments,
                risk_level="medium",
            )
            # ... 等待用户确认 ...
            return manager.is_approved(req.id)

        loop = AgentLoop(
            middleware_chain=[mw],
            permission_callback=confirm_callback,
        )
    """

    def __init__(
        self,
        manager: Optional[HITLManager] = None,
        policy: Optional[HITLPolicy] = None,
        permission_manager: Optional[Any] = None,
    ) -> None:
        self.manager: HITLManager = manager or HITLManager()
        self.policy: HITLPolicy = policy or HITLPolicy()
        self.permission_manager = permission_manager

    @property
    def priority(self) -> int:
        """HITL 中间件优先级 35."""
        return 35

    # ── before_tool_call ───────────────────────────────────────

    async def before_tool_call(
        self, tool_name: str, arguments: dict, state: LoopState
    ) -> tuple[str, dict]:
        """在工具执行前检查是否需要人工确认.

        决策流程:
            1. HITLPolicy.check() 评估操作
            2. auto → 放行
            3. block → 通过清空 tool_name 阻止执行
            4. confirm → 创建确认请求，记录到 state.metadata
               （实际确认由 permission_callback 处理）

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.
            state: 当前循环状态.

        Returns:
            (tool_name, arguments) — 可能被修改.
        """
        # 策略检查
        decision: PolicyDecision = self.policy.check(tool_name, arguments)

        # 记录到 metadata
        hitl_logs: list = state.metadata.setdefault("hitl", [])
        hitl_logs.append({
            "tool": tool_name,
            "action": decision.action,
            "reason": decision.reason,
            "risk_score": decision.risk_score.to_dict(),
        })

        if decision.action == "block":
            # 阻止执行：清空 tool_name（AgentLoop 找不到工具会返回错误）
            state.metadata["hitl_blocked"] = True
            state.metadata["hitl_block_reason"] = decision.reason
            # 返回空名称，使 AgentLoop 找不到对应工具
            return "", arguments

        elif decision.action == "confirm":
            # 创建确认请求
            req: ConfirmationRequest = self.manager.create_request(
                operation=tool_name,
                arguments=arguments,
                risk_level=decision.risk_score.level,
                description=decision.reason,
            )

            # 记录到 metadata
            state.metadata["hitl_pending_request"] = req.id
            state.metadata["hitl_needs_confirmation"] = True

            # 记录操作到学习历史（稍后用户确认/拒绝时更新）
            # 这里只记录待确认状态

        # auto → 放行
        return tool_name, arguments

    # ── 确认流程辅助 ──────────────────────────────────────────

    def create_confirmation(
        self,
        tool_name: str,
        arguments: dict,
        risk_level: str = RiskLevel.MEDIUM,
        description: str = "",
    ) -> ConfirmationRequest:
        """创建确认请求（可从外部调用）.

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.
            risk_level: 风险等级.
            description: 描述.

        Returns:
            ConfirmationRequest.
        """
        return self.manager.create_request(
            operation=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            description=description,
        )

    def check_and_confirm(
        self,
        tool_name: str,
        arguments: dict,
    ) -> ConfirmationRequest:
        """检查策略并创建确认请求（如果需要）.

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.

        Returns:
            ConfirmationRequest（如果需要确认）.
        """
        decision: PolicyDecision = self.policy.check(tool_name, arguments)
        if decision.action == "confirm":
            return self.manager.create_request(
                operation=tool_name,
                arguments=arguments,
                risk_level=decision.risk_score.level,
                description=decision.reason,
            )
        # 不需要确认时返回一个空请求
        return ConfirmationRequest(
            operation=tool_name,
            arguments=arguments,
            status=ConfirmationStatus.APPROVED,
            risk_level=RiskLevel.LOW,
        )

    def resolve_and_learn(
        self,
        request_id: str,
        approved: bool,
    ) -> bool:
        """解决确认请求并记录到学习历史.

        Args:
            request_id: 请求 ID.
            approved: 是否批准.

        Returns:
            True 如果成功解决.
        """
        req: Optional[ConfirmationRequest] = self.manager.get_request(
            request_id
        )
        if req is None or not req.is_pending:
            return False

        # 解决请求
        if approved:
            self.manager.approve(request_id)
        else:
            self.manager.reject(request_id)

        # 记录到学习历史
        command: str = req.arguments.get("command", "") if req.arguments else ""
        operation: str = command or req.operation
        self.policy.record(
            tool_name=req.operation.split(":")[0] if ":" in req.operation else req.operation,
            operation=operation,
            approved=approved,
        )

        return True

    # ── 查询 ──────────────────────────────────────────────────

    def get_pending_confirmations(self) -> list:
        """获取所有待确认请求.

        Returns:
            pending 请求列表.
        """
        return self.manager.get_pending()

    def is_tool_allowed(
        self,
        tool_name: str,
        arguments: dict,
    ) -> bool:
        """检查工具是否被允许执行（不需要确认）.

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.

        Returns:
            True 如果工具可以自动执行.
        """
        decision: PolicyDecision = self.policy.check(tool_name, arguments)
        return decision.action == "auto"
