"""
Suyi Phase 12 — 对话状态机模块.

管理复杂多轮对话的状态流转，支持状态定义、转换规则、守卫条件、
状态历史和 JSON 持久化.

Exports:
    Data:
        State, Transition, StateHistoryEntry, TransitionResult
    Exceptions:
        StateMachineError, StateNotFoundError,
        InvalidTransitionError, StateNotStartedError
    Engine:
        StateMachine

Usage::

    from suyi.statemachine import StateMachine, State, Transition

    sm = StateMachine()
    sm.add_state(State(name="idle", is_initial=True))
    sm.add_state(State(name="active"))
    sm.add_transition(Transition(
        source="idle", target="active", event="activate",
    ))
    sm.start()
    result = sm.trigger("activate")
    assert result.success
"""

from .machine import (
    State,
    Transition,
    StateHistoryEntry,
    TransitionResult,
    StateMachineError,
    StateNotFoundError,
    InvalidTransitionError,
    StateNotStartedError,
    StateMachine,
)

__all__ = [
    # 数据结构
    "State",
    "Transition",
    "StateHistoryEntry",
    "TransitionResult",
    # 异常
    "StateMachineError",
    "StateNotFoundError",
    "InvalidTransitionError",
    "StateNotStartedError",
    # 状态机
    "StateMachine",
]
