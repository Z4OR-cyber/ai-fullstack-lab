"""
Tests for Phase 12 — State Machine Module.

Tests cover:
    - State: creation, serialization, properties
    - Transition: creation, serialization
    - StateMachine: add states/transitions, start, trigger, guards, callbacks
    - State history: tracking, trace, failed transitions
    - Persistence: save/load
    - Error handling: not started, not found, invalid transition
    - Utilities: can_trigger, get_available_events, to_dot

All tests use no external API calls.
"""

import json
import os
import tempfile
import time
import pytest

from suyi.statemachine import (
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


# ═══════════════════════════════════════════════════════════════
#  State
# ═══════════════════════════════════════════════════════════════


class TestState:
    """状态定义测试."""

    def test_creation(self):
        state = State(name="idle", description="初始状态")
        assert state.name == "idle"
        assert state.description == "初始状态"
        assert state.is_initial is False
        assert state.is_final is False

    def test_with_flags(self):
        state = State(name="done", is_initial=False, is_final=True)
        assert state.is_final is True

    def test_serialization(self):
        state = State(name="active", description="活动状态", is_initial=True)
        d = state.to_dict()
        assert d["name"] == "active"
        assert d["description"] == "活动状态"
        assert d["is_initial"] is True
        assert d["is_final"] is False
        # 回调函数不序列化
        assert "on_enter" not in d

    def test_callbacks(self):
        entered = []
        state = State(
            name="test",
            on_enter=lambda ctx: entered.append("enter"),
            on_exit=lambda ctx: entered.append("exit"),
        )
        state.on_enter({})
        state.on_exit({})
        assert entered == ["enter", "exit"]


# ═══════════════════════════════════════════════════════════════
#  Transition
# ═══════════════════════════════════════════════════════════════


class TestTransition:
    """转换规则测试."""

    def test_creation(self):
        trans = Transition(source="idle", target="active", event="activate")
        assert trans.source == "idle"
        assert trans.target == "active"
        assert trans.event == "activate"
        assert trans.priority == 0

    def test_with_guard_action(self):
        trans = Transition(
            source="idle", target="active", event="activate",
            guard=lambda ctx: ctx.get("ready"),
            action=lambda ctx: ctx.update({"activated": True}),
        )
        assert trans.guard is not None
        assert trans.action is not None

    def test_serialization(self):
        trans = Transition(source="a", target="b", event="go", priority=5)
        d = trans.to_dict()
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["event"] == "go"
        assert d["priority"] == 5
        assert "guard" not in d


# ═══════════════════════════════════════════════════════════════


class TestStateMachineBasics:
    """状态机基础功能测试."""

    def _build_basic_sm(self):
        """构建基础状态机."""
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="collecting"))
        sm.add_state(State(name="processing"))
        sm.add_state(State(name="done", is_final=True))
        sm.add_transition(Transition(source="idle", target="collecting", event="start"))
        sm.add_transition(Transition(source="collecting", target="processing", event="submit"))
        sm.add_transition(Transition(source="processing", target="done", event="complete"))
        sm.add_transition(Transition(source="collecting", target="idle", event="cancel"))
        return sm

    def test_add_state(self):
        sm = StateMachine()
        sm.add_state(State(name="idle"))
        assert "idle" in sm.states

    def test_add_duplicate_state(self):
        sm = StateMachine()
        sm.add_state(State(name="idle"))
        with pytest.raises(StateMachineError, match="已存在"):
            sm.add_state(State(name="idle"))

    def test_add_transition(self):
        sm = StateMachine()
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b"))
        sm.add_transition(Transition(source="a", target="b", event="go"))
        assert len(sm.transitions) == 1

    def test_add_transition_invalid_source(self):
        sm = StateMachine()
        sm.add_state(State(name="b"))
        with pytest.raises(StateNotFoundError):
            sm.add_transition(Transition(source="a", target="b", event="go"))

    def test_add_transition_invalid_target(self):
        sm = StateMachine()
        sm.add_state(State(name="a"))
        with pytest.raises(StateNotFoundError):
            sm.add_transition(Transition(source="a", target="b", event="go"))

    def test_start_with_initial_flag(self):
        sm = self._build_basic_sm()
        initial = sm.start()
        assert initial == "idle"
        assert sm.current_state == "idle"
        assert sm.is_started is True

    def test_start_explicit(self):
        sm = self._build_basic_sm()
        initial = sm.start(initial_state="collecting")
        assert initial == "collecting"

    def test_start_no_initial_flag(self):
        sm = StateMachine()
        sm.add_state(State(name="only"))
        initial = sm.start()
        assert initial == "only"

    def test_start_with_context(self):
        sm = self._build_basic_sm()
        sm.start(context={"user": "alice"})
        assert sm.context["user"] == "alice"

    def test_start_invalid_state(self):
        sm = self._build_basic_sm()
        with pytest.raises(StateNotFoundError):
            sm.start(initial_state="nonexistent")

    def test_start_multiple_initial_error(self):
        sm = StateMachine()
        sm.add_state(State(name="a", is_initial=True))
        sm.add_state(State(name="b", is_initial=True))
        with pytest.raises(StateMachineError, match="多个初始状态"):
            sm.start()

    def test_trigger_before_start(self):
        sm = self._build_basic_sm()
        with pytest.raises(StateNotStartedError):
            sm.trigger("start")

    def test_basic_transition(self):
        sm = self._build_basic_sm()
        sm.start()
        result = sm.trigger("start")
        assert result.success is True
        assert result.from_state == "idle"
        assert result.to_state == "collecting"
        assert sm.current_state == "collecting"

    def test_no_matching_event(self):
        sm = self._build_basic_sm()
        sm.start()
        result = sm.trigger("nonexistent")
        assert result.success is False
        assert sm.current_state == "idle"

    def test_multiple_transitions(self):
        sm = self._build_basic_sm()
        sm.start()
        sm.trigger("start")
        sm.trigger("submit")
        assert sm.current_state == "processing"
        sm.trigger("complete")
        assert sm.current_state == "done"
        assert sm.is_final is True

    def test_cancel_transition(self):
        sm = self._build_basic_sm()
        sm.start()
        sm.trigger("start")
        result = sm.trigger("cancel")
        assert result.success is True
        assert sm.current_state == "idle"


