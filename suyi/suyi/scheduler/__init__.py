"""
Suyi Scheduler — Cron-driven task scheduling and trigger integration.

Exports:
    CronExpression:  Standard 5-field cron expression parser.
    ScheduledTask:   Dataclass representing a single scheduled task.
    TaskScheduler:   Manages task registration, scheduling, and persistence.
    CronTrigger:     Connects ScheduledTask to AgentLoop execution.
    TriggerResult:   Result of a single trigger execution.
    MockLoop:        Mock loop for testing CronTrigger.
    TriggerableLoop: Protocol for injectable loop objects.
    SchedulerBackend: Protocol for injectable backend objects.

Design:
    - Pure Python standard library only (no external dependencies).
    - Supports SQLiteBackend persistence (namespace: ``scheduler:``).
    - All components support Mock injection for testing.
    - Serialization via ``to_dict`` / ``from_dict``.

Usage::

    from suyi.scheduler import (
        CronExpression, TaskScheduler, CronTrigger, ScheduledTask,
    )

    # Parse a cron expression
    cron = CronExpression("*/5 * * * *")
    next_time = cron.next_run(datetime.now())

    # Register and schedule tasks
    scheduler = TaskScheduler()
    scheduler.register_task("check", "0 * * * *", {"prompt": "Check status"})

    # Execute due tasks
    trigger = CronTrigger()
    for task in scheduler.get_pending_tasks(datetime.now()):
        result = await trigger.trigger_once(task, my_agent_loop)
        scheduler.mark_executed(task.name, result.to_dict())
"""

from .cron_expr import CronExpression
from .task_scheduler import (
    ScheduledTask,
    TaskScheduler,
    SchedulerBackend,
)
from .trigger import (
    CronTrigger,
    TriggerResult,
    MockLoop,
    TriggerableLoop,
)

__all__ = [
    # Cron expression
    "CronExpression",
    # Task scheduling
    "ScheduledTask",
    "TaskScheduler",
    "SchedulerBackend",
    # Trigger
    "CronTrigger",
    "TriggerResult",
    "MockLoop",
    "TriggerableLoop",
]
