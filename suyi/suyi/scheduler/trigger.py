"""
Cron Trigger — Connects ScheduledTask to AgentLoop execution.

The ``CronTrigger`` bridges the scheduler layer and the agent loop:
given a ``ScheduledTask`` and an ``AgentLoop`` (or any duck-typed
loop with an async ``run`` method), it executes the task and
returns a structured result.

Design:
    - Pure Python + asyncio (no external dependencies).
    - Supports MockLoop injection for testing.
    - Handles exceptions gracefully — a failed execution still
      produces a valid result dict with ``success=False``.
    - ``trigger_once`` is async to match ``AgentLoop.run``.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

from .task_scheduler import ScheduledTask
from .cron_expr import CronExpression


# ═══════════════════════════════════════════════════════════════
#  Loop Protocol (Duck-typed)
# ═══════════════════════════════════════════════════════════════


@runtime_checkable
class TriggerableLoop(Protocol):
    """Minimal loop protocol for trigger execution.

    Any object with an async ``run(user_message: str) -> Any`` method
    satisfies this protocol — notably ``AgentLoop``.
    """

    async def run(self, user_message: str) -> Any: ...


# ═══════════════════════════════════════════════════════════════
#  MockLoop (for testing)
# ═══════════════════════════════════════════════════════════════


class MockLoop:
    """
    Mock loop for testing CronTrigger without a real AgentLoop.

    Records all calls and returns a configurable result. Can be
    programmed to raise an exception to test error handling.

    Usage::

        mock = MockLoop()
        trigger = CronTrigger()
        result = await trigger.trigger_once(task, mock)
        assert mock.call_count == 1
    """

    def __init__(self, response: str = "Task completed.") -> None:
        """Initialize the mock loop.

        Args:
            response: The default response content returned by ``run``.
        """
        self._response: str = response
        self.call_count: int = 0
        self.call_log: list[dict[str, Any]] = []
        self._should_raise: bool = False
        self._exception: Optional[Exception] = None

    def set_response(self, response: str) -> None:
        """Set the response returned by subsequent ``run`` calls."""
        self._response = response

    def set_exception(self, exc: Exception) -> None:
        """Configure the mock to raise *exc* on the next ``run`` call."""
        self._should_raise = True
        self._exception = exc

    def reset(self) -> None:
        """Reset call count, log, and exception state."""
        self.call_count = 0
        self.call_log.clear()
        self._should_raise = False
        self._exception = None

    async def run(self, user_message: str) -> Any:
        """Mock run — returns the configured response or raises."""
        self.call_count += 1
        self.call_log.append({
            "user_message": user_message,
            "timestamp": datetime.now().isoformat(),
        })

        if self._should_raise and self._exception is not None:
            raise self._exception

        # Return a simple object mimicking LoopResult
        return _MockLoopResult(content=self._response)


class _MockLoopResult:
    """Lightweight result object mimicking ``LoopResult``."""

    def __init__(self, content: str = "", partial: bool = False) -> None:
        self.content = content
        self.partial = partial
        self.turns_used = 1
        self.stop_reason = "natural"
        self.is_complete = not partial

    def __str__(self) -> str:
        return f"MockLoopResult(content={self.content!r})"


# ═══════════════════════════════════════════════════════════════
#  TriggerResult
# ═══════════════════════════════════════════════════════════════


class TriggerResult:
    """
    Result of a single trigger execution.

    Attributes:
        task_name:     Name of the executed task.
        success:       Whether the execution completed without error.
        content:       The output content from the loop (if any).
        error:         Error message if execution failed.
        started_at:    When execution started.
        finished_at:   When execution finished.
        turns_used:    Number of loop turns used (if available).
        stop_reason:   Why the loop stopped (if available).
    """

    def __init__(
        self,
        task_name: str,
        success: bool,
        content: str = "",
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        turns_used: int = 0,
        stop_reason: str = "",
    ) -> None:
        self.task_name: str = task_name
        self.success: bool = success
        self.content: str = content
        self.error: Optional[str] = error
        self.started_at: Optional[datetime] = started_at
        self.finished_at: Optional[datetime] = finished_at
        self.turns_used: int = turns_used
        self.stop_reason: str = stop_reason

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence."""
        return {
            "task_name": self.task_name,
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "turns_used": self.turns_used,
            "stop_reason": self.stop_reason,
        }

    def __repr__(self) -> str:
        status = "ok" if self.success else "error"
        return f"TriggerResult(task={self.task_name!r}, {status})"


