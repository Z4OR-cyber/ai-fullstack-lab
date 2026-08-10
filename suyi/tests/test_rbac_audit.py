"""
Suyi RBAC + AuditLog 测试套件.

覆盖范围:
    - RolePermission 矩阵正确性 (8 tests)
    - RBACManager 分配/撤销/检查/查询/持久化 (16 tests)
    - AuditLogger 记录/查询/过滤/持久化 (14 tests)
    - 集成测试: RBAC + Audit 联合 (6 tests)
    - 异常输入处理 (6 tests)

共 50 个测试.
"""

import time

import pytest

from suyi.web.rbac import (
    RBACManager,
    Role,
    Permission,
    ROLE_PERMISSIONS,
    role_to_str,
    role_from_str,
    permission_to_str,
    permission_from_str,
)
from suyi.web.audit_log import (
    AuditLogger,
    AuditEntry,
    AuditResult,
    AuditLevel,
    result_to_str,
    result_from_str,
    level_to_str,
    level_from_str,
    result_to_level,
)
from suyi.persistence import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def rbac_memory():
    """内存模式 RBACManager."""
    return RBACManager(backend=None)


@pytest.fixture
def rbac_sqlite(tmp_path):
    """SQLite 持久化模式 RBACManager."""
    backend = SQLiteBackend(str(tmp_path / "test_rbac.db"))
    return RBACManager(backend=backend)


@pytest.fixture
def audit_memory():
    """内存模式 AuditLogger."""
    return AuditLogger(backend=None)


@pytest.fixture
def audit_sqlite(tmp_path):
    """SQLite 持久化模式 AuditLogger."""
    backend = SQLiteBackend(str(tmp_path / "test_audit.db"))
    return AuditLogger(backend=backend)


# ═══════════════════════════════════════════════════════════════
#  Part 1 — RolePermission 矩阵正确性
# ═══════════════════════════════════════════════════════════════


