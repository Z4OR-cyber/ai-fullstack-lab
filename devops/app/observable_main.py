"""
第5题：可观测性 FastAPI 应用
功能：结构化日志 + Prometheus 指标暴露 + OpenTelemetry 追踪示例
运行：uvicorn app.observable_main:app --host 0.0.0.0 --port 8000
"""
import json
import logging
import time
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

# ============================================================
# 一、结构化日志（JSON 格式）
# ============================================================

class JsonFormatter(logging.Formatter):
    """将日志格式化为 JSON，方便 ELK/Loki 等日志系统采集和查询"""

    def format(self, record: logging.LogRecord) -> str:
        """重写 format 方法，输出 JSON 格式日志"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 如果有异常信息，加入堆栈
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 加入额外字段（通过 extra 参数传入的）
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "getMessage",
                "taskName",
            }:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """配置结构化日志系统"""
    logger = logging.getLogger("todo_app")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    # 防止日志向上传播到 root logger
    logger.propagate = False

    return logger


# 初始化日志
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))


# ============================================================
# 二、Prometheus 指标
# ============================================================

# 用 prometheus_client 库定义指标
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
)

# 自定义注册器（避免默认全局注册器的指标冲突）
registry = CollectorRegistry()

# 指标定义
# Counter：只增不减的计数器（请求数、错误数）
REQUEST_COUNT = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "endpoint", "status"],
    registry=registry,
)

# Histogram：分布统计（请求延迟分布）
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求处理耗时（秒）",
    ["method", "endpoint"],
    # 自定义桶边界（适合 API 响应时间）
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

# Gauge：可增可减的瞬时值（活跃连接数、队列长度）
ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "当前活跃请求数",
    registry=registry,
)

# 业务指标：待办事项计数
TODO_TOTAL = Gauge(
    "todo_items_total",
    "待办事项总数",
    ["status"],  # status: pending, completed
    registry=registry,
)


# ============================================================
# 三、OpenTelemetry 分布式追踪（概念示例）
# ============================================================

def setup_tracing(app_name: str = "todo-app"):
    """
    配置 OpenTelemetry 分布式追踪
    生产环境中应将数据导出到 Jaeger / Zipkin / Tempo

    这里用 try-except 包裹，因为 opentelemetry 包可能未安装
    追踪的价值在于：一个请求经过多个微服务时，能看到完整的调用链
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource

        # 创建 Tracer Provider
        provider = TracerProvider(
            resource=Resource.create({"service.name": app_name})
        )

        # 导出器：将追踪数据输出到控制台
        # 生产环境替换为 JaegerExporter / OTLPExporter
        exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # 设置全局 Tracer Provider
        trace.set_tracer_provider(provider)

        logger.info("OpenTelemetry 追踪已启用", extra={"component": "tracing"})
        return trace.get_tracer(app_name)

    except ImportError:
        logger.warning(
            "opentelemetry 未安装，追踪功能不可用。"
            "安装：pip install opentelemetry-api opentelemetry-sdk",
            extra={"component": "tracing"},
        )
        return None


tracer = setup_tracing()


# ============================================================
# 四、FastAPI 应用 + 中间件
# ============================================================

app = FastAPI(
    title="Observable Todo API",
    description="带完整可观测性的待办事项 API",
    version="1.0.0",
)

# 模拟数据存储
_todos: dict[int, dict] = {}
_next_id: int = 1


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """中间件：自动采集每个请求的指标和日志"""
    start_time = time.time()
    ACTIVE_REQUESTS.inc()  # 活跃请求 +1

    # 记录请求开始
    logger.info(
        "请求开始",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        },
    )

    try:
        response: Response = await call_next(request)
        return response
    except Exception as exc:
        logger.error(
            "请求处理异常",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise
    finally:
        # 计算请求耗时
        duration = time.time() - start_time
        ACTIVE_REQUESTS.dec()  # 活跃请求 -1

        # 记录指标
        status_code = response.status_code if "response" in dir() else 500
        endpoint = request.url.path

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(status_code),
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        # 更新业务指标
        pending_count = sum(1 for t in _todos.values() if not t["completed"])
        completed_count = sum(1 for t in _todos.values() if t["completed"])
        TODO_TOTAL.labels(status="pending").set(pending_count)
        TODO_TOTAL.labels(status="completed").set(completed_count)

        # 结构化日志记录请求完成
        logger.info(
            "请求完成",
            extra={
                "method": request.method,
                "path": endpoint,
                "status": status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )


# -------------------- 路由 --------------------

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus 指标暴露端点
    Prometheus 会定时抓取这个端点获取指标数据
    """
    return PlainTextResponse(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/todos")
async def list_todos():
    """获取所有待办事项"""
    if tracer:
        with tracer.start_as_current_span("list_todos"):
            # 创建一个子 span，追踪这个操作
            logger.info("查询所有待办事项", extra={"action": "list", "count": len(_todos)})
            return list(_todos.values())
    return list(_todos.values())


@app.post("/todos")
async def create_todo(title: str):
    """创建待办事项（简化版，title 通过查询参数传入）"""
    global _next_id

    if tracer:
        with tracer.start_as_current_span("create_todo") as span:
            span.set_attribute("todo.title", title)
            span.set_attribute("todo.id", _next_id)

    todo_data = {
        "id": _next_id,
        "title": title,
        "completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _todos[_next_id] = todo_data
    _next_id += 1

    logger.info(
        "创建待办事项",
        extra={"action": "create", "todo_id": todo_data["id"], "title": title},
    )
    return todo_data


@app.get("/todos/{todo_id}")
async def get_todo(todo_id: int):
    """获取单个待办事项"""
    if todo_id not in _todos:
        logger.warning(
            "待办事项不存在",
            extra={"action": "get", "todo_id": todo_id, "result": "not_found"},
        )
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")

    logger.info(
        "查询待办事项",
        extra={"action": "get", "todo_id": todo_id, "result": "found"},
    )
    return _todos[todo_id]


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    """删除待办事项"""
    global _next_id

    if todo_id not in _todos:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")

    deleted = _todos.pop(todo_id)
    logger.info(
        "删除待办事项",
        extra={"action": "delete", "todo_id": todo_id, "title": deleted["title"]},
    )
    return {"message": "deleted", "id": todo_id}


@app.get("/slow")
async def slow_endpoint():
    """模拟慢请求，用于测试延迟指标"""
    time.sleep(0.5)
    return {"message": "slow response completed"}


@app.get("/error")
async def error_endpoint():
    """模拟错误请求，用于测试错误指标"""
    logger.error("模拟错误发生", extra={"action": "error_simulation"})
    from fastapi import HTTPException
    raise HTTPException(status_code=500, detail="Simulated error for testing")
