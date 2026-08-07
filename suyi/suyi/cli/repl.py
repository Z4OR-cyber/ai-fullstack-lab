"""交互式 REPL — 用户在终端与 Suyi Agent 对话.

功能:
    - 多轮对话（维护对话历史）
    - 斜杠命令（/help, /memory, /tools 等）
    - Ctrl+C 中断当前请求
    - 美观的终端输出（ANSI 颜色、分隔线）
    - asyncio 运行，兼容 Windows
    - MockLLM 演示模式（--mock，无需 API key）

使用方式:
    # 直接运行
    python -m suyi.cli --mock

    # 在代码中调用
    import asyncio
    from suyi.cli import run_repl
    asyncio.run(run_repl())
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from . import formatter as fmt
from .formatter import (
    colorize, cyan, green, yellow, red, bold, dim, magenta, blue,
    Color, print_separator, print_title, print_banner,
    info, success, warning, error, user_prompt, thinking_indicator,
    format_tool_call, format_key_value, format_list_item,
)
from .commands import (
    CommandResult, dispatch_command, is_command, list_commands,
)

if TYPE_CHECKING:
    from ..core.loop import AgentLoop, LLMInterface, LoopResult, Tool
    from ..memory import MemoryManager
    from ..middleware import get_default_middleware
    from ..tools import AgentTool
    from ..skills import SkillLoader
    from ..evolution import InteractionRecord


# ═══════════════════════════════════════════════════════════════
#  REPL 上下文
# ═══════════════════════════════════════════════════════════════

@dataclass
class REPLContext:
    """REPL 运行时上下文，在斜杠命令之间共享状态.

    Attributes:
        agent_loop: AgentLoop 实例（核心 ReAct 循环）.
        llm: LLM 接口实例（MockLLM 或真实 LLM）.
        memory_manager: 记忆管理器实例.
        tools: 已注册工具列表.
        middleware: 中间件链.
        skill_loader: 技能加载器实例.
        config: 配置字典.
        conversation_history: 对话历史（user/assistant 消息列表）.
        turn_count: 当前对话轮数.
        interaction_records: 交互记录列表（用于自进化）.
    """
    agent_loop: Optional[Any] = None
    llm: Optional[Any] = None
    memory_manager: Optional[Any] = None
    tools: Optional[List[Any]] = None
    middleware: Optional[List[Any]] = None
    skill_loader: Optional[Any] = None
    config: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    interaction_records: List[Any] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  异步输入（兼容 Windows）
# ═══════════════════════════════════════════════════════════════

async def ainput(prompt: str = "") -> str:
    """异步读取用户输入.

    在线程池中执行阻塞的 ``input()``，避免阻塞事件循环.
    兼容 Windows 和 Unix.

    Args:
        prompt: 输入提示符.

    Returns:
        用户输入的字符串（已去除首尾空白）.
    """
    loop = asyncio.get_event_loop()
    # 使用 run_in_executor 在线程中执行阻塞的 input()
    result = await loop.run_in_executor(None, input, prompt)
    return result.strip()


# ═══════════════════════════════════════════════════════════════
#  Agent 初始化
# ═══════════════════════════════════════════════════════════════

def _create_mock_responses() -> List[Any]:
    """创建 MockLLM 的演示响应脚本.

    Returns:
        LLMResponse 列表，模拟一个会使用工具的 Agent.
    """
    from ..core import LLMResponse

    return [
        # 第一轮：使用搜索工具
        LLMResponse.action(
            "search",
            {"query": "Python asyncio tutorial"},
            content="我需要搜索一下相关信息.",
        ),
        # 第二轮：基于搜索结果回答
        LLMResponse.text(
            "根据搜索结果，Python asyncio 是用于编写并发代码的库，"
            "使用 async/await 语法。它提供了事件循环、协程、任务和 futures "
            "等核心概念，适合 I/O 密集型应用。"
        ),
        # 后续轮次：通用回答
        LLMResponse.text(
            "这是一个很好的问题！让我基于已有知识来回答。\n\n"
            "（注意：当前运行在 Mock 模式，此回答为预设的演示文本。"
            "使用真实 LLM 可获得更智能的回复。）"
        ),
    ]


def adapt_agent_tool(agent_tool: Any) -> Any:
    """将 AgentTool（来自 suyi.tools）适配为 Tool（来自 suyi.core.loop）.

    AgentTool 使用 ``execute(input_data, context) -> ToolResult`` 接口,
    而 AgentLoop 期望 ``Tool`` 接口（``async run(**kwargs) -> str``）.
    本适配器桥接两者差异.

    Args:
        agent_tool: AgentTool 实例.

    Returns:
        兼容 Tool 接口的适配器实例.
    """
    from ..core.loop import Tool
    from ..tools.base import ToolContext, ToolResult
    import json

    class _ToolAdapter(Tool):
        """AgentTool → Tool 适配器."""

        def __init__(self, atool: Any):
            self.name = atool.name
            self.description = atool.description
            self.default_permission = atool.default_permission
            self._agent_tool = atool
            # 构建 parameters dict 从 ToolParameter 列表
            params = atool.parameters or []
            self.parameters = {
                "type": "object",
                "properties": {
                    p.name: {"type": p.type, "description": p.description}
                    for p in params
                },
                "required": [p.name for p in params if p.required],
            }

        async def run(self, **kwargs) -> str:
            """执行工具，返回字符串结果."""
            ctx = ToolContext()
            result = self._agent_tool.execute(kwargs, ctx)
            # 处理 ToolResult
            if isinstance(result, ToolResult):
                if result.success:
                    output = result.output
                    if isinstance(output, (list, dict)):
                        return json.dumps(output, ensure_ascii=False)
                    return str(output) if output else ""
                else:
                    return f"Error: {result.error}"
            # 直接返回字符串
            return str(result)

        def assess_risk(self, arguments: dict) -> Optional[str]:
            """运行时风险评估（委托给 AgentTool）."""
            ctx = ToolContext()
            return self._agent_tool.assess_risk(arguments, ctx)

    return _ToolAdapter(agent_tool)


def build_context(
    config_path: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    mock: bool = False,
    skills_dir: str = "skills",
) -> REPLContext:
    """构建 REPL 上下文.

    根据参数初始化 MemoryManager、AgentLoop、工具和中间件.
    在 mock 模式下使用 MockLLM，无需 API key.

    Args:
        config_path: 配置文件路径（可选）.
        provider: LLM 提供商（可选）.
        model: 模型名称（可选）.
        mock: 是否使用 MockLLM 演示模式.
        skills_dir: 技能库目录.

    Returns:
        初始化好的 REPLContext.
    """
    from .. import (
        MemoryManager, AgentLoop, MockLLM, LLMResponse,
        get_builtin_tools, get_default_middleware,
    )

    # 配置字典
    config: Dict[str, Any] = {
        "mock": mock,
        "provider": provider or "default",
        "model": model or "default",
        "config_path": config_path or "N/A",
        "skills_dir": skills_dir,
    }

    # 记忆管理器（使用临时目录避免污染）
    import tempfile
    memory_manager = MemoryManager(
        storage_dir=tempfile.mkdtemp(prefix="suyi_repl_"),
    )

    # 工具 — 将 AgentTool 适配为 AgentLoop 兼容的 Tool 接口
    raw_tools = get_builtin_tools(skills_dir=skills_dir)
    tools = [adapt_agent_tool(t) for t in raw_tools]

    # 中间件
    middleware = get_default_middleware(memory_manager)

    # LLM
    if mock:
        llm = MockLLM(_create_mock_responses())
    else:
        # 非 mock 模式：尝试创建真实 LLM
        # 如果没有真实 LLM 实现，回退到 MockLLM
        llm = MockLLM(_create_mock_responses())
        config["mock"] = True
        config["_fallback_note"] = "未找到真实 LLM 实现，已回退到 Mock 模式"

    # AgentLoop
    agent_loop = AgentLoop(
        llm=llm,
        tools=tools,
        middleware_chain=middleware,
    )

    # 技能加载器（可选）
    skill_loader = None
    try:
        from ..skills import SkillLoader
        skill_loader = SkillLoader(skills_dir)
    except Exception:
        pass

    return REPLContext(
        agent_loop=agent_loop,
        llm=llm,
        memory_manager=memory_manager,
        tools=tools,
        middleware=middleware,
        skill_loader=skill_loader,
        config=config,
    )


# ═══════════════════════════════════════════════════════════════
#  欢迎信息
# ═══════════════════════════════════════════════════════════════

def _print_welcome(ctx: REPLContext) -> None:
    """打印欢迎信息."""
    print()
    print_banner("Suyi Agent — 自进化 AI 框架")
    print()
    mock_status = green("ON") if ctx.config.get("mock") else red("OFF")
    print(f"  {dim('模式:')}      {'MockLLM 演示模式 ' + mock_status if ctx.config.get('mock') else '真实 LLM 模式'}")
    print(f"  {dim('工具数:')}    {len(ctx.tools) if ctx.tools else 0}")
    print(f"  {dim('中间件:')}    {len(ctx.middleware) if ctx.middleware else 0} 层")
    if ctx.skill_loader is not None:
        print(f"  {dim('技能库:')}    已加载")
    else:
        print(f"  {dim('技能库:')}    {dim('未加载')}")
    print()

    # 显示可用命令
    print(bold("可用命令："))
    for name, desc in list_commands():
        print(f"  {yellow(name):<12} {dim(desc)}")
    print()
    print(dim("输入普通文本与 Agent 对话，Ctrl+C 中断当前请求，/quit 退出."))
    print_separator(color=Color.dim)
    print()


# ═══════════════════════════════════════════════════════════════
#  消息处理
# ═══════════════════════════════════════════════════════════════

async def _handle_user_message(ctx: REPLContext, message: str) -> None:
    """处理普通用户消息：调用 AgentLoop 并显示结果.

    Args:
        ctx: REPL 上下文.
        message: 用户消息文本.
    """
    if ctx.agent_loop is None:
        print(error("AgentLoop 未初始化，无法处理消息."))
        return

    # 记录用户消息
    ctx.conversation_history.append({"role": "user", "content": message})
    ctx.turn_count += 1

    # 显示思考中提示
    print(thinking_indicator(), end="", flush=True)
    start_time = time.time()

    try:
        # 调用 AgentLoop
        result = await ctx.agent_loop.run(message)
        elapsed = time.time() - start_time

        # 清除思考提示（用回车覆盖）
        print("\r" + " " * 30 + "\r", end="")

        # 显示工具调用（如果有）
        if hasattr(result, "history") and result.history:
            _display_tool_calls(result.history)

        # 显示最终回答
        print()
        print(bold("Suyi: ") + result.content)
        print()

        # 显示元信息
        meta_parts = []
        meta_parts.append(dim(f"⏱ {elapsed:.1f}s"))
        meta_parts.append(dim(f"🔄 {result.turns_used} 轮"))
        if result.stop_reason != "natural":
            meta_parts.append(yellow(f"⚠ {result.stop_reason}"))
        print("  " + "  ".join(meta_parts))
        print()

        # 记录 assistant 回复
        ctx.conversation_history.append({"role": "assistant", "content": result.content})

        # 记录到 working memory
        if ctx.memory_manager is not None:
            try:
                ctx.memory_manager.add_message("user", message)
                ctx.memory_manager.add_message("assistant", result.content)
            except Exception:
                pass

        # 记录交互（用于自进化）
        _record_interaction(ctx, message, result, elapsed)

    except asyncio.CancelledError:
        # Ctrl+C 中断
        print("\r" + " " * 30 + "\r", end="")
        print(yellow("  ⚡ 请求已中断."))
        print()
        raise  # 重新抛出，让外层处理
    except Exception as e:
        print("\r" + " " * 30 + "\r", end="")
        print(error(f"处理消息时出错: {e}"))
        print()


def _display_tool_calls(history: List[dict]) -> None:
    """从对话历史中提取并显示工具调用.

    Args:
        history: AgentLoop 的对话历史.
    """
    for msg in history:
        if msg.get("role") == "tool":
            tool_name = msg.get("name", "unknown")
            content = msg.get("content", "")
            # 截断过长的工具输出
            if len(content) > 200:
                content = content[:197] + "..."
            print(format_tool_call(tool_name, {}, content, success=True))


def _record_interaction(
    ctx: REPLContext,
    user_message: str,
    result: Any,
    elapsed: float,
) -> None:
    """记录一次交互，用于自进化分析.

    Args:
        ctx: REPL 上下文.
        user_message: 用户消息.
        result: LoopResult.
        elapsed: 耗时（秒）.
    """
    try:
        from ..evolution import InteractionRecord

        # 从历史中提取工具调用
        tool_calls = []
        if hasattr(result, "history"):
            for msg in result.history:
                if msg.get("role") == "tool":
                    tool_calls.append({
                        "name": msg.get("name", "unknown"),
                        "arguments": {},
                        "success": True,
                        "output_summary": str(msg.get("content", ""))[:100],
                    })

        record = InteractionRecord(
            task=user_message,
            tool_calls=tool_calls,
            success=result.is_complete,
            duration=elapsed,
            tokens_used=result.budget_status.tokens_used if result.budget_status else 0,
            tags=["repl"],
        )
        ctx.interaction_records.append(record)
    except ImportError:
        # 自进化模块未安装，静默跳过
        pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  主 REPL 循环
# ═══════════════════════════════════════════════════════════════

async def run_repl(config_path: Optional[str] = None) -> None:
    """启动交互式 REPL.

    Args:
        config_path: 可选的配置文件路径.
    """
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(
        description="Suyi Agent CLI — 交互式对话",
        prog="python -m suyi.cli",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="配置文件路径",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="LLM 提供商",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="模型名称",
    )
    parser.add_argument(
        "--mock", action="store_true", default=False,
        help="使用 MockLLM 演示模式（无需 API key）",
    )
    parser.add_argument(
        "--skills-dir", type=str, default="skills",
        help="技能库目录路径",
    )

    args = parser.parse_args()

    # 使用 config_path 参数或命令行参数
    cfg_path = config_path or args.config

    # 构建上下文
    print(dim("正在初始化 Suyi Agent..."))
    ctx = build_context(
        config_path=cfg_path,
        provider=args.provider,
        model=args.model,
        mock=args.mock,
        skills_dir=args.skills_dir,
    )

    # 如果回退到了 mock 模式，提示用户
    if ctx.config.get("_fallback_note"):
        print(yellow(f"  ⚠ {ctx.config['_fallback_note']}"))

    # 打印欢迎信息
    _print_welcome(ctx)

    # 主循环
    while True:
        try:
            # 读取用户输入
            user_input = await ainput(user_prompt())

            # 空输入跳过
            if not user_input:
                continue

            # 斜杠命令
            if is_command(user_input):
                result = await dispatch_command(user_input, ctx)
                if result.message:
                    print(result.message)
                    print()
                if result.should_quit:
                    break
                continue

            # 普通消息
            await _handle_user_message(ctx, user_input)

        except asyncio.CancelledError:
            # Ctrl+C 在等待输入时 → 询问是否退出
            print()
            try:
                confirm = await ainput(yellow("确定要退出吗？(y/n) "))
                if confirm.lower() in ("y", "yes", ""):
                    print(dim("再见！👋"))
                    break
                else:
                    print(green("继续对话."))
                    print()
            except (EOFError, asyncio.CancelledError):
                print(dim("\n再见！👋"))
                break

        except EOFError:
            # Ctrl+D
            print(dim("\n再见！👋"))
            break

        except KeyboardInterrupt:
            # 额外的 KeyboardInterrupt 保护
            print()
            continue


def run_repl_sync(config_path: Optional[str] = None) -> None:
    """同步启动 REPL（便捷入口）.

    Args:
        config_path: 可选的配置文件路径.
    """
    # Windows 兼容：使用 asyncio.run
    # 如果已有事件循环在运行，使用 create_task
    try:
        loop = asyncio.get_running_loop()
        # 已有事件循环，创建任务
        task = loop.create_task(run_repl(config_path))
        loop.run_until_complete(task)
    except RuntimeError:
        # 没有运行中的事件循环，直接 run
        asyncio.run(run_repl(config_path))


# ═══════════════════════════════════════════════════════════════
#  非交互式模式（用于测试和自动化）
# ═══════════════════════════════════════════════════════════════

async def process_message(
    ctx: REPLContext,
    message: str,
) -> Any:
    """处理单条消息（非交互式，用于测试）.

    Args:
        ctx: REPL 上下文.
        message: 用户消息.

    Returns:
        LoopResult.
    """
    if ctx.agent_loop is None:
        raise RuntimeError("AgentLoop 未初始化.")

    ctx.conversation_history.append({"role": "user", "content": message})
    ctx.turn_count += 1

    result = await ctx.agent_loop.run(message)

    ctx.conversation_history.append({"role": "assistant", "content": result.content})
    _record_interaction(ctx, message, result, 0.0)

    return result
