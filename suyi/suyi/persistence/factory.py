"""
持久化后端工厂 — 根据配置创建后端实例。

支持两种后端类型：
    - ``json``:   JSONBackend（文件存储）
    - ``sqlite``:  SQLiteBackend（数据库存储）

Usage::

    from suyi.persistence import create_backend

    # 默认JSON后端
    backend = create_backend()

    # SQLite后端
    backend = create_backend(backend_type="sqlite", db_path="./data/suyi.db")

    # 从配置创建
    from suyi.config import SuyiConfig, PersistenceConfig
    config = SuyiConfig(persistence=PersistenceConfig(backend="sqlite"))
    backend = create_backend_from_config(config)
"""

from __future__ import annotations

from typing import Any, Optional

from .sqlite_backend import JSONBackend, SQLiteBackend


# 后端类型注册表
_BACKEND_REGISTRY = {
    "json": JSONBackend,
    "sqlite": SQLiteBackend,
}

# 别名
_BACKEND_ALIASES = {
    "jsonfile": "json",
    "file": "json",
    "sqlite3": "sqlite",
    "db": "sqlite",
}


def register_backend(name: str, backend_class: type) -> None:
    """注册自定义后端类型。

    Args:
        name:           后端类型名称。
        backend_class:  后端类（需实现 get/set/delete/exists/list_keys 接口）。
    """
    _BACKEND_REGISTRY[name] = backend_class


def create_backend(
    backend_type: str = "json",
    **kwargs: Any,
) -> Any:
    """创建持久化后端实例。

    Args:
        backend_type: 后端类型，``"json"`` 或 ``"sqlite"``。
        **kwargs:     后端构造参数。

    Returns:
        后端实例。

    Raises:
        ValueError: 若后端类型不支持。
    """
    resolved = _BACKEND_ALIASES.get(backend_type.lower(), backend_type.lower())

    if resolved not in _BACKEND_REGISTRY:
        supported = ", ".join(sorted(set(_BACKEND_REGISTRY) | set(_BACKEND_ALIASES)))
        raise ValueError(
            f"不支持的后端类型: '{backend_type}'. "
            f"支持: {supported}"
        )

    backend_class = _BACKEND_REGISTRY[resolved]
    return backend_class(**kwargs)


def create_backend_from_config(config: Any) -> Any:
    """从SuyiConfig创建持久化后端实例。

    读取 ``config.persistence`` 中的配置：

    - ``backend``:     ``"json"`` 或 ``"sqlite"``
    - ``storage_dir``: JSON后端的存储目录
    - ``db_path``:     SQLite后端的数据库路径

    Args:
        config: SuyiConfig实例（需包含 ``persistence`` 属性）。

    Returns:
        后端实例。
    """
    if not hasattr(config, "persistence"):
        # 无持久化配置，使用默认JSON后端
        return create_backend(backend_type="json")

    persist_cfg = config.persistence
    backend_type = getattr(persist_cfg, "backend", "json")

    if backend_type == "sqlite":
        return create_backend(
            backend_type="sqlite",
            db_path=getattr(persist_cfg, "db_path", "./data/suyi.db"),
        )
    else:
        return create_backend(
            backend_type="json",
            storage_dir=getattr(persist_cfg, "storage_dir", "./data"),
            namespace=getattr(persist_cfg, "namespace", "default"),
        )


def list_backends() -> list[str]:
    """列出所有支持的后端类型名称（含别名）。"""
    return sorted(set(_BACKEND_REGISTRY) | set(_BACKEND_ALIASES))
