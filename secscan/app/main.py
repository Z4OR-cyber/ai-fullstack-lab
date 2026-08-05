"""FastAPI应用入口

SecScan - AI驱动的代码安全审计平台
阶段1：核心API + 安全审计引擎
阶段4：数据库持久化（SQLAlchemy + SQLite）
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import scan, report
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时初始化数据库（创建表），确保持久化存储就绪。
    """
    init_db()
    yield


app = FastAPI(
    title="SecScan",
    description=(
        "## SecScan 代码安全审计API\n\n"
        "AI驱动的代码安全审计平台，支持Python和JavaScript代码的安全扫描。\n\n"
        "### 支持检测的漏洞类型\n"
        "- SQL注入 (CWE-89)\n"
        "- 命令注入 (CWE-78)\n"
        "- XSS跨站脚本 (CWE-79)\n"
        "- 硬编码密钥 (CWE-798)\n"
        "- 路径遍历 (CWE-22)\n"
        "- 不安全的反序列化 (CWE-502)\n"
        "- 弱加密算法 (CWE-327)\n"
        "- SSRF服务端请求伪造 (CWE-918)\n"
        "- 敏感信息泄露 (CWE-532)\n"
        "- 不安全的随机数 (CWE-330)\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(scan.router)
app.include_router(report.router)


@app.get("/", summary="健康检查")
async def root():
    """根路径，返回API基本信息"""
    return {
        "name": "SecScan",
        "version": "2.0.0",
        "description": "AI驱动的代码安全审计平台",
        "docs": "/docs",
        "endpoints": {
            "scan": "POST /api/scan",
            "report": "GET /api/report/{scan_id}",
            "history": "GET /api/history",
            "delete_report": "DELETE /api/report/{scan_id}",
        },
    }
