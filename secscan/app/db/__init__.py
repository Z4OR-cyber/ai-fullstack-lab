"""数据库持久化模块

提供 SecScan 审计记录的数据库存储能力，包含：
- database.py: SQLAlchemy 引擎和会话管理
- models.py: ORM 模型定义（ScanRecord + VulnerabilityRecord）
- crud.py: 增删改查操作函数
"""
