"""
第三阶段 3.1 — FastAPI 后端开发 (10题)
涵盖: 路由/请求体/响应模型/依赖注入/中间件/后台任务/WebSocket/异步DB/异常处理/测试

使用 TestClient 进行测试, 无需启动真实服务器
"""
import pytest
import json
import asyncio
import time
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from fastapi import FastAPI, Depends, HTTPException, Query, Path, Body, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from contextlib import asynccontextmanager

# ============================================================
# 练习 1: 基础路由 — GET/POST + 路径参数 + 查询参数
# ============================================================

def test_01_basic_routing():
    """创建 FastAPI 应用, 实现基础 CRUD 路由"""
    app = FastAPI(title="Task API")
    
    # 内存存储
    tasks: dict[int, dict] = {}
    next_id = [1]
    
    @app.get("/")
    def root():
        return {"message": "Task API", "version": "1.0"}
    
    @app.get("/tasks")
    def list_tasks(skip: int = 0, limit: int = 10):
        all_tasks = list(tasks.values())
        return all_tasks[skip: skip + limit]
    
    @app.get("/tasks/{task_id}")
    def get_task(task_id: int):
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        return tasks[task_id]
    
    @app.post("/tasks", status_code=201)
    def create_task(title: str = Body(..., embed=True)):
        tid = next_id[0]
        next_id[0] += 1
        tasks[tid] = {"id": tid, "title": title, "done": False}
        return tasks[tid]
    
    @app.put("/tasks/{task_id}")
    def update_task(task_id: int, done: bool = Body(..., embed=True)):
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        tasks[task_id]["done"] = done
        return tasks[task_id]
    
    @app.delete("/tasks/{task_id}", status_code=204)
    def delete_task(task_id: int):
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        del tasks[task_id]
    
    client = TestClient(app)
    
    # 测试根路由
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["message"] == "Task API"
    
    # 创建任务
    r = client.post("/tasks", json={"title": "Learn FastAPI"})
    assert r.status_code == 201
    assert r.json()["title"] == "Learn FastAPI"
    assert r.json()["done"] is False
    
    # 查询列表
    r = client.get("/tasks")
    assert r.status_code == 200
    assert len(r.json()) == 1
    
    # 查询单个
    r = client.get("/tasks/1")
    assert r.status_code == 200
    assert r.json()["title"] == "Learn FastAPI"
    
    # 404
    r = client.get("/tasks/999")
    assert r.status_code == 404
    
    # 更新
    r = client.put("/tasks/1", json={"done": True})
    assert r.json()["done"] is True
    
    # 删除
    r = client.delete("/tasks/1")
    assert r.status_code == 204
    
    # 确认删除
    r = client.get("/tasks/1")
    assert r.status_code == 404
    
    print("✅ 练习1通过: 基础路由 CRUD + 路径/查询参数")


# ============================================================
# 练习 2: Pydantic 请求体模型 + 数据验证
# ============================================================

def test_02_pydantic_models():
    """使用 Pydantic 模型定义请求体, 实现数据验证"""
    
    class UserCreate(BaseModel):
        username: str = Field(..., min_length=3, max_length=20, pattern=r'^[a-zA-Z0-9_]+$')
        email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
        age: int = Field(..., ge=0, le=150)
        tags: List[str] = Field(default_factory=list, max_length=5)
        
        @field_validator('username')
        @classmethod
        def username_no_admin(cls, v):
            if v.lower() == 'admin':
                raise ValueError('username cannot be "admin"')
            return v
    
    class UserResponse(BaseModel):
        id: int
        username: str
        email: str
        age: int
        created_at: datetime
    
    app = FastAPI()
    users: dict[int, dict] = {}
    next_id = [1]
    
    @app.post("/users", response_model=UserResponse, status_code=201)
    def create_user(user: UserCreate):
        uid = next_id[0]
        next_id[0] += 1
        user_dict = user.model_dump()
        user_dict["id"] = uid
        user_dict["created_at"] = datetime.now()
        users[uid] = user_dict
        return user_dict
    
    @app.get("/users/{uid}", response_model=UserResponse)
    def get_user(uid: int):
        if uid not in users:
            raise HTTPException(404, "User not found")
        return users[uid]
    
    client = TestClient(app)
    
    # 正常创建
    r = client.post("/users", json={
        "username": "koze_dev", "email": "koze@test.com", "age": 25, "tags": ["python", "ai"]
    })
    assert r.status_code == 201
    assert r.json()["username"] == "koze_dev"
    assert "created_at" in r.json()
    
    # 用户名太短
    r = client.post("/users", json={"username": "ab", "email": "a@b.com", "age": 20})
    assert r.status_code == 422
    
    # 年龄超范围
    r = client.post("/users", json={"username": "testuser", "email": "a@b.com", "age": 200})
    assert r.status_code == 422
    
    # 用户名包含 admin
    r = client.post("/users", json={"username": "admin", "email": "a@b.com", "age": 20})
    assert r.status_code == 422
    
    # 邮箱格式错误
    r = client.post("/users", json={"username": "testuser2", "email": "notanemail", "age": 20})
    assert r.status_code == 422
    
    # 响应模型过滤 (created_at 应存在)
    r = client.get("/users/1")
    assert r.status_code == 200
    assert r.json()["username"] == "koze_dev"
    
    print("✅ 练习2通过: Pydantic 模型 + 字段验证 + 自定义验证器")


