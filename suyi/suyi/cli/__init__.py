"""Suyi CLI 模块 — 命令行交互入口.

提供交互式 REPL、斜杠命令、终端格式化和入口点.

模块结构:
    formatter  — ANSI 颜色、分隔线、代码块等终端格式化
    commands   — 斜杠命令处理（/help, /memory, /tools 等）
    repl       — 交互式 REPL 主循环
    __main__   — python -m suyi.cli 入口点

快速使用::

    # 命令行启动
    python -m suyi.cli --mock

    # 代码中调用
    import asyncio
    from suyi.cli import run_repl
    asyncio.run(run_repl())
"""

from .formatter import (
    Color,
    colorize,
    cyan, green, yellow, red, bold, dim, magenta, blue,
    separator, print_separator, title, print_title,
    code_block, print_code_block,
    format_tool_call, format_key_value, format_list_item,
    banner, print_banner,
    info, success, warning, error,
    user_prompt, thinking_indicator, truncate,
    set_color_enabled, is_color_enabled,
)

from .commands import (
    CommandResult,
    COMMAND_REGISTRY,
    COMMAND_ALIASES,
    get_command,
    get_command_description,
    list_commands,
    is_command,
    dispatch_command,
)

from .repl import (
    REPLContext,
    run_repl,
    run_repl_sync,
    build_context,
    process_message,
    adapt_agent_tool,
)

__all__ = [
    # formatter
    "Color",
    "colorize",
    "cyan", "green", "yellow", "red", "bold", "dim", "magenta", "blue",
    "separator", "print_separator", "title", "print_title",
    "code_block", "print_code_block",
    "format_tool_call", "format_key_value", "format_list_item",
    "banner", "print_banner",
    "info", "success", "warning", "error",
    "user_prompt", "thinking_indicator", "truncate",
    "set_color_enabled", "is_color_enabled",
    # commands
    "CommandResult",
    "COMMAND_REGISTRY",
    "COMMAND_ALIASES",
    "get_command",
    "get_command_description",
    "list_commands",
    "is_command",
    "dispatch_command",
    # repl
    "REPLContext",
    "run_repl",
    "run_repl_sync",
    "build_context",
    "process_message",
    "adapt_agent_tool",
]
