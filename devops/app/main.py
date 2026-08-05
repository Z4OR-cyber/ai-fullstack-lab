"""
第2题：被容器化的 FastAPI 应用
功能：提供一个简单的待办事项 API，包含健康检查端点
运行：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Todo API",
    description="一个简单的待办事项 API，用于 Docker 容器化练习",
    version="1.0.0",
)


# -------------------- 数据模型 --------------------
class TodoCreate(BaseModel):
    """创建待办事项的请求模型"""
    title: str
    description: Optional[str] = None


class TodoResponse(BaseModel):
    """待办事项的响应模型"""
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    created_at: str


# -------------------- 模拟数据库 --------------------
_todos: dict[int, dict] = {}
_next_id: int = 1


# -------------------- 路由 --------------------
@app.get("/health")
async def health_check():
    """健康检查端点，供 Docker HEALTHCHECK 和 K8s Probe 调用"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/")
async def root():
    """根路径，返回 API 基本信息"""
    return {
        "service": "Todo API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/todos")
async def list_todos():
    """获取所有待办事项"""
    return list(_todos.values())


@app.post("/todos", response_model=TodoResponse, status_code=201)
async def create_todo(todo: TodoCreate):
    """创建新的待办事项"""
    global _next_id
    todo_data = {
        "id": _next_id,
        "title": todo.title,
        "description": todo.description,
        "completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _todos[_next_id] = todo_data
    _next_id += 1
    return todo_data


@app.get("/todos/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: int):
    """根据 ID 获取单个待办事项"""
    if todo_id not in _todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    return _todos[todo_id]


@app.patch("/todos/{todo_id}/complete", response_model=TodoResponse)
async def complete_todo(todo_id: int):
    """标记待办事项为已完成"""
    if todo_id not in _todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    _todos[todo_id]["completed"] = True
    return _todos[todo_id]


@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    """删除待办事项"""
    if todo_id not in _todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    del _todos[todo_id]
    return None
