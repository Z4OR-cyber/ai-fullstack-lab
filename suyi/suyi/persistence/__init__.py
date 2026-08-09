"""
Suyi Persistence — 持久化层（JSON文件 + SQLite）。

Exports:
    SessionManager:     创建、保存、加载、列出、删除和导出会话。
    SessionData:        可序列化的会话快照数据类。
    JSONBackend:        JSON文件键值存储后端。
    SQLiteBackend:      SQLite键值存储后端（支持FTS5）。
    create_backend:     根据配置创建后端实例。
    create_backend_from_config: 从SuyiConfig创建后端。
    migrate_json_to_sqlite:       JSON → SQLite迁移函数。
    migrate_json_dir_to_sqlite:   JSON目录 → SQLite迁移函数。

Design:
    - JSON文件存储：无数据库依赖，每个会话/键值对存储为独立JSON文件。
    - SQLite存储：支持FTS5全文搜索、批量写入、事务、线程安全。
    - 两种后端共享相同接口（get/set/delete/exists/list_keys/search）。
    - 工厂模式根据配置选择后端类型。

Usage::

    from suyi.persistence import SessionManager, SQLiteBackend

    # 会话管理（JSON文件）
    mgr = SessionManager(storage_dir="./data")
    sid = mgr.create_session()
    mgr.add_message(sid, "user", "Hello!")
    mgr.save_session(sid)

    # 键值存储（SQLite）
    backend = SQLiteBackend("./data/suyi.db")
    backend.set("key1", {"content": "Hello World"})
    results = backend.search("Hello")
"""

from .session import SessionManager, SessionData
from .sqlite_backend import JSONBackend, SQLiteBackend
from .factory import (
    create_backend,
    create_backend_from_config,
    register_backend,
    list_backends,
)
from .migrations import (
    migrate_json_to_sqlite,
    migrate_json_dir_to_sqlite,
)

__all__ = [
    # 会话管理
    "SessionManager",
    "SessionData",
    # 持久化后端
    "JSONBackend",
    "SQLiteBackend",
    # 工厂
    "create_backend",
    "create_backend_from_config",
    "register_backend",
    "list_backends",
    # 迁移
    "migrate_json_to_sqlite",
    "migrate_json_dir_to_sqlite",
]
