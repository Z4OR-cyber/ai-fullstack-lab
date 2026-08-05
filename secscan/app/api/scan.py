"""扫描API路由

POST /api/scan - 上传代码文件并执行安全扫描
"""

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.engine.scanner import scanner
from app.models.scan_result import ScanResult

router = APIRouter(tags=["扫描"])


@router.post("/api/scan", response_model=ScanResult, summary="上传代码文件进行安全扫描")
async def scan_file(file: UploadFile = File(..., description="要扫描的代码文件(.py/.js)")):
    """上传代码文件并执行安全审计

    支持的文件类型：
    - Python (.py) - 使用AST分析，精度高
    - JavaScript (.js/.mjs) - 使用正则匹配，覆盖广

    返回扫描结果，包含检测到的所有漏洞信息和统计摘要。
    扫描结果会保存在内存中，可通过 scan_id 使用 GET /api/report/{scan_id} 查询。
    """
    # 读取文件内容
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    # 解码文件内容
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码不支持，请使用UTF-8编码")

    # 检查文件类型
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("py", "js", "mjs", "javascript"):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: .{ext}，目前支持 .py 和 .js 文件"
        )

    # 执行扫描
    result = scanner.scan_code(filename, text)
    return result
