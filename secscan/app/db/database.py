"""SQLAlchemy 引擎和会话管理模块

负责创建数据库引擎、管理会话工厂、初始化数据库表。
使用 SQLite 作为后端存储（开发环境），同步模式。

数据库文件默认路径：data/secscan.db
可通过环境变量 SECSCAN_DB_PATH 自定义路径（用于测试隔离）。
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session


# SQLAlchemy 声明式基类，所有 ORM 模型继承此类
Base = declarative_base()

# 模块级缓存：引擎和会话工厂（惰性初始化）
_engine = None
_SessionLocal = None


def get_db_path() -> str:
    """获取数据库文件路径

    优先读取环境变量 SECSCAN_DB_PATH，未设置则使用默认路径。

    Returns:
        数据库文件的绝对路径
    """
    env_path = os.environ.get("SECSCAN_DB_PATH")
    if env_path:
        return env_path
    # 默认路径：项目根目录下的 data/secscan.db
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "data", "secscan.db")


def get_database_url() -> str:
    """构建 SQLAlchemy 数据库连接 URL"""
    return f"sqlite:///{get_db_path()}"


def get_engine():
    """获取（惰性创建）SQLAlchemy 引擎实例

    使用 check_same_thread=False 允许 FastAPI 多线程访问 SQLite。

    Returns:
        SQLAlchemy Engine 实例
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """获取（惰性创建）会话工厂

    Returns:
        sessionmaker 实例，用于创建数据库会话
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_session() -> Session:
    """创建并返回一个新的数据库会话

    调用方负责在 使用完毕后关闭会话。

    Returns:
        SQLAlchemy Session 实例
    """
    return get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供数据库会话

    用法（在路由函数参数中）:
        def endpoint(db: Session = Depends(get_db)):
            ...

    Yields:
        数据库会话，请求结束后自动关闭
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库：创建数据目录和所有表

    在应用启动时调用，确保数据库文件和表结构就绪。
    幂等操作，重复调用不会报错。
    """
    # 确保数据目录存在
    db_path = get_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # 导入 ORM 模型，确保 Base.metadata 包含所有表定义
    from app.db.models import ScanRecord, VulnerabilityRecord  # noqa: F401

    # 创建所有表（已存在的表不会重建）
    Base.metadata.create_all(get_engine())


def reset_database() -> None:
    """重置数据库引擎和会话（用于测试隔离）

    释放旧引擎连接，删除数据库文件，重新初始化。
    生产环境不应调用此函数。
    """
    global _engine, _SessionLocal

    # 释放旧引擎
    if _engine is not None:
        _engine.dispose()

    # 重置缓存
    _engine = None
    _SessionLocal = None

    # 删除旧数据库文件
    db_path = get_db_path()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except (PermissionError, OSError):
            # 文件可能被其他进程锁定，跳过删除
            # 使用新的数据库文件路径避免冲突
            import time
            db_path = os.path.join(
                os.path.dirname(db_path),
                f"test_secscan_{int(time.time() * 1000)}.db"
            )
            os.environ["SECSCAN_DB_PATH"] = db_path

    # 重新初始化
    init_db()
