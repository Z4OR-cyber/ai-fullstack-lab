"""斜杠命令处理 — 每个命令一个 async 函数，通过命令注册表分发.

命令列表:
    /help    — 显示帮助
    /memory  — 查看当前记忆
    /tools   — 列出可用工具
    /skills  — 列出已加载技能
    /config  — 显示当前配置
    /clear   — 清空对话历史
    /reset   — 重置 Agent 状态
    /evolve  — 触发自进化
    /quit    — 退出

设计:
    - 每个命令是一个 ``async def cmd_xxx(ctx: REPLContext) -> CommandResult`` 函数.
    - 命令注册表 ``COMMAND_REGISTRY`` 映射命令名 → (函数, 描述).
    - ``CommandResult`` 表示命令执行结果（继续 / 退出 REPL）.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from . import formatter as fmt
from .formatter import (
    colorize, cyan, green, yellow, red, bold, dim, magenta, blue,
    Color, print_separator, print_title, format_key_value, format_list_item,
    info, success, warning, error,
)

if TYPE_CHECKING:
    from .repl import REPLContext


# ═══════════════════════════════════════════════════════════════
#  命令结果
# ═══════════════════════════════════════════════════════════════

@dataclass
class CommandResult:
    """斜杠命令执行结果.

    Attributes:
        should_quit: 是否应该退出 REPL.
        message: 输出消息（已格式化），None 表示无输出.
    """
    should_quit: bool = False
    message: Optional[str] = None

    @classmethod
    def continue_repl(cls, message: Optional[str] = None) -> "CommandResult":
        """继续 REPL（不退出）."""
        return cls(should_quit=False, message=message)

    @classmethod
    def quit_repl(cls, message: Optional[str] = None) -> "CommandResult":
        """退出 REPL."""
        return cls(should_quit=True, message=message)


# ═══════════════════════════════════════════════════════════════
#  命令实现
# ═══════════════════════════════════════════════════════════════

async def cmd_help(ctx: "REPLContext") -> CommandResult:
    """/help — 显示帮助信息."""
    lines = [bold("可用命令："), ""]
    for name, (_, desc) in sorted(COMMAND_REGISTRY.items()):
        lines.append(format_list_item(f"{yellow(name):<12} {dim(desc)}"))
    lines.append("")
    lines.append(dim("输入普通文本与 Agent 对话，Ctrl+C 中断当前请求."))
    return CommandResult.continue_repl("\n".join(lines))


async def cmd_memory(ctx: "REPLContext") -> CommandResult:
    """/memory — 查看当前记忆系统状态."""
    mgr = ctx.memory_manager
    if mgr is None:
        return CommandResult.continue_repl(warning("记忆系统未初始化."))

    status = mgr.get_status()

    lines = [bold("记忆系统状态"), ""]

    # Working memory
    wm = status.get("working", {})
    lines.append(cyan("Working Memory"))
    lines.append(format_key_value("消息数", wm.get("messages", 0)))
    lines.append(format_key_value("对话轮次", wm.get("turn_count", 0)))
    budget = wm.get("budget", {})
    lines.append(format_key_value("Token 预算", f"{budget.get('used', 0)}/{budget.get('limit', 0)}"))
    lines.append("")

    # Episodic memory
    em = status.get("episodic", {})
    lines.append(cyan("Episodic Memory"))
    lines.append(format_key_value("片段数", em.get("episodes", 0)))
    lines.append(format_key_value("会话数", em.get("sessions", 0)))
    lines.append("")

    # Semantic memory
    sm = status.get("semantic", {})
    lines.append(cyan("Semantic Memory"))
    lines.append(format_key_value("知识条目", sm.get("entries", 0)))
    lines.append(format_key_value("词汇表大小", sm.get("vocabulary", 0)))
    lines.append("")

    # Lifecycle
    lc = status.get("lifecycle", {})
    lines.append(cyan("Lifecycle"))
    lines.append(format_key_value("巩固阈值", lc.get("consolidate_threshold", "N/A")))
    lines.append(format_key_value("遗忘阈值", lc.get("forget_threshold", "N/A")))

    return CommandResult.continue_repl("\n".join(lines))


async def cmd_tools(ctx: "REPLContext") -> CommandResult:
    """/tools — 列出可用工具."""
    tools = ctx.tools or []
    if not tools:
        return CommandResult.continue_repl(warning("没有注册任何工具."))

    lines = [bold(f"已注册工具（{len(tools)} 个）"), ""]
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        desc = getattr(tool, "description", "")
        # 截断描述
        if len(desc) > 60:
            desc = desc[:57] + "..."
        perm = getattr(tool, "default_permission", "auto")
        perm_color = Color.green if perm == "auto" else (Color.yellow if perm == "confirm" else Color.red)
        perm_str = colorize(f"[{perm}]", perm_color)
        lines.append(f"  {yellow(name):<16} {perm_str} {dim(desc)}")

    return CommandResult.continue_repl("\n".join(lines))


async def cmd_skills(ctx: "REPLContext") -> CommandResult:
    """/skills — 列出已加载技能."""
    skill_loader = ctx.skill_loader
    if skill_loader is None:
        return CommandResult.continue_repl(warning("技能加载器未初始化."))

    # 尝试获取技能菜单
    try:
        from ..skills import SkillMenu
        menu = SkillMenu()
        menu_text = menu.generate(skill_loader)
        lines = [bold("已加载技能"), "", menu_text]
    except Exception:
        # 降级：直接列出技能元数据
        try:
            skills = skill_loader.list_skills()
            lines = [bold(f"已加载技能（{len(skills)} 个）"), ""]
            for sk in skills:
                name = getattr(sk, "name", str(sk))
                desc = getattr(sk, "description", "")
                lines.append(f"  {yellow(name):<20} {dim(desc)}")
            if not skills:
                lines.append(dim("  （无技能）"))
        except Exception as e:
            lines = [error(f"无法加载技能列表: {e}")]

    return CommandResult.continue_repl("\n".join(lines))


async def cmd_config(ctx: "REPLContext") -> CommandResult:
    """/config — 显示当前配置."""
    config = ctx.config or {}
    lines = [bold("当前配置"), ""]

    # 基本配置
    lines.append(cyan("基本配置"))
    lines.append(format_key_value("Mock 模式", green("ON") if config.get("mock") else red("OFF")))
    lines.append(format_key_value("Provider", config.get("provider", "default")))
    lines.append(format_key_value("Model", config.get("model", "default")))
    lines.append(format_key_value("Config 路径", config.get("config_path", "N/A")))
    lines.append("")

    # Agent 状态
    lines.append(cyan("Agent 状态"))
    lines.append(format_key_value("对话轮数", ctx.turn_count))
    lines.append(format_key_value("历史消息数", len(ctx.conversation_history)))
    lines.append(format_key_value("工具数", len(ctx.tools) if ctx.tools else 0))
    lines.append(format_key_value("中间件数", len(ctx.middleware) if ctx.middleware else 0))

    return CommandResult.continue_repl("\n".join(lines))


async def cmd_clear(ctx: "REPLContext") -> CommandResult:
    """/clear — 清空对话历史."""
    count = len(ctx.conversation_history)
    ctx.conversation_history.clear()

    # 同时清空 working memory 中的消息
    if ctx.memory_manager is not None:
        try:
            ctx.memory_manager.working.clear()
        except Exception:
            pass

    return CommandResult.continue_repl(
        success(f"已清空 {count} 条对话历史.")
    )


async def cmd_reset(ctx: "REPLContext") -> CommandResult:
    """/reset — 重置 Agent 状态."""
    # 清空对话历史
    ctx.conversation_history.clear()
    ctx.turn_count = 0
    ctx.interaction_records.clear()

    # 重置 AgentLoop 的 budget tracker
    if ctx.agent_loop is not None:
        try:
            ctx.agent_loop.budget_tracker.reset()
        except Exception:
            pass

    # 重置 MockLLM 的脚本索引（如果有）
    if ctx.llm is not None:
        reset_fn = getattr(ctx.llm, "reset", None)
        if callable(reset_fn):
            reset_fn()

    # 清空 working memory
    if ctx.memory_manager is not None:
        try:
            ctx.memory_manager.working.clear()
        except Exception:
            pass

    return CommandResult.continue_repl(
        success("Agent 状态已重置（对话历史、预算、MockLLM 脚本已清除）.")
    )


async def cmd_evolve(ctx: "REPLContext") -> CommandResult:
    """/evolve — 触发自进化."""
    records = ctx.interaction_records
    if len(records) < 3:
        return CommandResult.continue_repl(
            warning(
                f"交互记录不足（当前 {len(records)} 条），"
                f"至少需要 3 条才能触发进化分析. "
                f"请多与 Agent 对话后重试."
            )
        )

    lines = [bold("触发自进化分析..."), ""]

    try:
        from ..evolution import (
            EvolutionOrchestrator,
            InteractionRecord,
        )
        import tempfile

        # 使用临时目录避免污染
        storage_dir = tempfile.mkdtemp(prefix="suyi_evolve_")
        orchestrator = EvolutionOrchestrator(storage_dir=storage_dir)

        # 记录交互
        for record in records:
            orchestrator.record_interaction(record)

        lines.append(f"  {dim('已加载')} {len(records)} {dim('条交互记录')}")
        lines.append(f"  {dim('运行进化循环...')}")

        # 运行进化循环
        result = orchestrator.run_evolution_cycle()

        lines.append("")
        lines.append(green("进化循环完成！"))
        lines.append("")

        # 模式提取结果
        lines.append(cyan("模式提取"))
        lines.append(format_key_value("提取模式数", result.patterns_extracted))
        lines.append(format_key_value("策略版本", result.policy_version))
        lines.append("")

        # 技能生成
        lines.append(cyan("技能生成"))
        lines.append(format_key_value("生成技能数", len(result.skills_generated)))
        lines.append(format_key_value("激活技能数", result.skills_activated))
        lines.append("")

        # 评估报告
        if result.evaluation_report:
            report = result.evaluation_report
            metrics = report.metrics
            lines.append(cyan("评估报告"))
            lines.append(format_key_value("综合分数", f"{metrics.overall_score:.2%}"))
            lines.append(format_key_value("完成率", f"{metrics.completion_rate:.2%}"))
            lines.append(format_key_value("效率分数", f"{metrics.efficiency_score:.2%}"))
            lines.append(format_key_value("质量分数", f"{metrics.quality_score:.2%}"))
            lines.append(format_key_value("满意度", f"{metrics.user_satisfaction:.2%}"))
            lines.append("")

            # 改进建议
            if report.recommendations:
                lines.append(cyan("改进建议"))
                for i, rec_text in enumerate(report.recommendations, 1):
                    lines.append(f"  {yellow(str(i))}. {rec_text}")
        lines.append("")

        # 反馈统计
        if result.feedback_stats:
            lines.append(cyan("反馈统计"))
            fb = result.feedback_stats
            lines.append(format_key_value("总反馈数", fb.get("total_feedbacks", 0)))
            lines.append(format_key_value("正面反馈", fb.get("positive", 0)))
            lines.append(format_key_value("负面反馈", fb.get("negative", 0)))
            avg_signal = fb.get("average_signal", 0.0)
            signal_color = Color.green if avg_signal > 0 else (Color.red if avg_signal < 0 else Color.yellow)
            lines.append(format_key_value(
                "平均信号",
                colorize(f"{avg_signal:+.3f}", signal_color),
            ))

        lines.append("")
        lines.append(dim(f"耗时: {result.duration:.2f}s"))

    except ImportError:
        lines.append(error("自进化模块未安装."))
    except Exception as e:
        lines.append(error(f"进化循环出错: {e}"))

    return CommandResult.continue_repl("\n".join(lines))


async def cmd_quit(ctx: "REPLContext") -> CommandResult:
    """/quit — 退出 REPL."""
    return CommandResult.quit_repl(
        dim("再见！👋")
    )


# ═══════════════════════════════════════════════════════════════
#  命令注册表
# ═══════════════════════════════════════════════════════════════

# 命令名 → (处理函数, 描述)
COMMAND_REGISTRY: Dict[str, tuple[Callable, str]] = {
    "/help":   (cmd_help,   "显示可用命令"),
    "/memory": (cmd_memory, "查看记忆系统状态"),
    "/tools":  (cmd_tools,  "列出可用工具"),
    "/skills": (cmd_skills, "列出已加载技能"),
    "/config": (cmd_config, "显示当前配置"),
    "/clear":  (cmd_clear,  "清空对话历史"),
    "/reset":  (cmd_reset,  "重置 Agent 状态"),
    "/evolve": (cmd_evolve, "触发自进化分析"),
    "/quit":   (cmd_quit,   "退出 REPL"),
}

# 简写别名
COMMAND_ALIASES: Dict[str, str] = {
    "/h": "/help",
    "/m": "/memory",
    "/t": "/tools",
    "/s": "/skills",
    "/c": "/config",
    "/q": "/quit",
    "/exit": "/quit",
}


def get_command(name: str) -> Optional[Callable]:
    """获取命令处理函数.

    支持全名和别名查找.

    Args:
        name: 命令名（如 "/help" 或 "/h"）.

    Returns:
        命令处理函数，未找到返回 None.
    """
    # 先查别名
    resolved = COMMAND_ALIASES.get(name, name)
    entry = COMMAND_REGISTRY.get(resolved)
    if entry:
        return entry[0]
    return None


def get_command_description(name: str) -> Optional[str]:
    """获取命令描述."""
    resolved = COMMAND_ALIASES.get(name, name)
    entry = COMMAND_REGISTRY.get(resolved)
    if entry:
        return entry[1]
    return None


def list_commands() -> List[tuple[str, str]]:
    """返回所有命令（名, 描述）列表."""
    return [(name, desc) for name, (_, desc) in sorted(COMMAND_REGISTRY.items())]


def is_command(input_str: str) -> bool:
    """判断输入是否为斜杠命令."""
    return input_str.strip().startswith("/")


async def dispatch_command(
    input_str: str,
    ctx: "REPLContext",
) -> CommandResult:
    """分发斜杠命令.

    Args:
        input_str: 用户输入（以 / 开头）.
        ctx: REPL 上下文.

    Returns:
        命令执行结果.
    """
    parts = input_str.strip().split(maxsplit=1)
    cmd_name = parts[0].lower()

    handler = get_command(cmd_name)
    if handler is None:
        available = ", ".join(sorted(COMMAND_REGISTRY.keys()))
        return CommandResult.continue_repl(
            error(f"未知命令: {cmd_name}\n可用命令: {available}")
        )

    try:
        result = await handler(ctx)
        return result
    except Exception as e:
        return CommandResult.continue_repl(
            error(f"命令执行出错: {e}")
        )
