"""
Suyi Audit Log — 安全审计日志.

记录、查询和分析安全相关操作（成功、拒绝、错误）的审计日志模块.
构建在现有 ``SQLiteBackend`` 持久化层上，也可使用内存模式.

纯 Python 标准库实现（datetime / dataclasses / enum / typing），不引入新依赖.

功能概述
--------

1. **审计条目**
   - ``AuditEntry`` dataclass: 完整记录一次安全相关操作
   - 字段: timestamp, user_id, action, resource, resource_id,
     permission_required, result, ip_address, user_agent, details

2. **审计级别**
   - ``AuditLevel`` enum: ``INFO`` / ``WARNING`` / ``CRITICAL``
   - 成功操作 → INFO
   - 被拒绝 → WARNING
   - 错误 / 系统异常 → CRITICAL

3. **AuditLogger**
   - ``log(entry)`` — 记录审计条目
   - ``log_access(user_id, action, resource, result, **kwargs)`` — 便捷方法
   - ``query(filters)`` — 按条件查询
   - ``get_user_activity(user_id, limit)`` — 查询用户活动
   - ``get_denied_attempts(limit)`` — 查询被拒绝的访问
   - ``get_critical_events(limit)`` — 查询关键事件
   - 支持 ``SQLiteBackend`` 持久化（namespace ``audit:``）
   - ``backend=None`` 时用内存 ``list``

使用示例::

    from suyi.web.audit_log import AuditLogger, AuditEntry, AuditResult

    logger = AuditLogger()  # 内存模式
    logger.log_access(
        user_id="alice",
        action="DELETE",
        resource="/api/users/bob",
        result=AuditResult.SUCCESS,
    )
    denied = logger.get_denied_attempts(limit=10)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  枚举
# ═══════════════════════════════════════════════════════════════


class AuditResult(Enum):
    """审计操作结果.

    Attributes:
        SUCCESS: 操作成功.
        DENIED:  操作被拒绝（权限不足）.
        ERROR:   操作出错（系统异常）.
    """

    SUCCESS = auto()
    DENIED = auto()
    ERROR = auto()


class AuditLevel(Enum):
    """审计级别.

    Attributes:
        INFO:     常规信息（成功操作）.
        WARNING:  警告（被拒绝的访问）.
        CRITICAL: 关键（错误 / 系统异常）.
    """

    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


# ═══════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════


def _iso_timestamp() -> str:
    """返回 ISO-8601 UTC 时间戳字符串."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def result_to_level(result: AuditResult) -> AuditLevel:
    """根据操作结果推断审计级别.

    Mapping:
        - SUCCESS → INFO
        - DENIED  → WARNING
        - ERROR   → CRITICAL
    """
    return {
        AuditResult.SUCCESS: AuditLevel.INFO,
        AuditResult.DENIED: AuditLevel.WARNING,
        AuditResult.ERROR: AuditLevel.CRITICAL,
    }.get(result, AuditLevel.INFO)


def result_to_str(result: AuditResult) -> str:
    """将 ``AuditResult`` 转为字符串."""
    return result.name


def result_from_str(name: str) -> AuditResult:
    """从字符串还原 ``AuditResult``.

    Raises:
        ValueError: 如果名称不合法.
    """
    return AuditResult[name.upper()]


def level_to_str(level: AuditLevel) -> str:
    """将 ``AuditLevel`` 转为字符串."""
    return level.name


def level_from_str(name: str) -> AuditLevel:
    """从字符串还原 ``AuditLevel``.

    Raises:
        ValueError: 如果名称不合法.
    """
    return AuditLevel[name.upper()]


# ═══════════════════════════════════════════════════════════════
#  AuditEntry 数据类
# ═══════════════════════════════════════════════════════════════


