"""
Kanban Board — 四状态任务追踪看板测试.

覆盖：
    - TaskStatus 枚举
    - KanbanTask 数据类
    - KanbanBoard 内存模式 CRUD
    - KanbanBoard SQLite 模式 CRUD
    - 状态流转（move_task）
    - update_task 字段更新
    - delete_task 删除
    - get_board_summary 状态摘要
    - 边界条件：不存在的任务、重复操作等
"""

import os
import tempfile
import pytest

from suyi.task.kanban import KanbanBoard, KanbanTask, TaskStatus


# ═══════════════════════════════════════════════════════════════
# TaskStatus 枚举测试
# ═══════════════════════════════════════════════════════════════

class TestTaskStatus:
    """测试 TaskStatus 枚举。"""

    def test_four_states(self):
        """四种状态。"""
        assert TaskStatus.TODO.value == "TODO"
        assert TaskStatus.RUNNING.value == "RUNNING"
        assert TaskStatus.DONE.value == "DONE"
        assert TaskStatus.BLOCKED.value == "BLOCKED"

    def test_is_str(self):
        """继承 str。"""
        assert isinstance(TaskStatus.TODO, str)
        assert TaskStatus.TODO == "TODO"


# ═══════════════════════════════════════════════════════════════
# KanbanTask 数据类测试
# ═══════════════════════════════════════════════════════════════

class TestKanbanTask:
    """测试 KanbanTask 数据类。"""

    def test_default_values(self):
        """默认值正确。"""
        from datetime import datetime, timezone
        task = KanbanTask(id="abc", title="测试任务")
        assert task.title == "测试任务"
        assert task.description == ""
        assert task.status == TaskStatus.TODO
        assert task.priority == "normal"
        assert task.tags == []
        assert task.goal_id is None

    def test_str_format(self):
        """__str__ 格式正确。"""
        task = KanbanTask(id="1", title="写代码")
        assert "[TODO] 写代码" in str(task)

    def test_str_with_tags(self):
        """带标签的 __str__。"""
        task = KanbanTask(id="1", title="写代码", tags=["urgent", "v2"])
        s = str(task)
        assert "urgent" in s
        assert "v2" in s


# ═══════════════════════════════════════════════════════════════
# KanbanBoard 内存模式测试
# ═══════════════════════════════════════════════════════════════

