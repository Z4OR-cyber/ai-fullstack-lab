"""ORM 模型定义模块

定义 SQLAlchemy ORM 模型，对应数据库表结构。
与 Pydantic 模型（app.models.scan_result）分离，
通过 CRUD 层进行相互转换。

表关系：
    ScanRecord (1) ──→ VulnerabilityRecord (N)
    一个扫描记录包含多个漏洞记录。
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.db.database import Base


class ScanRecord(Base):
    """扫描记录表 — 对应一次代码安全扫描

    存储扫描的基本信息和统计摘要。
    漏洞详情通过 vulnerabilities 关系关联到 VulnerabilityRecord 表。
    """
    __tablename__ = "scan_records"

    # 自增主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 扫描任务唯一ID（UUID），用于外部查询
    scan_id = Column(String(64), unique=True, nullable=False, index=True)

    # 扫描的文件名
    filename = Column(String(256), nullable=False, index=True)

    # 代码语言（Python / JavaScript / Unknown）
    language = Column(String(32), nullable=False, index=True)

    # 扫描时间（ISO 格式字符串）
    scan_time = Column(String(64), nullable=False)

    # 统计摘要 — 直接存储在扫描记录上，避免每次查询都要聚合
    total = Column(Integer, default=0, nullable=False)
    critical = Column(Integer, default=0, nullable=False)
    high = Column(Integer, default=0, nullable=False)
    medium = Column(Integer, default=0, nullable=False)
    low = Column(Integer, default=0, nullable=False)
    info = Column(Integer, default=0, nullable=False)

    # 一对多关系：一个扫描记录对应多个漏洞
    vulnerabilities = relationship(
        "VulnerabilityRecord",
        back_populates="scan_record",
        cascade="all, delete-orphan",  # 删除扫描记录时级联删除关联的漏洞
    )


class VulnerabilityRecord(Base):
    """漏洞记录表 — 对应扫描中发现的一个安全漏洞

    通过 scan_record_id 外键关联到 ScanRecord。
    """
    __tablename__ = "vulnerability_records"

    # 自增主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 外键：关联的扫描记录ID
    scan_record_id = Column(
        Integer,
        ForeignKey("scan_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 规则ID，如 SC001
    rule_id = Column(String(16), nullable=False)

    # 漏洞类型，如 SQL注入
    vuln_type = Column(String(64), nullable=False)

    # CWE编号，如 CWE-89
    cwe_id = Column(String(32), nullable=False)

    # 严重程度（Critical / High / Medium / Low / Info）
    severity = Column(String(16), nullable=False, index=True)

    # 漏洞描述
    description = Column(Text, nullable=False)

    # 漏洞所在行号
    line = Column(Integer, nullable=False)

    # 漏洞代码片段
    code_snippet = Column(Text, nullable=False)

    # 修复建议
    fix_suggestion = Column(Text, nullable=False)

    # 反向关系：指向所属的扫描记录
    scan_record = relationship("ScanRecord", back_populates="vulnerabilities")