# ═══════════════════════════════════════════════════════════════
#  Guard Conditions
# ═══════════════════════════════════════════════════════════════


class TestGuardConditions:
    """守卫条件测试."""

    def test_guard_pass(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            guard=lambda ctx: ctx.get("ready") is True,
        ))
        sm.start(context={"ready": True})
        result = sm.trigger("go")
        assert result.success is True
        assert sm.current_state == "active"

    def test_guard_fail(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            guard=lambda ctx: ctx.get("ready") is True,
        ))
        sm.start(context={"ready": False})
        result = sm.trigger("go")
        assert result.success is False
        assert sm.current_state == "idle"

    def test_guard_exception(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))

        def bad_guard(ctx):
            raise RuntimeError("guard error")

        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            guard=bad_guard,
        ))
        sm.start()
        result = sm.trigger("go")
        assert result.success is False
        assert "守卫条件异常" in result.reason

    def test_multiple_guards_priority(self):
        """多个转换匹配同一事件时，按优先级尝试."""
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="path_a"))
        sm.add_state(State(name="path_b"))

        # 优先级低的先注册，但守卫不通过
        sm.add_transition(Transition(
            source="idle", target="path_a", event="go",
            guard=lambda ctx: False,  # 总是不通过
            priority=0,
        ))
        # 优先级高的
        sm.add_transition(Transition(
            source="idle", target="path_b", event="go",
            priority=10,
        ))
        sm.start()
        result = sm.trigger("go")
        assert result.success is True
        assert result.to_state == "path_b"

    def test_all_guards_fail(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b"))
        sm.add_transition(Transition(
            source="idle", target="a", event="go",
            guard=lambda ctx: False,
        ))
        sm.add_transition(Transition(
            source="idle", target="b", event="go",
            guard=lambda ctx: False,
        ))
        sm.start()
        result = sm.trigger("go")
        assert result.success is False
        assert "守卫条件不满足" in result.reason


# ═══════════════════════════════════════════════════════════════
#  Callbacks
# ═══════════════════════════════════════════════════════════════


class TestCallbacks:
    """回调函数测试."""

    def test_on_enter_callback(self):
        log = []
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(
            name="active",
            on_enter=lambda ctx: log.append(f"enter:{ctx.get('value', '')}"),
        ))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start(context={"value": "hello"})
        sm.trigger("go")
        assert log == ["enter:hello"]

    def test_on_exit_callback(self):
        log = []
        sm = StateMachine()
        sm.add_state(State(
            name="idle", is_initial=True,
            on_exit=lambda ctx: log.append("exit_idle"),
        ))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        sm.trigger("go")
        assert log == ["exit_idle"]

    def test_transition_action(self):
        log = []
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            action=lambda ctx: log.append("action"),
        ))
        sm.start()
        sm.trigger("go")
        assert log == ["action"]

    def test_callback_order(self):
        """验证回调执行顺序: on_exit → action → on_enter."""
        log = []
        sm = StateMachine()
        sm.add_state(State(
            name="idle", is_initial=True,
            on_exit=lambda ctx: log.append("exit"),
        ))
        sm.add_state(State(
            name="active",
            on_enter=lambda ctx: log.append("enter"),
        ))
        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            action=lambda ctx: log.append("action"),
        ))
        sm.start()
        sm.trigger("go")
        assert log == ["exit", "action", "enter"]


