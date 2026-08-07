"""Suyi CLI 模块测试.

测试不依赖终端的功能：
- 格式化器（formatter）：颜色、分隔线、代码块等
- 命令系统（commands）：命令注册、分发、别名
- REPL 上下文（repl）：上下文构建、消息处理

运行方式:
    cd /app/data/所有对话/主对话/suyi/
    python -m pytest tests/test_cli.py -v
"""

import asyncio
import os
import sys
import tempfile
import pytest

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ═══════════════════════════════════════════════════════════════
#  Formatter 测试
# ═══════════════════════════════════════════════════════════════

class TestColor:
    """Color 类测试."""

    def test_color_codes_exist(self):
        """所有颜色码应存在且为非空字符串."""
        from suyi.cli.formatter import Color
        assert Color.reset == "\033[0m"
        assert Color.cyan == "\033[36m"
        assert Color.green == "\033[32m"
        assert Color.yellow == "\033[33m"
        assert Color.red == "\033[31m"
        assert Color.bold == "\033[1m"
        assert Color.dim == "\033[2m"

    def test_bright_colors(self):
        """亮色码应存在."""
        from suyi.cli.formatter import Color
        assert Color.bright_cyan == "\033[96m"
        assert Color.bright_green == "\033[92m"
        assert Color.bright_red == "\033[91m"


class TestColorize:
    """colorize 函数测试."""

    def test_colorize_with_color(self):
        """启用颜色时应包裹 ANSI 码."""
        from suyi.cli import formatter as fmt
        fmt.set_color_enabled(True)
        result = fmt.colorize("hello", fmt.Color.green)
        assert "\033[32m" in result
        assert "hello" in result
        assert "\033[0m" in result

    def test_colorize_without_color(self):
        """禁用颜色时应返回原文."""
        from suyi.cli import formatter as fmt
        fmt.set_color_enabled(False)
        result = fmt.colorize("hello", fmt.Color.green)
        assert result == "hello"
        # 恢复
        fmt.set_color_enabled(True)

    def test_colorize_multiple_colors(self):
        """多个颜色应按顺序拼接."""
        from suyi.cli import formatter as fmt
        fmt.set_color_enabled(True)
        result = fmt.colorize("text", fmt.Color.cyan, fmt.Color.bold)
        assert "\033[36m" in result
        assert "\033[1m" in result

    def test_colorize_empty_colors(self):
        """无颜色参数时应返回原文."""
        from suyi.cli import formatter as fmt
        fmt.set_color_enabled(True)
        result = fmt.colorize("text")
        assert result == "text"

    def test_convenience_functions(self):
        """便捷函数应正确着色."""
        from suyi.cli import formatter as fmt
        fmt.set_color_enabled(True)
        assert "\033[36m" in fmt.cyan("x")
        assert "\033[32m" in fmt.green("x")
        assert "\033[33m" in fmt.yellow("x")
        assert "\033[31m" in fmt.red("x")
        assert "\033[1m" in fmt.bold("x")
        assert "\033[2m" in fmt.dim("x")


class TestSet_color_enabled:
    """颜色开关测试."""

    def test_enable_disable(self):
        """应能切换颜色开关."""
        from suyi.cli import formatter as fmt
        original = fmt.is_color_enabled()

        fmt.set_color_enabled(False)
        assert fmt.is_color_enabled() is False
        assert fmt.cyan("test") == "test"

        fmt.set_color_enabled(True)
        assert fmt.is_color_enabled() is True
        assert "\033[" in fmt.cyan("test")

        # 恢复
        fmt.set_color_enabled(original)


class TestSeparator:
    """分隔线测试."""

    def test_separator_default(self):
        """默认分隔线应返回字符串."""
        from suyi.cli.formatter import separator
        line = separator()
        assert isinstance(line, str)
        assert len(line) > 0

    def test_separator_custom_char(self):
        """自定义字符应出现在分隔线中."""
        from suyi.cli.formatter import separator
        line = separator(char="=", width=20)
        assert line == "=" * 20

    def test_separator_custom_width(self):
        """自定义宽度应正确."""
        from suyi.cli.formatter import separator
        line = separator(char="-", width=10)
        assert len(line) == 10
        assert line == "-" * 10


class TestTitle:
    """标题格式化测试."""

    def test_title_contains_text(self):
        """标题应包含原始文本."""
        from suyi.cli.formatter import title
        result = title("Test Title")
        assert "Test Title" in result

    def test_title_has_separators(self):
        """标题应包含分隔线."""
        from suyi.cli.formatter import title
        result = title("Test")
        assert "─" in result


