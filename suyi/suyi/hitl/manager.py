"""HITL 管理器 — 管理需要人工确认的操作.

功能:
    - 确认请求队列: pending / approved / rejected / expired
    - 确认请求: operation, arguments, risk_level, description, timeout
    - 确认回调: register_callback(operation_id, callback)
    - 超时处理: 默认 5 分钟超时自动拒绝
    - 批量确认: 支持一次确认多个低风险操作
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


# ── 确认状态常量 ──────────────────────────────────────────────

class ConfirmationStatus:
    """确认请求状态常量."""

    PENDING: str = "pending"
    APPROVED: str = "approved"
    REJECTED: str = "rejected"
    EXPIRED: str = "expired"


# ── 风险等级 ──────────────────────────────────────────────────

class RiskLevel:
    """风险等级常量."""

    LOW: str = "low"
    MEDIUM: str = "medium"
    HIGH: str = "high"
    CRITICAL: str = "critical"


# ── 确认请求 ──────────────────────────────────────────────────


@dataclass
class ConfirmationRequest:
    """确认请求.

    Attributes:
        id:          请求唯一 ID.
        operation:   操作描述（如 'bash:rm -rf /tmp'）.
        arguments:   操作参数.
        risk_level:  风险等级（low/medium/high/critical）.
        description: 人类可读的操作描述.
        timeout:     超时时间（秒），超时后自动拒绝.
        created_at:  创建时间戳.
        resolved_at: 解决时间戳.
        status:      当前状态（pending/approved/rejected/expired）.
        resolved_by: 解决者（user/auto）.
    """

    id: str = ""
    operation: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = RiskLevel.MEDIUM
    description: str = ""
    timeout: float = 300.0  # 默认 5 分钟
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    status: str = ConfirmationStatus.PENDING
    resolved_by: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())

    @property
    def is_pending(self) -> bool:
        """是否处于待确认状态."""
        return self.status == ConfirmationStatus.PENDING

    @property
    def is_expired(self) -> bool:
        """是否已超时."""
        if self.status != ConfirmationStatus.PENDING:
            return False
        return (time.time() - self.created_at) > self.timeout

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "operation": self.operation,
            "arguments": self.arguments,
            "risk_level": self.risk_level,
            "description": self.description,
            "timeout": self.timeout,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "status": self.status,
            "resolved_by": self.resolved_by,
        }


# 回调类型
ConfirmationCallback = Callable[[str, bool], Awaitable[None]]


# ── HITL 管理器 ───────────────────────────────────────────────


class HITLManager:
    """Human-in-the-loop 确认管理器.

    管理需要人工确认的操作的生命周期:
        1. 创建确认请求 → pending
        2. 用户确认 → approved / rejected
        3. 超时 → expired（自动拒绝）
        4. 回调通知

    支持批量确认低风险操作.

    Args:
        default_timeout: 默认超时时间（秒，默认 300 = 5 分钟）.
        auto_expire:     是否自动检查过期请求（默认 True）.
        batch_threshold: 批量确认的最大风险等级（默认 low）.

    使用示例::

        manager = HITLManager()

        # 创建确认请求
        req = manager.create_request(
            operation="bash:git push",
            arguments={"command": "git push origin main"},
            risk_level="medium",
            description="Push to remote repository",
        )

        # 注册回调
        async def callback(op_id: str, approved: bool):
            print(f"Operation {op_id} {'approved' if approved else 'rejected'}")

        manager.register_callback(req.id, callback)

        # 用户确认
        manager.approve(req.id)  # → 触发回调

        # 批量确认低风险操作
        manager.batch_approve(["req-1", "req-2"])
    """

    def __init__(
        self,
        default_timeout: float = 300.0,
        auto_expire: bool = True,
        batch_threshold: str = RiskLevel.LOW,
    ) -> None:
        self.default_timeout: float = default_timeout
        self.auto_expire: bool = auto_expire
        self.batch_threshold: str = batch_threshold

        self._requests: Dict[str, ConfirmationRequest] = {}
        self._callbacks: Dict[str, ConfirmationCallback] = {}
        self._pending_order: List[str] = []  # 保持创建顺序

    # ── 创建请求 ──────────────────────────────────────────────

    def create_request(
        self,
        operation: str,
        arguments: Optional[Dict[str, Any]] = None,
        risk_level: str = RiskLevel.MEDIUM,
        description: str = "",
        timeout: Optional[float] = None,
    ) -> ConfirmationRequest:
        """创建确认请求.

        Args:
            operation:   操作描述（如 'bash:rm -rf /tmp'）.
            arguments:   操作参数.
            risk_level:  风险等级（low/medium/high/critical）.
            description: 人类可读描述.
            timeout:     超时时间（None 使用默认值）.

        Returns:
            创建的 ConfirmationRequest.
        """
        req: ConfirmationRequest = ConfirmationRequest(
            operation=operation,
            arguments=arguments or {},
            risk_level=risk_level,
            description=description,
            timeout=timeout if timeout is not None else self.default_timeout,
        )
        self._requests[req.id] = req
        self._pending_order.append(req.id)
        return req

    # ── 确认/拒绝 ──────────────────────────────────────────────

    def approve(self, request_id: str) -> bool:
        """批准确认请求.

        Args:
            request_id: 请求 ID.

        Returns:
            True 如果成功批准，False 如果请求不存在或不在 pending 状态.
        """
        return self._resolve(
            request_id,
            ConfirmationStatus.APPROVED,
            resolved_by="user",
        )

    def reject(self, request_id: str) -> bool:
        """拒绝确认请求.

        Args:
            request_id: 请求 ID.

        Returns:
            True 如果成功拒绝，False 如果请求不存在或不在 pending 状态.
        """
        return self._resolve(
            request_id,
            ConfirmationStatus.REJECTED,
            resolved_by="user",
        )

    def _resolve(
        self,
        request_id: str,
        status: str,
        resolved_by: str = "user",
    ) -> bool:
        """内部方法：解决确认请求.

        Args:
            request_id:  请求 ID.
            status:      新状态.
            resolved_by: 解决者.

        Returns:
            True 如果成功解决.
        """
        req: Optional[ConfirmationRequest] = self._requests.get(request_id)
        if req is None or not req.is_pending:
            return False

        # 检查是否已过期
        if self.auto_expire and req.is_expired:
            req.status = ConfirmationStatus.EXPIRED
            req.resolved_at = time.time()
            req.resolved_by = "auto"
            return False

        req.status = status
        req.resolved_at = time.time()
        req.resolved_by = resolved_by

        # 从 pending 队列移除
        if request_id in self._pending_order:
            self._pending_order.remove(request_id)

        return True

    # ── 批量确认 ──────────────────────────────────────────────

    def batch_approve(
        self, request_ids: List[str]
    ) -> Dict[str, bool]:
        """批量批准确认请求.

        仅批准风险等级 <= batch_threshold 的请求.

        Args:
            request_ids: 请求 ID 列表.

        Returns:
            每个请求 ID 到是否成功的映射.
        """
        results: Dict[str, bool] = {}
        for req_id in request_ids:
            req: Optional[ConfirmationRequest] = self._requests.get(req_id)
            if req is None or not req.is_pending:
                results[req_id] = False
                continue

            # 检查风险等级
            if self._risk_at_or_below(req.risk_level, self.batch_threshold):
                results[req_id] = self.approve(req_id)
            else:
                results[req_id] = False

        return results

    @staticmethod
    def _risk_at_or_below(level: str, threshold: str) -> bool:
        """检查风险等级是否 <= 阈值.

        Args:
            level:     实际风险等级.
            threshold: 阈值风险等级.

        Returns:
            True 如果 level <= threshold.
        """
        order: Dict[str, int] = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        return order.get(level, 1) <= order.get(threshold, 0)

    # ── 超时处理 ──────────────────────────────────────────────

    def expire_pending(self) -> List[str]:
        """过期所有超时的 pending 请求.

        Returns:
            被过期的请求 ID 列表.
        """
        expired_ids: List[str] = []
        now: float = time.time()
        for req in self._requests.values():
            if req.is_pending and (now - req.created_at) > req.timeout:
                req.status = ConfirmationStatus.EXPIRED
                req.resolved_at = now
                req.resolved_by = "auto"
                expired_ids.append(req.id)
                if req.id in self._pending_order:
                    self._pending_order.remove(req.id)
        return expired_ids

    # ── 查询 ──────────────────────────────────────────────────

    def get_request(self, request_id: str) -> Optional[ConfirmationRequest]:
        """获取确认请求.

        Args:
            request_id: 请求 ID.

        Returns:
            ConfirmationRequest 或 None.
        """
        return self._requests.get(request_id)

    def get_pending(self) -> List[ConfirmationRequest]:
        """获取所有 pending 请求.

        Returns:
            pending 请求列表（按创建顺序）.
        """
        self.expire_pending()
        return [
            self._requests[rid]
            for rid in self._pending_order
            if rid in self._requests
            and self._requests[rid].is_pending
        ]

    def get_by_status(self, status: str) -> List[ConfirmationRequest]:
        """获取指定状态的请求.

        Args:
            status: 状态（pending/approved/rejected/expired）.

        Returns:
            请求列表.
        """
        return [r for r in self._requests.values() if r.status == status]

    def is_approved(self, request_id: str) -> bool:
        """检查请求是否已批准.

        Args:
            request_id: 请求 ID.

        Returns:
            True 如果已批准.
        """
        req: Optional[ConfirmationRequest] = self._requests.get(request_id)
        return req is not None and req.status == ConfirmationStatus.APPROVED

    def is_rejected(self, request_id: str) -> bool:
        """检查请求是否已拒绝.

        Args:
            request_id: 请求 ID.

        Returns:
            True 如果已拒绝或已过期.
        """
        req: Optional[ConfirmationRequest] = self._requests.get(request_id)
        return req is not None and req.status in (
            ConfirmationStatus.REJECTED,
            ConfirmationStatus.EXPIRED,
        )

    # ── 回调 ──────────────────────────────────────────────────

    def register_callback(
        self,
        request_id: str,
        callback: ConfirmationCallback,
    ) -> None:
        """注册确认回调.

        当请求被批准或拒绝时调用回调.
        回调接收 (request_id, approved) 参数.

        Args:
            request_id: 请求 ID.
            callback:  异步回调函数.
        """
        self._callbacks[request_id] = callback

    def get_callback(
        self, request_id: str
    ) -> Optional[ConfirmationCallback]:
        """获取已注册的回调.

        Args:
            request_id: 请求 ID.

        Returns:
            回调函数或 None.
        """
        return self._callbacks.get(request_id)

    # ── 清理 ──────────────────────────────────────────────────

    def clear(self) -> None:
        """清除所有请求和回调."""
        self._requests.clear()
        self._callbacks.clear()
        self._pending_order.clear()

    def clear_resolved(self) -> None:
        """清除已解决的请求（approved/rejected/expired）."""
        to_remove: List[str] = [
            rid for rid, req in self._requests.items()
            if req.status != ConfirmationStatus.PENDING
        ]
        for rid in to_remove:
            self._requests.pop(rid, None)
            self._callbacks.pop(rid, None)
            if rid in self._pending_order:
                self._pending_order.remove(rid)

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        """返回请求统计.

        Returns:
            各状态请求数的字典.
        """
        counts: Dict[str, int] = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
            "total": len(self._requests),
        }
        for req in self._requests.values():
            if req.status in counts:
                counts[req.status] += 1
        return counts
