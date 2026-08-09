"""
对话状态机 — 管理复杂多轮对话流程.

设计原则:
    - **状态定义**：每个状态有名称、描述、进入/退出回调.
    - **转换规则**：定义状态间的合法转换路径，含触发条件.
    - **守卫条件**：转换前的布尔检查函数，不满足则拒绝转换.
    - **状态历史**：完整记录状态转换轨迹，支持回溯和调试.
    - **JSON 持久化**：状态机配置和历史可持久化到 JSON 文件.
    - **事件钩子**：进入/退出状态时触发回调，支持副作用（如发送消息）.

信号流转::

    ┌─────────┐  event: "submit"   ┌──────────┐  event: "confirm"  ┌─────────┐
    │  IDLE   │ ──────────────────▶ │ COLLECT  │ ─────────────────▶ │ PROCESS │
    └─────────┘   guard: has_data   └──────────┘   guard: validated  └─────────┘
         ▲                              │                                  │
         │       event: "cancel"        │           event: "done"          │
         └──────────────────────────────┴──────────────────────────────────┘

使用示例::

    from suyi.statemachine import StateMachine, State, Transition

    sm = StateMachine()
    sm.add_state(State(name="idle", description="初始状态"))
    sm.add_state(State(name="collecting", description="收集信息"))
    sm.add_state(State(name="processing", description="处理中"))
    sm.add_state(State(name="done", description="完成"))

    sm.add_transition(Transition(
        source="idle", target="collecting", event="start",
        guard=lambda ctx: ctx.get("user_input") is not None,
    ))
    sm.add_transition(Transition(
        source="collecting", target="processing", event="submit",
    ))

    sm.start("idle")
    sm.trigger("start", context={"user_input": "hello"})
    assert sm.current_state == "collecting"
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════════════════════════


@dataclass
class State:
    """状态定义.

    Attributes:
        name:        状态名称（唯一标识）.
        description: 状态描述.
        on_enter:    进入状态时的回调函数（接收 context）.
        on_exit:     退出状态时的回调函数（接收 context）.
        is_initial:  是否为初始状态.
        is_final:    是否为终态.
    """

    name: str
    description: str = ""
    on_enter: Optional[Callable[[dict], None]] = None
    on_exit: Optional[Callable[[dict], None]] = None
    is_initial: bool = False
    is_final: bool = False

    def to_dict(self) -> dict:
        """序列化为字典（回调函数不序列化）."""
        return {
            "name": self.name,
            "description": self.description,
            "is_initial": self.is_initial,
            "is_final": self.is_final,
        }


@dataclass
class Transition:
    """状态转换规则.

    Attributes:
        source:    源状态名称.
        target:    目标状态名称.
        event:     触发事件名称.
        guard:     守卫条件函数（接收 context，返回 bool）.
                   返回 False 时拒绝转换.
        action:    转换时执行的动作函数（接收 context）.
        priority:  优先级（当多个转换匹配同一事件时，优先级高的先执行）.
    """

    source: str
    target: str
    event: str
    guard: Optional[Callable[[dict], bool]] = None
    action: Optional[Callable[[dict], None]] = None
    priority: int = 0

    def to_dict(self) -> dict:
        """序列化为字典（函数不序列化）."""
        return {
            "source": self.source,
            "target": self.target,
            "event": self.event,
            "priority": self.priority,
        }


@dataclass
class StateHistoryEntry:
    """状态历史记录条目.

    Attributes:
        from_state:   源状态.
        to_state:     目标状态.
        event:        触发事件.
        timestamp:    时间戳.
        success:      转换是否成功.
        reason:       失败原因（如果失败）.
        context_snapshot: 转换时的上下文快照.
    """

    from_state: str
    to_state: str
    event: str
    timestamp: float
    success: bool = True
    reason: str = ""
    context_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TransitionResult:
    """转换结果.

    Attributes:
        success:    转换是否成功.
        from_state: 源状态.
        to_state:   目标状态.
        event:      触发事件.
        reason:     失败原因（如果失败）.
    """

    success: bool
    from_state: str
    to_state: str
    event: str
    reason: str = ""


# ═══════════════════════════════════════════════════════════════
#  异常
# ═══════════════════════════════════════════════════════════════


class StateMachineError(Exception):
    """状态机基础异常."""


class StateNotFoundError(StateMachineError):
    """状态不存在."""


class InvalidTransitionError(StateMachineError):
    """非法转换."""


class StateNotStartedError(StateMachineError):
    """状态机尚未启动."""


# ═══════════════════════════════════════════════════════════════
#  状态机
# ═══════════════════════════════════════════════════════════════


class StateMachine:
    """对话状态机 — 管理多轮对话的状态流转.

    核心功能:
        - 状态注册：add_state()
        - 转换注册：add_transition()
        - 事件触发：trigger() — 根据事件查找匹配的转换
        - 守卫检查：转换前的布尔验证
        - 状态历史：完整记录所有转换轨迹
        - 持久化：save() / load()

    Args:
        storage_path: JSON 持久化路径（None 表示不持久化）.

    使用示例::

        sm = StateMachine()
        sm.add_state(State(name="idle", is_initial=True))
        sm.add_state(State(name="active"))
        sm.add_transition(Transition(
            source="idle", target="active", event="activate",
        ))
        sm.start()
        result = sm.trigger("activate")
        assert result.success
        assert sm.current_state == "active"
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._current_state: Optional[str] = None
        self._context: dict[str, Any] = {}
        self._history: list[StateHistoryEntry] = []
        self._started: bool = False

    # ── 状态管理 ──────────────────────────────────────────

    def add_state(self, state: State) -> "StateMachine":
        """添加状态.

        Args:
            state: State 实例.

        Returns:
            self（支持链式调用）.

        Raises:
            StateMachineError: 状态名重复.
        """
        if state.name in self._states:
            raise StateMachineError(f"状态 '{state.name}' 已存在")
        self._states[state.name] = state
        return self

    def get_state(self, name: str) -> State:
        """获取状态定义.

        Raises:
            StateNotFoundError: 状态不存在.
        """
        if name not in self._states:
            raise StateNotFoundError(f"状态 '{name}' 不存在")
        return self._states[name]

    @property
    def states(self) -> list[str]:
        """所有状态名称列表."""
        return list(self._states.keys())

    @property
    def current_state(self) -> Optional[str]:
        """当前状态名称."""
        return self._current_state

    @property
    def context(self) -> dict[str, Any]:
        """当前上下文."""
        return self._context

    @property
    def is_started(self) -> bool:
        """状态机是否已启动."""
        return self._started

    @property
    def is_final(self) -> bool:
        """当前是否处于终态."""
        if self._current_state is None:
            return False
        state = self._states.get(self._current_state)
        return state is not None and state.is_final

    # ── 转换管理 ──────────────────────────────────────────

    def add_transition(self, transition: Transition) -> "StateMachine":
        """添加转换规则.

        Args:
            transition: Transition 实例.

        Returns:
            self（支持链式调用）.

        Raises:
            StateNotFoundError: 源状态或目标状态不存在.
        """
        if transition.source not in self._states:
            raise StateNotFoundError(
                f"源状态 '{transition.source}' 不存在"
            )
        if transition.target not in self._states:
            raise StateNotFoundError(
                f"目标状态 '{transition.target}' 不存在"
            )
        self._transitions.append(transition)
        return self

    @property
    def transitions(self) -> list[Transition]:
        """所有转换规则列表."""
        return list(self._transitions)

    def get_transitions_from(self, state_name: str) -> list[Transition]:
        """获取从指定状态出发的所有转换."""
        return [t for t in self._transitions if t.source == state_name]

    def get_transitions_for_event(self, event: str) -> list[Transition]:
        """获取匹配指定事件的所有转换（从当前状态出发）."""
        if self._current_state is None:
            return []
        return [
            t for t in self._transitions
            if t.event == event and t.source == self._current_state
        ]

    # ── 生命周期 ──────────────────────────────────────────

    def start(
        self,
        initial_state: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> str:
        """启动状态机.

        Args:
            initial_state: 初始状态名称（None 则使用 is_initial=True 的状态）.
            context:       初始上下文.

        Returns:
            初始状态名称.

        Raises:
            StateMachineError: 无法确定初始状态.
        """
        # 确定初始状态
        if initial_state is not None:
            if initial_state not in self._states:
                raise StateNotFoundError(
                    f"初始状态 '{initial_state}' 不存在"
                )
            start_name = initial_state
        else:
            initial_states = [
                s for s in self._states.values() if s.is_initial
            ]
            if not initial_states:
                # 如果没有标记 is_initial，使用第一个状态
                if not self._states:
                    raise StateMachineError("状态机没有定义任何状态")
                start_name = list(self._states.keys())[0]
            elif len(initial_states) > 1:
                raise StateMachineError("多个初始状态，请指定 initial_state")
            else:
                start_name = initial_states[0].name

        self._context = dict(context) if context else {}
        self._current_state = start_name
        self._started = True
        self._history.clear()

        # 执行 on_enter 回调
        state = self._states[start_name]
        if state.on_enter:
            state.on_enter(self._context)

        # 记录历史
        self._history.append(StateHistoryEntry(
            from_state="",
            to_state=start_name,
            event="start",
            timestamp=time.time(),
            success=True,
            context_snapshot=dict(self._context),
        ))

        return start_name

    def reset(self) -> None:
        """重置状态机到未启动状态."""
        self._current_state = None
        self._context.clear()
        self._history.clear()
        self._started = False

    # ── 事件触发 ──────────────────────────────────────────

    def trigger(
        self,
        event: str,
        context: Optional[dict] = None,
    ) -> TransitionResult:
        """触发事件，尝试状态转换.

        Args:
            event:   事件名称.
            context: 可选的上下文更新（合并到当前上下文）.

        Returns:
            TransitionResult 描述转换结果.

        Raises:
            StateNotStartedError: 状态机未启动.
        """
        if not self._started or self._current_state is None:
            raise StateNotStartedError("状态机尚未启动，请先调用 start()")

        # 更新上下文
        if context:
            self._context.update(context)

        # 查找匹配的转换（当前状态 + 事件）
        candidates = [
            t for t in self._transitions
            if t.source == self._current_state and t.event == event
        ]

        if not candidates:
            # 没有匹配的转换
            result = TransitionResult(
                success=False,
                from_state=self._current_state,
                to_state=self._current_state,
                event=event,
                reason=f"从状态 '{self._current_state}' 没有事件 '{event}' 的转换",
            )
            self._history.append(StateHistoryEntry(
                from_state=self._current_state,
                to_state=self._current_state,
                event=event,
                timestamp=time.time(),
                success=False,
                reason=result.reason,
                context_snapshot=dict(self._context),
            ))
            return result

        # 按优先级排序（高优先级先匹配）
        candidates.sort(key=lambda t: -t.priority)

        # 依次检查守卫条件
        for trans in candidates:
            # 守卫条件检查
            if trans.guard is not None:
                try:
                    if not trans.guard(self._context):
                        continue  # 守卫不通过，尝试下一个
                except Exception as e:
                    # 守卫函数异常，视为不通过
                    result = TransitionResult(
                        success=False,
                        from_state=self._current_state,
                        to_state=trans.target,
                        event=event,
                        reason=f"守卫条件异常: {e}",
                    )
                    self._history.append(StateHistoryEntry(
                        from_state=self._current_state,
                        to_state=trans.target,
                        event=event,
                        timestamp=time.time(),
                        success=False,
                        reason=result.reason,
                        context_snapshot=dict(self._context),
                    ))
                    return result

            # 守卫通过，执行转换
            old_state_name = self._current_state
            new_state_name = trans.target

            # 执行旧状态的 on_exit 回调
            old_state = self._states[old_state_name]
            if old_state.on_exit:
                old_state.on_exit(self._context)

            # 执行转换动作
            if trans.action:
                trans.action(self._context)

            # 切换状态
            self._current_state = new_state_name

            # 执行新状态的 on_enter 回调
            new_state = self._states[new_state_name]
            if new_state.on_enter:
                new_state.on_enter(self._context)

            # 记录历史
            self._history.append(StateHistoryEntry(
                from_state=old_state_name,
                to_state=new_state_name,
                event=event,
                timestamp=time.time(),
                success=True,
                context_snapshot=dict(self._context),
            ))

            return TransitionResult(
                success=True,
                from_state=old_state_name,
                to_state=new_state_name,
                event=event,
            )

        # 所有候选转换的守卫都不通过
        result = TransitionResult(
            success=False,
            from_state=self._current_state,
            to_state=self._current_state,
            event=event,
            reason=f"事件 '{event}' 的所有转换守卫条件不满足",
        )
        self._history.append(StateHistoryEntry(
            from_state=self._current_state,
            to_state=self._current_state,
            event=event,
            timestamp=time.time(),
            success=False,
            reason=result.reason,
            context_snapshot=dict(self._context),
        ))
        return result

    def can_trigger(self, event: str) -> bool:
        """检查是否可以触发指定事件（不实际触发）.

        Args:
            event: 事件名称.

        Returns:
            True 如果存在至少一个守卫通过的转换.
        """
        if not self._started or self._current_state is None:
            return False
        candidates = [
            t for t in self._transitions
            if t.source == self._current_state and t.event == event
        ]
        for trans in candidates:
            if trans.guard is None:
                return True
            try:
                if trans.guard(self._context):
                    return True
            except Exception:
                continue
        return False

    def get_available_events(self) -> list[str]:
        """获取当前状态下所有可用事件（守卫通过的）."""
        if not self._started or self._current_state is None:
            return []
        events: set[str] = set()
        for trans in self._transitions:
            if trans.source != self._current_state:
                continue
            if trans.guard is None or self.can_trigger(trans.event):
                events.add(trans.event)
        return sorted(events)

    # ── 上下文管理 ────────────────────────────────────────

    def set_context(self, key: str, value: Any) -> None:
        """设置上下文值."""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文值."""
        return self._context.get(key, default)

    def update_context(self, data: dict) -> None:
        """批量更新上下文."""
        self._context.update(data)

    # ── 历史记录 ──────────────────────────────────────────

    @property
    def history(self) -> list[StateHistoryEntry]:
        """完整状态转换历史."""
        return list(self._history)

    @property
    def history_count(self) -> int:
        """历史记录数."""
        return len(self._history)

    def get_state_trace(self) -> list[str]:
        """获取状态轨迹（仅状态名列表）."""
        trace: list[str] = []
        for entry in self._history:
            if entry.success and entry.to_state:
                trace.append(entry.to_state)
            elif not entry.success and entry.from_state:
                if not trace or trace[-1] != entry.from_state:
                    trace.append(entry.from_state)
        return trace

    def get_failed_transitions(self) -> list[StateHistoryEntry]:
        """获取所有失败的转换记录."""
        return [e for e in self._history if not e.success]

    def clear_history(self) -> None:
        """清空历史记录."""
        self._history.clear()

    # ── 持久化 ────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> None:
        """保存状态机配置和历史到 JSON 文件.

        Args:
            path: 文件路径（None 使用 storage_path）.
        """
        save_path = path or self.storage_path
        if not save_path:
            return
        data = {
            "states": [s.to_dict() for s in self._states.values()],
            "transitions": [t.to_dict() for t in self._transitions],
            "current_state": self._current_state,
            "context": dict(self._context),
            "started": self._started,
            "history": [e.to_dict() for e in self._history],
        }
        dir_path = os.path.dirname(save_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: Optional[str] = None) -> None:
        """从 JSON 文件加载状态机配置和历史.

        注意: 回调函数（on_enter, on_exit, guard, action）无法序列化，
        加载后需要重新注册.

        Args:
            path: 文件路径（None 使用 storage_path）.
        """
        load_path = path or self.storage_path
        if not load_path or not os.path.exists(load_path):
            return
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 恢复状态（不含回调）
            self._states.clear()
            for s_dict in data.get("states", []):
                state = State(
                    name=s_dict["name"],
                    description=s_dict.get("description", ""),
                    is_initial=s_dict.get("is_initial", False),
                    is_final=s_dict.get("is_final", False),
                )
                self._states[state.name] = state

            # 恢复转换（不含 guard/action）
            self._transitions.clear()
            for t_dict in data.get("transitions", []):
                trans = Transition(
                    source=t_dict["source"],
                    target=t_dict["target"],
                    event=t_dict["event"],
                    priority=t_dict.get("priority", 0),
                )
                self._transitions.append(trans)

            # 恢复运行时状态
            self._current_state = data.get("current_state")
            self._context = data.get("context", {})
            self._started = data.get("started", False)

            # 恢复历史
            self._history.clear()
            for h_dict in data.get("history", []):
                self._history.append(StateHistoryEntry(**h_dict))
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # ── 可视化 ────────────────────────────────────────────

    def to_dot(self) -> str:
        """生成 Graphviz DOT 格式的状态图（用于可视化）."""
        lines = ["digraph StateMachine {", "    rankdir=LR;"]
        for name, state in self._states.items():
            shape = "doublecircle" if state.is_final else "circle"
            label = f"{name}"
            if state.description:
                label += f"\\n{state.description}"
            lines.append(f'    "{name}" [label="{label}", shape={shape}];')
        for trans in self._transitions:
            lines.append(
                f'    "{trans.source}" -> "{trans.target}" '
                f'[label="{trans.event}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        state = self._current_state or "未启动"
        return (
            f"StateMachine(current={state}, "
            f"states={len(self._states)}, "
            f"transitions={len(self._transitions)})"
        )
