"""
端到端集成测试 — 验证完整 Agent 运行链路。

覆盖五条端到端场景：
    1. 完整对话链路：用户消息 → MockLLM 文本回复 → 验证响应与记忆
    2. 工具调用链路：MockLLM 返回 ToolCall → 执行工具 → MockLLM 返回最终回复
    3. 记忆持久化链路：对话存储到 SQLiteBackend → 重新加载 → 验证数据一致
    4. 多工具编排链路：MockLLM 返回多个 ToolCall → 并行执行 → 验证结果
    5. 错误处理链路：工具执行失败 → AgentLoop 优雅处理 → 返回错误信息

所有测试使用 MockLLM（不依赖真实 LLM）和临时文件/临时数据库（不污染环境）。
"""

import asyncio
import json
import os
import tempfile

import pytest

from suyi.core.loop import (
    AgentLoop,
    MockLLM,
    LLMResponse,
    Tool,
    FunctionTool,
    ToolResult,
    LoopResult,
)
from suyi.core.budget import BudgetTracker, BudgetConfig
from suyi.core.context import ContextAssembler, IdentityConfig, ProjectRules
from suyi.memory import WorkingMemory
from suyi.persistence import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  测试 1：完整对话链路
# ═══════════════════════════════════════════════════════════════


class TestE2EFullConversation:
    """端到端测试 1：完整对话链路。

    验证用户消息 → MockLLM 返回文本回复 → WorkingMemory 记录所有对话。
    """

    async def test_full_conversation_chain(self):
        """发送3轮对话，验证每轮返回正确且 WorkingMemory 记录完整。"""

        # --- 准备 MockLLM，预设3轮文本回复 ---
        mock_llm = MockLLM([
            LLMResponse.text("你好！我是 Suyi，很高兴为你服务。"),
            LLMResponse.text("Python 是一门简洁优雅的编程语言。"),
            LLMResponse.text("再见！祝你有个愉快的一天。"),
        ])

        # --- 创建 AgentLoop ---
        loop = AgentLoop(llm=mock_llm)

        # --- 创建 WorkingMemory 记录对话 ---
        working_memory = WorkingMemory(token_budget=8192)

        # --- 执行3轮对话 ---
        conversations = [
            ("你好", "你好！我是 Suyi，很高兴为你服务。"),
            ("介绍一下 Python", "Python 是一门简洁优雅的编程语言。"),
            ("再见", "再见！祝你有个愉快的一天。"),
        ]

        results = []
        for user_msg, expected_reply in conversations:
            # 记录用户消息到 WorkingMemory
            working_memory.add_message("user", user_msg)

            # 执行 Agent 循环
            result = await loop.run(user_msg)
            results.append(result)

            # 记录助手回复到 WorkingMemory
            working_memory.add_message("assistant", result.content)

        # --- 断言 1：每轮返回的 content 与预设回复一致 ---
        for i, (_, expected_reply) in enumerate(conversations):
            assert results[i].content == expected_reply, (
                f"第 {i+1} 轮回复不匹配：期望 '{expected_reply}'，"
                f"实际 '{results[i].content}'"
            )

        # --- 断言 2：每轮都是自然结束（非部分/中断） ---
        for i, result in enumerate(results):
            assert result.is_complete, f"第 {i+1} 轮未自然结束"
            assert result.stop_reason == "natural", (
                f"第 {i+1} 轮停止原因为 {result.stop_reason}，期望 'natural'"
            )

        # --- 断言 3：WorkingMemory 记录了所有6条消息（3轮 × 2条） ---
        assert working_memory.get_turn_count() == 6, (
            f"WorkingMemory 应记录6条消息，实际 {working_memory.get_turn_count()}"
        )

        # --- 断言 4：WorkingMemory 消息角色交替正确 ---
        roles = [msg["role"] for msg in working_memory.messages]
        assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"], (
            f"消息角色序列不正确：{roles}"
        )

        # --- 断言 5：MockLLM 被调用了3次 ---
        assert mock_llm.calls_made == 3, (
            f"MockLLM 应被调用3次，实际 {mock_llm.calls_made} 次"
        )


# ═══════════════════════════════════════════════════════════════
#  测试 2：工具调用链路
# ═══════════════════════════════════════════════════════════════


