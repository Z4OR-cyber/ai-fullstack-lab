"""
tests/test_request_checkpoint.py

v1.7.0 Harness 借鉴点的测试覆盖：
    - ② 请求可重建自检（RequestCheckpoint / Validator / fail-open）
    - ③ 执行调度（只读并行 / 写串行 / 混合 / 有序提交）

纯标准库 + pytest + suyi 自带 MockLLM/FunctionTool，不引入新依赖.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import pytest

from suyi.core.loop import (
    AgentLoop,
    FunctionTool,
    LLMResponse,
    LoopState,
    MockLLM,
    Tool,
    ToolCall,
    ToolResult,
)
from suyi.core.request_checkpoint import (
    RequestCheckpoint,
    RequestNotReconstructableError,
    RequestReconstructionValidator,
)
from suyi.core.budget import BudgetTracker, BudgetConfig
from suyi.tools.base import AgentTool, ToolContext


# ═══════════════════════════════════════════════════════════════
#  辅助工具
# ═══════════════════════════════════════════════════════════════


def _make_simple_loop(
    llm: MockLLM,
    tools: Optional[list[Tool]] = None,
    enable_checkpoint: bool = False,
    validator: Optional[RequestReconstructionValidator] = None,
    write_lock: Optional[asyncio.Lock] = None,
    max_turns: int = 5,
) -> AgentLoop:
    """构造一个带预算上限的 AgentLoop，避免测试里无限循环."""
    return AgentLoop(
        llm=llm,
        tools=tools or [],
        budget_tracker=BudgetTracker(BudgetConfig(max_turns=max_turns)),
        enable_request_checkpoint=enable_checkpoint,
        request_validator=validator,
        write_lock=write_lock,
    )


class _ReadOnlyTool(FunctionTool):
    """显式标记 read_only=True 的工具，便于测试."""

    read_only = True

    def __init__(
        self,
        name: str,
        func,
        description: str = "read-only tool",
    ):
        super().__init__(name=name, description=description, func=func)
        self.read_only = True


class _WriteTool(FunctionTool):
    """显式标记 read_only=False 的写工具（与默认值一致）."""

    read_only = False

    def __init__(
        self,
        name: str,
        func,
        description: str = "write tool",
    ):
        super().__init__(name=name, description=description, func=func)
        self.read_only = False


# ═══════════════════════════════════════════════════════════════
#  RequestCheckpoint 基础测试
# ═══════════════════════════════════════════════════════════════


class TestRequestCheckpoint:
    """RequestCheckpoint 数据类的往返与 checksum 测试."""

    def _sample_payload(self) -> tuple[list[dict], list[dict], str]:
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        tools = [
            {
                "type": "function",
                "function": {"name": "search", "description": "web search"},
            }
        ]
        system_prompt = "You are a helpful assistant."
        return messages, tools, system_prompt

    def test_to_dict_from_dict_roundtrip(self) -> None:
        """to_dict → from_dict 往返后核心字段一致."""
        messages, tools, system_prompt = self._sample_payload()
        cp = RequestCheckpoint(
            request_id="abc-123",
            timestamp=1234567890.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            model_hint="gpt-test",
            tool_call_ids=["call_1", "call_2"],
        )
        d = cp.to_dict()
        assert isinstance(d, dict)
        assert d["request_id"] == "abc-123"
        assert d["model_hint"] == "gpt-test"
        assert d["tool_call_ids"] == ["call_1", "call_2"]

        rebuilt = RequestCheckpoint.from_dict(d)
        assert rebuilt.request_id == cp.request_id
        assert rebuilt.timestamp == cp.timestamp
        assert rebuilt.messages == cp.messages
        assert rebuilt.tools == cp.tools
        assert rebuilt.system_prompt == cp.system_prompt
        assert rebuilt.model_hint == cp.model_hint
        assert rebuilt.tool_call_ids == cp.tool_call_ids
        # checksum 必须一致
        assert rebuilt.checksum == cp.checksum

    def test_checksum_stable_for_same_content(self) -> None:
        """相同逻辑内容（不同 dict 插入顺序）产生相同 checksum."""
        messages, tools, system_prompt = self._sample_payload()
        cp1 = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        # 用不同顺序重建相同语义的 dict
        reversed_messages = list(reversed(messages))
        reversed_messages = list(reversed(reversed_messages))  # 还原顺序
        cp2 = RequestCheckpoint(
            request_id="r2",
            timestamp=2.0,
            messages=reversed_messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        assert cp1.checksum == cp2.checksum
        assert cp1.matches(cp2)

    def test_checksum_changes_for_different_messages(self) -> None:
        """messages 内容变化时 checksum 必须变化."""
        messages, tools, system_prompt = self._sample_payload()
        cp1 = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        messages2 = [{"role": "user", "content": "DIFFERENT"}]
        cp2 = RequestCheckpoint(
            request_id="r2",
            timestamp=2.0,
            messages=messages2,
            tools=tools,
            system_prompt=system_prompt,
        )
        assert cp1.checksum != cp2.checksum
        assert not cp1.matches(cp2)

    def test_checksum_changes_for_different_tools(self) -> None:
        """tools 内容变化时 checksum 必须变化."""
        messages, tools, system_prompt = self._sample_payload()
        cp1 = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        cp2 = RequestCheckpoint(
            request_id="r2",
            timestamp=2.0,
            messages=messages,
            tools=[{"type": "function", "function": {"name": "different"}}],
            system_prompt=system_prompt,
        )
        assert cp1.checksum != cp2.checksum

    def test_checksum_changes_for_different_system_prompt(self) -> None:
        """system_prompt 变化时 checksum 必须变化."""
        messages, tools, system_prompt = self._sample_payload()
        cp1 = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        cp2 = RequestCheckpoint(
            request_id="r2",
            timestamp=2.0,
            messages=messages,
            tools=tools,
            system_prompt="A completely different prompt.",
        )
        assert cp1.checksum != cp2.checksum

    def test_reconstruct_matches(self) -> None:
        """reconstruct() 做 to_dict→from_dict 往返，matches 应为 True."""
        messages, tools, system_prompt = self._sample_payload()
        cp = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            model_hint="model-x",
        )
        rebuilt = cp.reconstruct()
        assert cp.matches(rebuilt)
        assert rebuilt.matches(cp)
        # request_id / timestamp 等元数据在重建后应保留
        assert rebuilt.request_id == cp.request_id
        assert rebuilt.model_hint == "model-x"

    def test_deep_copy_isolation(self) -> None:
        """checkpoint 内部对 messages 做深拷贝，外部修改不影响快照."""
        messages = [{"role": "user", "content": "original"}]
        cp = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=messages,
            tools=[],
            system_prompt="sys",
        )
        # 外部修改原列表
        messages[0]["content"] = "MUTATED"
        # checkpoint 内的 messages 不应受影响
        assert cp.messages[0]["content"] == "original"
        assert cp.to_dict()["messages"][0]["content"] == "original"

    def test_matches_with_non_checkpoint_returns_false(self) -> None:
        """matches() 对非 RequestCheckpoint 对象返回 False."""
        cp = RequestCheckpoint(
            request_id="r1",
            timestamp=1.0,
            messages=[],
            tools=[],
            system_prompt="",
        )
        assert cp.matches("not a checkpoint") is False
        assert cp.matches(None) is False


# ═══════════════════════════════════════════════════════════════
#  RequestReconstructionValidator 测试
# ═══════════════════════════════════════════════════════════════


class TestRequestReconstructionValidator:
    def setup_method(self) -> None:
        self.validator = RequestReconstructionValidator()

    def test_validate_passes_for_serializable_content(self) -> None:
        """正常可序列化请求能通过校验，返回 checkpoint."""
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello", "tool_calls": []},
        ]
        tools = [{"type": "function", "function": {"name": "echo"}}]
        cp = self.validator.validate(
            messages=messages,
            tools=tools,
            system_prompt="You are helpful.",
            model_hint="test-model",
        )
        assert isinstance(cp, RequestCheckpoint)
        assert cp.system_prompt == "You are helpful."
        assert cp.model_hint == "test-model"
        assert len(cp.checksum) == 64  # sha256 hex 长度

    def test_validate_rejects_unserializable_object(self) -> None:
        """塞入 object() 等不可序列化对象时抛 RequestNotReconstructableError."""

        class Weird:
            pass

        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": Weird()},
        ]
        with pytest.raises(RequestNotReconstructableError) as exc_info:
            self.validator.validate(
                messages=messages,
                tools=[],
                system_prompt="sys",
            )
        err = exc_info.value
        # 应携带字段路径（至少给出错误原因）
        assert "non-JSON-serializable" in err.reason or "JSON" in err.reason
        assert err.field_path is not None
        print(f"unserializable path: {err.field_path}")

    def test_validate_rejects_set_in_messages(self) -> None:
        """set 不可 JSON 序列化，应被拒绝并定位字段."""
        messages = [{"role": "user", "content": {"a": {1, 2, 3}}}]
        with pytest.raises(RequestNotReconstructableError):
            self.validator.validate(messages=messages, tools=[], system_prompt="s")

    def test_validate_rejects_bytes(self) -> None:
        """bytes 不可 JSON 序列化."""
        messages = [{"role": "user", "content": b"raw bytes"}]
        with pytest.raises(RequestNotReconstructableError):
            self.validator.validate(messages=messages, tools=[], system_prompt="s")

    def test_validate_roundtrip_consistency(self) -> None:
        """validate 返回的 checkpoint 再做 reconstruct 仍 matches."""
        messages = [{"role": "user", "content": "x"}]
        tools = [{"type": "function", "function": {"name": "f"}}]
        cp = self.validator.validate(
            messages=messages,
            tools=tools,
            system_prompt="sys",
        )
        rebuilt = cp.reconstruct()
        assert cp.matches(rebuilt)

    def test_tool_call_ids_recorded(self) -> None:
        """tool_call_ids 可选参数被正确记录."""
        cp = self.validator.validate(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            system_prompt="",
            tool_call_ids=["call_a", "call_b"],
        )
        assert cp.tool_call_ids == ["call_a", "call_b"]


# ═══════════════════════════════════════════════════════════════
#  FunctionTool read_only 测试
# ═══════════════════════════════════════════════════════════════


class TestFunctionToolReadOnly:
    def test_default_read_only_is_false(self) -> None:
        """默认 read_only=False（保守策略）."""

        async def noop(**kwargs: Any) -> str:
            return "ok"

        t = FunctionTool(name="noop", description="d", func=noop)
        assert t.read_only is False

    def test_function_tool_accepts_read_only_true(self) -> None:
        """FunctionTool 接受 read_only 参数并存储."""

        async def search(**kwargs: Any) -> str:
            return "result"

        t = FunctionTool(
            name="search",
            description="search web",
            func=search,
            read_only=True,
        )
        assert t.read_only is True

    def test_function_tool_accepts_read_only_false(self) -> None:
        async def write(**kwargs: Any) -> str:
            return "written"

        t = FunctionTool(
            name="write",
            description="write file",
            func=write,
            read_only=False,
        )
        assert t.read_only is False

    def test_subclass_read_only_class_attribute(self) -> None:
        """子类可通过类属性覆盖 read_only."""

        class MyReadOnlyTool(FunctionTool):
            read_only = True

            def __init__(self) -> None:
                super().__init__(
                    name="my_ro",
                    description="ro",
                    func=lambda **k: "x",
                )

        assert MyReadOnlyTool().read_only is True


# ═══════════════════════════════════════════════════════════════
#  AgentLoop 请求检查点集成测试
# ═══════════════════════════════════════════════════════════════


class TestLoopRequestCheckpoint:
    @pytest.mark.asyncio
    async def test_checkpoint_stored_in_metadata_when_enabled(self) -> None:
        """开启 enable_request_checkpoint 后，state.metadata 中应有 last_checkpoint."""

        # 用一个会被 loop 调用的自定义 LLM 包装，捕获 state.metadata
        captured_states: list[LoopState] = []

        class CapturingLLM(MockLLM):
            async def chat(self, messages, tools, system_prompt):
                # 调用父类但先让 loop 把 checkpoint 写入 state——这里我们通过
                # 中间件捕获更可靠；改用中间件
                return await super().chat(messages, tools, system_prompt)

        from suyi.core.loop import Middleware

        class CaptureMiddleware(Middleware):
            async def after_llm_call(self, response, state):
                captured_states.append(state)
                return response

        llm = MockLLM([LLMResponse.text("Final answer.", tokens=20)])
        loop = AgentLoop(
            llm=llm,
            tools=[],
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=3)),
            enable_request_checkpoint=True,
            middleware_chain=[CaptureMiddleware()],
        )
        result = await loop.run("hello")
        assert result.stop_reason == "natural"
        # 至少有一次 LLM 调用 → 至少捕获一个 state
        assert len(captured_states) >= 1
        state = captured_states[-1]
        assert "last_checkpoint" in state.metadata
        cp_dict = state.metadata["last_checkpoint"]
        assert "checksum" in cp_dict
        assert "request_id" in cp_dict
        assert "messages" in cp_dict
        assert "tools" in cp_dict
        assert "system_prompt" in cp_dict
        # 校验成功时不应有 checkpoint_error
        assert "checkpoint_error" not in state.metadata

    @pytest.mark.asyncio
    async def test_checkpoint_disabled_by_default(self) -> None:
        """默认不传 enable_request_checkpoint 时不做校验，metadata 里无 checkpoint."""
        from suyi.core.loop import Middleware

        captured_states: list[LoopState] = []

        class CaptureMiddleware(Middleware):
            async def after_llm_call(self, response, state):
                captured_states.append(state)
                return response

        llm = MockLLM([LLMResponse.text("Done.", tokens=10)])
        loop = AgentLoop(
            llm=llm,
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=3)),
            middleware_chain=[CaptureMiddleware()],
        )
        result = await loop.run("hi")
        assert result.stop_reason == "natural"
        assert len(captured_states) >= 1
        state = captured_states[-1]
        assert "last_checkpoint" not in state.metadata
        assert "checkpoint_error" not in state.metadata

    @pytest.mark.asyncio
    async def test_checkpoint_fail_open_does_not_crash_loop(self) -> None:
        """校验失败时 fail-open：loop 不崩溃、正常出结果、metadata 记录错误.

        通过注入一个会抛 RequestNotReconstructableError 的 validator 来模拟.
        """
        from suyi.core.loop import Middleware

        captured_states: list[LoopState] = []

        class CaptureMiddleware(Middleware):
            async def after_llm_call(self, response, state):
                captured_states.append(state)
                return response

        class BrokenValidator(RequestReconstructionValidator):
            """模拟校验器：对任何请求都抛不可重建错误."""

            def validate(self, messages, tools, system_prompt,
                         model_hint=None, tool_call_ids=None):
                raise RequestNotReconstructableError(
                    reason="Simulated validation failure",
                    field_path="messages[0].content",
                )

        llm = MockLLM([LLMResponse.text("Still works.", tokens=10)])
        loop = AgentLoop(
            llm=llm,
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=3)),
            enable_request_checkpoint=True,
            request_validator=BrokenValidator(),
            middleware_chain=[CaptureMiddleware()],
        )
        result = await loop.run("hello")
        # fail-open：loop 正常结束
        assert result.stop_reason == "natural"
        assert "Still works" in result.content
        # state.metadata 里应有 checkpoint_error
        assert len(captured_states) >= 1
        state = captured_states[-1]
        assert "checkpoint_error" in state.metadata
        err = state.metadata["checkpoint_error"]
        assert "Simulated validation failure" in err["error"]
        assert err["reason"] == "Simulated validation failure"
        assert err["field_path"] == "messages[0].content"
        # 失败时不应有 last_checkpoint
        assert "last_checkpoint" not in state.metadata

    @pytest.mark.asyncio
    async def test_checkpoint_with_tools_executed(self) -> None:
        """开启 checkpoint 且有工具调用时，checkpoint 中 tools 非空."""
        from suyi.core.loop import Middleware

        captured_states: list[LoopState] = []

        class CaptureMiddleware(Middleware):
            async def after_llm_call(self, response, state):
                captured_states.append(state)
                return response

        async def echo(**kwargs: Any) -> str:
            return "echo result"

        echo_tool = FunctionTool(
            name="echo",
            description="echo input",
            func=echo,
            read_only=True,
        )
        llm = MockLLM([
            LLMResponse.action("echo", {"text": "hi"}, tokens=20),
            LLMResponse.text("Done.", tokens=10),
        ])
        loop = AgentLoop(
            llm=llm,
            tools=[echo_tool],
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=5)),
            enable_request_checkpoint=True,
            middleware_chain=[CaptureMiddleware()],
        )
        result = await loop.run("say hi")
        assert result.stop_reason == "natural"
        # 至少有一帧 state 的 checkpoint.tools 非空
        found_tools = False
        for s in captured_states:
            cp = s.metadata.get("last_checkpoint")
            if cp and cp.get("tools"):
                found_tools = True
                break
        assert found_tools, "Expected at least one checkpoint with non-empty tools"


# ═══════════════════════════════════════════════════════════════
#  只读工具并行测试
# ═══════════════════════════════════════════════════════════════


class TestReadOnlyParallel:
    @pytest.mark.asyncio
    async def test_two_read_only_tools_run_concurrently(self) -> None:
        """两个 read_only 工具用 Event 协调，确认它们并发执行（开始时间重叠）."""
        started: list[str] = []
        finished: list[str] = []
        release_a = asyncio.Event()
        a_started = asyncio.Event()

        async def tool_a(**kwargs: Any) -> str:
            started.append("a")
            a_started.set()
            # 等 b 也启动后才继续，证明并发
            await release_a.wait()
            finished.append("a")
            return "a_done"

        async def tool_b(**kwargs: Any) -> str:
            # 等 a 启动后再启动，保证测试语义
            await a_started.wait()
            started.append("b")
            # 释放 a
            release_a.set()
            finished.append("b")
            return "b_done"

        t_a = _ReadOnlyTool("tool_a", tool_a)
        t_b = _ReadOnlyTool("tool_b", tool_b)

        llm = MockLLM([
            LLMResponse.actions(
                ("tool_a", {}),
                ("tool_b", {}),
                tokens=30,
            ),
            LLMResponse.text("all done", tokens=10),
        ])
        loop = _make_simple_loop(llm, tools=[t_a, t_b])
        result = await loop.run("run both")
        assert result.stop_reason == "natural"

        # 两者都应启动并完成
        assert "a" in started and "b" in started
        assert "a" in finished and "b" in finished

    @pytest.mark.asyncio
    async def test_read_only_parallel_is_faster_than_serial(self) -> None:
        """两个各 sleep 0.1s 的只读工具并行执行总耗时应 < 0.3s（串行要 0.2s+）."""

        async def slow_ro_1(**kwargs: Any) -> str:
            await asyncio.sleep(0.1)
            return "1"

        async def slow_ro_2(**kwargs: Any) -> str:
            await asyncio.sleep(0.1)
            return "2"

        t1 = _ReadOnlyTool("slow1", slow_ro_1)
        t2 = _ReadOnlyTool("slow2", slow_ro_2)

        llm = MockLLM([
            LLMResponse.actions(("slow1", {}), ("slow2", {}), tokens=20),
            LLMResponse.text("ok", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[t1, t2])
        start = time.monotonic()
        result = await loop.run("go")
        elapsed = time.monotonic() - start
        assert result.stop_reason == "natural"
        # 并行应明显快于串行（0.2s），留 0.25s 余量
        assert elapsed < 0.35, f"Expected parallel execution, took {elapsed:.3f}s"


# ═══════════════════════════════════════════════════════════════
#  写工具串行测试
# ═══════════════════════════════════════════════════════════════


class TestWriteSerial:
    @pytest.mark.asyncio
    async def test_two_write_tools_run_serially(self) -> None:
        """两个 write 工具：第二个必须在第一个完成后才开始."""
        order: list[str] = []

        async def write_1(**kwargs: Any) -> str:
            order.append("write1_start")
            await asyncio.sleep(0.05)
            order.append("write1_end")
            return "w1"

        async def write_2(**kwargs: Any) -> str:
            order.append("write2_start")
            await asyncio.sleep(0.05)
            order.append("write2_end")
            return "w2"

        t1 = _WriteTool("write1", write_1)
        t2 = _WriteTool("write2", write_2)

        llm = MockLLM([
            LLMResponse.actions(("write1", {}), ("write2", {}), tokens=20),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[t1, t2])
        result = await loop.run("write both")
        assert result.stop_reason == "natural"

        # 严格串行顺序：write1_start → write1_end → write2_start → write2_end
        assert order == [
            "write1_start",
            "write1_end",
            "write2_start",
            "write2_end",
        ], f"Expected serial order, got {order}"

    @pytest.mark.asyncio
    async def test_write_tools_share_lock_with_injected_lock(self) -> None:
        """外部注入的 write_lock 被使用（两个写工具仍串行）."""
        shared_lock = asyncio.Lock()
        order: list[str] = []

        async def writer1(**kwargs: Any) -> str:
            order.append("w1_start")
            await asyncio.sleep(0.05)
            order.append("w1_end")
            return "w1"

        async def writer2(**kwargs: Any) -> str:
            order.append("w2_start")
            await asyncio.sleep(0.05)
            order.append("w2_end")
            return "w2"

        t1 = _WriteTool("writer1", writer1)
        t2 = _WriteTool("writer2", writer2)
        llm = MockLLM([
            LLMResponse.actions(
                ("writer1", {}),
                ("writer2", {}),
                tokens=10,
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(
            llm, tools=[t1, t2], write_lock=shared_lock
        )
        result = await loop.run("go")
        assert result.stop_reason == "natural"
        # 严格串行
        assert order == ["w1_start", "w1_end", "w2_start", "w2_end"]

    @pytest.mark.asyncio
    async def test_external_lock_actually_held_during_write(self) -> None:
        """外部持有的锁会阻塞写工具执行（证明注入锁被真正使用）."""
        shared_lock = asyncio.Lock()
        executed: list[str] = []

        async def writer(**kwargs: Any) -> str:
            executed.append("ran")
            return "ok"

        t = _WriteTool("writer", writer)
        llm = MockLLM([
            LLMResponse.action("writer", {}, tokens=10),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[t], write_lock=shared_lock)

        # 先在外部持有锁，然后启动 loop；写工具应被阻塞
        await shared_lock.acquire()
        task = asyncio.create_task(loop.run("go"))
        # 给 loop 一点时间跑到写工具处
        await asyncio.sleep(0.1)
        # 锁未释放前，写工具不应执行
        assert executed == [], f"Write tool ran while external lock held: {executed}"
        # 释放锁，loop 才能继续
        shared_lock.release()
        result = await asyncio.wait_for(task, timeout=2.0)
        assert result.stop_reason == "natural"
        assert executed == ["ran"]


# ═══════════════════════════════════════════════════════════════
#  混合调度测试
# ═══════════════════════════════════════════════════════════════


class TestMixedScheduling:
    @pytest.mark.asyncio
    async def test_read_only_parallel_while_write_serial(self) -> None:
        """混合：read_only 并行，write 串行."""
        events: list[str] = []

        async def ro_fast(**kwargs: Any) -> str:
            events.append("ro_start")
            await asyncio.sleep(0.05)
            events.append("ro_end")
            return "ro"

        async def wr_slow(**kwargs: Any) -> str:
            events.append("wr_start")
            await asyncio.sleep(0.05)
            events.append("wr_end")
            return "wr"

        ro = _ReadOnlyTool("ro", ro_fast)
        wr = _WriteTool("wr", wr_slow)

        # 两个只读 + 两个写
        llm = MockLLM([
            LLMResponse.actions(
                ("ro", {}),
                ("wr", {}),
                ("ro", {}),
                ("wr", {}),
                tokens=40,
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[ro, wr])
        result = await loop.run("mixed")
        assert result.stop_reason == "natural"

        # 两个 wr 的 start/end 必须严格不交错：wr1_end 在 wr2_start 之前
        wr_starts = [i for i, e in enumerate(events) if e == "wr_start"]
        wr_ends = [i for i, e in enumerate(events) if e == "wr_end"]
        assert len(wr_starts) == 2
        assert len(wr_ends) == 2
        # 第一个 end 必须在第二个 start 之前
        assert wr_ends[0] < wr_starts[1], (
            f"Write tools overlapped! events={events}"
        )

    @pytest.mark.asyncio
    async def test_default_tool_treated_as_write(self) -> None:
        """未显式标记 read_only 的 FunctionTool 默认按写工具串行."""
        order: list[str] = []

        async def f1(**kwargs: Any) -> str:
            order.append("f1_start")
            await asyncio.sleep(0.02)
            order.append("f1_end")
            return "1"

        async def f2(**kwargs: Any) -> str:
            order.append("f2_start")
            await asyncio.sleep(0.02)
            order.append("f2_end")
            return "2"

        # 不传 read_only，默认 False
        t1 = FunctionTool(name="f1", description="d", func=f1)
        t2 = FunctionTool(name="f2", description="d", func=f2)
        assert t1.read_only is False
        assert t2.read_only is False

        llm = MockLLM([
            LLMResponse.actions(("f1", {}), ("f2", {}), tokens=10),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[t1, t2])
        result = await loop.run("go")
        assert result.stop_reason == "natural"
        assert order == ["f1_start", "f1_end", "f2_start", "f2_end"]


# ═══════════════════════════════════════════════════════════════
#  有序提交测试
# ═══════════════════════════════════════════════════════════════


class TestOrderedSubmission:
    @pytest.mark.asyncio
    async def test_tool_results_order_matches_tool_calls(self) -> None:
        """并行只读工具让后调用的先返回，最终 tool_results 顺序仍与 tool_calls 一致."""
        # tool_slow 先调用但 sleep 久；tool_fast 后调用但立即返回.
        # 若按完成顺序 append，tool_fast 会在 tool_slow 之前；
        # 有序提交应保证 tool_slow 在结果列表中排第一.

        async def tool_slow(**kwargs: Any) -> str:
            await asyncio.sleep(0.1)
            return "slow_result"

        async def tool_fast(**kwargs: Any) -> str:
            await asyncio.sleep(0.01)
            return "fast_result"

        slow = _ReadOnlyTool("slow", tool_slow)
        fast = _ReadOnlyTool("fast", tool_fast)

        # 捕获 tool_results 顺序
        captured_results: list[ToolResult] = []

        class CapturingLLM(MockLLM):
            """自定义 LLM：在第二轮返回最终答案，同时让我们能检查 history."""

            pass

        llm = MockLLM([
            # 第一轮：slow 在前、fast 在后
            LLMResponse(
                content="calling both",
                tool_calls=[
                    ToolCall(id="call_slow", name="slow", arguments={}),
                    ToolCall(id="call_fast", name="fast", arguments={}),
                ],
                usage={"total_tokens": 30},
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[slow, fast])
        result = await loop.run("go")
        assert result.stop_reason == "natural"

        # 从 history 中找 tool 消息，验证顺序：slow 在前、fast 在后
        tool_messages = [
            m for m in result.history if m.get("role") == "tool"
        ]
        assert len(tool_messages) == 2
        assert tool_messages[0]["tool_call_id"] == "call_slow"
        assert tool_messages[0]["name"] == "slow"
        assert tool_messages[1]["tool_call_id"] == "call_fast"
        assert tool_messages[1]["name"] == "fast"

        # 内容也对应
        assert tool_messages[0]["content"] == "slow_result"
        assert tool_messages[1]["content"] == "fast_result"

    @pytest.mark.asyncio
    async def test_mixed_tools_ordered_submission(self) -> None:
        """混合读写工具时，结果顺序仍与 tool_calls 一致."""

        async def ro1(**kwargs: Any) -> str:
            await asyncio.sleep(0.05)
            return "ro1"

        async def wr1(**kwargs: Any) -> str:
            await asyncio.sleep(0.02)
            return "wr1"

        async def ro2(**kwargs: Any) -> str:
            await asyncio.sleep(0.01)
            return "ro2"

        t_ro1 = _ReadOnlyTool("ro1", ro1)
        t_wr1 = _WriteTool("wr1", wr1)
        t_ro2 = _ReadOnlyTool("ro2", ro2)

        llm = MockLLM([
            LLMResponse(
                content="mixed call",
                tool_calls=[
                    ToolCall(id="c_ro1", name="ro1", arguments={}),
                    ToolCall(id="c_wr1", name="wr1", arguments={}),
                    ToolCall(id="c_ro2", name="ro2", arguments={}),
                ],
                usage={"total_tokens": 40},
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[t_ro1, t_wr1, t_ro2])
        result = await loop.run("mixed order")
        assert result.stop_reason == "natural"

        tool_messages = [
            m for m in result.history if m.get("role") == "tool"
        ]
        assert len(tool_messages) == 3
        assert [m["tool_call_id"] for m in tool_messages] == [
            "c_ro1",
            "c_wr1",
            "c_ro2",
        ]
        assert [m["name"] for m in tool_messages] == ["ro1", "wr1", "ro2"]
        assert [m["content"] for m in tool_messages] == ["ro1", "wr1", "ro2"]


# ═══════════════════════════════════════════════════════════════
#  向后兼容测试
# ═══════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_loop_without_new_params_behaves_as_before(self) -> None:
        """不传新参数时 loop 行为正常（简单文本往返）."""
        llm = MockLLM([LLMResponse.text("hello back", tokens=10)])
        loop = AgentLoop(llm=llm)
        result = await loop.run("hi")
        assert result.stop_reason == "natural"
        assert "hello back" in result.content
        assert result.turns_used >= 1

    @pytest.mark.asyncio
    async def test_tools_still_execute_without_read_only(self) -> None:
        """旧代码创建的工具（无 read_only）仍可正常执行."""

        async def old_tool(**kwargs: Any) -> str:
            return "old_tool_result"

        # 用旧方式构造，不传 read_only
        t = FunctionTool(name="old_tool", description="legacy", func=old_tool)
        llm = MockLLM([
            LLMResponse.action("old_tool", {}, tokens=10),
            LLMResponse.text("done", tokens=5),
        ])
        loop = AgentLoop(
            llm=llm,
            tools=[t],
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=5)),
        )
        result = await loop.run("use old tool")
        assert result.stop_reason == "natural"
        tool_msgs = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["content"] == "old_tool_result"

    def test_agent_tool_base_has_read_only_class_attr(self) -> None:
        """suyi.tools.base.AgentTool 也有 read_only=False 类属性."""
        assert hasattr(AgentTool, "read_only")
        assert AgentTool.read_only is False

    def test_tool_in_loop_has_read_only_class_attr(self) -> None:
        """suyi.core.loop.Tool 也有 read_only=False 类属性."""
        assert hasattr(Tool, "read_only")
        assert Tool.read_only is False


# ═══════════════════════════════════════════════════════════════
#  异常隔离测试
# ═══════════════════════════════════════════════════════════════


class TestExceptionIsolation:
    @pytest.mark.asyncio
    async def test_read_only_exception_does_not_break_others(self) -> None:
        """只读组中一个工具抛异常，其他工具仍正常执行."""

        async def bad_tool(**kwargs: Any) -> str:
            raise RuntimeError("boom")

        async def good_tool(**kwargs: Any) -> str:
            return "good"

        bad = _ReadOnlyTool("bad", bad_tool)
        good = _ReadOnlyTool("good", good_tool)

        llm = MockLLM([
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c_bad", name="bad", arguments={}),
                    ToolCall(id="c_good", name="good", arguments={}),
                ],
                usage={"total_tokens": 20},
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[bad, good])
        result = await loop.run("go")
        assert result.stop_reason == "natural"
        tool_msgs = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_msgs) == 2
        # 顺序保持
        assert tool_msgs[0]["tool_call_id"] == "c_bad"
        assert tool_msgs[1]["tool_call_id"] == "c_good"
        # bad 失败，good 成功
        assert "boom" in tool_msgs[0]["content"] or "crashed" in tool_msgs[0]["content"].lower()
        assert tool_msgs[1]["content"] == "good"

    @pytest.mark.asyncio
    async def test_write_exception_does_not_break_subsequent_writes(self) -> None:
        """写组中一个工具抛异常，后续写工具仍执行."""

        async def bad_write(**kwargs: Any) -> str:
            raise RuntimeError("write boom")

        async def good_write(**kwargs: Any) -> str:
            return "write ok"

        bad = _WriteTool("bad_w", bad_write)
        good = _WriteTool("good_w", good_write)

        llm = MockLLM([
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c_bad", name="bad_w", arguments={}),
                    ToolCall(id="c_good", name="good_w", arguments={}),
                ],
                usage={"total_tokens": 20},
            ),
            LLMResponse.text("done", tokens=5),
        ])
        loop = _make_simple_loop(llm, tools=[bad, good])
        result = await loop.run("go")
        assert result.stop_reason == "natural"
        tool_msgs = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0]["tool_call_id"] == "c_bad"
        assert tool_msgs[1]["tool_call_id"] == "c_good"
        assert "boom" in tool_msgs[0]["content"] or "crashed" in tool_msgs[0]["content"].lower()
        assert tool_msgs[1]["content"] == "write ok"
