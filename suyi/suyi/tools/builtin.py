"""内置工具 — BashTool / ReadFileTool / WriteFileTool / SearchTool / SkillTool.

每个工具自描述风险画像（default_permission + assess_risk），
权限内聚在工具自身，不依赖外部配置表.
"""

import os
import subprocess
from typing import Any, Dict, List, Optional

from .base import AgentTool, ToolContext, ToolParameter, ToolResult


# ═══════════════════════════════════════════════════════════════
#  BashTool — 命令执行工具
# ═══════════════════════════════════════════════════════════════


class BashTool(AgentTool):
    """Bash 命令执行工具.

    执行 shell 命令，``assess_risk`` 根据命令内容动态调整风险级别.

    **风险分级**：
    - SAFE_PREFIXES 中的命令前缀 → ``'auto'``（如 ``ls``, ``cat``, ``git status``）.
    - DANGEROUS 中的危险模式 → ``'block'``（如 ``rm -rf``, ``mkfs``）.
    - 其他命令 → ``None``（回退到 ``default_permission = 'confirm'``）.

    **命令级签名**：
    ``get_signature_key`` 提取命令前缀作为签名键.
    对于 ``git`` 命令，包含子命令（如 ``git status``）.
    对于其他命令，仅取第一个词（如 ``ls``）.

    Attributes:
        SAFE_PREFIXES: 安全命令前缀列表.
        DANGEROUS: 危险命令模式列表.
    """

    SAFE_PREFIXES: List[str] = [
        "ls",
        "cat",
        "echo",
        "pwd",
        "git status",
        "git diff",
        "git log",
        "git branch",
        "head",
        "tail",
        "wc",
        "find",
        "grep",
    ]

    DANGEROUS: List[str] = [
        "rm -rf",
        "rm -fr",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",
        "> /dev/sda",
        "chmod 777",
        "shutdown",
        "reboot",
        "halt",
        "kill -9",
    ]

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command. Use for file operations, "
            "git commands, and other shell tasks. "
            "Input: {'command': str, 'timeout': int (optional, default 60)}"
        )

    @property
    def default_permission(self) -> str:
        return "confirm"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to execute.",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds (default: 60).",
                required=False,
                default=60,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """执行 bash 命令.

        Args:
            input_data: 包含 ``command``（必填）和 ``timeout``（可选）.
            context: 执行上下文，``working_dir`` 指定工作目录.

        Returns:
            执行结果，``output`` 为 stdout + stderr.
        """
        command = input_data.get("command", "")
        timeout = input_data.get("timeout", 60)

        if not command:
            return ToolResult(success=False, error="No command provided")

        try:
            cwd = context.working_dir if context.working_dir else None
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

            output = result.stdout
            if result.stderr:
                output = output + "\n" + result.stderr if output else result.stderr

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {result.returncode}",
                )

            return ToolResult(success=True, output=output.strip())

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def assess_risk(self, input_data: dict, context: ToolContext) -> Optional[str]:
        """运行时风险评估.

        - DANGEROUS 模式匹配 → ``'block'``（硬限制）.
        - SAFE_PREFIXES 匹配 → ``'auto'``（安全）.
        - 其他 → ``None``（回退到 ``default_permission = 'confirm'``）.

        Args:
            input_data: 包含 ``command`` 字段.
            context: 执行上下文.

        Returns:
            风险级别字符串或 ``None``.
        """
        command = input_data.get("command", "").strip()
        if not command:
            return None

        # 检查危险模式
        for pattern in self.DANGEROUS:
            if pattern in command:
                return "block"

        # 检查安全前缀
        for prefix in self.SAFE_PREFIXES:
            if command.startswith(prefix):
                return "auto"

        return None

    def get_signature_key(self, input_data: dict) -> str:
        """提取命令级签名键.

        对于 ``git`` 命令，返回 ``git <subcommand>``（如 ``git status``）.
        对于其他命令，返回第一个词（如 ``ls``）.

        Examples:
            >>> tool = BashTool()
            >>> tool.get_signature_key({"command": "git status"})
            'git status'
            >>> tool.get_signature_key({"command": "ls -la"})
            'ls'
            >>> tool.get_signature_key({"command": "rm -rf /"})
            'rm'
        """
        command = input_data.get("command", "").strip()
        if not command:
            return ""

        parts = command.split()
        if not parts:
            return ""

        # git 子命令需要更细粒度
        if parts[0] == "git" and len(parts) > 1:
            return f"{parts[0]} {parts[1]}"

        return parts[0]