# ═══════════════════════════════════════════════════════════════
#  History
# ═══════════════════════════════════════════════════════════════


class TestStateHistory:
    """状态历史测试."""

    def test_history_tracking(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        sm.trigger("go")

        history = sm.history
        assert len(history) == 2  # start + go
        assert history[0].to_state == "idle"
        assert history[1].from_state == "idle"
        assert history[1].to_state == "active"
        assert history[1].success is True

    def test_history_failed_transition(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start()
        sm.trigger("nonexistent")  # 失败

        failed = sm.get_failed_transitions()
        assert len(failed) == 1
        assert failed[0].success is False

    def test_state_trace(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_state(State(name="done", is_final=True))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.add_transition(Transition(source="active", target="done", event="finish"))
        sm.start()
        sm.trigger("go")
        sm.trigger("finish")

        trace = sm.get_state_trace()
        assert trace == ["idle", "active", "done"]

    def test_history_count(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        sm.trigger("go")
        assert sm.history_count == 2

    def test_clear_history(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start()
        sm.clear_history()
        assert sm.history_count == 0

    def test_context_snapshot_in_history(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start(context={"key": "value"})
        sm.trigger("go", context={"key2": "value2"})

        history = sm.history
        last_entry = history[-1]
        assert "key" in last_entry.context_snapshot
        assert "key2" in last_entry.context_snapshot


# ═══════════════════════════════════════════════════════════════
#  Context Management
# ═══════════════════════════════════════════════════════════════


class TestContextManagement:
    """上下文管理测试."""

    def test_set_get_context(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start()
        sm.set_context("foo", "bar")
        assert sm.get_context("foo") == "bar"
        assert sm.get_context("missing", "default") == "default"

    def test_update_context(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start(context={"a": 1})
        sm.update_context({"b": 2, "a": 10})
        assert sm.context["a"] == 10
        assert sm.context["b"] == 2

    def test_trigger_updates_context(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        sm.trigger("go", context={"trigger_data": "hello"})
        assert sm.context["trigger_data"] == "hello"


# ═══════════════════════════════════════════════════════════════
#  Utility Methods
# ═══════════════════════════════════════════════════════════════


class TestUtilityMethods:
    """工具方法测试."""

    def test_can_trigger(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        assert sm.can_trigger("go") is True
        assert sm.can_trigger("nonexistent") is False

    def test_can_trigger_with_guard(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(
            source="idle", target="active", event="go",
            guard=lambda ctx: ctx.get("ready") is True,
        ))
        sm.start()
        assert sm.can_trigger("go") is False
        sm.set_context("ready", True)
        assert sm.can_trigger("go") is True

    def test_get_available_events(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.add_transition(Transition(source="idle", target="idle", event="reset"))
        sm.start()
        events = sm.get_available_events()
        assert "go" in events
        assert "reset" in events

    def test_get_transitions_from(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.add_transition(Transition(source="active", target="idle", event="back"))
        from_idle = sm.get_transitions_from("idle")
        assert len(from_idle) == 1
        assert from_idle[0].event == "go"

    def test_get_transitions_for_event(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(source="idle", target="active", event="go"))
        sm.start()
        trans = sm.get_transitions_for_event("go")
        assert len(trans) == 1

    def test_to_dot(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="done", is_final=True))
        sm.add_transition(Transition(source="idle", target="done", event="go"))
        dot = sm.to_dot()
        assert "digraph" in dot
        assert "idle" in dot
        assert "done" in dot
        assert "doublecircle" in dot  # final state shape

    def test_repr(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start()
        r = repr(sm)
        assert "StateMachine" in r
        assert "idle" in r

    def test_reset(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.start()
        sm.reset()
        assert sm.is_started is False
        assert sm.current_state is None


# ═══════════════════════════════════════════════════════════════
#  Persistence
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """持久化测试."""

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sm.json")
            sm = StateMachine(storage_path=path)
            sm.add_state(State(name="idle", is_initial=True, description="初始"))
            sm.add_state(State(name="active", description="活动"))
            sm.add_transition(Transition(
                source="idle", target="active", event="go", priority=5,
            ))
            sm.start(context={"user": "alice"})
            sm.trigger("go")
            sm.save()

            # 加载
            sm2 = StateMachine(storage_path=path)
            sm2.load()
            assert "idle" in sm2.states
            assert "active" in sm2.states
            assert sm2.current_state == "active"
            assert sm2.context.get("user") == "alice"
            assert sm2.history_count == 2
            assert len(sm2.transitions) == 1

    def test_load_nonexistent(self):
        sm = StateMachine(storage_path="/nonexistent/path/sm.json")
        sm.load()  # 不应抛出异常
        assert len(sm.states) == 0

    def test_callbacks_not_restored(self):
        """回调函数无法序列化，加载后应为 None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sm.json")
            sm = StateMachine(storage_path=path)
            sm.add_state(State(
                name="idle", is_initial=True,
                on_enter=lambda ctx: None,
            ))
            sm.save()

            sm2 = StateMachine(storage_path=path)
            sm2.load()
            state = sm2.get_state("idle")
            assert state.on_enter is None  # 回调丢失


# ═══════════════════════════════════════════════════════════════
#  Error Handling
# ═══════════════════════════════════════════════════════════════


class TestErrorHandling:
    """异常处理测试."""

    def test_get_state_not_found(self):
        sm = StateMachine()
        with pytest.raises(StateNotFoundError):
            sm.get_state("nonexistent")

    def test_no_states_start(self):
        sm = StateMachine()
        with pytest.raises(StateMachineError, match="没有定义任何状态"):
            sm.start()

    def test_trigger_not_started(self):
        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        with pytest.raises(StateNotStartedError):
            sm.trigger("go")

    def test_is_final_before_start(self):
        sm = StateMachine()
        assert sm.is_final is False


# ═══════════════════════════════════════════════════════════════
#  Complex Scenario
# ═══════════════════════════════════════════════════════════════


class TestComplexScenario:
    """复杂场景测试 — 模拟订单流程状态机."""

    def test_order_flow(self):
        """模拟电商订单流程."""
        sm = StateMachine()
        sm.add_state(State(name="created", is_initial=True, description="已创建"))
        sm.add_state(State(name="paid", description="已支付"))
        sm.add_state(State(name="shipped", description="已发货"))
        sm.add_state(State(name="delivered", description="已送达"))
        sm.add_state(State(name="cancelled", description="已取消"))
        sm.add_state(State(name="refunded", is_final=True, description="已退款"))

        sm.add_transition(Transition(
            source="created", target="paid", event="pay",
            guard=lambda ctx: ctx.get("amount", 0) > 0,
        ))
        sm.add_transition(Transition(
            source="created", target="cancelled", event="cancel",
        ))
        sm.add_transition(Transition(
            source="paid", target="shipped", event="ship",
        ))
        sm.add_transition(Transition(
            source="paid", target="refunded", event="refund",
        ))
        sm.add_transition(Transition(
            source="shipped", target="delivered", event="deliver",
        ))
        sm.add_transition(Transition(
            source="delivered", target="refunded", event="return",
        ))

        # 正常流程
        sm.start(context={"amount": 100})
        assert sm.trigger("pay").success is True
        assert sm.current_state == "paid"
        assert sm.trigger("ship").success is True
        assert sm.current_state == "shipped"
        assert sm.trigger("deliver").success is True
        assert sm.current_state == "delivered"
        assert sm.trigger("return").success is True
        assert sm.current_state == "refunded"
        assert sm.is_final is True

        # 验证历史
        trace = sm.get_state_trace()
        assert trace == ["created", "paid", "shipped", "delivered", "refunded"]

    def test_order_flow_cancel(self):
        """订单取消流程."""
        sm = StateMachine()
        sm.add_state(State(name="created", is_initial=True))
        sm.add_state(State(name="paid"))
        sm.add_state(State(name="cancelled"))
        sm.add_transition(Transition(
            source="created", target="paid", event="pay",
            guard=lambda ctx: ctx.get("amount", 0) > 0,
        ))
        sm.add_transition(Transition(
            source="created", target="cancelled", event="cancel",
        ))

        # 金额为 0，支付守卫不通过
        sm.start(context={"amount": 0})
        result = sm.trigger("pay")
        assert result.success is False
        # 取消
        result = sm.trigger("cancel")
        assert result.success is True
        assert sm.current_state == "cancelled"