class TestCodeBlock:
    """代码块格式化测试."""

    def test_code_block_contains_text(self):
        """代码块应包含原始文本."""
        from suyi.cli.formatter import code_block
        result = code_block("print('hello')")
        assert "print('hello')" in result

    def test_code_block_has_border(self):
        """代码块应有边框."""
        from suyi.cli.formatter import code_block
        result = code_block("x = 1")
        assert "┌" in result
        assert "└" in result
        assert "│" in result

    def test_code_block_with_language(self):
        """代码块应包含语言标识."""
        from suyi.cli.formatter import code_block
        result = code_block("x = 1", language="python")
        assert "python" in result


class TestFormatToolCall:
    """工具调用格式化测试."""

    def test_format_tool_call_basic(self):
        """基本工具调用格式化."""
        from suyi.cli.formatter import format_tool_call
        result = format_tool_call("search", {"query": "test"})
        assert "search" in result
        assert "query" in result
        assert "test" in result

    def test_format_tool_call_with_result(self):
        """带结果的工具调用格式化."""
        from suyi.cli.formatter import format_tool_call
        result = format_tool_call("bash", {"command": "ls"}, result="file1\nfile2")
        assert "bash" in result
        assert "file1" in result

    def test_format_tool_call_truncates_long_result(self):
        """过长结果应被截断."""
        from suyi.cli.formatter import format_tool_call
        long_result = "x" * 600
        result = format_tool_call("read_file", {"path": "f"}, result=long_result)
        assert "..." in result
        assert len(result) < 700  # 截断后应更短

    def test_format_tool_call_failure(self):
        """失败的工具调用."""
        from suyi.cli.formatter import format_tool_call
        result = format_tool_call("bash", {"command": "rm"}, success=False)
        assert "✗" in result or "bash" in result


class TestFormatKeyValue:
    """键值对格式化测试."""

    def test_format_key_value(self):
        """键值对应包含键和值."""
        from suyi.cli.formatter import format_key_value
        result = format_key_value("name", "value")
        assert "name" in result
        assert "value" in result

    def test_format_key_value_indent(self):
        """缩进应正确."""
        from suyi.cli.formatter import format_key_value
        result = format_key_value("k", "v", indent=4)
        assert result.startswith("    ")


class TestFormatListItem:
    """列表项格式化测试."""

    def test_format_list_item(self):
        """列表项应包含文本."""
        from suyi.cli.formatter import format_list_item
        result = format_list_item("item text")
        assert "item text" in result

    def test_format_list_item_level(self):
        """缩进层级应正确."""
        from suyi.cli import formatter as fmt
        # 禁用颜色以便准确检查缩进
        fmt.set_color_enabled(False)
        try:
            result_l0 = fmt.format_list_item("x", level=0)
            result_l1 = fmt.format_list_item("x", level=1)
            result_l2 = fmt.format_list_item("x", level=2)
            # level=0 → 无缩进
            assert result_l0.startswith("•") or result_l0.startswith("  •") is False
            # level=1 → 2 空格缩进
            assert result_l1.startswith("  ")
            assert not result_l1.startswith("    ")
            # level=2 → 4 空格缩进
            assert result_l2.startswith("    ")
        finally:
            fmt.set_color_enabled(True)


class TestMessageFormatters:
    """消息格式化函数测试."""

    def test_info(self):
        """info 消息应包含 [INFO] 标记."""
        from suyi.cli.formatter import info
        result = info("message")
        assert "[INFO]" in result
        assert "message" in result

    def test_success(self):
        """success 消息应包含 [OK] 标记."""
        from suyi.cli.formatter import success
        result = success("done")
        assert "[OK]" in result
        assert "done" in result

    def test_warning(self):
        """warning 消息应包含 [WARN] 标记."""
        from suyi.cli.formatter import warning
        result = warning("careful")
        assert "[WARN]" in result
        assert "careful" in result

    def test_error(self):
        """error 消息应包含 [ERROR] 标记."""
        from suyi.cli.formatter import error
        result = error("failed")
        assert "[ERROR]" in result
        assert "failed" in result


