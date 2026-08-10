"""
Task Scheduler — Cron-driven task registration, scheduling, and persistence.

Manages a collection of ``ScheduledTask`` objects, each bound to a
cron expression. The scheduler determines which tasks are due at a
given time and tracks execution history.

Persistence:
    - When a ``SQLiteBackend`` (or any backend with ``get``/``set``/
      ``delete``/``list_keys``) is provided, tasks are stored under
      the ``scheduler:`` namespace.
    - When ``backend=None``, an in-memory dict is used.

Design:
    - Pure Python standard library only.
    - All state changes are immediately persisted (when backend is set).
    - Supports Mock injection for testing.
    - ``ScheduledTask`` and ``TaskScheduler`` both support
      ``to_dict`` / ``from_dict`` serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

from .cron_expr import CronExpression


# ═══════════════════════════════════════════════════════════════
#  Backend Protocol (Duck-typed)
# ═══════════════════════════════════════════════════════════════


@runtime_checkable
class SchedulerBackend(Protocol):
    """Minimal backend protocol for scheduler persistence.

    Any object with ``get``, ``set``, ``delete``, and ``list_keys``
    methods satisfies this protocol — notably ``SQLiteBackend`` and
    ``JSONBackend``.
    """

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...

    def delete(self, key: str) -> bool: ...

    def list_keys(self, pattern: Optional[str] = None) -> list[str]: ...


# ═══════════════════════════════════════════════════════════════
#  ScheduledTask
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScheduledTask:
    """
    A single scheduled task with its cron expression and configuration.

    Attributes:
        name:        Unique task identifier.
        cron_expr:   ``CronExpression`` determining when the task fires.
        task_config: Free-form dict of task parameters (e.g. prompt,
                     tools, budget) passed to the executor.
        enabled:     Whether the task is active (disabled tasks are
                     skipped by ``get_pending_tasks``).
        last_run:    Timestamp of the most recent execution, or ``None``.
        next_run:    Pre-computed next fire time, or ``None`` if not
                     yet calculated.
        last_result: Result of the most recent execution, or ``None``.
        run_count:   Total number of times this task has been executed.
    """

    name: str
    cron_expr: CronExpression
    task_config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Optional[dict[str, Any]] = None
    run_count: int = 0

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence.

        Datetime fields are converted to ISO-8601 strings.

        Returns:
            A JSON-serializable dict.
        """
        return {
            "name": self.name,
            "cron_expression": self.cron_expr.expression,
            "task_config": self.task_config,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_result": self.last_result,
            "run_count": self.run_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScheduledTask":
        """Reconstruct a ``ScheduledTask`` from a dict.

        Args:
            d: A dict produced by ``to_dict``.

        Returns:
            A new ``ScheduledTask`` instance.
        """
        last_run = None
        if d.get("last_run"):
            last_run = datetime.fromisoformat(d["last_run"])

        next_run = None
        if d.get("next_run"):
            next_run = datetime.fromisoformat(d["next_run"])

        return cls(
            name=d["name"],
            cron_expr=CronExpression(d["cron_expression"]),
            task_config=d.get("task_config", {}),
            enabled=d.get("enabled", True),
            last_run=last_run,
            next_run=next_run,
            last_result=d.get("last_result"),
            run_count=d.get("run_count", 0),
        )

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return (
            f"ScheduledTask(name={self.name!r}, "
            f"cron='{self.cron_expr.expression}', {status})"
        )


# ═══════════════════════════════════════════════════════════════
#  TaskScheduler
# ═══════════════════════════════════════════════════════════════


class TaskScheduler:
    """
    Manages registration, scheduling, and persistence of cron tasks.

    The scheduler maintains an in-memory registry of ``ScheduledTask``
    objects and optionally mirrors them to a persistent backend.

    Args:
        backend:    A ``SchedulerBackend``-compatible object (e.g.
                    ``SQLiteBackend``) for persistence.  When ``None``,
                    an in-memory dict is used and nothing is persisted.
        namespace:  Key namespace prefix for backend storage.
                    Default: ``"scheduler:"``.

    Usage::

        scheduler = TaskScheduler(backend=SQLiteBackend("./data/suyi.db"))
        scheduler.register_task("daily_report", "0 9 * * *", {"prompt": "..."})
        due = scheduler.get_pending_tasks(datetime.now())
        for task in due:
            # execute task...
            scheduler.mark_executed(task.name, {"success": True})
    """

    def __init__(
        self,
        backend: Optional[SchedulerBackend] = None,
        namespace: str = "scheduler:",
    ) -> None:
        self._backend: Optional[SchedulerBackend] = backend
        self._namespace: str = namespace
        self._tasks: dict[str, ScheduledTask] = {}

        # Load existing tasks from backend on init
        if self._backend is not None:
            self._load_from_backend()

    # ── Key Helpers ────────────────────────────────────────────

    def _make_key(self, name: str) -> str:
        """Build a backend storage key for a task name."""
        return f"{self._namespace}{name}"

    def _load_from_backend(self) -> None:
        """Load all tasks from the backend into the in-memory registry."""
        assert self._backend is not None
        pattern = self._namespace
        keys = self._backend.list_keys(pattern)
        for key in keys:
            data = self._backend.get(key)
            if data and isinstance(data, dict):
                try:
                    task = ScheduledTask.from_dict(data)
                    self._tasks[task.name] = task
                except (KeyError, ValueError):
                    # Skip corrupted entries
                    continue

    def _persist_task(self, task: ScheduledTask) -> None:
        """Save a single task to the backend (if configured)."""
        if self._backend is not None:
            self._backend.set(self._make_key(task.name), task.to_dict())

    def _delete_task_from_backend(self, name: str) -> None:
        """Remove a task from the backend (if configured)."""
        if self._backend is not None:
            self._backend.delete(self._make_key(name))

    # ── Public API ─────────────────────────────────────────────

    def register_task(
        self,
        name: str,
        cron_expr: str,
        task_config: Optional[dict[str, Any]] = None,
        enabled: bool = True,
    ) -> ScheduledTask:
        """Register a new scheduled task or update an existing one.

        Args:
            name:        Unique task name. If a task with this name
                         already exists, it will be replaced.
            cron_expr:   Cron expression string (e.g. ``"0 9 * * *"``).
            task_config: Free-form configuration dict for the task.
            enabled:     Whether the task starts enabled.

        Returns:
            The newly created ``ScheduledTask``.

        Raises:
            ValueError: If the cron expression is invalid.
        """
        cron = CronExpression(cron_expr)
        task = ScheduledTask(
            name=name,
            cron_expr=cron,
            task_config=task_config or {},
            enabled=enabled,
        )
        # Compute initial next_run
        task.next_run = cron.next_run(datetime.now())
        self._tasks[name] = task
        self._persist_task(task)
        return task

    def remove_task(self, name: str) -> bool:
        """Remove a scheduled task by name.

        Args:
            name: The task name to remove.

        Returns:
            ``True`` if the task existed and was removed,
            ``False`` otherwise.
        """
        if name in self._tasks:
            del self._tasks[name]
            self._delete_task_from_backend(name)
            return True
        return False

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        """Retrieve a task by name.

        Args:
            name: The task name.

        Returns:
            The ``ScheduledTask`` or ``None`` if not found.
        """
        return self._tasks.get(name)

    def list_tasks(self, enabled_only: bool = False) -> list[ScheduledTask]:
        """List all registered tasks.

        Args:
            enabled_only: If ``True``, only return enabled tasks.

        Returns:
            A list of ``ScheduledTask`` objects, sorted by name.
        """
        tasks = list(self._tasks.values())
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return sorted(tasks, key=lambda t: t.name)

    def enable_task(self, name: str) -> bool:
        """Enable a previously disabled task.

        Args:
            name: The task name.

        Returns:
            ``True`` if the task was found and enabled.
        """
        task = self._tasks.get(name)
        if task is None:
            return False
        task.enabled = True
        task.next_run = task.cron_expr.next_run(datetime.now())
        self._persist_task(task)
        return True

    def disable_task(self, name: str) -> bool:
        """Disable a task (it will be skipped by get_pending_tasks).

        Args:
            name: The task name.

        Returns:
            ``True`` if the task was found and disabled.
        """
        task = self._tasks.get(name)
        if task is None:
            return False
        task.enabled = False
        self._persist_task(task)
        return True

    def get_pending_tasks(self, now: datetime) -> list[ScheduledTask]:
        """Return all enabled tasks that are due at or before *now*.

        A task is "pending" if:
            - It is enabled.
            - Its ``next_run`` is ``None`` or ≤ *now*.
            - It has not been executed since its last ``next_run``.

        After returning pending tasks, their ``next_run`` is **not**
        automatically updated — call ``mark_executed`` to advance the
        schedule.

        Args:
            now: The current datetime.

        Returns:
            A list of due ``ScheduledTask`` objects, sorted by
            ``next_run`` ascending.
        """
        pending: list[ScheduledTask] = []
        for task in self._tasks.values():
            if not task.enabled:
                continue
            if task.next_run is None:
                # Recompute if missing
                task.next_run = task.cron_expr.next_run(now)
                self._persist_task(task)
            if task.next_run <= now:
                pending.append(task)
        pending.sort(key=lambda t: t.next_run or now)
        return pending

    def mark_executed(
        self,
        name: str,
        result: dict[str, Any],
        now: Optional[datetime] = None,
    ) -> Optional[ScheduledTask]:
        """Record the execution result of a task and advance its schedule.

        Updates ``last_run``, ``last_result``, increments ``run_count``,
        and recomputes ``next_run`` based on the cron expression.

        Args:
            name:   The task name.
            result: A dict describing the execution result (e.g.
                    ``{"success": True, "output": "..."}``).
            now:    The timestamp to use as "now" for computing the
                    next run. Defaults to ``datetime.now()``.

        Returns:
            The updated ``ScheduledTask``, or ``None`` if the task
            was not found.
        """
        task = self._tasks.get(name)
        if task is None:
            return None

        current_time = now or datetime.now()
        task.last_run = current_time
        task.last_result = result
        task.run_count += 1
        task.next_run = task.cron_expr.next_run(current_time)
        self._persist_task(task)
        return task

    def update_next_runs(self, now: datetime) -> None:
        """Recompute ``next_run`` for all enabled tasks.

        Useful after a period of downtime or when the system clock
        has changed.

        Args:
            now: The reference datetime.
        """
        for task in self._tasks.values():
            if task.enabled:
                task.next_run = task.cron_expr.next_run(now)
                self._persist_task(task)

    def count(self) -> int:
        """Return the total number of registered tasks."""
        return len(self._tasks)

    def clear(self) -> int:
        """Remove all tasks.

        Returns:
            The number of tasks removed.
        """
        count = len(self._tasks)
        names = list(self._tasks.keys())
        for name in names:
            self._delete_task_from_backend(name)
        self._tasks.clear()
        return count

    def __repr__(self) -> str:
        backend_type = type(self._backend).__name__ if self._backend else "None"
        return (
            f"TaskScheduler(tasks={len(self._tasks)}, "
            f"backend={backend_type})"
        )
