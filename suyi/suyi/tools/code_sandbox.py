"""代码沙箱工具 — CodeSandboxTool.

安全的 Python 代码执行沙箱，通过 subprocess 在独立进程中执行用户代码.
使用手动 ast 检查过滤危险导入和危险函数调用.

设计原则：
- **纵深防御**：ast 静态检查（拦截危险 import / eval / exec）+ subprocess 隔离.
- **超时保护**：默认 30 秒超时，防止死循环.
- **风险分级**：默认 ``confirm``（执行任意代码有副作用）.

安全策略：
- 禁止导入危险模块：os, subprocess, socket, ctypes, shutil, pickle, marshal,
  importlib, multiprocessing, signal, pty, fcntl, resource, pathlib, tempfile,
  glob, linecache, atexit 等.
- 禁止调用危险函数：__import__, eval, exec, compile, breakpoint,
  getattr, setattr, delattr, globals, locals, vars, dir.
- 禁止访问 dunder 属性（__class__、__bases__、__subclasses__ 等），
  仅放行安全的模块级属性（__name__、__doc__ 等）.
- 禁止以写/追加/独占/更新模式调用 ``open()``（仅允许只读模式）.
- 子进程隔离：用户代码在独立进程中运行，超时自动终止，
  清理环境变量，最小化继承.
"""

import ast
import os
import platform
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
    # P0 加固：新增危险模块
    "pathlib",    # 可替代文件操作
    "tempfile",   # 可创建临时文件后执行
    "glob",       # 文件枚举
    "linecache",  # 可读取任意文件
    "atexit",     # 可注册退出时执行的代码
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
    # P0 加固：反射/内省函数，可用于绕过静态检查
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
}

# 允许访问的 dunder 属性白名单（安全的模块级属性）
# 这些属性通常用于模块元信息，不构成沙箱逃逸风险
_ALLOWED_DUNDER_ATTRS = {
    "__name__",
    "__doc__",
    "__file__",
    "__package__",
    "__loader__",
    "__spec__",
    "__build_class__",
}

# open() 调用中禁止的文件模式字符
# 'w' 写, 'a' 追加, 'x' 独占创建, '+' 更新（读写）
_OPEN_FORBIDDEN_MODE_CHARS = frozenset("wax+")


# ═══════════════════════════════════════════════════════════════
#  AST 检查辅助函数
# ═══════════════════════════════════════════════════════════════


def _is_dunder_attr(attr_name: str) -> bool:
    """判断属性名是否为 dunder 属性（以双下划线开头和结尾）.

    Args:
        attr_name: 属性名字符串.

    Returns:
        如果是 dunder 属性且不在白名单中返回 True.
    """
    if not (attr_name.startswith("__") and attr_name.endswith("__")):
        return False
    return attr_name not in _ALLOWED_DUNDER_ATTRS


def _check_open_call(node: ast.Call) -> Optional[str]:
    """检查 ``open()`` 调用是否使用了危险的文件模式.

    允许只读模式（'r'、'rt'、'rb'），禁止写/追加/独占/更新模式.
    支持位置参数和关键字参数两种传参方式.

    Args:
        node: ast.Call 节点，其 func 为 open 调用.

    Returns:
        拦截原因字符串，如果安全则返回 None.
    """
    # 确定 mode 参数值
    mode_value: Optional[str] = None

    # 检查关键字参数 mode=
    for keyword in node.keywords:
        if keyword.arg == "mode":
            if isinstance(keyword.value, ast.Constant) and isinstance(
                keyword.value.value, str
            ):
                mode_value = keyword.value.value
            break

    # 检查位置参数：open(file, mode, ...)
    if mode_value is None and len(node.args) >= 2:
        second_arg = node.args[1]
        if isinstance(second_arg, ast.Constant) and isinstance(
            second_arg.value, str
        ):
            mode_value = second_arg.value

    # 默认模式为 'r'（只读），无需拦截
    if mode_value is None:
        return None

    # 检查是否包含禁止的模式字符
    for char in mode_value:
        if char in _OPEN_FORBIDDEN_MODE_CHARS:
            return (
                f"禁止以写/追加/更新模式打开文件: open(..., mode='{mode_value}')"
            )

    return None


