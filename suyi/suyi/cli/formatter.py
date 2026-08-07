"""终端输出格式化 — 纯 ANSI 转义码，不依赖第三方库.

提供颜色输出、分隔线、标题、代码块等格式化功能，
用于 REPL 和示例脚本的终端美化.

ANSI 转义码基础:
    \\033[<code>m  — 设置样式
    \\033[0m       — 重置所有样式

Windows 10+ 支持原生 ANSI，但需要启用虚拟终端处理.
本模块在导入时自动尝试启用.
"""

from __future__ import annotations

import os
import sys
import shutil
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  Windows ANSI 支持
# ═══════════════════════════════════════════════════════════════

def _enable_windows_ansi() -> None:
    """在 Windows 上启用 ANSI 转义码支持.

    Windows 10+ 需要调用 SetConsoleMode 启用虚拟终端处理.
    使用 ctypes 调用 Windows API，失败时静默忽略.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        for handle_id in (-11, -12):  # STD_OUTPUT, STD_ERROR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(
                    handle, mode.value | 0x0004
                )
    except Exception:
        pass


# 模块导入时自动启用
_enable_windows_ansi()


# ═══════════════════════════════════════════════════════════════
#  颜色定义
# ═══════════════════════════════════════════════════════════════

class Color:
    """ANSI 颜色码集合.

    每个属性是一个 ANSI 转义字符串，使用 ``Color.cyan + "text" + Color.reset``
    的方式包裹文本.
    """

    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    italic = "\033[3m"
    underline = "\033[4m"

    # 前景色
    black = "\033[30m"
    red = "\033[31m"
    green = "\033[32m"
    yellow = "\033[33m"
    blue = "\033[34m"
    magenta = "\033[35m"
    cyan = "\033[36m"
    white = "\033[37m"

    # 亮色前景
    bright_red = "\033[91m"
    bright_green = "\033[92m"
    bright_yellow = "\033[93m"
    bright_blue = "\033[94m"
    bright_magenta = "\033[95m"
    bright_cyan = "\033[96m"


# 检测终端是否支持颜色
def _supports_color() -> bool:
    """检测当前终端是否支持 ANSI 颜色.

    - 非 TTY 环境（如管道、重定向）→ False
    - NO_COLOR 环境变量 → False
    - Windows 10+ → True（已通过 _enable_windows_ansi 启用）
    - 其他 Unix → True
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


# 全局颜色开关
_COLOR_ENABLED: bool = _supports_color()


def set_color_enabled(enabled: bool) -> None:
    """手动设置颜色输出开关.

    Args:
        enabled: True 启用颜色，False 禁用.
    """
    global _COLOR_ENABLED
    _COLOR_ENABLED = enabled


def is_color_enabled() -> bool:
    """返回颜色输出是否启用."""
    return _COLOR_ENABLED


# ═══════════════════════════════════════════════════════════════
#  格式化函数
# ═══════════════════════════════════════════════════════════════

def colorize(text: str, *colors: str) -> str:
    """用指定颜色包裹文本.

    Args:
        text: 要着色的文本.
        *colors: 一个或多个 Color 属性，如 ``Color.cyan, Color.bold``.

    Returns:
        着色后的字符串（颜色禁用时返回原文）.

    Example:
        >>> colorize("Hello", Color.green, Color.bold)
        '\\033[1m\\033[32mHello\\033[0m'
    """
    if not _COLOR_ENABLED or not colors:
        return text
    prefix = "".join(colors)
    return f"{prefix}{text}{Color.reset}"


def cyan(text: str) -> str:
    """青色文本."""
    return colorize(text, Color.cyan)


def green(text: str) -> str:
    """绿色文本."""
    return colorize(text, Color.green)


def yellow(text: str) -> str:
    """黄色文本."""
    return colorize(text, Color.yellow)


def red(text: str) -> str:
    """红色文本."""
    return colorize(text, Color.red)


def bold(text: str) -> str:
    """粗体文本."""
    return colorize(text, Color.bold)


def dim(text: str) -> str:
    """暗淡文本."""
    return colorize(text, Color.dim)


def magenta(text: str) -> str:
    """品红文本."""
    return colorize(text, Color.magenta)


def blue(text: str) -> str:
    """蓝色文本."""
    return colorize(text, Color.blue)


# ═══════════════════════════════════════════════════════════════
#  结构化输出
# ═══════════════════════════════════════════════════════════════

def separator(char: str = "─", width: Optional[int] = None) -> str:
    """生成分隔线.

    Args:
        char: 分隔线字符.
        width: 线宽（默认为终端宽度）.

    Returns:
        分隔线字符串.
    """
    if width is None:
        width = shutil.get_terminal_size((80, 24)).columns
    return char * width


def print_separator(char: str = "─", color: Optional[str] = None) -> None:
    """打印分隔线.

    Args:
        char: 分隔线字符.
        color: 可选的颜色（Color 属性）.
    """
    line = separator(char)
    if color:
        line = colorize(line, color)
    print(line)


def title(text: str, color: str = Color.cyan) -> str:
    """格式化标题（带分隔线）.

    Args:
        text: 标题文本.
        color: 标题颜色.

    Returns:
        格式化后的标题字符串.
    """
    width = shutil.get_terminal_size((80, 24)).columns
    line = "─" * width
    return colorize(line, Color.dim) + "\n" + colorize(text, color, Color.bold) + "\n" + colorize(line, Color.dim)


