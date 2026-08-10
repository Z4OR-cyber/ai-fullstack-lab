"""
Suyi RBAC — Role-Based Access Control.

基于角色的访问控制模块，构建在现有 ``AuthManager`` 认证层之上，
提供角色定义、权限矩阵、角色分配与权限检查.

纯 Python 标准库实现（enum / dataclasses / typing），不引入新依赖.
支持 ``SQLiteBackend`` 持久化（namespace ``rbac:``），也支持内存模式.

功能概述
--------

1. **角色定义**
   - ``Role`` enum: ``ADMIN`` / ``DEVELOPER`` / ``OPERATOR`` / ``VIEWER``
   - 每个角色对应预定义的权限集

2. **权限定义**
   - ``Permission`` enum: ``READ`` / ``WRITE`` / ``EXECUTE`` /
     ``DELETE`` / ``MANAGE_USERS`` / ``VIEW_AUDIT_LOG``

3. **角色-权限矩阵**
   - ``ROLE_PERMISSIONS`` 定义每个角色的权限集
   - ADMIN 拥有全部权限
   - 权限检查支持角色继承（ADMIN 包含所有其他角色的权限）

4. **RBACManager**
   - ``assign_role(user_id, role)`` — 分配角色
   - ``revoke_role(user_id)`` — 撤销角色
   - ``check_permission(user_id, permission)`` — 检查权限
   - ``get_user_role(user_id)`` — 获取角色
   - ``get_role_permissions(role)`` — 获取角色权限集
   - ``list_users_by_role(role)`` — 按角色列出用户
   - ``backend=None`` 时用内存 ``dict``，否则用 ``SQLiteBackend``

使用示例::

    from suyi.web.rbac import RBACManager, Role, Permission

    rbac = RBACManager()  # 内存模式
    rbac.assign_role("alice", Role.ADMIN)
    rbac.check_permission("alice", Permission.MANAGE_USERS)  # True
    rbac.check_permission("bob", Permission.READ)             # False
"""

from __future__ import annotations

import json
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ..persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  角色与权限枚举
# ═══════════════════════════════════════════════════════════════


class Role(Enum):
    """用户角色.

    层级从高到低:
        ADMIN > DEVELOPER > OPERATOR > VIEWER

    Attributes:
        ADMIN:     超级管理员，拥有全部权限.
        DEVELOPER: 开发者，可读写和执行.
        OPERATOR:  操作员，可查看和执行.
        VIEWER:    只读用户，仅可查看.
    """

    ADMIN = auto()
    DEVELOPER = auto()
    OPERATOR = auto()
    VIEWER = auto()


class Permission(Enum):
    """权限类型.

    Attributes:
        READ:           读取数据 / 查看资源.
        WRITE:          写入数据 / 修改资源.
        EXECUTE:        执行操作 / 运行工具.
        DELETE:         删除数据 / 资源.
        MANAGE_USERS:   管理用户（分配/撤销角色）.
        VIEW_AUDIT_LOG: 查看审计日志.
    """

    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    DELETE = auto()
    MANAGE_USERS = auto()
    VIEW_AUDIT_LOG = auto()


# ═══════════════════════════════════════════════════════════════
#  角色-权限矩阵
# ═══════════════════════════════════════════════════════════════


def _all_permissions() -> Set[Permission]:
    """返回全部权限集合."""
    return set(Permission)


#: 预定义角色-权限矩阵.
#: 每个角色映射到该角色拥有的权限集合.
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: _all_permissions(),
    Role.DEVELOPER: {
        Permission.READ,
        Permission.WRITE,
        Permission.EXECUTE,
        Permission.DELETE,
    },
    Role.OPERATOR: {
        Permission.READ,
        Permission.EXECUTE,
    },
    Role.VIEWER: {
        Permission.READ,
    },
}


# ═══════════════════════════════════════════════════════════════
#  序列化辅助
# ═══════════════════════════════════════════════════════════════