# ============================================================
# 练习 3: 依赖注入 — 分层依赖 + 数据库会话模拟
# ============================================================

def test_03_dependency_injection():
    """FastAPI 依赖注入: 参数依赖, 分层依赖, Yield 依赖"""
    
    # 模拟数据库
    class FakeDB:
        def __init__(self):
            self.data = {"items": []}
            self.connected = True
        
        def add(self, item):
            self.data["items"].append(item)
            return item
        
        def query(self):
            return list(self.data["items"])
    
    db_instance = FakeDB()
    
    app = FastAPI()
    
    # 基础依赖: 获取数据库会话
    def get_db():
        if not db_instance.connected:
            raise HTTPException(503, "Database unavailable")
        yield db_instance  # yield 模式, 请求结束后可做清理
    
    # 分层依赖: 分页参数
    def pagination(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
        return {"skip": skip, "limit": limit}
    
    # 组合依赖: 需要 DB + 分页
    def get_items_with_pagination(db: FakeDB = Depends(get_db), paging: dict = Depends(pagination)):
        items = db.query()
        return items[paging["skip"]: paging["skip"] + paging["limit"]]
    
    @app.get("/items")
    def list_items(result: list = Depends(get_items_with_pagination)):
        return {"items": result, "count": len(result)}
    
    @app.post("/items")
    def create_item(name: str = Body(..., embed=True), db: FakeDB = Depends(get_db)):
        item = db.add({"name": name})
        return item
    
    @app.get("/db-status")
    def db_status(db: FakeDB = Depends(get_db)):
        return {"connected": db.connected, "total": len(db.data["items"])}
    
    client = TestClient(app)
    
    # 添加数据
    for i in range(5):
        r = client.post("/items", json={"name": f"item_{i}"})
        assert r.status_code == 200
        assert r.json()["name"] == f"item_{i}"
    
    # 查询全部
    r = client.get("/items")
    assert r.status_code == 200
    assert r.json()["count"] == 5
    
    # 分页
    r = client.get("/items?skip=2&limit=2")
    assert r.json()["count"] == 2
    
    # 分页超出范围
    r = client.get("/items?skip=10&limit=5")
    assert r.json()["count"] == 0
    
    # DB 状态
    r = client.get("/db-status")
    assert r.json()["connected"] is True
    assert r.json()["total"] == 5
    
    # 模拟 DB 断开
    db_instance.connected = False
    r = client.get("/items")
    assert r.status_code == 503
    db_instance.connected = True  # 恢复
    
    print("✅ 练习3通过: 依赖注入 + 分层依赖 + Yield 依赖 + 分页")


# ============================================================
# 练习 4: 中间件 — CORS + 请求日志 + 自定义Header
# ============================================================

def test_04_middleware():
    """FastAPI 中间件: CORS, 请求日志, 响应头注入"""
    app = FastAPI()
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 自定义中间件: 请求计时 + 日志
    request_log: list = []
    
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        request_log.append({
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration, 2)
        })
        response.headers["X-Process-Time"] = f"{duration:.4f}"
        response.headers["X-Custom-Header"] = "FastAPI-Learning"
        return response
    
    @app.get("/hello")
    def hello():
        return {"msg": "world"}
    
    @app.get("/error")
    def error_endpoint():
        raise HTTPException(500, "Something went wrong")
    
    client = TestClient(app)
    
    # 正常请求
    r = client.get("/hello")
    assert r.status_code == 200
    assert r.json()["msg"] == "world"
    assert "X-Process-Time" in r.headers
    assert r.headers["X-Custom-Header"] == "FastAPI-Learning"
    
    # CORS preflight
    r = client.options("/hello", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers
    
    # 错误请求也被记录
    r = client.get("/error")
    assert r.status_code == 500
    
    # 检查日志
    assert len(request_log) == 3
    assert request_log[0]["path"] == "/hello"
    assert request_log[0]["status"] == 200
    assert request_log[2]["status"] == 500
    
    print("✅ 练习4通过: CORS + 请求日志中间件 + 自定义响应头")


# ============================================================
# 练习 5: 后台任务 — 异步执行 + 任务状态追踪
# ============================================================

def test_05_background_tasks():
    """FastAPI 后台任务: 异步发送通知 + 文件处理"""
    app = FastAPI()
    
    task_results: dict = {}
    
    def send_notification(email: str, message: str):
        """模拟发送邮件通知"""
        time.sleep(0.1)
        task_results[email] = {"message": message, "sent_at": datetime.now().isoformat()}
    
    def process_file(file_id: str):
        """模拟文件处理"""
        time.sleep(0.1)
        task_results[file_id] = {"status": "processed", "size": 1024}
    
    @app.post("/notify")
    def notify(
        background_tasks: BackgroundTasks,
        email: str = Body(..., embed=True),
        message: str = Body(..., embed=True)
    ):
        background_tasks.add_task(send_notification, email, message)
        return {"status": "queued", "email": email}
    
    @app.post("/upload")
    def upload(background_tasks: BackgroundTasks, filename: str = Body(..., embed=True)):
        file_id = f"file_{filename}_{int(time.time())}"
        background_tasks.add_task(process_file, file_id)
        return {"file_id": file_id, "status": "processing"}
    
    @app.get("/task-status/{key}")
    def task_status(key: str):
        if key not in task_results:
            return {"status": "pending"}
        return task_results[key]
    
    client = TestClient(app)
    
    # 发送通知 (后台任务)
    r = client.post("/notify", json={"email": "user@test.com", "message": "Welcome!"})
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    
    # 后台任务在响应后执行, 需等待
    time.sleep(0.3)
    
    # 检查通知结果
    r = client.get("/task-status/user@test.com")
    assert r.json()["message"] == "Welcome!"
    assert "sent_at" in r.json()
    
    # 上传文件
    r = client.post("/upload", json={"filename": "report.pdf"})
    assert r.json()["status"] == "processing"
    time.sleep(0.3)
    
    # 检查文件处理结果
    file_id = r.json()["file_id"]
    r = client.get(f"/task-status/{file_id}")
    assert r.json()["status"] == "processed"
    
    print("✅ 练习5通过: 后台任务 + 通知发送 + 文件处理")


# ============================================================
# 练习 6: 异步路由 + async/await + 并发请求
# ============================================================

def test_06_async_routes():
    """异步路由 + 并发处理 + async 依赖"""
    app = FastAPI()
    
    async def fetch_data_async(source: str, delay: float = 0.05):
        """模拟异步数据获取"""
        await asyncio.sleep(delay)
        return {"source": source, "data": f"data_from_{source}", "fetched_at": time.time()}
    
    @app.get("/async-single")
    async def async_single():
        result = await fetch_data_async("db")
        return result
    
    @app.get("/async-concurrent")
    async def async_concurrent():
        """并发获取多个数据源"""
        results = await asyncio.gather(
            fetch_data_async("db", 0.05),
            fetch_data_async("cache", 0.03),
            fetch_data_async("api", 0.04),
        )
        return {"results": results, "count": len(results)}
    
    @app.get("/async-sequential")
    async def async_sequential():
        """顺序获取 (对比)"""
        results = []
        results.append(await fetch_data_async("db", 0.03))
        results.append(await fetch_data_async("cache", 0.03))
        results.append(await fetch_data_async("api", 0.03))
        return {"results": results, "count": len(results)}
    
    client = TestClient(app)
    
    # 单个异步请求
    r = client.get("/async-single")
    assert r.status_code == 200
    assert r.json()["source"] == "db"
    
    # 并发请求 (应该比顺序快)
    start = time.time()
    r = client.get("/async-concurrent")
    concurrent_time = time.time() - start
    assert r.status_code == 200
    assert r.json()["count"] == 3
    
    # 顺序请求
    start = time.time()
    r = client.get("/async-sequential")
    sequential_time = time.time() - start
    assert r.status_code == 200
    assert r.json()["count"] == 3
    
    # 并发应该更快 (3个0.03-0.05的任务, 并发~0.05s, 顺序~0.09s)
    assert concurrent_time < sequential_time, f"并发{concurrent_time:.3f}s应快于顺序{sequential_time:.3f}s"
    
    print(f"✅ 练习6通过: 异步路由 + 并发({concurrent_time:.3f}s) < 顺序({sequential_time:.3f}s)")


# ============================================================
# 练习 7: 自定义异常处理 + 统一错误响应
# ============================================================

def test_07_exception_handling():
    """自定义异常 + 全局异常处理器 + 统一错误格式"""
    app = FastAPI()
    
    # 自定义异常
    class BusinessError(Exception):
        def __init__(self, code: str, message: str, status_code: int = 400):
            self.code = code
            self.message = message
            self.status_code = status_code
    
    class NotFoundError(Exception):
        def __init__(self, resource: str, resource_id: str):
            self.resource = resource
            self.resource_id = resource_id
    
    # 统一错误响应格式
    def error_response(code: str, message: str, details: dict = None):
        return {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        }
    
    # 异常处理器
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.code, exc.message)
        )
    
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content=error_response(
                "NOT_FOUND",
                f"{exc.resource} with id '{exc.resource_id}' not found",
                {"resource": exc.resource, "id": exc.resource_id}
            )
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422,
            content=error_response("VALIDATION_ERROR", str(exc))
        )
    
    # 路由
    products = {"p1": {"name": "Widget", "price": 29.99}}
    
    @app.get("/products/{pid}")
    def get_product(pid: str):
        if pid not in products:
            raise NotFoundError("Product", pid)
        return products[pid]
    
    @app.post("/products/{pid}/purchase")
    def purchase(pid: str, quantity: int = Body(..., embed=True)):
        if pid not in products:
            raise NotFoundError("Product", pid)
        if quantity <= 0:
            raise BusinessError("INVALID_QUANTITY", "Quantity must be positive", 400)
        if quantity > 100:
            raise BusinessError("QUANTITY_EXCEEDED", "Cannot purchase more than 100 units", 400)
        return {"product_id": pid, "quantity": quantity, "total": products[pid]["price"] * quantity}
    
    @app.get("/calculate")
    def calculate(operation: str, a: float = 0, b: float = 0):
        if operation == "divide" and b == 0:
            raise ValueError("Cannot divide by zero")
        ops = {"add": a + b, "subtract": a - b, "multiply": a * b, "divide": a / b}
        if operation not in ops:
            raise BusinessError("UNKNOWN_OP", f"Unknown operation: {operation}", 400)
        return {"result": ops[operation]}
    
    client = TestClient(app)
    
    # 正常获取
    r = client.get("/products/p1")
    assert r.status_code == 200
    assert r.json()["name"] == "Widget"
    
    # 自定义 NotFound
    r = client.get("/products/p999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert "Product" in r.json()["error"]["message"]
    
    # 业务错误
    r = client.post("/products/p1/purchase", json={"quantity": 0})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_QUANTITY"
    
    r = client.post("/products/p1/purchase", json={"quantity": 200})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "QUANTITY_EXCEEDED"
    
    # ValueError 处理
    r = client.get("/calculate?operation=divide&a=10&b=0")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "divide by zero" in r.json()["error"]["message"]
    
    # 正常计算
    r = client.get("/calculate?operation=add&a=5&b=3")
    assert r.json()["result"] == 8.0
    
    print("✅ 练习7通过: 自定义异常 + 统一错误格式 + 多类型异常处理")


# ============================================================
# 练习 8: Lifespan 事件 + 应用生命周期管理
# ============================================================

def test_08_lifespan_events():
    """Lifespan 上下文管理器: 启动/关闭事件 + 资源管理"""
    startup_log = []
    shutdown_log = []
    shared_state = {}
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动
        startup_log.append("connecting_to_db")
        shared_state["db_connected"] = True
        shared_state["connection_time"] = datetime.now().isoformat()
        
        startup_log.append("loading_cache")
        shared_state["cache"] = {"cached_key": "cached_value"}
        
        startup_log.append("warming_up_models")
        shared_state["models_loaded"] = 3
        
        yield  # 应用运行
        
        # 关闭
        shutdown_log.append("closing_db")
        shared_state["db_connected"] = False
        
        shutdown_log.append("clearing_cache")
        shared_state.pop("cache", None)
        
        shutdown_log.append("releasing_models")
        shared_state.pop("models_loaded", None)
    
    app = FastAPI(lifespan=lifespan)
    
    @app.get("/health")
    def health():
        return {
            "db_connected": shared_state.get("db_connected", False),
            "models_loaded": shared_state.get("models_loaded", 0),
            "cache_keys": list(shared_state.get("cache", {}).keys()),
        }
    
    @app.get("/cache/{key}")
    def get_cache(key: str):
        cache = shared_state.get("cache", {})
        if key not in cache:
            raise HTTPException(404, "Cache key not found")
        return {"key": key, "value": cache[key]}
    
    with TestClient(app) as client:
        # 启动事件已执行
        assert "connecting_to_db" in startup_log
        assert "loading_cache" in startup_log
        assert "warming_up_models" in startup_log
        assert len(startup_log) == 3
        
        # 应用运行中
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["db_connected"] is True
        assert r.json()["models_loaded"] == 3
        assert "cached_key" in r.json()["cache_keys"]
        
        # 读取缓存
        r = client.get("/cache/cached_key")
        assert r.json()["value"] == "cached_value"
        
    # 退出 with 块后, 关闭事件已执行
    assert "closing_db" in shutdown_log
    assert "clearing_cache" in shutdown_log
    assert "releasing_models" in shutdown_log
    assert shared_state.get("db_connected") is False
    
    print("✅ 练习8通过: Lifespan 事件 + 启动/关闭资源管理")


# ============================================================
# 练习 9: API 认证 — API Key + Bearer Token + 权限控制
# ============================================================

def test_09_authentication():
    """API 认证: API Key 认证 + Bearer Token + 角色权限"""
    from fastapi import Header
    
    app = FastAPI()
    
    # 模拟用户数据库
    USERS = {
        "key_admin_123": {"username": "admin", "role": "admin"},
        "key_user_456": {"username": "user1", "role": "user"},
        "key_read_789": {"username": "reader", "role": "read_only"},
    }
    
    TOKENS = {
        "Bearer token_admin": {"username": "admin", "role": "admin"},
        "Bearer token_user": {"username": "user1", "role": "user"},
    }
    
    # API Key 依赖 (用 Header 手动实现, 兼容 TestClient)
    def get_current_user_by_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
        if x_api_key is None:
            raise HTTPException(401, "API Key required")
        if x_api_key not in USERS:
            raise HTTPException(401, "Invalid API Key")
        return USERS[x_api_key]
    
    # Bearer Token 依赖 (用 Header 手动实现)
    def get_current_user_by_token(authorization: Optional[str] = Header(None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Invalid authorization header")
        if authorization not in TOKENS:
            raise HTTPException(401, "Invalid token")
        return TOKENS[authorization]
    
    # 权限检查依赖
    def require_role(*roles):
        def role_checker(user: dict = Depends(get_current_user_by_api_key)):
            if user["role"] not in roles:
                raise HTTPException(403, f"Requires role: {roles}")
            return user
        return role_checker
    
    # 路由
    @app.get("/public")
    def public():
        return {"message": "Public endpoint"}
    
    @app.get("/api/data")
    def get_data(user: dict = Depends(get_current_user_by_api_key)):
        return {"data": "sensitive", "accessed_by": user["username"]}
    
    @app.get("/api/admin")
    def admin_only(user: dict = Depends(require_role("admin"))):
        return {"message": "Admin area", "admin": user["username"]}
    
    @app.get("/api/write")
    def write_data(user: dict = Depends(require_role("admin", "user"))):
        return {"message": "Write successful", "user": user["username"]}
    
    @app.get("/api/token-protected")
    def token_protected(user: dict = Depends(get_current_user_by_token)):
        return {"user": user["username"], "role": user["role"]}
    
    client = TestClient(app)
    
    # 公开接口
    r = client.get("/public")
    assert r.status_code == 200
    
    # 无 API Key
    r = client.get("/api/data")
    assert r.status_code == 401
    
    # 有效 API Key
    r = client.get("/api/data", headers={"X-API-Key": "key_user_456"})
    assert r.status_code == 200
    assert r.json()["accessed_by"] == "user1"
    
    # 无效 API Key
    r = client.get("/api/data", headers={"X-API-Key": "invalid_key"})
    assert r.status_code == 401
    
    # Admin 接口 - 有权限
    r = client.get("/api/admin", headers={"X-API-Key": "key_admin_123"})
    assert r.status_code == 200
    assert r.json()["admin"] == "admin"
    
    # Admin 接口 - 无权限
    r = client.get("/api/admin", headers={"X-API-Key": "key_user_456"})
    assert r.status_code == 403
    
    # Write 接口 - admin 和 user 可访问
    r = client.get("/api/write", headers={"X-API-Key": "key_admin_123"})
    assert r.status_code == 200
    
    r = client.get("/api/write", headers={"X-API-Key": "key_user_456"})
    assert r.status_code == 200
    
    # Write 接口 - read_only 无权限
    r = client.get("/api/write", headers={"X-API-Key": "key_read_789"})
    assert r.status_code == 403
    
    # Bearer Token 认证
    r = client.get("/api/token-protected", headers={"Authorization": "Bearer token_admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    
    # 无效 Token
    r = client.get("/api/token-protected", headers={"Authorization": "Bearer invalid_token"})
    assert r.status_code == 401
    
    print("✅ 练习9通过: API Key + Bearer Token + 角色权限控制")


# ============================================================
# 练习 10: 综合实战 — 完整的博客 API (路由分组 + 分页 + 认证)
# ============================================================

def test_10_blog_api_integration():
    """综合实战: 博客 API (文章CRUD + 评论 + 作者认证 + 分页)"""
    app = FastAPI(title="Blog API", version="1.0")
    
    # 数据模型
    class Author(BaseModel):
        id: int
        name: str
        email: str
    
    class PostCreate(BaseModel):
        title: str = Field(..., min_length=1, max_length=200)
        content: str = Field(..., min_length=1)
    
    class PostResponse(BaseModel):
        id: int
        title: str
        content: str
        author_id: int
        author_name: str
        created_at: datetime
        comments_count: int
    
    class CommentCreate(BaseModel):
        content: str = Field(..., min_length=1, max_length=500)
    
    class CommentResponse(BaseModel):
        id: int
        post_id: int
        content: str
        author_name: str
        created_at: datetime
    
    # 内存存储
    authors_db: dict[int, Author] = {
        1: Author(id=1, name="Alice", email="alice@blog.com"),
        2: Author(id=2, name="Bob", email="bob@blog.com"),
    }
    posts_db: dict[int, dict] = {}
    comments_db: dict[int, dict] = {}
    post_next_id = [1]
    comment_next_id = [1]
    
    # 认证依赖
    def get_author(author_id: int = Query(...)):
        if author_id not in authors_db:
            raise HTTPException(401, "Invalid author")
        return authors_db[author_id]
    
    # API 路由
    @app.get("/posts", response_model=List[PostResponse])
    def list_posts(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50)):
        all_posts = list(posts_db.values())
        result = []
        for p in all_posts[skip: skip + limit]:
            p_copy = {**p}
            p_copy["author_name"] = authors_db[p["author_id"]].name
            p_copy["comments_count"] = sum(1 for c in comments_db.values() if c["post_id"] == p["id"])
            result.append(p_copy)
        return result
    
    @app.post("/posts", response_model=PostResponse, status_code=201)
    def create_post(post: PostCreate, author: Author = Depends(get_author)):
        pid = post_next_id[0]
        post_next_id[0] += 1
        post_dict = {
            "id": pid,
            "title": post.title,
            "content": post.content,
            "author_id": author.id,
            "created_at": datetime.now(),
            "comments_count": 0,
            "author_name": author.name,
        }
        posts_db[pid] = post_dict
        return post_dict
    
    @app.get("/posts/{pid}", response_model=PostResponse)
    def get_post(pid: int):
        if pid not in posts_db:
            raise HTTPException(404, "Post not found")
        p = {**posts_db[pid]}
        p["author_name"] = authors_db[p["author_id"]].name
        p["comments_count"] = sum(1 for c in comments_db.values() if c["post_id"] == pid)
        return p
    
    @app.post("/posts/{pid}/comments", response_model=CommentResponse, status_code=201)
    def add_comment(pid: int, comment: CommentCreate, author: Author = Depends(get_author)):
        if pid not in posts_db:
            raise HTTPException(404, "Post not found")
        cid = comment_next_id[0]
        comment_next_id[0] += 1
        comment_dict = {
            "id": cid,
            "post_id": pid,
            "content": comment.content,
            "author_name": author.name,
            "created_at": datetime.now(),
        }
        comments_db[cid] = comment_dict
        return comment_dict
    
    @app.get("/posts/{pid}/comments", response_model=List[CommentResponse])
    def list_comments(pid: int):
        if pid not in posts_db:
            raise HTTPException(404, "Post not found")
        return [c for c in comments_db.values() if c["post_id"] == pid]
    
    @app.delete("/posts/{pid}", status_code=204)
    def delete_post(pid: int, author: Author = Depends(get_author)):
        if pid not in posts_db:
            raise HTTPException(404, "Post not found")
        if posts_db[pid]["author_id"] != author.id:
            raise HTTPException(403, "Can only delete your own posts")
        del posts_db[pid]
        # 删除关联评论
        to_del = [cid for cid, c in comments_db.items() if c["post_id"] == pid]
        for cid in to_del:
            del comments_db[cid]
    
    # === 测试完整流程 ===
    client = TestClient(app)
    
    # Alice 创建文章
    r = client.post("/posts?author_id=1", json={"title": "FastAPI Guide", "content": "Learning FastAPI is fun!"})
    assert r.status_code == 201
    post_id = r.json()["id"]
    assert r.json()["author_name"] == "Alice"
    assert r.json()["comments_count"] == 0
    
    # Bob 创建文章
    r = client.post("/posts?author_id=2", json={"title": "Vue Tips", "content": "Vue 3 composition API is great."})
    assert r.status_code == 201
    
    # 列表 + 分页
    r = client.get("/posts")
    assert len(r.json()) == 2
    
    r = client.get("/posts?skip=1&limit=1")
    assert len(r.json()) == 1
    
    # 获取单篇
    r = client.get(f"/posts/{post_id}")
    assert r.json()["title"] == "FastAPI Guide"
    
    # Alice 给自己的文章加评论
    r = client.post(f"/posts/{post_id}/comments?author_id=1", json={"content": "Great post!"})
    assert r.status_code == 201
    assert r.json()["author_name"] == "Alice"
    
    # Bob 也评论
    r = client.post(f"/posts/{post_id}/comments?author_id=2", json={"content": "Nice work!"})
    assert r.status_code == 201
    assert r.json()["author_name"] == "Bob"
    
    # 查看评论列表
    r = client.get(f"/posts/{post_id}/comments")
    assert len(r.json()) == 2
    
    # 查看文章评论数
    r = client.get(f"/posts/{post_id}")
    assert r.json()["comments_count"] == 2
    
    # Bob 尝试删除 Alice 的文章 (403)
    r = client.delete(f"/posts/{post_id}?author_id=2")
    assert r.status_code == 403
    
    # Alice 删除自己的文章
    r = client.delete(f"/posts/{post_id}?author_id=1")
    assert r.status_code == 204
    
    # 确认删除
    r = client.get(f"/posts/{post_id}")
    assert r.status_code == 404
    
    # 无效 author
    r = client.post("/posts?author_id=999", json={"title": "test", "content": "test"})
    assert r.status_code == 401
    
    print("✅ 练习10通过: 综合博客API (CRUD+评论+认证+权限+分页)")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("第三阶段 3.1 — FastAPI 后端开发 (10题)")
    print("=" * 60)
    print()
    
    tests = [
        test_01_basic_routing,
        test_02_pydantic_models,
        test_03_dependency_injection,
        test_04_middleware,
        test_05_background_tasks,
        test_06_async_routes,
        test_07_exception_handling,
        test_08_lifespan_events,
        test_09_authentication,
        test_10_blog_api_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            failed += 1
    
    print()
    print(f"结果: {passed}/{passed + failed} 通过")
    if failed == 0:
        print("🎉 全部通过!")