class TestRolePermissionMatrix:
    """角色-权限矩阵正确性."""

    def test_admin_has_all_permissions(self):
        """ADMIN 拥有全部 6 个权限."""
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert perms == set(Permission)
        assert len(perms) == 6

    def test_developer_permissions(self):
        """DEVELOPER 拥有 READ/WRITE/EXECUTE/DELETE."""
        perms = ROLE_PERMISSIONS[Role.DEVELOPER]
        assert Permission.READ in perms
        assert Permission.WRITE in perms
        assert Permission.EXECUTE in perms
        assert Permission.DELETE in perms
        assert Permission.MANAGE_USERS not in perms
        assert Permission.VIEW_AUDIT_LOG not in perms

    def test_operator_permissions(self):
        """OPERATOR 拥有 READ/EXECUTE."""
        perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.READ in perms
        assert Permission.EXECUTE in perms
        assert Permission.WRITE not in perms
        assert Permission.DELETE not in perms
        assert Permission.MANAGE_USERS not in perms
        assert Permission.VIEW_AUDIT_LOG not in perms

    def test_viewer_permissions(self):
        """VIEWER 仅拥有 READ."""
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert perms == {Permission.READ}

    def test_role_hierarchy_admin_superset(self):
        """ADMIN 权限是所有其他角色的超集."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        for role in [Role.DEVELOPER, Role.OPERATOR, Role.VIEWER]:
            assert ROLE_PERMISSIONS[role].issubset(admin_perms)

    def test_developer_superset_of_operator(self):
        """DEVELOPER 权限是 OPERATOR 的超集."""
        dev_perms = ROLE_PERMISSIONS[Role.DEVELOPER]
        op_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert op_perms.issubset(dev_perms)

    def test_operator_superset_of_viewer(self):
        """OPERATOR 权限是 VIEWER 的超集."""
        op_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert viewer_perms.issubset(op_perms)

    def test_all_roles_cover_all_permissions(self):
        """所有角色的权限集合并起来覆盖全部权限."""
        all_perms = set()
        for role in Role:
            all_perms |= ROLE_PERMISSIONS[role]
        assert all_perms == set(Permission)


# ═══════════════════════════════════════════════════════════════
#  Part 2 — RBACManager 测试
# ═══════════════════════════════════════════════════════════════


class TestRBACManagerMemory:
    """内存模式 RBACManager 操作."""

    def test_assign_role(self, rbac_memory):
        """分配角色后可获取."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        assert rbac_memory.get_user_role("alice") == Role.ADMIN

    def test_assign_role_overwrite(self, rbac_memory):
        """重复分配角色会覆盖."""
        rbac_memory.assign_role("alice", Role.VIEWER)
        rbac_memory.assign_role("alice", Role.ADMIN)
        assert rbac_memory.get_user_role("alice") == Role.ADMIN

    def test_revoke_role(self, rbac_memory):
        """撤销角色后用户无角色."""
        rbac_memory.assign_role("alice", Role.DEVELOPER)
        assert rbac_memory.revoke_role("alice") is True
        assert rbac_memory.get_user_role("alice") is None

    def test_revoke_nonexistent_role(self, rbac_memory):
        """撤销不存在角色的用户返回 False."""
        assert rbac_memory.revoke_role("nobody") is False

    def test_check_permission_admin(self, rbac_memory):
        """ADMIN 通过所有权限检查."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        for perm in Permission:
            assert rbac_memory.check_permission("alice", perm) is True

    def test_check_permission_viewer(self, rbac_memory):
        """VIEWER 只能通过 READ 检查."""
        rbac_memory.assign_role("bob", Role.VIEWER)
        assert rbac_memory.check_permission("bob", Permission.READ) is True
        assert rbac_memory.check_permission("bob", Permission.WRITE) is False
        assert rbac_memory.check_permission("bob", Permission.DELETE) is False
        assert (
            rbac_memory.check_permission("bob", Permission.MANAGE_USERS)
            is False
        )

    def test_check_permission_no_role(self, rbac_memory):
        """没有角色的用户所有权限检查均失败."""
        for perm in Permission:
            assert rbac_memory.check_permission("ghost", perm) is False

    def test_get_role_permissions_returns_copy(self, rbac_memory):
        """get_role_permissions 返回副本，修改不影响矩阵."""
        perms = rbac_memory.get_role_permissions(Role.ADMIN)
        perms.add(Permission.READ)  # 已存在
        # 原矩阵不应被修改
        original = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.READ in original

    def test_list_users_by_role(self, rbac_memory):
        """按角色列出用户."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        rbac_memory.assign_role("bob", Role.VIEWER)
        rbac_memory.assign_role("carol", Role.VIEWER)
        viewers = rbac_memory.list_users_by_role(Role.VIEWER)
        assert viewers == ["bob", "carol"]
        admins = rbac_memory.list_users_by_role(Role.ADMIN)
        assert admins == ["alice"]

    def test_list_users_by_role_empty(self, rbac_memory):
        """空角色列表返回空列表."""
        assert rbac_memory.list_users_by_role(Role.ADMIN) == []

    def test_list_all_users(self, rbac_memory):
        """列出所有用户及其角色."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        rbac_memory.assign_role("bob", Role.VIEWER)
        all_users = rbac_memory.list_all_users()
        assert all_users["alice"] == "ADMIN"
        assert all_users["bob"] == "VIEWER"

    def test_assign_multiple_users_different_roles(self, rbac_memory):
        """分配多个用户不同角色."""
        rbac_memory.assign_role("a1", Role.ADMIN)
        rbac_memory.assign_role("a2", Role.DEVELOPER)
        rbac_memory.assign_role("a3", Role.OPERATOR)
        rbac_memory.assign_role("a4", Role.VIEWER)
        assert rbac_memory.get_user_role("a1") == Role.ADMIN
        assert rbac_memory.get_user_role("a2") == Role.DEVELOPER
        assert rbac_memory.get_user_role("a3") == Role.OPERATOR
        assert rbac_memory.get_user_role("a4") == Role.VIEWER

    def test_to_dict_and_from_dict(self, rbac_memory):
        """序列化和反序列化往返."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        rbac_memory.assign_role("bob", Role.VIEWER)
        data = rbac_memory.to_dict()
        restored = RBACManager.from_dict(data)
        assert restored.get_user_role("alice") == Role.ADMIN
        assert restored.get_user_role("bob") == Role.VIEWER

    def test_repr(self, rbac_memory):
        """repr 包含模式和用户数."""
        rbac_memory.assign_role("alice", Role.ADMIN)
        repr_str = repr(rbac_memory)
        assert "memory" in repr_str
        assert "users=1" in repr_str