def check_code_safety(code: str) -> Tuple[bool, str]:
    """静态检查代码安全性.

    通过 ast 解析检查：
    1. 禁止导入的危险模块（import / from ... import）.
    2. 禁止调用的危险函数（eval / exec / compile / __import__ /
       getattr / setattr / globals / locals 等）.
    3. 禁止以写/追加/更新模式调用 ``open()``.
    4. 禁止访问 dunder 属性（__class__、__bases__、__subclasses__ 等），
       防止沙箱逃逸.

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

        # 检查属性访问：禁止 dunder 属性（沙箱逃逸防护）
        elif isinstance(node, ast.Attribute):
            if _is_dunder_attr(node.attr):
                return False, f"禁止访问 dunder 属性: {node.attr}"

        # 检查危险函数调用
        elif isinstance(node, ast.Call):
            func = node.func

            # 直接名称调用：eval()、exec()、getattr() 等
            if isinstance(func, ast.Name) and func.id in DANGEROUS_NAMES:
                return False, f"禁止调用函数: {func.id}"

            # 属性调用：xxx.__import__() 等
            if isinstance(func, ast.Attribute):
                # 检查 __import__ 属性调用（如 builtins.__import__）
                if func.attr == "__import__":
                    return False, "禁止调用 __import__"
                # getattr/setattr 等通过属性方式调用也拦截
                # （如 builtins.getattr）
                if func.attr in DANGEROUS_NAMES:
                    return False, f"禁止调用函数: {func.attr}"

            # 检查 open() 调用的写模式
            if isinstance(func, ast.Name) and func.id == "open":
                open_reason = _check_open_call(node)
                if open_reason:
                    return False, open_reason
            elif isinstance(func, ast.Attribute) and func.attr == "open":
                # 如 builtins.open()
                open_reason = _check_open_call(node)
                if open_reason:
                    return False, open_reason

    return True, ""


# ═══════════════════════════════════════════════════════════════
#  子进程环境构建
# ═══════════════════════════════════════════════════════════════


def _build_safe_env() -> Dict[str, str]:
    """构建最小化的子进程环境变量字典.

    只保留运行 Python 所必需的环境变量，防止父进程环境变量中的
    敏感信息（如 API_KEY、TOKEN、SECRET 等）泄露到沙箱子进程.

    保留的变量:
        - PATH: 系统可执行文件搜索路径（Python 运行可能需要）
        - PYTHONPATH: Python 模块搜索路径（如果存在）
        - SYSTEMROOT: Windows 系统目录（Windows 平台必需）
        - HOME / USERPROFILE: 用户主目录（某些库需要）
        - TEMP / TMP: 临时目录（某些库需要）
        - LANG / LC_ALL: 区域设置（如果存在）

    Returns:
        最小化的环境变量字典.
    """
    safe_env: Dict[str, str] = {}
    current_env: Dict[str, str] = dict(os.environ)

    # 必需变量
    for key in ("PATH",):
        if key in current_env:
            safe_env[key] = current_env[key]

    # Python 相关
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONIOENCODING"):
        if key in current_env:
            safe_env[key] = current_env[key]

    # 跨平台主目录
    for key in ("HOME", "USERPROFILE"):
        if key in current_env:
            safe_env[key] = current_env[key]

    # 临时目录
    for key in ("TEMP", "TMP", "TMPDIR"):
        if key in current_env:
            safe_env[key] = current_env[key]

    # 区域设置
    for key in ("LANG", "LC_ALL", "LC_CTYPE"):
        if key in current_env:
            safe_env[key] = current_env[key]

    # Windows 特有
    if platform.system() == "Windows":
        for key in ("SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR"):
            if key in current_env:
                safe_env[key] = current_env[key]

    return safe_env


def _get_subprocess_flags() -> int:
    """获取平台相关的子进程创建标志.

    Windows 平台使用 ``CREATE_NO_WINDOW`` 防止弹出控制台窗口，
    以及 ``CREATE_NEW_PROCESS_GROUP`` 以便能正确终止进程组.
    Unix 平台返回 0（无特殊标志）.

    Returns:
        subprocess 标志位整数.
    """
    if platform.system() == "Windows":
        # CREATE_NO_WINDOW = 0x08000000
        # CREATE_NEW_PROCESS_GROUP = 0x00000200
        return 0x08000000 | 0x00000200
    return 0


# ═══════════════════════════════════════════════════════════════
#  CodeSandboxTool
# ═══════════════════════════════════════════════════════════════


class CodeSandboxTool(AgentTool):
    """Python 代码执行沙箱.

    在独立子进程中安全执行 Python 代码，通过 ast 静态检查拦截危险导入
    和危险函数调用.

    **安全策略**：
    - ast 检查：拦截 os / subprocess / socket 等危险模块导入，
      拦截 eval / exec / compile / __import__ / getattr 等危险函数调用，
      拦截 dunder 属性访问（沙箱逃逸），拦截写模式 open().
    - subprocess 隔离：代码在独立进程中执行，超时自动终止，
      环境变量最小化清理，Windows 平台无窗口创建.

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
            "Dangerous imports (os, subprocess, socket, etc.), "
            "dangerous calls (eval, exec, getattr, etc.), "
            "dunder attribute access, and write-mode open() are blocked. "
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

        # 构建安全的子进程环境（最小化环境变量，防止泄露）
        safe_env: Dict[str, str] = _build_safe_env()
        # 获取平台相关的创建标志
        creation_flags: int = _get_subprocess_flags()

        # 在子进程中执行
        start = time.perf_counter()
        try:
            # 构建 subprocess.run 参数
            run_kwargs: Dict[str, Any] = {
                "args": [sys.executable, "-c", code],
                "capture_output": True,
                "text": True,
                "timeout": timeout,
                "env": safe_env,
            }
            # Windows 平台传入 creationflags
            if creation_flags:
                run_kwargs["creationflags"] = creation_flags

            result = subprocess.run(**run_kwargs)
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