# ═══════════════════════════════════════════════════════════════
#  CronTrigger
# ═══════════════════════════════════════════════════════════════


class CronTrigger:
    """
    Connects a ``ScheduledTask`` to an ``AgentLoop`` for execution.

    The trigger extracts the user message from the task's
    ``task_config`` (key ``"prompt"`` or ``"message"`` or
    ``"user_message"``), invokes ``loop.run()``, and wraps the
    result in a ``TriggerResult``.

    Args:
        default_prompt: Fallback prompt used when the task config
                        doesn't specify one.

    Usage::

        trigger = CronTrigger()
        loop = AgentLoop(llm=MockLLM([...]))
        result = await trigger.trigger_once(task, loop)
        if result.success:
            print(result.content)
    """

    def __init__(self, default_prompt: str = "Execute scheduled task.") -> None:
        self.default_prompt: str = default_prompt

    # ── Core Method ────────────────────────────────────────────

    async def trigger_once(
        self,
        task: ScheduledTask,
        loop: TriggerableLoop,
    ) -> TriggerResult:
        """Execute a single scheduled task via the provided loop.

        Args:
            task: The ``ScheduledTask`` to execute.
            loop: A loop object with an async ``run(user_message)``
                  method (e.g. ``AgentLoop`` or ``MockLoop``).

        Returns:
            A ``TriggerResult`` describing the outcome. Exceptions
            from the loop are caught and recorded as ``success=False``.
        """
        started_at = datetime.now()
        prompt = self._extract_prompt(task)

        try:
            loop_result = await loop.run(prompt)
            finished_at = datetime.now()

            # Extract content and metadata from the result
            content = self._extract_content(loop_result)
            turns_used = self._extract_turns(loop_result)
            stop_reason = self._extract_stop_reason(loop_result)

            return TriggerResult(
                task_name=task.name,
                success=True,
                content=content,
                started_at=started_at,
                finished_at=finished_at,
                turns_used=turns_used,
                stop_reason=stop_reason,
            )

        except Exception as exc:
            finished_at = datetime.now()
            error_msg = f"{type(exc).__name__}: {exc}"
            # Capture traceback for debugging (stored in error, truncated)
            tb = traceback.format_exc()
            if len(tb) > 500:
                tb = tb[:500] + "...(truncated)"

            return TriggerResult(
                task_name=task.name,
                success=False,
                content="",
                error=error_msg,
                started_at=started_at,
                finished_at=finished_at,
            )

    # ── Batch Execution ────────────────────────────────────────

    async def trigger_many(
        self,
        tasks: list[ScheduledTask],
        loop: TriggerableLoop,
    ) -> list[TriggerResult]:
        """Execute multiple tasks sequentially.

        Tasks are executed in order (not concurrently) to avoid
        resource contention. For concurrent execution, call
        ``trigger_once`` within an ``asyncio.gather``.

        Args:
            tasks: List of tasks to execute.
            loop:  The loop to use for all tasks.

        Returns:
            A list of ``TriggerResult`` objects, one per task.
        """
        results: list[TriggerResult] = []
        for task in tasks:
            result = await self.trigger_once(task, loop)
            results.append(result)
        return results

    # ── Helpers ────────────────────────────────────────────────

    def _extract_prompt(self, task: ScheduledTask) -> str:
        """Extract the user message from the task config.

        Checks keys in order: ``"prompt"``, ``"message"``,
        ``"user_message"``. Falls back to ``default_prompt``.
        """
        config = task.task_config or {}
        for key in ("prompt", "message", "user_message"):
            val = config.get(key)
            if val and isinstance(val, str):
                return val
        return self.default_prompt

    @staticmethod
    def _extract_content(result: Any) -> str:
        """Extract text content from a loop result object."""
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        # Duck-typed: look for .content attribute
        content = getattr(result, "content", None)
        if content is not None:
            return str(content)
        return str(result)

    @staticmethod
    def _extract_turns(result: Any) -> int:
        """Extract turn count from a loop result object."""
        if result is None:
            return 0
        turns = getattr(result, "turns_used", None)
        if turns is not None:
            return int(turns)
        return 0

    @staticmethod
    def _extract_stop_reason(result: Any) -> str:
        """Extract stop reason from a loop result object."""
        if result is None:
            return ""
        reason = getattr(result, "stop_reason", None)
        if reason is not None:
            return str(reason)
        return ""

    def __repr__(self) -> str:
        return f"CronTrigger(default_prompt={self.default_prompt!r})"
