"""Suyi 工具系统模块.

导出工具基类、权限管理器、内置工具和工具函数.
"""

from .base import (
    AgentTool,
    ToolContext,
    ToolParameter,
    ToolResult,
)
from .permissions import (
    PermissionManager,
    SecurityClassifier,
    ClassifierInput,
    ClassifierResult,
    PERMISSION_AUTO,
    PERMISSION_CONFIRM,
    PERMISSION_BLOCK,
)
from .builtin import (
    BashTool,
    ReadFileTool,
    WriteFileTool,
    SearchTool,
    SkillTool,
    get_builtin_tools,
)

__all__ = [
    # 基类
    "AgentTool",
    "ToolContext",
    "ToolParameter",
    "ToolResult",
    # 权限
    "PermissionManager",
    "SecurityClassifier",
    "ClassifierInput",
    "ClassifierResult",
    "PERMISSION_AUTO",
    "PERMISSION_CONFIRM",
    "PERMISSION_BLOCK",
    # 内置工具
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchTool",
    "SkillTool",
    "get_builtin_tools",
]