def permission_to_str(permission: Permission) -> str:
    """将 ``Permission`` 转为字符串名称."""
    return permission.name


def permission_from_str(name: str) -> Permission:
    """从字符串名称还原 ``Permission``.

    Raises:
        ValueError: 如果名称不合法.
    """
    return Permission[name.upper()]


def role_to_str(role: Role) -> str:
    """将 ``Role`` 转为字符串名称."""
    return role.name


def role_from_str(name: str) -> Role:
    """从字符串名称还原 ``Role``.

    Raises:
        ValueError: 如果名称不合法.
    """
    return Role[name.upper()]


def _serialize_permission_set(permissions: Set[Permission]) -> List[str]:
    """将权限集合序列化为字符串列表."""
    return sorted(p.name for p in permissions)


def _deserialize_permission_set(names: List[str]) -> Set[Permission]:
    """从字符串列表反序列化权限集合."""
    return {Permission[n] for n in names}


# ═══════════════════════════════════════════════════════════════
#  RBAC 管理器
# ═══════════════════════════════════════════════════════════════


class RBACManager:
    """RBAC 管理器 — 角色分配与权限检查.

    支持两种持久化模式:
        1. **内存模式** (``backend=None``): 使用内存 ``dict``,
           适合测试和临时使用.
        2. **SQLite 持久化**: 传入 ``SQLiteBackend`` 实例,
           用户-角色映射持久化到 ``kv_store`` 表,
           键名前缀 ``rbac:user:``.

    Args:
        backend: ``SQLiteBackend`` 实例.  为 ``None`` 时使用内存模式.

    Attributes:
        backend:         底层持久化后端.
        namespace:       键名前缀, 默认 ``rbac:user:``.
        _user_prefix:    用户角色键前缀.
    """

    #: 持久化键前缀.
    _USER_PREFIX: str = "rbac:user:"

    #: 存储全部用户-角色映射的索引键.
    _INDEX_KEY: str = "rbac:user_index"

    def __init__(self, backend: Optional[SQLiteBackend] = None) -> None:
        self.backend: Optional[SQLiteBackend] = backend
        self._user_prefix: str = self._USER_PREFIX
        # 内存模式的数据存储（仅在 backend=None 时使用）
        self._memory: Dict[str, str] = {}

    # ───────────────────────────────────────────────────────
    #  内部存储
    # ───────────────────────────────────────────────────────

    def _set_user_role(self, user_id: str, role_name: str) -> None:
        """存储用户-角色映射（内部方法）."""
        if self.backend is not None:
            self.backend.set(
                f"{self._user_prefix}{user_id}", {"role": role_name}
            )
        else:
            self._memory[user_id] = role_name

    def _get_user_role(self, user_id: str) -> Optional[str]:
        """读取用户-角色映射（内部方法）."""
        if self.backend is not None:
            data = self.backend.get(
                f"{self._user_prefix}{user_id}", None
            )
            if data is None:
                return None
            return data.get("role") if isinstance(data, dict) else None
        return self._memory.get(user_id)

    def _delete_user_role(self, user_id: str) -> bool:
        """删除用户-角色映射（内部方法）."""
        if self.backend is not None:
            return self.backend.delete(f"{self._user_prefix}{user_id}")
        if user_id in self._memory:
            del self._memory[user_id]
            return True
        return False

    def _get_all_user_roles(self) -> Dict[str, str]:
        """返回全部用户-角色映射.

        Returns:
            ``{user_id: role_name}`` 字典.
        """
        if self.backend is not None:
            keys = self.backend.list_keys(self._user_prefix)
            result: Dict[str, str] = {}
            for key in keys:
                data = self.backend.get(key, None)
                if data is not None and isinstance(data, dict):
                    # 从键名中提取 user_id
                    user_id = key[len(self._user_prefix):]
                    role_name = data.get("role")
                    if role_name is not None:
                        result[user_id] = role_name
            return result
        return dict(self._memory)

    # ───────────────────────────────────────────────────────
    #  公开 API
    # ───────────────────────────────────────────────────────

    def assign_role(self, user_id: str, role: Role) -> None:
        """为用户分配角色.

        若用户已有角色，则覆盖更新为新角色.

        Args:
            user_id: 用户唯一标识.
            role:    要分配的角色.

        Raises:
            ValueError: 如果 ``user_id`` 为空.
        """
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id 不能为空")
        self._set_user_role(user_id, role.name)

    def revoke_role(self, user_id: str) -> bool:
        """撤销用户的角色.

        Args:
            user_id: 用户唯一标识.

        Returns:
            ``True`` 如果用户有角色且已撤销;
            ``False`` 如果用户原本就没有角色.

        Raises:
            ValueError: 如果 ``user_id`` 为空.
        """
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id 不能为空")
        return self._delete_user_role(user_id)

    def get_user_role(self, user_id: str) -> Optional[Role]:
        """获取用户的角色.

        Args:
            user_id: 用户唯一标识.

        Returns:
            ``Role`` 枚举值，或 ``None``（如果用户没有角色）.
        """
        role_name = self._get_user_role(user_id)
        if role_name is None:
            return None
        try:
            return role_from_str(role_name)
        except (KeyError, ValueError):
            return None

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """检查用户是否拥有指定权限.

        检查逻辑:
            1. 获取用户角色
            2. 查询角色权限矩阵
            3. 返回该权限是否在角色权限集合中

        若用户没有角色（未分配），返回 ``False``.

        Args:
            user_id:    用户唯一标识.
            permission: 要检查的权限.

        Returns:
            ``True`` 如果用户拥有该权限.
        """
        role = self.get_user_role(user_id)
        if role is None:
            return False
        role_perms = ROLE_PERMISSIONS.get(role, set())
        return permission in role_perms

    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """获取角色对应的权限集.

        Args:
            role: 角色枚举值.

        Returns:
            该角色的权限集合（返回副本，修改不影响原矩阵）.
        """
        return set(ROLE_PERMISSIONS.get(role, set()))

    def list_users_by_role(self, role: Role) -> List[str]:
        """按角色列出所有用户.

        Args:
            role: 要查询的角色.

        Returns:
            拥有该角色的用户 ID 列表（排序后）.
        """
        all_users = self._get_all_user_roles()
        return sorted(
            uid for uid, rname in all_users.items() if rname == role.name
        )

    def list_all_users(self) -> Dict[str, str]:
        """列出所有用户及其角色.

        Returns:
            ``{user_id: role_name}`` 字典.
        """
        return dict(self._get_all_user_roles())

    # ───────────────────────────────────────────────────────
    #  序列化与还原
    # ───────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 化的字典.

        Returns:
            包含全部用户-角色映射的字典.
        """
        users = self._get_all_user_roles()
        return {
            "users": [
                {"user_id": uid, "role": rname}
                for uid, rname in sorted(users.items())
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        backend: Optional[SQLiteBackend] = None,
    ) -> RBACManager:
        """从字典还原 RBACManager 实例.

        Args:
            data:    ``to_dict()`` 产生的字典.
            backend: 可选的持久化后端.

        Returns:
            新的 ``RBACManager`` 实例.
        """
        manager = cls(backend=backend)
        for entry in data.get("users", []):
            uid = entry["user_id"]
            rname = entry["role"]
            manager._set_user_role(uid, rname)
        return manager

    # ───────────────────────────────────────────────────────
    #  辅助
    # ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        count = len(self._get_all_user_roles())
        mode = "sqlite" if self.backend is not None else "memory"
        return f"RBACManager(mode={mode}, users={count})"


__all__ = [
    "Role",
    "Permission",
    "ROLE_PERMISSIONS",
    "RBACManager",
    "role_to_str",
    "role_from_str",
    "permission_to_str",
    "permission_from_str",
]