@dataclass
class AuditEntry:
    """审计日志条目.

    Attributes:
        timestamp:           ISO-8601 UTC 时间戳.
        user_id:             执行操作的用户 ID.
        action:              操作类型（如 ``"DELETE"``、``"WRITE"``）.
        resource:            被访问的资源路径（如 ``"/api/users"``）.
        resource_id:         资源 ID（可选）.
        permission_required: 本次操作所需权限名称（可选）.
        result:              操作结果 (``SUCCESS`` / ``DENIED`` / ``ERROR``).
        level:               审计级别 (``INFO`` / ``WARNING`` / ``CRITICAL``).
        ip_address:          请求来源 IP（可选）.
        user_agent:          请求 User-Agent（可选）.
        details:             额外详情（字符串或 JSON 可序列化对象）.
    """

    timestamp: str = ""
    user_id: str = ""
    action: str = ""
    resource: str = ""
    resource_id: Optional[str] = None
    permission_required: Optional[str] = None
    result: AuditResult = AuditResult.SUCCESS
    level: AuditLevel = AuditLevel.INFO
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Any = None

    def __post_init__(self) -> None:
        """初始化后处理: 补全时间戳和审计级别."""
        if not self.timestamp:
            self.timestamp = _iso_timestamp()
        # 如果 level 与 result 不一致，优先以 result 推导
        expected_level = result_to_level(self.result)
        if self.level != expected_level:
            self.level = expected_level

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 化的字典.

        Returns:
            全部字段的字典表示，``result`` 和 ``level``
            以字符串名称存储.
        """
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "permission_required": self.permission_required,
            "result": result_to_str(self.result),
            "level": level_to_str(self.level),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuditEntry:
        """从字典还原 ``AuditEntry`` 实例.

        Args:
            data: ``to_dict()`` 产生的字典.

        Returns:
            新的 ``AuditEntry`` 实例.
        """
        result_name = data.get("result", "SUCCESS")
        level_name = data.get("level", "INFO")
        return cls(
            timestamp=data.get("timestamp", ""),
            user_id=data.get("user_id", ""),
            action=data.get("action", ""),
            resource=data.get("resource", ""),
            resource_id=data.get("resource_id"),
            permission_required=data.get("permission_required"),
            result=result_from_str(result_name),
            level=level_from_str(level_name),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            details=data.get("details"),
        )


# ═══════════════════════════════════════════════════════════════
#  AuditLogger 审计日志记录器
# ═══════════════════════════════════════════════════════════════


class AuditLogger:
    """审计日志记录器.

    支持两种持久化模式:
        1. **内存模式** (``backend=None``): 使用内存 ``list``,
           适合测试和临时使用.
        2. **SQLite 持久化**: 传入 ``SQLiteBackend`` 实例,
           审计条目持久化到 ``kv_store`` 表,
           键名前缀 ``audit:entry:``.

    Args:
        backend: ``SQLiteBackend`` 实例.  为 ``None`` 时使用内存模式.
    """

    #: 持久化键前缀.
    _ENTRY_PREFIX: str = "audit:entry:"

    def __init__(self, backend: Optional[SQLiteBackend] = None) -> None:
        self.backend: Optional[SQLiteBackend] = backend
        # 内存模式的数据存储
        self._memory: List[AuditEntry] = []
        # 自增计数器（用于生成唯一键）
        self._counter: int = 0

    # ───────────────────────────────────────────────────────
    #  内部存储
    # ───────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """生成下一个条目 ID.

        使用 ``时间戳毫秒 + 计数器`` 保证唯一性和大致有序.
        """
        self._counter += 1
        ms = int(time.time() * 1000)
        return f"{ms}_{self._counter:06d}"

    def _store_entry(self, entry: AuditEntry) -> str:
        """存储审计条目，返回其键名."""
        if self.backend is not None:
            entry_id = self._next_id()
            key = f"{self._ENTRY_PREFIX}{entry_id}"
            self.backend.set(key, entry.to_dict())
            return key
        else:
            self._memory.append(entry)
            return str(len(self._memory) - 1)

    def _load_all_entries(self) -> List[AuditEntry]:
        """加载全部审计条目（按时间戳排序）."""
        if self.backend is not None:
            keys = self.backend.list_keys(self._ENTRY_PREFIX)
            entries: List[AuditEntry] = []
            for key in keys:
                data = self.backend.get(key, None)
                if data is not None and isinstance(data, dict):
                    entries.append(AuditEntry.from_dict(data))
            # 按时间戳排序
            entries.sort(key=lambda e: e.timestamp)
            return entries
        return list(self._memory)

    # ───────────────────────────────────────────────────────
    #  公开 API — 记录
    # ───────────────────────────────────────────────────────

    def log(self, entry: AuditEntry) -> None:
        """记录审计条目.

        若 ``entry.timestamp`` 为空，自动补全当前 UTC 时间.
        若 ``entry.level`` 与 ``entry.result`` 不一致，以 result 推导.

        Args:
            entry: 审计条目.
        """
        self._store_entry(entry)

    def log_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        result: AuditResult = AuditResult.SUCCESS,
        *,
        resource_id: Optional[str] = None,
        permission_required: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Any = None,
        level: Optional[AuditLevel] = None,
    ) -> AuditEntry:
        """便捷方法 — 记录访问操作.

        构造 ``AuditEntry`` 并立即记录.

        Args:
            user_id:             用户 ID.
            action:              操作类型.
            resource:            资源路径.
            result:              操作结果，默认 ``SUCCESS``.
            resource_id:         资源 ID（可选）.
            permission_required: 所需权限名称（可选）.
            ip_address:          请求 IP（可选）.
            user_agent:          User-Agent（可选）.
            details:             额外详情（可选）.
            level:               审计级别，为 ``None`` 时自动从 result 推导.

        Returns:
            已记录的 ``AuditEntry`` 实例.
        """
        entry = AuditEntry(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            permission_required=permission_required,
            result=result,
            level=level or result_to_level(result),
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        self.log(entry)
        return entry

    # ───────────────────────────────────────────────────────
    #  公开 API — 查询
    # ───────────────────────────────────────────────────────

    def query(self, filters: Dict[str, Any]) -> List[AuditEntry]:
        """按条件查询审计条目.

        支持的过滤字段:
            - ``user_id``
            - ``action``
            - ``resource``
            - ``resource_id``
            - ``result`` (``AuditResult`` 或字符串名称)
            - ``level`` (``AuditLevel`` 或字符串名称)
            - ``ip_address``
            - ``permission_required``

        全部条件为 AND 关系；空字典返回全部.

        Args:
            filters: 过滤条件字典.

        Returns:
            匹配的审计条目列表（按时间戳升序）.
        """
        entries = self._load_all_entries()

        # 预处理 filters 中的枚举值
        normalized: Dict[str, str] = {}
        for key, value in filters.items():
            if isinstance(value, Enum):
                normalized[key] = value.name
            else:
                normalized[key] = str(value) if value is not None else None

        def _match(entry: AuditEntry) -> bool:
            entry_dict = entry.to_dict()
            for key, expected in normalized.items():
                if expected is None:
                    continue
                actual = entry_dict.get(key)
                if actual != expected:
                    return False
            return True

        return [e for e in entries if _match(e)]

    def get_user_activity(
        self, user_id: str, limit: int = 50
    ) -> List[AuditEntry]:
        """查询指定用户的活动记录.

        Args:
            user_id: 用户 ID.
            limit:   最大返回数量.

        Returns:
            该用户的审计条目列表（最新的在前）.
        """
        entries = self._load_all_entries()
        filtered = [e for e in entries if e.user_id == user_id]
        # 降序（最新在前）
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[:limit]

    def get_denied_attempts(
        self, limit: int = 50
    ) -> List[AuditEntry]:
        """查询被拒绝的访问记录.

        Args:
            limit: 最大返回数量.

        Returns:
            ``result == DENIED`` 的审计条目列表（最新的在前）.
        """
        entries = self._load_all_entries()
        filtered = [
            e for e in entries if e.result == AuditResult.DENIED
        ]
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[:limit]

    def get_critical_events(
        self, limit: int = 50
    ) -> List[AuditEntry]:
        """查询关键事件.

        Args:
            limit: 最大返回数量.

        Returns:
            ``level == CRITICAL`` 的审计条目列表（最新的在前）.
        """
        entries = self._load_all_entries()
        filtered = [
            e for e in entries if e.level == AuditLevel.CRITICAL
        ]
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[:limit]

    def count(self) -> int:
        """返回审计条目总数."""
        if self.backend is not None:
            return len(self.backend.list_keys(self._ENTRY_PREFIX))
        return len(self._memory)

    def clear(self) -> int:
        """清空全部审计条目.

        Returns:
            被清除的条目数量.
        """
        if self.backend is not None:
            keys = self.backend.list_keys(self._ENTRY_PREFIX)
            count = 0
            for key in keys:
                if self.backend.delete(key):
                    count += 1
            return count
        count = len(self._memory)
        self._memory.clear()
        self._counter = 0
        return count

    # ───────────────────────────────────────────────────────
    #  序列化与还原
    # ───────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 化的字典.

        Returns:
            包含全部审计条目的字典.
        """
        entries = self._load_all_entries()
        return {
            "entries": [e.to_dict() for e in entries],
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        backend: Optional[SQLiteBackend] = None,
    ) -> AuditLogger:
        """从字典还原 ``AuditLogger`` 实例.

        Args:
            data:    ``to_dict()`` 产生的字典.
            backend: 可选的持久化后端.

        Returns:
            新的 ``AuditLogger`` 实例.
        """
        logger = cls(backend=backend)
        for entry_dict in data.get("entries", []):
            logger.log(AuditEntry.from_dict(entry_dict))
        return logger

    # ───────────────────────────────────────────────────────
    #  辅助
    # ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        mode = "sqlite" if self.backend is not None else "memory"
        return f"AuditLogger(mode={mode}, count={self.count()})"


__all__ = [
    "AuditResult",
    "AuditLevel",
    "AuditEntry",
    "AuditLogger",
    "result_to_str",
    "result_from_str",
    "level_to_str",
    "level_from_str",
    "result_to_level",
]