class TestRBACManagerSQLite:
    """SQLite 持久化模式 RBACManager."""

    def test_sqlite_assign_and_get(self, rbac_sqlite):
        """SQLite 模式分配角色后可获取."""
        rbac_sqlite.assign_role("alice", Role.ADMIN)
        assert rbac_sqlite.get_user_role("alice") == Role.ADMIN

    def test_sqlite_persistence_across_instances(self, tmp_path):
        """SQLite 持久化：新实例能读取之前的数据."""
        db_path = str(tmp_path / "persist_rbac.db")
        backend1 = SQLiteBackend(db_path)
        rbac1 = RBACManager(backend=backend1)
        rbac1.assign_role("alice", Role.DEVELOPER)
        rbac1.assign_role("bob", Role.VIEWER)
        backend1.close()

        # 新后端实例读取同一数据库
        backend2 = SQLiteBackend(db_path)
        rbac2 = RBACManager(backend=backend2)
        assert rbac2.get_user_role("alice") == Role.DEVELOPER
        assert rbac2.get_user_role("bob") == Role.VIEWER
        backend2.close()

    def test_sqlite_revoke(self, rbac_sqlite):
        """SQLite 模式撤销角色."""
        rbac_sqlite.assign_role("alice", Role.ADMIN)
        assert rbac_sqlite.revoke_role("alice") is True
        assert rbac_sqlite.get_user_role("alice") is None

    def test_sqlite_list_users_by_role(self, rbac_sqlite):
        """SQLite 模式按角色列出用户."""
        rbac_sqlite.assign_role("a1", Role.ADMIN)
        rbac_sqlite.assign_role("a2", Role.VIEWER)
        rbac_sqlite.assign_role("a3", Role.VIEWER)
        viewers = rbac_sqlite.list_users_by_role(Role.VIEWER)
        assert sorted(viewers) == ["a2", "a3"]
        admins = rbac_sqlite.list_users_by_role(Role.ADMIN)
        assert admins == ["a1"]


# ═══════════════════════════════════════════════════════════════
#  Part 3 — AuditLogger 测试
# ═══════════════════════════════════════════════════════════════


class TestAuditEntry:
    """AuditEntry 数据类测试."""

    def test_entry_auto_timestamp(self):
        """AuditEntry 自动补全时间戳."""
        entry = AuditEntry(user_id="alice", action="READ", resource="/api")
        assert entry.timestamp != ""
        assert entry.timestamp.endswith("Z")

    def test_entry_result_to_level(self):
        """不同 result 自动推导 level."""
        assert result_to_level(AuditResult.SUCCESS) == AuditLevel.INFO
        assert result_to_level(AuditResult.DENIED) == AuditLevel.WARNING
        assert result_to_level(AuditResult.ERROR) == AuditLevel.CRITICAL

    def test_entry_post_init_level_sync(self):
        """__post_init__ 同步 level 与 result."""
        entry = AuditEntry(
            user_id="alice",
            action="DELETE",
            resource="/api",
            result=AuditResult.DENIED,
        )
        assert entry.level == AuditLevel.WARNING

    def test_entry_to_dict_and_from_dict(self):
        """序列化往返."""
        entry = AuditEntry(
            user_id="alice",
            action="DELETE",
            resource="/api/users/bob",
            resource_id="bob",
            permission_required="DELETE",
            result=AuditResult.DENIED,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
            details={"reason": "insufficient permissions"},
        )
        d = entry.to_dict()
        assert d["result"] == "DENIED"
        assert d["level"] == "WARNING"
        restored = AuditEntry.from_dict(d)
        assert restored.user_id == "alice"
        assert restored.result == AuditResult.DENIED
        assert restored.level == AuditLevel.WARNING
        assert restored.ip_address == "10.0.0.1"
        assert restored.details == {"reason": "insufficient permissions"}