class TestKanbanBoardMemory:
    """测试 KanbanBoard 的内存模式。"""

    @pytest.fixture
    def board(self):
        """创建内存模式看板。"""
        return KanbanBoard()

    def test_add_task(self, board):
        """添加任务。"""
        task = board.add_task("实现登录功能")
        assert task.title == "实现登录功能"
        assert task.status == TaskStatus.TODO
        assert len(task.id) > 0

    def test_add_task_with_details(self, board):
        """添加带详细描述的任务。"""
        task = board.add_task(
            title="写文档",
            description="API 文档和部署指南",
            priority="high",
            tags=["docs", "v1"],
            goal_id="goal-123",
        )
        assert task.description == "API 文档和部署指南"
        assert task.priority == "high"
        assert task.tags == ["docs", "v1"]
        assert task.goal_id == "goal-123"

    def test_get_task(self, board):
        """根据 ID 获取任务。"""
        task = board.add_task("测试获取")
        found = board.get_task(task.id)
        assert found is not None
        assert found.title == "测试获取"

    def test_get_task_not_found(self, board):
        """获取不存在的任务返回 None。"""
        assert board.get_task("nonexistent") is None

    def test_get_all(self, board):
        """获取所有任务。"""
        board.add_task("任务1")
        board.add_task("任务2")
        board.add_task("任务3")
        assert len(board.get_all()) == 3

    def test_get_tasks_by_status(self, board):
        """按状态筛选任务。"""
        t1 = board.add_task("任务1")
        t2 = board.add_task("任务2")
        board.move_task(t1.id, TaskStatus.RUNNING)

        todo_tasks = board.get_tasks(TaskStatus.TODO)
        running_tasks = board.get_tasks(TaskStatus.RUNNING)

        assert len(todo_tasks) == 1
        assert todo_tasks[0].title == "任务2"
        assert len(running_tasks) == 1
        assert running_tasks[0].title == "任务1"

    def test_move_task(self, board):
        """移动任务状态。"""
        task = board.add_task("测试移动")
        assert board.move_task(task.id, TaskStatus.RUNNING)
        updated = board.get_task(task.id)
        assert updated.status == TaskStatus.RUNNING

    def test_move_task_full_flow(self, board):
        """完整状态流转：TODO → RUNNING → DONE。"""
        task = board.add_task("流转测试")
        assert task.status == TaskStatus.TODO
        board.move_task(task.id, TaskStatus.RUNNING)
        assert board.get_task(task.id).status == TaskStatus.RUNNING
        board.move_task(task.id, TaskStatus.DONE)
        assert board.get_task(task.id).status == TaskStatus.DONE

    def test_move_to_blocked(self, board):
        """任何状态都可以转入 BLOCKED。"""
        task = board.add_task("阻塞测试")
        assert board.move_task(task.id, TaskStatus.BLOCKED)
        assert board.get_task(task.id).status == TaskStatus.BLOCKED

    def test_unblock(self, board):
        """从 BLOCKED 恢复到 TODO。"""
        task = board.add_task("阻塞恢复")
        board.move_task(task.id, TaskStatus.BLOCKED)
        board.move_task(task.id, TaskStatus.TODO)
        assert board.get_task(task.id).status == TaskStatus.TODO

    def test_move_nonexistent_returns_false(self, board):
        """移动不存在的任务返回 False。"""
        assert board.move_task("nonexistent", TaskStatus.RUNNING) is False

    def test_delete_task(self, board):
        """删除任务。"""
        task = board.add_task("要删除的任务")
        assert board.delete_task(task.id) is True
        assert board.get_task(task.id) is None
        assert len(board.get_all()) == 0

    def test_delete_nonexistent_returns_false(self, board):
        """删除不存在的任务返回 False。"""
        assert board.delete_task("nonexistent") is False

    def test_update_task_title(self, board):
        """更新任务标题。"""
        task = board.add_task("原标题")
        board.update_task(task.id, title="新标题")
        assert board.get_task(task.id).title == "新标题"

    def test_update_task_description(self, board):
        """更新任务描述。"""
        task = board.add_task("测试")
        board.update_task(task.id, description="新描述")
        assert board.get_task(task.id).description == "新描述"

    def test_update_task_tags(self, board):
        """更新任务标签。"""
        task = board.add_task("测试", tags=["old"])
        board.update_task(task.id, tags=["new1", "new2"])
        assert board.get_task(task.id).tags == ["new1", "new2"]

    def test_update_task_priority(self, board):
        """更新任务优先级。"""
        task = board.add_task("测试")
        board.update_task(task.id, priority="critical")
        assert board.get_task(task.id).priority == "critical"

    def test_update_task_status(self, board):
        """通过 update_task 更新状态。"""
        task = board.add_task("测试")
        board.update_task(task.id, status=TaskStatus.DONE)
        assert board.get_task(task.id).status == TaskStatus.DONE

    def test_update_task_goal_id(self, board):
        """更新任务的 goal_id。"""
        task = board.add_task("测试")
        board.update_task(task.id, goal_id="goal-456")
        assert board.get_task(task.id).goal_id == "goal-456"

    def test_update_nonexistent_returns_false(self, board):
        """更新不存在的任务返回 False。"""
        assert board.update_task("nonexistent", title="x") is False

    def test_get_board_summary_empty(self, board):
        """空看板的摘要。"""
        summary = board.get_board_summary()
        assert summary == {
            TaskStatus.TODO: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.DONE: 0,
            TaskStatus.BLOCKED: 0,
        }

    def test_get_board_summary(self, board):
        """有任务的看板摘要。"""
        t1 = board.add_task("任务1")
        t2 = board.add_task("任务2")
        t3 = board.add_task("任务3")
        board.move_task(t1.id, TaskStatus.RUNNING)
        board.move_task(t2.id, TaskStatus.DONE)

        summary = board.get_board_summary()
        assert summary[TaskStatus.TODO] == 1
        assert summary[TaskStatus.RUNNING] == 1
        assert summary[TaskStatus.DONE] == 1
        assert summary[TaskStatus.BLOCKED] == 0

    def test_task_ids_unique(self, board):
        """每个任务的 ID 唯一。"""
        tasks = [board.add_task(f"任务{i}") for i in range(10)]
        ids = [t.id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_tags_default_empty(self, board):
        """不传 tags 时默认为空列表。"""
        task = board.add_task("无标签")
        assert task.tags == []

    def test_update_time_changes(self, board):
        """更新后 updated_at 应该变化。"""
        task = board.add_task("时间测试")
        original_updated = task.updated_at
        import time
        time.sleep(0.01)  # 确保时间差异
        board.update_task(task.id, title="更新后")
        updated_task = board.get_task(task.id)
        assert updated_task.updated_at >= original_updated

    def test_repr(self, board):
        """__repr__ 包含模式和数量。"""
        board.add_task("任务1")
        r = repr(board)
        assert "memory" in r
        assert "tasks=1" in r


# ═══════════════════════════════════════════════════════════════
# KanbanBoard SQLite 模式测试
# ═══════════════════════════════════════════════════════════════

class TestKanbanBoardSQLite:
    """测试 KanbanBoard 的 SQLite 持久化模式。"""

    @pytest.fixture
    def db_board(self, tmp_path):
        """创建 SQLite 模式看板。"""
        db_path = str(tmp_path / "test_kanban.db")
        board = KanbanBoard(db_path=db_path)
        yield board
        board.close()

    def test_add_and_get(self, db_board):
        """SQLite 模式下添加和获取任务。"""
        task = db_board.add_task("SQLite任务")
        found = db_board.get_task(task.id)
        assert found is not None
        assert found.title == "SQLite任务"

    def test_persistence(self, tmp_path):
        """数据持久化：关闭后重新打开能读到。"""
        db_path = str(tmp_path / "persist.db")

        # 写入
        board1 = KanbanBoard(db_path=db_path)
        task = board1.add_task("持久化测试", tags=["p", "test"])
        task_id = task.id
        board1.close()

        # 重新打开读取
        board2 = KanbanBoard(db_path=db_path)
        found = board2.get_task(task_id)
        assert found is not None
        assert found.title == "持久化测试"
        assert found.tags == ["p", "test"]
        board2.close()

    def test_move_task_sqlite(self, db_board):
        """SQLite 模式下移动任务。"""
        task = db_board.add_task("移动测试")
        db_board.move_task(task.id, TaskStatus.RUNNING)
        found = db_board.get_task(task.id)
        assert found.status == TaskStatus.RUNNING

    def test_update_task_sqlite(self, db_board):
        """SQLite 模式下更新任务。"""
        task = db_board.add_task("更新测试")
        db_board.update_task(task.id, title="新标题", description="新描述")
        found = db_board.get_task(task.id)
        assert found.title == "新标题"
        assert found.description == "新描述"

    def test_delete_task_sqlite(self, db_board):
        """SQLite 模式下删除任务。"""
        task = db_board.add_task("删除测试")
        assert db_board.delete_task(task.id) is True
        assert db_board.get_task(task.id) is None

    def test_get_tasks_by_status_sqlite(self, db_board):
        """SQLite 模式下按状态筛选。"""
        t1 = db_board.add_task("任务1")
        t2 = db_board.add_task("任务2")
        db_board.move_task(t1.id, TaskStatus.DONE)

        done = db_board.get_tasks(TaskStatus.DONE)
        todo = db_board.get_tasks(TaskStatus.TODO)
        assert len(done) == 1
        assert len(todo) == 1

    def test_get_board_summary_sqlite(self, db_board):
        """SQLite 模式下的看板摘要。"""
        db_board.add_task("A")
        t2 = db_board.add_task("B")
        db_board.move_task(t2.id, TaskStatus.BLOCKED)

        summary = db_board.get_board_summary()
        assert summary[TaskStatus.TODO] == 1
        assert summary[TaskStatus.BLOCKED] == 1

    def test_tags_json_serialization(self, db_board):
        """tags 用 JSON 序列化存储。"""
        task = db_board.add_task("JSON测试", tags=["中文标签", "english"])
        found = db_board.get_task(task.id)
        assert found.tags == ["中文标签", "english"]

    def test_update_tags_sqlite(self, db_board):
        """SQLite 模式下更新 tags。"""
        task = db_board.add_task("标签更新", tags=["old"])
        db_board.update_task(task.id, tags=["new1", "new2"])
        found = db_board.get_task(task.id)
        assert found.tags == ["new1", "new2"]

    def test_goal_id_persistence(self, db_board):
        """goal_id 持久化。"""
        task = db_board.add_task("关联目标", goal_id="goal-789")
        found = db_board.get_task(task.id)
        assert found.goal_id == "goal-789"

    def test_repr_sqlite(self, db_board):
        """SQLite 模式的 __repr__。"""
        db_board.add_task("X")
        r = repr(db_board)
        assert "db=" in r
        assert "tasks=1" in r