class TestTruncate:
    """截断函数测试."""

    def test_truncate_short(self):
        """短文本不应被截断."""
        from suyi.cli.formatter import truncate
        assert truncate("short", max_len=100) == "short"

    def test_truncate_long(self):
        """长文本应被截断并加后缀."""
        from suyi.cli.formatter import truncate
        text = "x" * 100
        result = truncate(text, max_len=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        """自定义后缀."""
        from suyi.cli.formatter import truncate
        text = "x" * 100
        result = truncate(text, max_len=50, suffix="[...]")
        assert result.endswith("[...]")


class TestUserPrompt:
    """用户提示符测试."""

    def test_user_prompt_default(self):
        """默认提示符."""
        from suyi.cli.formatter import user_prompt
        result = user_prompt()
        assert "suyi" in result
        assert ">" in result

    def test_user_prompt_custom(self):
        """自定义提示符."""
        from suyi.cli.formatter import user_prompt
        result = user_prompt(prefix="custom")
        assert "custom" in result


# ═══════════════════════════════════════════════════════════════
#  Commands 测试
# ═══════════════════════════════════════════════════════════════

class TestCommandRegistry:
    """命令注册表测试."""

    def test_all_commands_registered(self):
        """所有预期命令应已注册."""
        from suyi.cli.commands import COMMAND_REGISTRY
        expected = {"/help", "/memory", "/tools", "/skills", "/config",
                    "/clear", "/reset", "/evolve", "/quit"}
        assert expected.issubset(set(COMMAND_REGISTRY.keys()))

    def test_command_has_handler_and_description(self):
        """每个命令应有处理函数和描述."""
        from suyi.cli.commands import COMMAND_REGISTRY
        for name, (handler, desc) in COMMAND_REGISTRY.items():
            assert callable(handler), f"{name} handler is not callable"
            assert isinstance(desc, str) and len(desc) > 0, f"{name} description is empty"

    def test_command_aliases(self):
        """别名应正确映射."""
        from suyi.cli.commands import COMMAND_ALIASES
        assert COMMAND_ALIASES["/h"] == "/help"
        assert COMMAND_ALIASES["/q"] == "/quit"
        assert COMMAND_ALIASES["/exit"] == "/quit"

    def test_get_command_existing(self):
        """获取已注册命令应返回处理函数."""
        from suyi.cli.commands import get_command
        handler = get_command("/help")
        assert handler is not None
        assert callable(handler)

    def test_get_command_via_alias(self):
        """通过别名获取命令应返回对应处理函数."""
        from suyi.cli.commands import get_command
        handler = get_command("/h")
        assert handler is not None
        assert callable(handler)

    def test_get_command_nonexistent(self):
        """获取不存在的命令应返回 None."""
        from suyi.cli.commands import get_command
        assert get_command("/nonexistent") is None

    def test_get_command_description(self):
        """获取命令描述."""
        from suyi.cli.commands import get_command_description
        desc = get_command_description("/help")
        assert desc is not None
        assert isinstance(desc, str)

    def test_list_commands(self):
        """列出所有命令应返回有序列表."""
        from suyi.cli.commands import list_commands
        commands = list_commands()
        assert len(commands) >= 9
        # 应按名称排序
        names = [c[0] for c in commands]
        assert names == sorted(names)

    def test_is_command(self):
        """识别斜杠命令."""
        from suyi.cli.commands import is_command
        assert is_command("/help") is True
        assert is_command("/quit") is True
        assert is_command("  /clear") is True
        assert is_command("hello world") is False
        assert is_command("") is False


class TestCommandDispatch:
    """命令分发测试."""

    @pytest.fixture
    def ctx(self):
        """创建测试用的 REPLContext."""
        from suyi.cli.repl import REPLContext
        return REPLContext(config={"mock": True, "provider": "test"})

    @pytest.mark.asyncio
    async def test_dispatch_help(self, ctx):
        """/help 应返回帮助信息."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/help", ctx)
        assert result.should_quit is False
        assert result.message is not None
        assert "命令" in result.message or "command" in result.message.lower()

    @pytest.mark.asyncio
    async def test_dispatch_quit(self, ctx):
        """/quit 应返回退出信号."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/quit", ctx)
        assert result.should_quit is True

    @pytest.mark.asyncio
    async def test_dispatch_unknown(self, ctx):
        """未知命令应返回错误信息."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/unknown", ctx)
        assert result.should_quit is False
        assert result.message is not None
        assert "未知" in result.message or "unknown" in result.message.lower()

    @pytest.mark.asyncio
    async def test_dispatch_alias(self, ctx):
        """别名应正确分发."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/h", ctx)
        assert result.should_quit is False
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_dispatch_tools_empty(self, ctx):
        """/tools 在无工具时应显示警告."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/tools", ctx)
        assert result.message is not None
        # ctx.tools 为 None，应显示警告
        assert "未" in result.message or "没有" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_tools_with_tools(self, ctx):
        """/tools 在有工具时应列出工具."""
        from suyi.cli.commands import dispatch_command
        from suyi.core.loop import FunctionTool
        ctx.tools = [
            FunctionTool("search", "Search the web", lambda **k: "result"),
            FunctionTool("read_file", "Read a file", lambda **k: "content"),
        ]
        result = await dispatch_command("/tools", ctx)
        assert result.message is not None
        assert "search" in result.message
        assert "read_file" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_config(self, ctx):
        """/config 应显示配置信息."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/config", ctx)
        assert result.message is not None
        assert "mock" in result.message.lower() or "Mock" in result.message
        assert "test" in result.message  # provider

    @pytest.mark.asyncio
    async def test_dispatch_clear(self, ctx):
        """/clear 应清空对话历史."""
        from suyi.cli.commands import dispatch_command
        ctx.conversation_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = await dispatch_command("/clear", ctx)
        assert result.message is not None
        assert len(ctx.conversation_history) == 0

    @pytest.mark.asyncio
    async def test_dispatch_reset(self, ctx):
        """/reset 应重置 Agent 状态."""
        from suyi.cli.commands import dispatch_command
        ctx.conversation_history = [{"role": "user", "content": "x"}]
        ctx.turn_count = 5
        ctx.interaction_records = [1, 2, 3]
        result = await dispatch_command("/reset", ctx)
        assert result.message is not None
        assert len(ctx.conversation_history) == 0
        assert ctx.turn_count == 0
        assert len(ctx.interaction_records) == 0

    @pytest.mark.asyncio
    async def test_dispatch_evolve_insufficient(self, ctx):
        """/evolve 在交互记录不足时应提示."""
        from suyi.cli.commands import dispatch_command
        result = await dispatch_command("/evolve", ctx)
        assert result.message is not None
        assert "不足" in result.message or "insufficient" in result.message.lower()

    @pytest.mark.asyncio
    async def test_dispatch_evolve_with_records(self, ctx):
        """/evolve 在有足够交互记录时应运行进化分析."""
        from suyi.cli.commands import dispatch_command
        from suyi.evolution import InteractionRecord
        # 添加足够的交互记录
        for i in range(5):
            ctx.interaction_records.append(InteractionRecord(
                task=f"task_{i}",
                tool_calls=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": "ok"},
                ],
                success=True,
                duration=1.0,
                tokens_used=100,
            ))
        result = await dispatch_command("/evolve", ctx)
        assert result.should_quit is False
        # 应有输出（可能是成功或错误信息）
        assert result.message is not None


