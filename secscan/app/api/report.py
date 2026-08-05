"""报告查询与管理API路由

GET    /api/report/{scan_id} — 根据扫描ID获取扫描报告
GET    /api/history          — 查询扫描历史列表（分页，支持筛选）
DELETE /api/report/{scan_id} — 删除指定扫描记录
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.engine.scanner import scanner
from app.models.scan_result import ScanResult
from app.db.database import get_db
from app.db import crud

router = APIRouter(tags=["报告"])


@router.get("/api/report/{scan_id}", response_model=ScanResult, summary="获取扫描报告")
async def get_report(scan_id: str):
    """根据扫描ID获取安全扫描报告

    扫描结果持久化存储在 SQLite 数据库中，服务重启后仍可查询。
    """
    result = scanner.get_result(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="扫描报告不存在")
    return result


@router.get("/api/history", summary="查询扫描历史列表")
async def get_history(
    skip: int = Query(0, ge=0, description="跳过的记录数（分页偏移）"),
    limit: int = Query(20, ge=1, le=100, description="每页记录数（1-100）"),
    filename: str = Query(None, description="按文件名筛选（模糊匹配）"),
    language: str = Query(None, description="按语言筛选（精确匹配）"),
    db: Session = Depends(get_db),
):
    """查询扫描历史记录列表

    支持分页和按文件名/语言筛选。
    返回扫描记录摘要（不包含漏洞详情），按时间倒序排列。
    """
    return crud.get_scan_history(
        db, skip=skip, limit=limit, filename=filename, language=language
    )


@router.delete("/api/report/{scan_id}", summary="删除扫描记录")
async def delete_report(
    scan_id: str,
    db: Session = Depends(get_db),
):
    """删除指定的扫描记录及其关联的漏洞详情

    删除操作不可恢复。
    """
    deleted = crud.delete_scan_result(db, scan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="扫描报告不存在")

    db.commit()
    return {"message": f"扫描记录 {scan_id} 已删除"}
