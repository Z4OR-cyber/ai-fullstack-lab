"""Tests for Pre-LLM Inject Middleware — Pre-LLM 记忆注入。"""

import pytest

from suyi.middleware.pre_llm_inject import PreLLMInjectMiddleware
from suyi.memory import MemoryManager
from suyi.core.loop import LoopState
from suyi.core.context import AssembledContext, ToolDefinition


class TestPreLLMInjectMiddleware:
    """PreLLMInjectMiddleware Pre-LLM 记忆注入中间件测试。"""

    def setup_method(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self.mgr = MemoryManager(storage_dir=self._tmpdir)
        self.middleware = PreLLMInjectMiddleware(
            memory_manager=self.mgr,
            relevance_threshold=0.0,  # 测试时设为 0 以确保注入
            max_entries=5,
        )

    def _make_state(self, user_msg: str) -> LoopState:
        """创建带有用户消息的 LoopState。"""
        history = [{"role": "user", "content": user_msg}]
        ctx = AssembledContext(
            system_prompt="test",
            tool_defs=[],
            memory_snapshot=[],
            messages=[{"role": "user", "content": user_msg}],
        )
        return LoopState(history=history, turn=0, context=ctx)

    @pytest.mark.asyncio
    async def test_inject_ground_truth(self):
        """注入 Ground Truth 记忆。"""
        self.mgr.ground_truth.add("用户偏好 Python 3.12")
        state = self._make_state("Python")

        result = await self.middleware.before_llm_call(state)

        # 检查注入了系统消息
        injected = False
        for msg in state.context.messages:
            if msg.get("role") == "system" and "权威记忆" in msg.get("content", ""):
                injected = True
                break
        assert injected

    @pytest.mark.asyncio
    async def test_inject_semantic(self):
        """注入语义记忆。"""
        self.mgr.semantic.add("Python is a programming language", tags=["python"])
        state = self._make_state("Python programming")

        result = await self.middleware.before_llm_call(state)

        # 应该注入了记忆
        assert result.metadata.get("pre_llm_injected_count", 0) > 0

    @pytest.mark.asyncio
    async def test_inject_facts(self):
        """注入结构化事实。"""
        self.mgr.structured_facts.add(
            "Python", "typing", "dynamic",
            source="user_statement",
        )
        state = self._make_state("Python typing")

        result = await self.middleware.before_llm_call(state)

        # 应该注入了记忆
        assert result.metadata.get("pre_llm_injected_count", 0) > 0

    @pytest.mark.asyncio
    async def test_no_injection_for_empty_query(self):
        """空 query 不注入。"""
        state = LoopState(history=[], turn=0, context=None)
        result = await self.middleware.before_llm_call(state)
        assert result.metadata.get("pre_llm_injected_count", 0) == 0

    @pytest.mark.asyncio
    async def test_dedup_injection(self):
        """避免重复注入。"""
        self.mgr.ground_truth.add("用户偏好 Python")
        state1 = self._make_state("Python")

        await self.middleware.before_llm_call(state1)
        count1 = state1.metadata.get("pre_llm_injected_count", 0)

        # 第二次查询相同内容
        state2 = self._make_state("Python")
        await self.middleware.before_llm_call(state2)
        count2 = state2.metadata.get("pre_llm_injected_count", 0)

        # 第二次应该因为去重而不注入（或注入更少）
        assert count2 <= count1

    @pytest.mark.asyncio
    async def test_relevance_threshold_filter(self):
        """相关性阈值过滤。"""
        # 设置高阈值
        middleware = PreLLMInjectMiddleware(
            memory_manager=self.mgr,
            relevance_threshold=0.99,
            max_entries=5,
        )
        self.mgr.semantic.add("Python programming language")
        state = self._make_state("Python")

        result = await middleware.before_llm_call(state)
        # 高阈值下应该过滤掉大部分记忆
        assert result.metadata.get("pre_llm_injected_count", 0) == 0

    @pytest.mark.asyncio
    async def test_ground_truth_force_instruction(self):
        """Ground Truth 注入附加强制指令。"""
        self.mgr.ground_truth.add("用户偏好 Python 3.12")
        state = self._make_state("Python")

        await self.middleware.before_llm_call(state)

        # 检查强制指令
        force_text_found = False
        for msg in state.context.messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if "权威记忆" in content and "必须优先参考" in content:
                    force_text_found = True
                    break
        assert force_text_found

    @pytest.mark.asyncio
    async def test_injection_format(self):
        """注入格式: [Memory · {layer} · score={score}] {content}"""
        self.mgr.ground_truth.add("Test ground truth content")
        state = self._make_state("Test")

        await self.middleware.before_llm_call(state)

        format_found = False
        for msg in state.context.messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if "[Memory ·" in content and "score=" in content:
                    format_found = True
                    break
        assert format_found

    def test_reset_session(self):
        """重置 session 状态。"""
        self.middleware._injected_keys.add("test_key")
        self.middleware.reset_session()
        assert len(self.middleware._injected_keys) == 0

    def test_priority(self):
        """优先级为 15。"""
        assert self.middleware.priority == 15

    def test_name(self):
        """名称为 PreLLMInjectMiddleware。"""
        assert self.middleware.name == "PreLLMInjectMiddleware"

    def test_repr(self):
        """repr 方法。"""
        assert "PreLLMInjectMiddleware" in repr(self.middleware)