class TestCommandResult:
    """CommandResult 测试."""

    def test_continue_repl(self):
        """continue_repl 应设置 should_quit=False."""
        from suyi.cli.commands import CommandResult
        r = CommandResult.continue_repl("message")
        assert r.should_quit is False
        assert r.message == "message"

    def test_continue_repl_no_message(self):
        """continue_repl 无消息时 message 为 None."""
        from suyi.cli.commands import CommandResult
        r = CommandResult.continue_repl()
        assert r.should_quit is False
        assert r.message is None

    def test_quit_repl(self):
        """quit_repl 应设置 should_quit=True."""
        from suyi.cli.commands import CommandResult
        r = CommandResult.quit_repl("bye")
        assert r.should_quit is True
        assert r.message == "bye"


# ═══════════════════════════════════════════════════════════════
#  REPL 测试
# ═══════════════════════════════════════════════════════════════

class TestREPLContext:
    """REPLContext 测试."""

    def test_default_values(self):
        """默认值应正确."""
        from suyi.cli.repl import REPLContext
        ctx = REPLContext()
        assert ctx.agent_loop is None
        assert ctx.llm is None
        assert ctx.memory_manager is None
        assert ctx.tools is None
        assert ctx.middleware is None
        assert ctx.skill_loader is None
        assert ctx.config == {}
        assert ctx.conversation_history == []
        assert ctx.turn_count == 0
        assert ctx.interaction_records == []

    def test_with_values(self):
        """设置值应正确."""
        from suyi.cli.repl import REPLContext
        ctx = REPLContext(
            config={"mock": True},
            turn_count=3,
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        assert ctx.config["mock"] is True
        assert ctx.turn_count == 3
        assert len(ctx.conversation_history) == 1


class TestBuildContext:
    """build_context 函数测试."""

    def test_build_context_mock(self):
        """mock 模式应正确构建上下文."""
        from suyi.cli.repl import build_context
        ctx = build_context(mock=True)
        assert ctx.agent_loop is not None
        assert ctx.llm is not None
        assert ctx.memory_manager is not None
        assert ctx.tools is not None
        assert ctx.middleware is not None
        assert ctx.config["mock"] is True

    def test_build_context_has_tools(self):
        """构建的上下文应包含内置工具."""
        from suyi.cli.repl import build_context
        ctx = build_context(mock=True)
        tool_names = [t.name for t in ctx.tools]
        assert "bash" in tool_names
        assert "read_file" in tool_names
        assert "search" in tool_names

    def test_build_context_has_middleware(self):
        """构建的上下文应包含中间件链."""
        from suyi.cli.repl import build_context
        ctx = build_context(mock=True)
        assert len(ctx.middleware) >= 2  # 至少有 loop_detection 和 clarification

    def test_build_context_fallback_to_mock(self):
        """非 mock 模式无真实 LLM 时应回退到 Mock."""
        from suyi.cli.repl import build_context
        ctx = build_context(mock=False)
        # 应回退到 mock
        assert ctx.config["mock"] is True
        assert "_fallback_note" in ctx.config


class TestProcessMessage:
    """process_message 函数测试."""

    @pytest.mark.asyncio
    async def test_process_message_basic(self):
        """基本消息处理."""
        from suyi.cli.repl import build_context, process_message

        ctx = build_context(mock=True)
        result = await process_message(ctx, "Hello")

        assert result is not None
        assert hasattr(result, "content")
        assert len(result.content) > 0
        assert ctx.turn_count == 1
        assert len(ctx.conversation_history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_process_message_multi_turn(self):
        """多轮消息处理."""
        from suyi.cli.repl import build_context, process_message

        ctx = build_context(mock=True)
        # 第一轮
        await process_message(ctx, "Hi")
        # 第二轮
        await process_message(ctx, "Tell me more")

        assert ctx.turn_count == 2
        assert len(ctx.conversation_history) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_process_message_records_interaction(self):
        """消息处理应记录交互."""
        from suyi.cli.repl import build_context, process_message

        ctx = build_context(mock=True)
        await process_message(ctx, "Test message")

        assert len(ctx.interaction_records) == 1
        record = ctx.interaction_records[0]
        assert record.task == "Test message"

    @pytest.mark.asyncio
    async def test_process_message_no_agent_loop(self):
        """无 AgentLoop 时应抛出异常."""
        from suyi.cli.repl import REPLContext, process_message

        ctx = REPLContext()  # agent_loop is None
        with pytest.raises(RuntimeError):
            await process_message(ctx, "test")


# ═══════════════════════════════════════════════════════════════
#  CLI 模块导入测试
# ═══════════════════════════════════════════════════════════════

class TestCLIImports:
    """CLI 模块导入测试."""

    def test_import_formatter(self):
        """能导入 formatter 模块."""
        from suyi.cli import formatter
        assert hasattr(formatter, "Color")
        assert hasattr(formatter, "colorize")
        assert hasattr(formatter, "cyan")

    def test_import_commands(self):
        """能导入 commands 模块."""
        from suyi.cli import commands
        assert hasattr(commands, "COMMAND_REGISTRY")
        assert hasattr(commands, "dispatch_command")
        assert hasattr(commands, "is_command")

    def test_import_repl(self):
        """能导入 repl 模块."""
        from suyi.cli import repl
        assert hasattr(repl, "REPLContext")
        assert hasattr(repl, "run_repl")
        assert hasattr(repl, "build_context")

    def test_import_cli_package(self):
        """能导入 cli 包并访问导出."""
        from suyi.cli import (
            Color, colorize, cyan, green,
            CommandResult, COMMAND_REGISTRY,
            REPLContext, run_repl, build_context,
        )
        assert Color is not None
        assert COMMAND_REGISTRY is not None
        assert REPLContext is not None

    def test_suyi_init_exports_cli(self):
        """suyi.__init__ 不需要导出 cli（但 cli 可正常导入）."""
        import suyi
        # cli 模块可以通过 suyi.cli 访问
        import suyi.cli
        assert suyi.cli is not None