def print_title(text: str, color: str = Color.cyan) -> None:
    """打印格式化标题."""
    print(title(text, color))


def code_block(text: str, language: str = "") -> str:
    """格式化代码块.

    Args:
        text: 代码内容.
        language: 可选的语言标识（显示在头部）.

    Returns:
        格式化后的代码块字符串.
    """
    lines = text.strip("\n").split("\n")
    width = max(len(line) for line in lines) if lines else 0
    width = max(width, len(language) + 4, 40)

    top = "┌" + "─" * (width + 2) + "┐"
    bottom = "└" + "─" * (width + 2) + "┘"

    parts = [colorize(top, Color.dim)]
    if language:
        lang_line = f" {language} "
        padding = width - len(lang_line)
        header = "│ " + lang_line + " " * padding + " │"
        parts.append(colorize(header, Color.dim))

    for line in lines:
        padding = width - len(line)
        # 处理可能的宽字符（简单处理，不精确）
        if padding < 0:
            padding = 0
        row = "│ " + line + " " * padding + " │"
        parts.append(colorize(row, Color.dim))

    parts.append(colorize(bottom, Color.dim))
    return "\n".join(parts)


def print_code_block(text: str, language: str = "") -> None:
    """打印代码块."""
    print(code_block(text, language))


def format_tool_call(
    tool_name: str,
    arguments: dict,
    result: Optional[str] = None,
    success: bool = True,
) -> str:
    """格式化工具调用结果.

    Args:
        tool_name: 工具名称.
        arguments: 调用参数.
        result: 工具返回结果（可选）.
        success: 是否成功.

    Returns:
        格式化后的工具调用信息字符串.
    """
    # 工具名和参数
    args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    status_icon = green("✓") if success else red("✗")
    header = f"  {status_icon} {colorize(tool_name, Color.yellow)}({args_str})"

    parts = [header]
    if result:
        # 截断过长的结果
        result_str = str(result)
        if len(result_str) > 500:
            result_str = result_str[:497] + "..."
        parts.append(f"    {dim('→')} {colorize(result_str, Color.dim)}")

    return "\n".join(parts)


def format_key_value(
    key: str,
    value: Any,
    key_color: str = Color.cyan,
    indent: int = 2,
) -> str:
    """格式化键值对.

    Args:
        key: 键名.
        value: 值.
        key_color: 键的颜色.
        indent: 缩进空格数.

    Returns:
        格式化后的键值对字符串.
    """
    prefix = " " * indent
    return f"{prefix}{colorize(key, key_color)}: {value}"


def format_list_item(
    text: str,
    level: int = 0,
    bullet: str = "•",
    bullet_color: str = Color.cyan,
) -> str:
    """格式化列表项.

    Args:
        text: 列表项文本.
        level: 缩进层级（0=顶层）.
        bullet: 项目符号.
        bullet_color: 项目符号颜色.

    Returns:
        格式化后的列表项字符串.
    """
    indent = "  " * level
    return f"{indent}{colorize(bullet, bullet_color)} {text}"


def banner(text: str, color: str = Color.bright_cyan) -> str:
    """生成横幅文本（居中、带边框）.

    Args:
        text: 横幅文本.
        color: 颜色.

    Returns:
        格式化后的横幅字符串.
    """
    width = shutil.get_terminal_size((80, 24)).columns
    text_len = len(text)
    if text_len + 4 > width:
        # 文本太长，不居中
        return colorize(text, color, Color.bold)

    total_padding = width - text_len - 4
    left_pad = total_padding // 2
    right_pad = total_padding - left_pad

    top = "╔" + "═" * (width - 2) + "╗"
    middle = "║" + " " * left_pad + colorize(text, color, Color.bold) + " " * right_pad + "║"
    bottom = "╚" + "═" * (width - 2) + "╝"

    return colorize(top, Color.dim) + "\n" + middle + "\n" + colorize(bottom, Color.dim)


def print_banner(text: str, color: str = Color.bright_cyan) -> None:
    """打印横幅."""
    print(banner(text, color))


def info(message: str) -> str:
    """格式化信息消息（蓝色 [INFO] 前缀）."""
    return f"{colorize('[INFO]', Color.blue)} {message}"


def success(message: str) -> str:
    """格式化成功消息（绿色 [OK] 前缀）."""
    return f"{colorize('[OK]', Color.green)} {message}"


def warning(message: str) -> str:
    """格式化警告消息（黄色 [WARN] 前缀）."""
    return f"{colorize('[WARN]', Color.yellow)} {message}"


def error(message: str) -> str:
    """格式化错误消息（红色 [ERROR] 前缀）."""
    return f"{colorize('[ERROR]', Color.red)} {message}"


def user_prompt(prefix: str = "suyi") -> str:
    """生成用户输入提示符.

    Args:
        prefix: 提示符前缀文本.

    Returns:
        带颜色的提示符字符串.
    """
    return colorize(f"{prefix}> ", Color.bright_cyan, Color.bold)


def thinking_indicator() -> str:
    """返回思考中指示器文本."""
    return colorize("  ⠋ thinking...", Color.dim, Color.italic)


def truncate(text: str, max_len: int = 200, suffix: str = "...") -> str:
    """截断过长文本.

    Args:
        text: 原始文本.
        max_len: 最大长度.
        suffix: 截断后缀.

    Returns:
        截断后的文本.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix
