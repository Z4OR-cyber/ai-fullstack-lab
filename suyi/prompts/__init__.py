"""Suyi Prompts 模块 — Prompt 模板管理系统.

提供模板插值、版本管理、热重载和预置模板库：

    PromptTemplate / SystemPrompt / ReActPrompt / ToolPrompt — 模板类
    PromptManager    — 模板注册、版本管理、热重载
    PromptLibrary    — 预置模板库（中英双语）

使用示例::

    from suyi.prompts import PromptTemplate, PromptManager, PromptLibrary

    # 基础模板
    tpl = PromptTemplate("Hello, {name}!")
    text = tpl.render(name="World")

    # 管理器
    mgr = PromptManager()
    mgr.register(tpl)
    mgr.render("greeting", name="Alice")

    # 预置库
    lib = PromptLibrary()
    text = lib.render("system_general_en")
"""

from .templates import (
    PromptTemplate,
    SystemPrompt,
    ReActPrompt,
    ToolPrompt,
    MultiAgentPrompt,
)
from .manager import (
    PromptManager,
    TemplateVersion,
)
from .library import (
    PromptLibrary,
    get_library,
    get_template,
    render_template,
)

__all__ = [
    # Templates
    "PromptTemplate",
    "SystemPrompt",
    "ReActPrompt",
    "ToolPrompt",
    "MultiAgentPrompt",
    # Manager
    "PromptManager",
    "TemplateVersion",
    # Library
    "PromptLibrary",
    "get_library",
    "get_template",
    "render_template",
]