# ═══════════════════════════════════════════════════════════════
#  ReadFileTool — 文件读取工具
# ═══════════════════════════════════════════════════════════════


class ReadFileTool(AgentTool):
    """文件读取工具.

    只读操作，``default_permission = 'auto'``.
    支持分页读取大文件.
    """

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the content of a file. "
            "Input: {'path': str, 'offset': int (optional), 'limit': int (optional)}"
        )

    @property
    def default_permission(self) -> str:
        return "auto"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to read.",
                required=True,
            ),
            ToolParameter(
                name="offset",
                type="integer",
                description="Line number to start reading from (1-based). Default: 1.",
                required=False,
                default=1,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of lines to read. Default: all.",
                required=False,
                default=None,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """读取文件内容.

        Args:
            input_data: 包含 ``path``（必填）、``offset`` 和 ``limit``（可选）.
            context: 执行上下文.

        Returns:
            文件内容字符串.
        """
        path = input_data.get("path", "")
        offset = input_data.get("offset", 1)
        limit = input_data.get("limit", None)

        if not path:
            return ToolResult(success=False, error="No file path provided")

        # 解析路径（支持相对路径基于 working_dir）
        if context.working_dir and not os.path.isabs(path):
            path = os.path.join(context.working_dir, path)

        try:
            if not os.path.exists(path):
                return ToolResult(success=False, error=f"File not found: {path}")
            if not os.path.isfile(path):
                return ToolResult(success=False, error=f"Not a file: {path}")

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # 分页
            start = max(0, offset - 1)
            if limit is not None:
                lines = lines[start: start + limit]
            else:
                lines = lines[start:]

            content = "".join(lines)
            return ToolResult(success=True, output=content)

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_signature_key(self, input_data: dict) -> str:
        """文件路径作为签名键."""
        path = input_data.get("path", "")
        if not path:
            return ""
        # 归一化路径用于签名
        return os.path.normpath(path)


# ═══════════════════════════════════════════════════════════════
#  WriteFileTool — 文件写入工具
# ═══════════════════════════════════════════════════════════════


class WriteFileTool(AgentTool):
    """文件写入工具.

    有副作用操作，``default_permission = 'confirm'``.
    """

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. Overwrites existing content. "
            "Input: {'path': str, 'content': str, 'append': bool (optional)}"
        )

    @property
    def default_permission(self) -> str:
        return "confirm"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to write.",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write to the file.",
                required=True,
            ),
            ToolParameter(
                name="append",
                type="boolean",
                description="If true, append to file instead of overwriting. Default: false.",
                required=False,
                default=False,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """写入文件.

        Args:
            input_data: 包含 ``path``、``content``（必填）和 ``append``（可选）.
            context: 执行上下文.

        Returns:
            写入结果.
        """
        path = input_data.get("path", "")
        content = input_data.get("content", "")
        append = input_data.get("append", False)

        if not path:
            return ToolResult(success=False, error="No file path provided")

        # 解析路径
        if context.working_dir and not os.path.isabs(path):
            path = os.path.join(context.working_dir, path)

        try:
            # 确保目录存在
            dir_path = os.path.dirname(path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"File written: {path} ({len(content)} chars)",
            )

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_signature_key(self, input_data: dict) -> str:
        """文件路径作为签名键."""
        path = input_data.get("path", "")
        if not path:
            return ""
        return os.path.normpath(path)


# ═══════════════════════════════════════════════════════════════
#  SearchTool — 搜索工具（可 mock）
# ═══════════════════════════════════════════════════════════════


class SearchTool(AgentTool):
    """搜索工具（可 mock）.

    只读操作，``default_permission = 'auto'``.

    当 ``search_fn`` 未提供时，返回 mock 结果，
    便于测试和无网络环境下的开发.
    """

    def __init__(self, search_fn=None):
        """
        Args:
            search_fn: 自定义搜索函数，签名为 ``fn(query: str) -> list[dict]``.
                未提供时使用内置 mock.
        """
        self._search_fn = search_fn

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search the web or knowledge base for information. "
            "Input: {'query': str, 'max_results': int (optional, default 5)}"
        )

    @property
    def default_permission(self) -> str:
        return "auto"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query string.",
                required=True,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results. Default: 5.",
                required=False,
                default=5,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """执行搜索.

        Args:
            input_data: 包含 ``query``（必填）和 ``max_results``（可选）.
            context: 执行上下文.

        Returns:
            搜索结果列表.
        """
        query = input_data.get("query", "")
        max_results = input_data.get("max_results", 5)

        if not query:
            return ToolResult(success=False, error="No search query provided")

        if self._search_fn:
            try:
                results = self._search_fn(query)
                if isinstance(results, list):
                    results = results[:max_results]
                return ToolResult(success=True, output=results)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        # Mock 模式
        mock_results = [
            {
                "title": f"[Mock] Search result for: {query}",
                "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                "snippet": f"This is a mock search result for the query '{query}'. "
                f"Provide a search_fn to get real results.",
            }
        ]
        return ToolResult(success=True, output=mock_results)

    def get_signature_key(self, input_data: dict) -> str:
        """搜索查询作为签名键（截断以保持合理长度）."""
        query = input_data.get("query", "")
        if not query:
            return ""
        # 截断到 50 字符以避免签名过长
        return query[:50]


