"""
Kanban Board — 四状态任务追踪看板.

设计要点：
    - 四状态流转：TODO → RUNNING → DONE，任何状态均可转入 BLOCKED
    - 双模式存储：纯内存（dict）或 SQLite 持久化
    - 关联 StructuredGoal：每个任务可选关联一个目标 ID
    - 纯标准库：sqlite3, json, uuid, datetime, enum, dataclasses

Usage::

    from suyi.task import KanbanBoard, TaskStatus

    # 内存模式
    board = KanbanBoard()
    task = board.add_task("实现登录功能", priority="high")
    board.move_task(task.id, TaskStatus.RUNNING)

    # SQLite 持久化模式
    board = KanbanBoard(db_path="kanban.db")
    board.add_task("写文档", tags=["docs", "v1"])
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """任务状态枚举。"""
    TODO = "TODO"
    RUNNING = "RUNNING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


@dataclass
class KanbanTask:
    """
    看板任务。

    Attributes:
        id:          唯一标识（uuid4）
        title:       任务标题
        description: 任务描述
        status:      当前状态
        priority:    优先级 (low/normal/high/critical)
        created_at:  创建时间
        updated_at:  更新时间
        tags:        标签列表
        goal_id:     关联的 StructuredGoal ID（可选）
    """
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: str = "normal"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    goal_id: Optional[str] = None

    def __str__(self) -> str:
        """简洁的人类可读格式。"""
        tag_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        return f"[{self.status.value}] {self.title}{tag_str}"


class KanbanBoard:
    """
    四状态任务追踪看板。

    支持两种存储模式：
        - 纯内存模式（db_path=None）：数据存在 dict 中，进程结束即丢失
        - SQLite 持久化模式（db_path=路径）：数据写入 SQLite 数据库

    状态流转：
        TODO → RUNNING → DONE（正常流程）
        任何状态 → BLOCKED（阻塞）
        BLOCKED → TODO / RUNNING（解除阻塞）

    Attributes:
        db_path: 数据库路径，None 表示纯内存模式
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        初始化看板。

        Args:
            db_path: SQLite 数据库路径。None = 纯内存模式。
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

        if db_path is not None:
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
            self._create_table()
        else:
            # 纯内存存储
            self._memory: dict[str, KanbanTask] = {}

    def _create_table(self) -> None:
        """创建 SQLite 表（如果不存在）。"""
        assert self._conn is not None
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kanban_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'TODO',
                priority TEXT NOT NULL DEFAULT 'normal',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                goal_id TEXT
            )
        """)
        self._conn.commit()

    def _now_iso(self) -> str:
        """返回当前 UTC 时间的 ISO 格式字符串。"""
        return datetime.now(timezone.utc).isoformat()

    def _row_to_task(self, row: dict | sqlite3.Row) -> KanbanTask:
        """将数据库行转换为 KanbanTask。"""
        if isinstance(row, sqlite3.Row):
            row = dict(row)
        return KanbanTask(
            id=row["id"],
            title=row["title"],
            description=row.get("description", ""),
            status=TaskStatus(row["status"]),
            priority=row.get("priority", "normal"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            tags=json.loads(row.get("tags", "[]")),
            goal_id=row.get("goal_id"),
        )

    def _row_to_task_from_dict(self, row: dict) -> KanbanTask:
        """将 dict 行转换为 KanbanTask。"""
        return KanbanTask(
            id=row["id"],
            title=row["title"],
            description=row.get("description", ""),
            status=TaskStatus(row["status"]),
            priority=row.get("priority", "normal"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            tags=json.loads(row.get("tags", "[]")),
            goal_id=row.get("goal_id"),
        )

    # ── CRUD 操作 ───────────────────────────────────────────────

    def add_task(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        tags: Optional[list[str]] = None,
        goal_id: Optional[str] = None,
    ) -> KanbanTask:
        """
        添加新任务。

        Args:
            title:       任务标题
            description: 任务描述
            priority:    优先级
            tags:        标签列表
            goal_id:     关联的目标 ID

        Returns:
            新创建的 KanbanTask
        """
        now = self._now_iso()
        task = KanbanTask(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status=TaskStatus.TODO,
            priority=priority,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            tags=tags or [],
            goal_id=goal_id,
        )

        if self._conn is not None:
            self._conn.execute(
                """INSERT INTO kanban_tasks
                   (id, title, description, status, priority, created_at, updated_at, tags, goal_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id, task.title, task.description,
                    task.status.value, task.priority,
                    now, now,
                    json.dumps(task.tags), task.goal_id,
                ),
            )
            self._conn.commit()
        else:
            self._memory[task.id] = task

        return task

    def get_task(self, task_id: str) -> Optional[KanbanTask]:
        """
        根据 ID 获取任务。

        Args:
            task_id: 任务 ID

        Returns:
            KanbanTask 或 None
        """
        if self._conn is not None:
            cursor = self._conn.execute(
                "SELECT * FROM kanban_tasks WHERE id = ?", (task_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_task(row)
        else:
            return self._memory.get(task_id)

    def get_tasks(self, status: Optional[TaskStatus] = None) -> list[KanbanTask]:
        """
        获取任务列表，可按状态筛选。

        Args:
            status: 筛选状态，None = 全部

        Returns:
            任务列表
        """
        if self._conn is not None:
            if status is not None:
                cursor = self._conn.execute(
                    "SELECT * FROM kanban_tasks WHERE status = ? ORDER BY created_at",
                    (status.value,),
                )
            else:
                cursor = self._conn.execute(
                    "SELECT * FROM kanban_tasks ORDER BY created_at"
                )
            return [self._row_to_task(row) for row in cursor.fetchall()]
        else:
            tasks = list(self._memory.values())
            if status is not None:
                tasks = [t for t in tasks if t.status == status]
            return sorted(tasks, key=lambda t: t.created_at)

    def get_all(self) -> list[KanbanTask]:
        """
        获取所有任务。

        Returns:
            全部任务列表
        """
        return self.get_tasks(status=None)

    def move_task(self, task_id: str, new_status: TaskStatus) -> bool:
        """
        移动任务到新状态。

        Args:
            task_id:    任务 ID
            new_status: 新状态

        Returns:
            True=成功, False=任务不存在
        """
        task = self.get_task(task_id)
        if task is None:
            return False

        now = self._now_iso()
        if self._conn is not None:
            self._conn.execute(
                """UPDATE kanban_tasks
                   SET status = ?, updated_at = ?
                   WHERE id = ?""",
                (new_status.value, now, task_id),
            )
            self._conn.commit()
        else:
            task.status = new_status
            task.updated_at = datetime.fromisoformat(now)
            self._memory[task_id] = task

        return True

    def update_task(self, task_id: str, **kwargs) -> bool:
        """
        更新任务字段。

        支持的字段：title, description, priority, status, tags, goal_id

        Args:
            task_id: 任务 ID
            **kwargs: 要更新的字段和值

        Returns:
            True=成功, False=任务不存在
        """
        task = self.get_task(task_id)
        if task is None:
            return False

        now = self._now_iso()
        updates: dict[str, object] = {"updated_at": now}

        if "title" in kwargs:
            updates["title"] = kwargs["title"]
        if "description" in kwargs:
            updates["description"] = kwargs["description"]
        if "priority" in kwargs:
            updates["priority"] = kwargs["priority"]
        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, TaskStatus):
                updates["status"] = status_val.value
            else:
                updates["status"] = status_val
        if "tags" in kwargs:
            updates["tags"] = json.dumps(kwargs["tags"])
        if "goal_id" in kwargs:
            updates["goal_id"] = kwargs["goal_id"]

        if self._conn is not None:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [task_id]
            self._conn.execute(
                f"UPDATE kanban_tasks SET {set_clause} WHERE id = ?",
                values,
            )
            self._conn.commit()
        else:
            # 更新内存中的任务
            for k, v in updates.items():
                if k == "updated_at":
                    task.updated_at = datetime.fromisoformat(str(v))
                elif k == "status":
                    task.status = TaskStatus(str(v))
                elif k == "tags":
                    task.tags = json.loads(str(v))
                elif k == "goal_id":
                    task.goal_id = v  # type: ignore[assignment]
                elif hasattr(task, k):
                    setattr(task, k, v)
            self._memory[task_id] = task

        return True

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务。

        Args:
            task_id: 任务 ID

        Returns:
            True=成功删除, False=任务不存在
        """
        if self._conn is not None:
            cursor = self._conn.execute(
                "DELETE FROM kanban_tasks WHERE id = ?", (task_id,)
            )
            self._conn.commit()
            return cursor.rowcount > 0
        else:
            if task_id in self._memory:
                del self._memory[task_id]
                return True
            return False

    def get_board_summary(self) -> dict[TaskStatus, int]:
        """
        获取看板状态摘要。

        Returns:
            {TaskStatus: 数量} 字典，包含所有四种状态
        """
        summary: dict[TaskStatus, int] = {
            TaskStatus.TODO: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.DONE: 0,
            TaskStatus.BLOCKED: 0,
        }

        if self._conn is not None:
            cursor = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM kanban_tasks GROUP BY status"
            )
            for row in cursor.fetchall():
                status = TaskStatus(row["status"])
                summary[status] = row["cnt"]
        else:
            for task in self._memory.values():
                summary[task.status] += 1

        return summary

    def close(self) -> None:
        """关闭数据库连接（仅 SQLite 模式）。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        """析构时关闭连接。"""
        self.close()

    def __repr__(self) -> str:
        mode = f"db={self.db_path!r}" if self.db_path else "memory"
        count = len(self.get_all())
        return f"KanbanBoard({mode}, tasks={count})"
