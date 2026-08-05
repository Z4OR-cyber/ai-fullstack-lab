"""pytest配置 - 将项目根目录加入Python路径，配置测试数据库"""

import sys
import os
import pytest

# 设置测试数据库路径（必须在导入app模块之前设置）
_test_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "test_secscan.db"
)
os.environ["SECSCAN_DB_PATH"] = _test_db_path

# 确保app模块可被导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session", autouse=True)
def reset_test_database():
    """在测试会话开始前重置测试数据库，确保干净状态

    1. 删除旧测试数据库文件
    2. 重建引擎和表结构
    3. 测试结束后清理数据库文件
    """
    from app.db.database import reset_database

    # 重置数据库（删除旧文件 + 重建引擎和表）
    reset_database()

    yield

    # 测试会话结束后：释放引擎连接并清理数据库文件
    from app.db.database import get_engine
    try:
        get_engine().dispose()
    except Exception:
        pass
    if os.path.exists(_test_db_path):
        try:
            os.remove(_test_db_path)
        except PermissionError:
            pass  # 引擎未完全释放时跳过清理，下次 reset 会处理