class TestAuditLoggerMemory:
    """内存模式 AuditLogger 操作."""

    def test_log_entry(self, audit_memory):
        """log() 记录条目."""
        entry = AuditEntry(user_id="alice", action="READ", resource="/api")
        audit_memory.log(entry)
        assert audit_memory.count() == 1

    def test_log_access_convenience(self, audit_memory):
        """log_access() 便捷方法."""
        entry = audit_memory.log_access(
            user_id="alice",
            action="WRITE",
            resource="/api/data",
            result=AuditResult.SUCCESS,
        )
        assert entry.user_id == "alice"
        assert entry.action == "WRITE"
        assert entry.result == AuditResult.SUCCESS
        assert entry.level == AuditLevel.INFO
        assert audit_memory.count() == 1

    def test_log_access_denied_auto_level(self, audit_memory):
        """log_access DENIED 自动设为 WARNING."""
        entry = audit_memory.log_access(
            user_id="bob",
            action="DELETE",
            resource="/api/users",
            result=AuditResult.DENIED,
        )
        assert entry.level == AuditLevel.WARNING

    def test_get_user_activity(self, audit_memory):
        """查询用户活动."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("alice", "WRITE", "/b", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "READ", "/c", AuditResult.SUCCESS)
        alice_activity = audit_memory.get_user_activity("alice", limit=10)
        assert len(alice_activity) == 2
        for entry in alice_activity:
            assert entry.user_id == "alice"

    def test_get_denied_attempts(self, audit_memory):
        """查询被拒绝的访问."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "DELETE", "/b", AuditResult.DENIED)
        audit_memory.log_access("carol", "WRITE", "/c", AuditResult.DENIED)
        denied = audit_memory.get_denied_attempts(limit=10)
        assert len(denied) == 2
        for entry in denied:
            assert entry.result == AuditResult.DENIED

    def test_get_critical_events(self, audit_memory):
        """查询关键事件."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "EXECUTE", "/b", AuditResult.ERROR)
        critical = audit_memory.get_critical_events(limit=10)
        assert len(critical) == 1
        assert critical[0].user_id == "bob"
        assert critical[0].level == AuditLevel.CRITICAL

    def test_query_by_user_id(self, audit_memory):
        """query 按 user_id 过滤."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "READ", "/b", AuditResult.SUCCESS)
        results = audit_memory.query({"user_id": "alice"})
        assert len(results) == 1
        assert results[0].user_id == "alice"

    def test_query_by_action_and_result(self, audit_memory):
        """query 多条件 AND 过滤."""
        audit_memory.log_access("alice", "DELETE", "/a", AuditResult.DENIED)
        audit_memory.log_access("bob", "DELETE", "/b", AuditResult.SUCCESS)
        audit_memory.log_access("carol", "READ", "/c", AuditResult.DENIED)
        results = audit_memory.query(
            {"action": "DELETE", "result": AuditResult.DENIED}
        )
        assert len(results) == 1
        assert results[0].user_id == "alice"

    def test_query_empty_filter_returns_all(self, audit_memory):
        """空过滤器返回全部条目."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "READ", "/b", AuditResult.SUCCESS)
        results = audit_memory.query({})
        assert len(results) == 2

    def test_query_by_enum_value(self, audit_memory):
        """query 支持 enum 值过滤."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "READ", "/b", AuditResult.DENIED)
        results = audit_memory.query({"result": AuditResult.DENIED})
        assert len(results) == 1
        assert results[0].user_id == "bob"

    def test_query_by_string_value(self, audit_memory):
        """query 支持字符串值过滤."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "READ", "/b", AuditResult.DENIED)
        results = audit_memory.query({"result": "DENIED"})
        assert len(results) == 1
        assert results[0].user_id == "bob"

    def test_count(self, audit_memory):
        """count 返回条目总数."""
        assert audit_memory.count() == 0
        audit_memory.log_access("a", "READ", "/x", AuditResult.SUCCESS)
        audit_memory.log_access("b", "READ", "/y", AuditResult.SUCCESS)
        assert audit_memory.count() == 2

    def test_clear(self, audit_memory):
        """clear 清空所有条目."""
        audit_memory.log_access("a", "READ", "/x", AuditResult.SUCCESS)
        audit_memory.log_access("b", "READ", "/y", AuditResult.SUCCESS)
        cleared = audit_memory.clear()
        assert cleared == 2
        assert audit_memory.count() == 0

    def test_to_dict_and_from_dict(self, audit_memory):
        """序列化和反序列化往返."""
        audit_memory.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_memory.log_access("bob", "DELETE", "/b", AuditResult.DENIED)
        data = audit_memory.to_dict()
        restored = AuditLogger.from_dict(data)
        assert restored.count() == 2
        # 验证内容
        denied = restored.get_denied_attempts(limit=10)
        assert len(denied) == 1
        assert denied[0].user_id == "bob"


class TestAuditLoggerSQLite:
    """SQLite 持久化模式 AuditLogger."""

    def test_sqlite_log_and_count(self, audit_sqlite):
        """SQLite 模式记录条目."""
        audit_sqlite.log_access(
            "alice", "READ", "/api", AuditResult.SUCCESS
        )
        assert audit_sqlite.count() == 1

    def test_sqlite_persistence_across_instances(self, tmp_path):
        """SQLite 持久化：新实例能读取之前的数据."""
        db_path = str(tmp_path / "persist_audit.db")
        backend1 = SQLiteBackend(db_path)
        logger1 = AuditLogger(backend=backend1)
        logger1.log_access("alice", "DELETE", "/api", AuditResult.DENIED)
        logger1.log_access("bob", "READ", "/api", AuditResult.SUCCESS)
        assert logger1.count() == 2
        backend1.close()

        backend2 = SQLiteBackend(db_path)
        logger2 = AuditLogger(backend=backend2)
        assert logger2.count() == 2
        denied = logger2.get_denied_attempts(limit=10)
        assert len(denied) == 1
        assert denied[0].user_id == "alice"
        backend2.close()

    def test_sqlite_get_user_activity(self, audit_sqlite):
        """SQLite 模式查询用户活动."""
        audit_sqlite.log_access("alice", "READ", "/a", AuditResult.SUCCESS)
        audit_sqlite.log_access("alice", "WRITE", "/b", AuditResult.SUCCESS)
        audit_sqlite.log_access("bob", "READ", "/c", AuditResult.SUCCESS)
        activity = audit_sqlite.get_user_activity("alice", limit=10)
        assert len(activity) == 2
        for e in activity:
            assert e.user_id == "alice"

    def test_sqlite_query(self, audit_sqlite):
        """SQLite 模式条件查询."""
        audit_sqlite.log_access(
            "alice", "DELETE", "/users", AuditResult.DENIED
        )
        audit_sqlite.log_access(
            "bob", "READ", "/users", AuditResult.SUCCESS
        )
        results = audit_sqlite.query({"result": AuditResult.DENIED})
        assert len(results) == 1
        assert results[0].user_id == "alice"


# ═══════════════════════════════════════════════════════════════
#  Part 4 — 集成测试: RBAC + Audit 联合
# ═══════════════════════════════════════════════════════════════


class TestRBACAuditIntegration:
    """RBAC + Audit 联合集成测试."""

    def test_permission_check_with_audit_logging(self):
        """权限检查拒绝时记录审计日志."""
        rbac = RBACManager()
        audit = AuditLogger()
        rbac.assign_role("bob", Role.VIEWER)

        # bob 尝试 DELETE（无权限）
        allowed = rbac.check_permission("bob", Permission.DELETE)
        if not allowed:
            audit.log_access(
                user_id="bob",
                action="DELETE",
                resource="/api/users/alice",
                result=AuditResult.DENIED,
                permission_required="DELETE",
                ip_address="192.168.1.1",
            )

        assert allowed is False
        denied = audit.get_denied_attempts(limit=10)
        assert len(denied) == 1
        assert denied[0].user_id == "bob"
        assert denied[0].permission_required == "DELETE"

    def test_permission_check_success_with_audit_logging(self):
        """权限检查通过时记录审计日志."""
        rbac = RBACManager()
        audit = AuditLogger()
        rbac.assign_role("alice", Role.ADMIN)

        allowed = rbac.check_permission("alice", Permission.MANAGE_USERS)
        if allowed:
            audit.log_access(
                user_id="alice",
                action="MANAGE_USERS",
                resource="/api/users",
                result=AuditResult.SUCCESS,
            )

        assert allowed is True
        assert audit.count() == 1
        activity = audit.get_user_activity("alice", limit=10)
        assert activity[0].result == AuditResult.SUCCESS

    def test_full_workflow_memory(self):
        """完整工作流：分配→检查→审计→查询."""
        rbac = RBACManager()
        audit = AuditLogger()

        # 1. 分配角色
        rbac.assign_role("alice", Role.DEVELOPER)
        rbac.assign_role("bob", Role.VIEWER)

        # 2. alice 尝试 WRITE（有权限）
        if rbac.check_permission("alice", Permission.WRITE):
            audit.log_access(
                "alice", "WRITE", "/api/data", AuditResult.SUCCESS
            )

        # 3. bob 尝试 WRITE（无权限）
        if not rbac.check_permission("bob", Permission.WRITE):
            audit.log_access(
                "bob", "WRITE", "/api/data", AuditResult.DENIED
            )

        # 4. 验证审计记录
        assert audit.count() == 2
        alice_activity = audit.get_user_activity("alice", limit=10)
        assert len(alice_activity) == 1
        assert alice_activity[0].result == AuditResult.SUCCESS

        bob_activity = audit.get_user_activity("bob", limit=10)
        assert len(bob_activity) == 1
        assert bob_activity[0].result == AuditResult.DENIED

        denied = audit.get_denied_attempts(limit=10)
        assert len(denied) == 1
        assert denied[0].user_id == "bob"

    def test_full_workflow_sqlite(self, tmp_path):
        """完整工作流（SQLite 持久化）."""
        backend = SQLiteBackend(str(tmp_path / "integration.db"))
        rbac = RBACManager(backend=backend)
        audit = AuditLogger(backend=backend)

        rbac.assign_role("alice", Role.OPERATOR)
        rbac.assign_role("bob", Role.VIEWER)

        # alice 有 EXECUTE 权限
        assert rbac.check_permission("alice", Permission.EXECUTE) is True
        audit.log_access(
            "alice", "EXECUTE", "/api/tools/run", AuditResult.SUCCESS
        )

        # bob 没有 EXECUTE 权限
        assert rbac.check_permission("bob", Permission.EXECUTE) is False
        audit.log_access(
            "bob", "EXECUTE", "/api/tools/run", AuditResult.DENIED
        )

        # 验证审计
        assert audit.count() == 2
        denied = audit.get_denied_attempts(limit=10)
        assert len(denied) == 1

        # 验证 RBAC 持久化
        assert rbac.list_users_by_role(Role.OPERATOR) == ["alice"]
        assert rbac.list_users_by_role(Role.VIEWER) == ["bob"]

    def test_rbac_revoke_blocks_access(self):
        """撤销角色后权限检查失败并记录审计."""
        rbac = RBACManager()
        audit = AuditLogger()
        rbac.assign_role("alice", Role.DEVELOPER)
        assert rbac.check_permission("alice", Permission.WRITE) is True

        rbac.revoke_role("alice")
        assert rbac.check_permission("alice", Permission.WRITE) is False
        audit.log_access(
            "alice", "WRITE", "/api/data", AuditResult.DENIED
        )
        assert audit.count() == 1

    def test_role_change_affects_audit_pattern(self):
        """角色变更后审计模式变化."""
        rbac = RBACManager()
        audit = AuditLogger()
        rbac.assign_role("alice", Role.VIEWER)

        # VIEWER 无法 WRITE
        assert rbac.check_permission("alice", Permission.WRITE) is False
        audit.log_access("alice", "WRITE", "/api", AuditResult.DENIED)

        # 升级为 DEVELOPER
        rbac.assign_role("alice", Role.DEVELOPER)
        assert rbac.check_permission("alice", Permission.WRITE) is True
        audit.log_access("alice", "WRITE", "/api", AuditResult.SUCCESS)

        # 验证审计历史
        activity = audit.get_user_activity("alice", limit=10)
        assert len(activity) == 2
        results = [e.result for e in activity]
        assert AuditResult.DENIED in results
        assert AuditResult.SUCCESS in results


# ═══════════════════════════════════════════════════════════════
#  Part 5 — 异常输入处理
# ═══════════════════════════════════════════════════════════════


class TestExceptionHandling:
    """异常输入处理."""

    def test_assign_role_empty_user_id_raises(self, rbac_memory):
        """空 user_id 抛出 ValueError."""
        with pytest.raises(ValueError, match="user_id"):
            rbac_memory.assign_role("", Role.ADMIN)

    def test_assign_role_none_user_id_raises(self, rbac_memory):
        """None user_id 抛出 ValueError."""
        with pytest.raises(ValueError):
            rbac_memory.assign_role(None, Role.ADMIN)  # type: ignore

    def test_revoke_role_empty_user_id_raises(self, rbac_memory):
        """空 user_id 撤销抛出 ValueError."""
        with pytest.raises(ValueError, match="user_id"):
            rbac_memory.revoke_role("")

    def test_role_from_str_invalid(self):
        """非法角色名称抛出异常."""
        with pytest.raises(KeyError):
            role_from_str("SUPERUSER")

    def test_permission_from_str_invalid(self):
        """非法权限名称抛出异常."""
        with pytest.raises(KeyError):
            permission_from_str("GOD_MODE")

    def test_audit_entry_from_dict_invalid_result(self):
        """非法 result 字符串抛出异常."""
        with pytest.raises(KeyError):
            AuditEntry.from_dict(
                {"user_id": "x", "result": "INVALID"}
            )


# ═══════════════════════════════════════════════════════════════
#  Part 6 — 序列化辅助函数
# ═══════════════════════════════════════════════════════════════


class TestSerializationHelpers:
    """序列化辅助函数往返测试."""

    def test_role_str_roundtrip(self):
        """Role 字符串往返."""
        for role in Role:
            assert role_from_str(role_to_str(role)) == role

    def test_permission_str_roundtrip(self):
        """Permission 字符串往返."""
        for perm in Permission:
            assert permission_from_str(permission_to_str(perm)) == perm

    def test_result_str_roundtrip(self):
        """AuditResult 字符串往返."""
        for result in AuditResult:
            assert result_from_str(result_to_str(result)) == result

    def test_level_str_roundtrip(self):
        """AuditLevel 字符串往返."""
        for level in AuditLevel:
            assert level_from_str(level_to_str(level)) == level