class TestE2EToolCall:
    """端到端测试 2：工具调用链路。

    验证 MockLLM 返回 ToolCall → 执行工具 → 结果传回 LLM → 最终回复。
    """

    async def test_tool_call_chain(self, tmp_path):
        """MockLLM 先返回读文件 ToolCall，再返回包含文件内容的最终回复。"""

        # --- 准备临时测试文件 ---
        test_file = tmp_path / "secret.txt"
        test_content = "The answer is 42."
        test_file.write_text(test_content, encoding="utf-8")

        # --- 创建读文件工具（基于 FunctionTool，适配 AgentLoop 的 Tool 接口） ---
        def read_file_func(path: str) -> str:
            """读取文件内容的工具函数。"""
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        read_tool = FunctionTool(
            name="read_file",
            description="Read the content of a file.",
            func=read_file_func,
            default_permission="auto",
        )

        # --- 准备 MockLLM：第一次返回 ToolCall，第二次返回最终文本 ---
        mock_llm = MockLLM([
            LLMResponse.action(
                name="read_file",
                arguments={"path": str(test_file)},
                content="我需要读取文件内容来回答你的问题。",
            ),
            LLMResponse.text(
                f"根据文件内容，{test_content}"
            ),
        ])

        # --- 创建 AgentLoop，注册读文件工具 ---
        loop = AgentLoop(llm=mock_llm, tools=[read_tool])

        # --- 执行对话 ---
        result = await loop.run("文件里写了什么？")

        # --- 断言 1：最终回复包含工具执行结果 ---
        assert "42" in result.content, (
            f"最终回复应包含工具读取的内容 '42'，实际：'{result.content}'"
        )

        # --- 断言 2：MockLLM 被调用了2次（第一次返回 ToolCall，第二次返回文本） ---
        assert mock_llm.calls_made == 2, (
            f"MockLLM 应被调用2次，实际 {mock_llm.calls_made} 次"
        )

        # --- 断言 3：对话历史中包含工具调用和工具结果消息 ---
        tool_messages = [msg for msg in result.history if msg.get("role") == "tool"]
        assert len(tool_messages) == 1, (
            f"历史中应有1条工具结果消息，实际 {len(tool_messages)} 条"
        )
        assert test_content in tool_messages[0]["content"], (
            f"工具结果消息应包含文件内容 '{test_content}'，"
            f"实际：'{tool_messages[0]['content']}'"
        )

        # --- 断言 4：助手消息中包含 ToolCall ---
        assistant_msgs = [msg for msg in result.history if msg.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1, "应至少有1条助手消息"
        first_assistant = assistant_msgs[0]
        assert "tool_calls" in first_assistant, "助手消息应包含 tool_calls 字段"
        assert first_assistant["tool_calls"][0]["function"]["name"] == "read_file", (
            f"ToolCall 名称应为 'read_file'，实际："
            f"{first_assistant['tool_calls'][0]['function']['name']}"
        )

        # --- 断言 5：循环自然结束 ---
        assert result.is_complete, "循环应自然结束"
        assert result.turns_used == 2, (
            f"应使用2轮（工具调用 + 最终回复），实际 {result.turns_used} 轮"
        )


# ═══════════════════════════════════════════════════════════════
#  测试 3：记忆持久化链路
# ═══════════════════════════════════════════════════════════════


class TestE2EMemoryPersistence:
    """端到端测试 3：记忆持久化链路。

    验证对话存储到 SQLiteBackend → 重新加载 → search() 找到之前的数据。
    """

    def test_memory_persistence_chain(self, tmp_path):
        """存储对话记录到 SQLite，重新打开后验证数据一致。"""

        db_path = str(tmp_path / "test_memory.db")

        # --- 第一阶段：写入对话记录 ---
        backend = SQLiteBackend(db_path=db_path)

        conversations = [
            {
                "key": "conv_001",
                "value": {
                    "role": "user",
                    "content": "Python 的 GIL 是什么？",
                    "timestamp": "2026-08-09T10:00:00Z",
                },
            },
            {
                "key": "conv_002",
                "value": {
                    "role": "assistant",
                    "content": "GIL 是全局解释器锁，防止多线程并行执行字节码。",
                    "timestamp": "2026-08-09T10:00:05Z",
                },
            },
            {
                "key": "conv_003",
                "value": {
                    "role": "user",
                    "content": "如何绕过 GIL 的限制？",
                    "timestamp": "2026-08-09T10:01:00Z",
                },
            },
        ]

        for conv in conversations:
            backend.set(conv["key"], conv["value"])

        # --- 断言 1：写入后 count 为 3 ---
        assert backend.count() == 3, (
            f"写入3条记录后 count 应为3，实际 {backend.count()}"
        )

        # --- 关闭后端，模拟进程退出 ---
        backend.close()

        # --- 第二阶段：重新打开数据库 ---
        backend_reloaded = SQLiteBackend(db_path=db_path)

        # --- 断言 2：重新加载后数据仍然存在 ---
        assert backend_reloaded.count() == 3, (
            f"重新加载后 count 应为3，实际 {backend_reloaded.count()}"
        )

        # --- 断言 3：exists() 正确识别已有键 ---
        assert backend_reloaded.exists("conv_001"), "conv_001 应存在"
        assert backend_reloaded.exists("conv_002"), "conv_002 应存在"
        assert not backend_reloaded.exists("conv_999"), "conv_999 不应存在"

        # --- 断言 4：get() 返回的数据与写入时一致 ---
        retrieved = backend_reloaded.get("conv_002")
        assert retrieved is not None, "conv_002 不应为 None"
        assert retrieved["role"] == "assistant", (
            f"conv_002 的 role 应为 'assistant'，实际 '{retrieved['role']}'"
        )
        assert "GIL" in retrieved["content"], (
            "conv_002 的 content 应包含 'GIL'"
        )

        # --- 断言 5：search() 能通过全文搜索找到之前的对话 ---
        search_results = backend_reloaded.search("GIL", top_k=10)
        assert len(search_results) > 0, (
            "搜索 'GIL' 应返回至少1条结果"
        )
        found_keys = {r["key"] for r in search_results}
        assert "conv_002" in found_keys, (
            f"搜索结果应包含 conv_002，实际包含：{found_keys}"
        )

        # --- 断言 6：list_keys() 返回所有键 ---
        all_keys = backend_reloaded.list_keys()
        assert set(all_keys) == {"conv_001", "conv_002", "conv_003"}, (
            f"list_keys 应返回3个键，实际：{all_keys}"
        )

        # --- 清理 ---
        backend_reloaded.close()


# ═══════════════════════════════════════════════════════════════
#  测试 4：多工具编排链路
# ═══════════════════════════════════════════════════════════════


class TestE2EMultiToolOrchestration:
    """端到端测试 4：多工具编排链路。

    验证 MockLLM 一次返回多个 ToolCall → 并行执行 → 结果都传回 LLM。
    """

    async def test_multi_tool_orchestration(self, tmp_path):
        """MockLLM 返回 WriteFile + ReadFile 两个 ToolCall，验证都被执行。"""

        # --- 准备临时文件路径 ---
        write_path = str(tmp_path / "output.txt")
        read_source = tmp_path / "source.txt"
        read_source.write_text("源文件内容：Hello World", encoding="utf-8")

        # --- 创建写文件工具 ---
        def write_file_func(path: str, content: str) -> str:
            """写入文件内容的工具函数。"""
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"文件已写入：{path}（{len(content)} 字符）"

        write_tool = FunctionTool(
            name="write_file",
            description="Write content to a file.",
            func=write_file_func,
            default_permission="auto",
        )

        # --- 创建读文件工具 ---
        def read_file_func(path: str) -> str:
            """读取文件内容的工具函数。"""
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        read_tool = FunctionTool(
            name="read_file",
            description="Read the content of a file.",
            func=read_file_func,
            default_permission="auto",
        )

        # --- 准备 MockLLM：第一次返回两个并行 ToolCall，第二次返回最终文本 ---
        mock_llm = MockLLM([
            LLMResponse.actions(
                ("write_file", {"path": write_path, "content": "写入的内容：测试数据"}),
                ("read_file", {"path": str(read_source)}),
                content="我需要同时写入一个文件并读取另一个文件。",
            ),
            LLMResponse.text("两个工具都已成功执行。"),
        ])

        # --- 创建 AgentLoop，注册两个工具 ---
        loop = AgentLoop(llm=mock_llm, tools=[write_tool, read_tool])

        # --- 执行对话 ---
        result = await loop.run("请同时写入文件并读取源文件。")

        # --- 断言 1：最终回复确认两个工具都执行了 ---
        assert "成功" in result.content, (
            f"最终回复应包含 '成功'，实际：'{result.content}'"
        )

        # --- 断言 2：对话历史中有2条工具结果消息 ---
        tool_messages = [msg for msg in result.history if msg.get("role") == "tool"]
        assert len(tool_messages) == 2, (
            f"历史中应有2条工具结果消息，实际 {len(tool_messages)} 条"
        )

        # --- 断言 3：两个工具都被执行（通过工具名验证） ---
        tool_names = {msg.get("name") for msg in tool_messages}
        assert "write_file" in tool_names, (
            f"工具结果中应包含 'write_file'，实际：{tool_names}"
        )
        assert "read_file" in tool_names, (
            f"工具结果中应包含 'read_file'，实际：{tool_names}"
        )

        # --- 断言 4：写文件工具确实写入了文件 ---
        assert os.path.exists(write_path), "写入的文件应存在"
        with open(write_path, "r", encoding="utf-8") as f:
            written_content = f.read()
        assert "测试数据" in written_content, (
            f"写入的文件应包含 '测试数据'，实际：'{written_content}'"
        )

        # --- 断言 5：读文件工具结果包含源文件内容 ---
        read_result_msg = next(
            msg for msg in tool_messages if msg.get("name") == "read_file"
        )
        assert "Hello World" in read_result_msg["content"], (
            f"读文件结果应包含 'Hello World'，实际：'{read_result_msg['content']}'"
        )

        # --- 断言 6：MockLLM 被调用2次（多工具调用 + 最终回复） ---
        assert mock_llm.calls_made == 2, (
            f"MockLLM 应被调用2次，实际 {mock_llm.calls_made} 次"
        )


# ═══════════════════════════════════════════════════════════════
#  测试 5：错误处理链路
# ═══════════════════════════════════════════════════════════════


class TestE2EErrorHandling:
    """端到端测试 5：错误处理链路。

    验证工具执行失败时 AgentLoop 不崩溃，错误信息被正确记录并传回 LLM。
    """

    async def test_tool_error_handling(self):
        """工具执行失败 → AgentLoop 优雅处理 → 返回包含错误信息的回复。"""

        # --- 创建一个会抛出异常的工具 ---
        def failing_command(command: str) -> str:
            """模拟执行不存在的命令，抛出异常。"""
            raise FileNotFoundError(
                f"命令执行失败：'{command}' 不是有效的命令"
            )

        error_tool = FunctionTool(
            name="bash",
            description="Execute a bash command.",
            func=failing_command,
            default_permission="auto",
        )

        # --- 准备 MockLLM：第一次返回 ToolCall，第二次返回包含错误信息的文本 ---
        mock_llm = MockLLM([
            LLMResponse.action(
                name="bash",
                arguments={"command": "nonexistent_command_xyz"},
                content="我需要执行一个命令来完成任务。",
            ),
            LLMResponse.text("命令执行失败，该命令不存在，请检查命令名称。"),
        ])

        # --- 创建 AgentLoop，注册会失败的工具 ---
        loop = AgentLoop(llm=mock_llm, tools=[error_tool])

        # --- 执行对话 ---
        result = await loop.run("请执行 nonexistent_command_xyz 命令。")

        # --- 断言 1：AgentLoop 没有崩溃，返回了有效结果 ---
        assert result is not None, "AgentLoop 应返回有效结果，不应崩溃"
        assert result.content != "", "返回内容不应为空"

        # --- 断言 2：循环自然结束（工具失败后 LLM 给出了最终回复） ---
        assert result.is_complete, (
            f"循环应自然结束，实际 stop_reason={result.stop_reason}"
        )
        assert result.stop_reason == "natural", (
            f"停止原因应为 'natural'，实际 '{result.stop_reason}'"
        )

        # --- 断言 3：对话历史中包含工具结果消息，且标记为失败 ---
        tool_messages = [msg for msg in result.history if msg.get("role") == "tool"]
        assert len(tool_messages) == 1, (
            f"应有1条工具结果消息，实际 {len(tool_messages)} 条"
        )
        error_content = tool_messages[0]["content"]
        assert "失败" in error_content or "failed" in error_content.lower(), (
            f"工具结果应包含错误信息，实际：'{error_content}'"
        )

        # --- 断言 4：MockLLM 被调用2次（工具调用 + 最终回复） ---
        assert mock_llm.calls_made == 2, (
            f"MockLLM 应被调用2次，实际 {mock_llm.calls_made} 次"
        )

        # --- 断言 5：最终回复包含错误相关信息 ---
        assert "失败" in result.content or "不存在" in result.content, (
            f"最终回复应包含错误相关信息，实际：'{result.content}'"
        )

    async def test_tool_not_found_error(self):
        """MockLLM 调用不存在的工具名 → AgentLoop 优雅处理。"""

        # --- 准备 MockLLM：返回一个未注册工具的 ToolCall ---
        mock_llm = MockLLM([
            LLMResponse.action(
                name="nonexistent_tool",
                arguments={"query": "test"},
                content="我需要使用一个特殊工具。",
            ),
            LLMResponse.text("该工具不可用，我无法完成此操作。"),
        ])

        # --- 创建 AgentLoop，不注册任何工具 ---
        loop = AgentLoop(llm=mock_llm, tools=[])

        # --- 执行对话 ---
        result = await loop.run("请使用特殊工具。")

        # --- 断言 1：AgentLoop 没有崩溃 ---
        assert result is not None, "AgentLoop 应返回有效结果"
        assert result.is_complete, "循环应自然结束"

        # --- 断言 2：工具结果消息中包含"不可用"信息 ---
        tool_messages = [msg for msg in result.history if msg.get("role") == "tool"]
        assert len(tool_messages) == 1, (
            f"应有1条工具结果消息，实际 {len(tool_messages)} 条"
        )
        assert "not available" in tool_messages[0]["content"] or "不可用" in tool_messages[0]["content"], (
            f"工具结果应包含不可用信息，实际：'{tool_messages[0]['content']}'"
        )

        # --- 断言 3：MockLLM 被调用2次 ---
        assert mock_llm.calls_made == 2, (
            f"MockLLM 应被调用2次，实际 {mock_llm.calls_made} 次"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
