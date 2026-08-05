"""CRUD 操作模块

提供扫描记录的增删改查函数，在 Pydantic 模型 和 ORM 模型 之间转换。
所有函数接收一个 SQLAlchemy Session 参数，由调用方管理事务提交。
"""

from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.db.models import ScanRecord, VulnerabilityRecord
from app.models.scan_result import ScanResult, ScanSummary, Vulnerability


# ============================================================
# Pydantic ↔ ORM 转换函数
# ============================================================

def _pydantic_to_orm(scan_result: ScanResult) -> ScanRecord:
    """将 Pydantic ScanResult 转换为 ORM ScanRecord

    Args:
        scan_result: Pydantic 扫描结果对象

    Returns:
        ScanRecord ORM 对象（尚未持久化）
    """
    record = ScanRecord(
        scan_id=scan_result.scan_id,
        filename=scan_result.filename,
        language=scan_result.language,
        scan_time=scan_result.scan_time,
        total=scan_result.summary.total,
        critical=scan_result.summary.critical,
        high=scan_result.summary.high,
        medium=scan_result.summary.medium,
        low=scan_result.summary.low,
        info=scan_result.summary.info,
    )

    # 转换漏洞列表
    for vuln in scan_result.vulnerabilities:
        vuln_record = VulnerabilityRecord(
            rule_id=vuln.rule_id,
            vuln_type=vuln.vuln_type,
            cwe_id=vuln.cwe_id,
            severity=vuln.severity,
            description=vuln.description,
            line=vuln.line,
            code_snippet=vuln.code_snippet,
            fix_suggestion=vuln.fix_suggestion,
        )
        record.vulnerabilities.append(vuln_record)

    return record


def _orm_to_pydantic(record: ScanRecord) -> ScanResult:
    """将 ORM ScanRecord 转换为 Pydantic ScanResult

    Args:
        record: ORM 扫描记录对象

    Returns:
        ScanResult Pydantic 对象
    """
    # 转换漏洞列表
    vulnerabilities = [
        Vulnerability(
            rule_id=v.rule_id,
            vuln_type=v.vuln_type,
            cwe_id=v.cwe_id,
            severity=v.severity,
            description=v.description,
            line=v.line,
            code_snippet=v.code_snippet,
            fix_suggestion=v.fix_suggestion,
        )
        for v in record.vulnerabilities
    ]

    # 构建统计摘要
    summary = ScanSummary(
        total=record.total,
        critical=record.critical,
        high=record.high,
        medium=record.medium,
        low=record.low,
        info=record.info,
    )

    return ScanResult(
        scan_id=record.scan_id,
        filename=record.filename,
        language=record.language,
        scan_time=record.scan_time,
        vulnerabilities=vulnerabilities,
        summary=summary,
    )


# ============================================================
# CRUD 操作函数
# ============================================================

def create_scan_result(db: Session, scan_result: ScanResult) -> ScanRecord:
    """将扫描结果存入数据库

    Args:
        db: 数据库会话
        scan_result: Pydantic 扫描结果对象

    Returns:
        持久化后的 ORM ScanRecord 对象
    """
    record = _pydantic_to_orm(scan_result)
    db.add(record)
    db.flush()  # 刷新以获取 record.id，但不提交事务
    return record


def get_scan_result(db: Session, scan_id: str) -> Optional[ScanResult]:
    """根据扫描ID查询扫描结果

    Args:
        db: 数据库会话
        scan_id: 扫描任务唯一ID

    Returns:
        ScanResult Pydantic 对象，未找到时返回 None
    """
    record = db.query(ScanRecord).filter(ScanRecord.scan_id == scan_id).first()
    if record is None:
        return None
    return _orm_to_pydantic(record)


def get_scan_history(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    filename: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """查询扫描历史列表（分页，支持筛选）

    Args:
        db: 数据库会话
        skip: 跳过的记录数（分页偏移）
        limit: 每页记录数
        filename: 按文件名筛选（模糊匹配），None 表示不筛选
        language: 按语言筛选（精确匹配），None 表示不筛选

    Returns:
        包含 items（列表）、total（总数）、skip、limit 的字典
    """
    # 构建基础查询
    query = db.query(ScanRecord)

    # 按文件名模糊筛选
    if filename:
        query = query.filter(ScanRecord.filename.like(f"%{filename}%"))

    # 按语言精确筛选
    if language:
        query = query.filter(ScanRecord.language == language)

    # 获取总数（在分页之前）
    total = query.count()

    # 按扫描时间倒序排列，分页查询
    records = (
        query.order_by(ScanRecord.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 转换为简化的历史记录格式（不包含漏洞详情）
    items = [
        {
            "scan_id": r.scan_id,
            "filename": r.filename,
            "language": r.language,
            "scan_time": r.scan_time,
            "summary": {
                "total": r.total,
                "critical": r.critical,
                "high": r.high,
                "medium": r.medium,
                "low": r.low,
                "info": r.info,
            },
        }
        for r in records
    ]

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


def delete_scan_result(db: Session, scan_id: str) -> bool:
    """删除指定扫描记录及其关联的漏洞记录

    利用 ORM 级联删除（cascade="all, delete-orphan"），
    删除 ScanRecord 时自动删除关联的 VulnerabilityRecord。

    Args:
        db: 数据库会话
        scan_id: 扫描任务唯一ID

    Returns:
        True 表示删除成功，False 表示记录不存在
    """
    record = db.query(ScanRecord).filter(ScanRecord.scan_id == scan_id).first()
    if record is None:
        return False

    db.delete(record)
    db.flush()
    return True
