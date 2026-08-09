"""代码沙箱工具 — CodeSandboxTool.

安全的 Python 代码执行沙箱，通过 subprocess 在独立进程中执行用户代码.
使用手动 ast 检查过滤危险导入和危险函数调用.

设计原则：
- **纵深防御**：ast 静态检查（拦截危险 import / eval / exec）+ subprocess 隔离.
- **超时保护**：默认 30 秒超时，防止死循环.
- **风险分级**：默认 ``confirm``（执行任意代码有副作用）.

安全策略：
- 禁止导入危险模块：os, subprocess, socket, ctypes, shutil, pickle, marshal,
  importlib, multiprocessing, signal, pty, fcntl, resource.
- 禁止调用危险函数：__import__, eval, exec, compile, breakpoint.
- 子进程隔离：用户代码在独立进程中运行，超时自动终止.
"""

import ast
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import AgentTool, ToolContext, ToolParameter, ToolResult


# ═══════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30

# 禁止导入的模块（根模块名）
BLOCKED_MODULES = {
    "os",
    "subprocess",
    "socket",
    "ctypes",
    "shutil",
    "pickle",
    "marshal",
    "importlib",
    "multiprocessing",
    "signal",
    "pty",
    "fcntl",
    "resource",
    "asyncio",  # 可用于网络操作
    "http",
    "http.client",
    "urllib",
    "xmlrpc",
    "telnetlib",
    "ftplib",
    "smtplib",
    "imaplib",
    "poplib",
    "webbrowser",
}

# 禁止调用的危险函数名
DANGEROUS_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "breakpoint",
    "exit",
    "quit",
}


# ═══════════════════════════════════════════════════════════════
#  代码安全检查
# ═══════════════════════════════════════════════════════════════


def check_code_safety(code: str) -> Tuple[bool, str]:
    """静态检查代码安全性.

    通过 ast 解析检查：
    1. 禁止导入的危险模块（import / from ... import）.
    2. 禁止调用的危险函数（eval / exec / compile / __import__ 等）.

    Args:
        code: 待检查的 Python 代码字符串.

    Returns:
        (is_safe, reason): is_safe=True 表示通过安全检查;
        is_safe=False 时 reason 为拦截原因.
    """
    # 解析 AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"语法错误: {e.msg}（第 {e.lineno} 行）"

    for node in ast.walk(tree):
        # 检查 import 语句
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in BLOCKED_MODULES:
                    return False, f"禁止导入模块: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in BLOCKED_MODULES:
                    return False, f"禁止导入模块: {node.module}"
        # 检查危险函数调用
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in DANGEROUS_NAMES:
                return False, f"禁止调用函数: {func.id}"
            # 检查 __import__ 属性调用（如 builtins.__import__）
            if isinstance(func, ast.Attribute) and func.attr == "__import__":
                return False, "禁止调用 __import__"

    return True, ""


# ═══════════════════════════════════════════════════════════════
#  CodeSandboxTool
# ═══════════════════════════════════════════════════════════════


class CodeSandboxTool(AgentTool):
    """Python 代码执行沙箱.

    在独立子进程中安全执行 Python 代码，通过 ast 静态检查拦截危险导入
    和危险函数调用.

    **安全策略**：
    - ast 检查：拦截 os / subprocess / socket 等危险模块导入，
      拦截 eval / exec / compile / __import__ 等危险函数调用.
    - subprocess 隔离：代码在独立进程中执行，超时自动终止.
    - 不使用 RestrictedPython（不可用），改用手动 ast 检查.

    **风险分级**：
    - 默认 ``'confirm'``（执行任意代码有副作用）.
    - ``assess_risk`` 始终返回 ``None``，回退到默认权限.

    **返回结构**::

        {
            "stdout": "标准输出内容",
            "stderr": "标准错误内容",
            "exit_code": 0,
            "elapsed_ms": 42
        }
    """

    @property
    def name(self) -> str:
        return "code_sandbox"

    @property
    def description(self) -> str:
        return (
            "Execute Python code in a sandboxed subprocess. "
            "Dangerous imports (os, subprocess, socket, etc.) and "
            "dangerous calls (eval, exec, etc.) are blocked. "
            "Input: {'code': str (required), 'timeout': int (default 30)}"
        )

    @property
    def default_permission(self) -> str:
        return "confirm"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="The Python code to execute.",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Execution timeout in seconds. Default: 30.",
                required=False,
                default=DEFAULT_TIMEOUT,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """在沙箱中执行 Python 代码.

        Args:
            input_data: 包含 ``code``（必填）和 ``timeout``（可选）.
            context: 执行上下文.

        Returns:
            包含 ``stdout``、``stderr``、``exit_code``、``elapsed_ms`` 的 ToolResult.
            安全检查失败或超时时返回 success=False.
        """
        code = input_data.get("code", "")
        timeout = input_data.get("timeout", DEFAULT_TIMEOUT)

        # 参数校验
        if not code:
            return ToolResult(success=False, error="未提供代码")

        if not isinstance(code, str):
            return ToolResult(success=False, error="代码必须是字符串")

        if not isinstance(timeout, (int, float)) or timeout <= 0:
            return ToolResult(success=False, error="超时时间必须为正数")

        # 安全检查（ast 静态分析）
        is_safe, reason = check_code_safety(code)
        if not is_safe:
            return ToolResult(
                success=False,
                error=reason,
                output={
                    "stdout": "",
                    "stderr": reason,
                    "exit_code": -1,
                    "elapsed_ms": 0,
                },
            )

        # 在子进程中执行
        start = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            return ToolResult(
                success=(result.returncode == 0),
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "elapsed_ms": elapsed_ms,
                },
                error=(
                    f"代码执行失败（退出码 {result.returncode}）"
                    if result.returncode != 0
                    else None
                ),
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                success=False,
                error=f"代码执行超时（{timeout}s）",
                output={
                    "stdout": "",
                    "stderr": f"TimeoutExpired: 代码执行超过 {timeout}s",
                    "exit_code": -1,
                    "elapsed_ms": elapsed_ms,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"执行异常: {e}")

    def assess_risk(
        self, input_data: dict, context: ToolContext
    ) -> Optional[str]:
        """运行时风险评估.

        代码沙箱始终需要用户确认，返回 ``None`` 回退到
        ``default_permission = 'confirm'``.

        Args:
            input_data: 工具输入参数.
            context: 执行上下文.

        Returns:
            始终返回 ``None``.
        """
        return None

    def get_signature_key(self, input_data: dict) -> str:
        """代码前 50 字符作为签名键.

        用于权限签名，粒度到代码片段级别.

        Args:
            input_data: 包含 ``code`` 字段.

        Returns:
            代码前 50 字符.
        """
        code = input_data.get("code", "")
        if not code:
            return ""
        return code[:50]