# ═══════════════════════════════════════════════════════════════
#  SkillTool — 技能加载工具
# ═══════════════════════════════════════════════════════════════


class SkillTool(AgentTool):
    """技能加载工具.

    按名称加载技能正文（SKILL.md），返回正文内容 + 附件清单.

    遵循渐进式披露原则：
    1. 启动时只挂目录（name + description）.
    2. 本工具按需读取正文.
    3. 附件（scripts/, references/）通过 ReadFileTool 按需读取.

    只读操作，``default_permission = 'auto'``.

    Attributes:
        skills_dir: 技能库根目录路径.
    """

    def __init__(self, skills_dir: str = "skills"):
        """
        Args:
            skills_dir: 技能库根目录路径.
        """
        self.skills_dir = skills_dir

    @property
    def name(self) -> str:
        return "skill"

    @property
    def description(self) -> str:
        return (
            "Load a skill's content (SKILL.md) by name. "
            "Returns the skill body text and a list of attachments "
            "(scripts/ and references/ files). "
            "Input: {'skill_name': str}"
        )

    @property
    def default_permission(self) -> str:
        return "auto"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="skill_name",
                type="string",
                description="Name of the skill to load.",
                required=True,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """加载技能正文.

        Args:
            input_data: 包含 ``skill_name``（必填）.
            context: 执行上下文.

        Returns:
            包含 ``content``（正文）和 ``attachments``（附件清单）的字典.
        """
        skill_name = input_data.get("skill_name", "")
        if not skill_name:
            return ToolResult(success=False, error="No skill name provided")

        # 解析技能目录路径
        skill_dir = os.path.join(self.skills_dir, skill_name)
        if context.working_dir and not os.path.isabs(skill_dir):
            skill_dir = os.path.join(context.working_dir, skill_dir)

        skill_md_path = os.path.join(skill_dir, "SKILL.md")

        try:
            if not os.path.exists(skill_md_path):
                return ToolResult(
                    success=False,
                    error=f"Skill not found: {skill_name} "
                    f"(looked for: {skill_md_path})",
                )

            # 读取正文
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 收集附件清单
            attachments = self._list_attachments(skill_dir)

            return ToolResult(
                success=True,
                output={
                    "content": content,
                    "attachments": attachments,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _list_attachments(self, skill_dir: str) -> List[Dict[str, str]]:
        """列出技能目录下的附件文件.

        扫描 ``scripts/`` 和 ``references/`` 子目录.

        Args:
            skill_dir: 技能目录路径.

        Returns:
            附件信息列表，每项包含 ``path`` 和 ``type``.
        """
        attachments = []
        subdirs = ["scripts", "references"]

        for subdir in subdirs:
            subdir_path = os.path.join(skill_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue

            for root, _dirs, files in os.walk(subdir_path):
                for filename in sorted(files):
                    file_path = os.path.relpath(
                        os.path.join(root, filename), skill_dir
                    )
                    attachments.append({
                        "path": file_path,
                        "type": subdir,
                    })

        return attachments

    def get_signature_key(self, input_data: dict) -> str:
        """技能名作为签名键."""
        return input_data.get("skill_name", "")


# ═══════════════════════════════════════════════════════════════
#  内置工具注册表
# ═══════════════════════════════════════════════════════════════


def get_builtin_tools(
    skills_dir: str = "skills",
    search_fn=None,
) -> List[AgentTool]:
    """获取所有内置工具实例.

    Args:
        skills_dir: 技能库根目录（用于 SkillTool）.
        search_fn: 自定义搜索函数（用于 SearchTool）.

    Returns:
        内置工具实例列表.
    """
    return [
        BashTool(),
        ReadFileTool(),
        WriteFileTool(),
        SearchTool(search_fn=search_fn),
        SkillTool(skills_dir=skills_dir),
    ]
