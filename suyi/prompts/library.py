"""预置 Prompt 库 — 常用模板集合，中英双语支持.

提供的预置模板::

    ┌──────────────────────────────────────────────────────┐
    │  系统提示模板   — 通用助手 / 代码助手 / 研究助手          │
    │  ReAct 推理模板 — 标准 ReAct / 紧凑 ReAct               │
    │  工具调用模板   — 工具描述 / 工具选择指导                 │
    │  多Agent协作   — 协调者 / 工作者 / 评审者               │
    └──────────────────────────────────────────────────────┘

使用示例::

    from suyi.prompts.library import PromptLibrary

    lib = PromptLibrary()

    # 获取预置模板
    tpl = lib.get("system_general_en")
    rendered = tpl.render()

    # 获取所有预置模板名
    names = lib.list_templates()

    # 直接渲染
    text = lib.render("react_standard_en", tools_desc="...", history_desc="...")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .templates import (
    PromptTemplate,
    SystemPrompt,
    ReActPrompt,
    ToolPrompt,
    MultiAgentPrompt,
)
from .manager import PromptManager


# ═══════════════════════════════════════════════════════════════
#  Predefined Templates (English)
# ═══════════════════════════════════════════════════════════════

GENERAL_ASSISTANT_EN = """You are a helpful, harmless, and honest AI assistant.

Your goal is to assist users with their tasks to the best of your ability.
Always strive to provide accurate, relevant, and well-structured responses.

When you are not sure about something, say so honestly rather than making things up."""

CODE_ASSISTANT_EN = """You are an expert programming assistant.

You help users with:
- Writing, reviewing, and debugging code
- Explaining technical concepts
- Suggesting best practices and design patterns
- Analyzing code for security and performance issues

Guidelines:
- Always consider edge cases and error handling
- Prefer clean, readable code over clever tricks
- Explain your reasoning when making architectural decisions
- When reviewing code, be specific about what to change and why"""

RESEARCH_ASSISTANT_EN = """You are a thorough research assistant.

Your role is to:
- Find and synthesize information from multiple sources
- Present findings in a structured, objective manner
- Distinguish between facts, hypotheses, and opinions
- Cite sources when possible

Always:
- Consider multiple perspectives
- Acknowledge uncertainty and limitations
- Prioritize primary sources over secondary ones
- Be transparent about your search and reasoning process"""

# ═══════════════════════════════════════════════════════════════
#  Predefined Templates (Chinese)
# ═══════════════════════════════════════════════════════════════

GENERAL_ASSISTANT_ZH = """你是一个有帮助、无害且诚实的 AI 助手。

你的目标是尽最大努力帮助用户完成任务。
始终努力提供准确、相关且结构良好的回答。

当你不确定时，请诚实说明，而不是编造信息。"""

CODE_ASSISTANT_ZH = """你是一个专业的编程助手。

你帮助用户：
- 编写、审查和调试代码
- 解释技术概念
- 建议最佳实践和设计模式
- 分析代码的安全性和性能问题

准则：
- 始终考虑边界情况和错误处理
- 优先选择简洁、可读的代码而非巧妙的技巧
- 在做出架构决策时解释你的推理
- 审查代码时，具体说明需要修改什么以及为什么"""

RESEARCH_ASSISTANT_ZH = """你是一个严谨的研究助手。

你的职责是：
- 从多个来源查找和综合信息
- 以结构化、客观的方式呈现发现
- 区分事实、假设和观点
- 尽可能引用来源

始终：
- 考虑多个视角
- 承认不确定性和局限性
- 优先使用一手资料而非二手资料
- 对你的搜索和推理过程保持透明"""

# ═══════════════════════════════════════════════════════════════
#  ReAct Templates
# ═══════════════════════════════════════════════════════════════

REACT_STANDARD_EN = """You are an AI assistant operating in a ReAct (Reasoning + Acting) loop.

## Available Tools
{tools_desc}

## Conversation History
{history_desc}

## Budget Constraint
{budget_desc}

## Instructions
Follow the ReAct pattern:
1. **Thought**: Reason about what you need to do next.
2. **Action**: If you need information or action, call a tool.
3. **Observation**: Review the tool result.
4. Repeat steps 1-3 until you have enough information.
5. **Final Answer**: When ready, provide your answer without any tool calls.

Be efficient: use the minimum number of tool calls necessary.
If a tool fails, try an alternative approach rather than repeating the same call.

{task_desc}"""

REACT_COMPACT_EN = """Tools: {tools_desc}
History: {history_desc}
Budget: {budget_desc}
Task: {task_desc}
Think step by step. Use tools when needed. Provide final answer when ready."""

REACT_STANDARD_ZH = """你是一个在 ReAct（推理+行动）循环中运行的 AI 助手。

## 可用工具
{tools_desc}

## 对话历史
{history_desc}

## 预算约束
{budget_desc}

## 指示
遵循 ReAct 模式：
1. **思考**：推理下一步需要做什么。
2. **行动**：如果需要信息或操作，调用工具。
3. **观察**：审查工具结果。
4. 重复步骤 1-3，直到获得足够信息。
5. **最终回答**：准备好后，给出不含工具调用的回答。

保持高效：使用最少的工具调用次数。
如果工具调用失败，尝试替代方法而不是重复相同的调用。

{task_desc}"""

# ═══════════════════════════════════════════════════════════════
#  Tool Description Templates
# ═══════════════════════════════════════════════════════════════

TOOL_SELECTION_GUIDE_EN = """## Tool Selection Guidelines

When choosing which tool to use, consider:
1. **Relevance**: Does the tool directly address the user's need?
2. **Efficiency**: Can one tool call replace multiple calls?
3. **Safety**: Is the tool safe to use with the given arguments?
4. **Fallback**: If the tool fails, what's your backup plan?

Avoid:
- Calling tools you don't need
- Repeating failed tool calls with the same arguments
- Ignoring tool error messages"""

TOOL_FORMAT_EN = """### {tool_name}
{tool_description}

Parameters:
{tool_parameters}

Use this tool when: {use_case}"""

# ═══════════════════════════════════════════════════════════════
#  Multi-Agent Templates
# ═══════════════════════════════════════════════════════════════

ORCHESTRATOR_PROMPT_EN = """You are the Orchestrator Agent in a multi-agent system.

Your responsibilities:
1. Analyze the user's request and decompose it into sub-tasks.
2. Assign each sub-task to the most appropriate agent.
3. Monitor agent progress and handle failures.
4. Synthesize results into a coherent final answer.

Available agents:
{agent_descriptions}

Collaboration rules:
{collaboration_rules}

Current task: {task}"""

WORKER_PROMPT_EN = """You are a Worker Agent named "{agent_name}".

Your specialty: {specialty}
Your current sub-task: {sub_task}

Instructions:
- Focus on your assigned sub-task
- Use available tools as needed
- Report your findings clearly
- If you cannot complete the task, explain why

Available tools:
{tools_desc}"""

REVIEWER_PROMPT_EN = """You are a Reviewer Agent.

Your job is to review the work produced by other agents and provide feedback.

Review criteria:
- **Correctness**: Is the information accurate?
- **Completeness**: Are all aspects of the task addressed?
- **Clarity**: Is the output clear and well-structured?
- **Safety**: Are there any safety concerns?

Work to review:
{work_to_review}

Provide your assessment with specific, actionable feedback."""


# ═══════════════════════════════════════════════════════════════
#  Prompt Library
# ═══════════════════════════════════════════════════════════════


class PromptLibrary:
    """预置 Prompt 模板库.

    提供常用系统提示、ReAct 模板、工具模板和多 Agent 模板.
    支持中英双语.

    Usage::

        lib = PromptLibrary()

        # 获取模板
        tpl = lib.get("system_general_en")
        text = tpl.render()

        # 直接渲染
        text = lib.render("react_standard_en",
                          tools_desc="...", history_desc="...",
                          budget_desc="...", task_desc="")

        # 添加自定义模板
        lib.add("my_template", PromptTemplate("Hello {name}!"))

        # 获取 PromptManager 实例（用于版本管理等高级功能）
        mgr = lib.manager
    """

    def __init__(self):
        self._manager = PromptManager()
        self._register_defaults()

    @property
    def manager(self) -> PromptManager:
        """返回底层 PromptManager 实例."""
        return self._manager

    def _register_defaults(self) -> None:
        """注册所有预置模板."""
        # 系统提示 — 英文
        self._manager.register(
            PromptTemplate(GENERAL_ASSISTANT_EN, name="system_general_en",
                           description="General assistant system prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(CODE_ASSISTANT_EN, name="system_code_en",
                           description="Code assistant system prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(RESEARCH_ASSISTANT_EN, name="system_research_en",
                           description="Research assistant system prompt (English)"),
        )

        # 系统提示 — 中文
        self._manager.register(
            PromptTemplate(GENERAL_ASSISTANT_ZH, name="system_general_zh",
                           description="通用助手系统提示（中文）"),
        )
        self._manager.register(
            PromptTemplate(CODE_ASSISTANT_ZH, name="system_code_zh",
                           description="编程助手系统提示（中文）"),
        )
        self._manager.register(
            PromptTemplate(RESEARCH_ASSISTANT_ZH, name="system_research_zh",
                           description="研究助手系统提示（中文）"),
        )

        # ReAct 模板
        self._manager.register(
            PromptTemplate(REACT_STANDARD_EN, name="react_standard_en",
                           description="Standard ReAct prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(REACT_COMPACT_EN, name="react_compact_en",
                           description="Compact ReAct prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(REACT_STANDARD_ZH, name="react_standard_zh",
                           description="标准 ReAct 提示（中文）"),
        )

        # 工具模板
        self._manager.register(
            PromptTemplate(TOOL_SELECTION_GUIDE_EN, name="tool_selection_guide_en",
                           description="Tool selection guidelines (English)"),
        )
        self._manager.register(
            PromptTemplate(TOOL_FORMAT_EN, name="tool_format_en",
                           description="Tool description format (English)"),
        )

        # 多 Agent 模板
        self._manager.register(
            PromptTemplate(ORCHESTRATOR_PROMPT_EN, name="orchestrator_en",
                           description="Orchestrator agent prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(WORKER_PROMPT_EN, name="worker_en",
                           description="Worker agent prompt (English)"),
        )
        self._manager.register(
            PromptTemplate(REVIEWER_PROMPT_EN, name="reviewer_en",
                           description="Reviewer agent prompt (English)"),
        )

    # ── 委托方法 ──────────────────────────────────────────

    def get(self, name: str, version: Optional[int] = None) -> PromptTemplate:
        """获取模板."""
        return self._manager.get(name, version)

    def render(self, template_name: str, version: Optional[int] = None, **kwargs: Any) -> str:
        """获取并渲染模板."""
        return self._manager.render(template_name, version=version, **kwargs)

    def render_safe(self, template_name: str, version: Optional[int] = None, **kwargs: Any) -> str:
        """安全渲染模板."""
        return self._manager.render_safe(template_name, version=version, **kwargs)

    def add(self, name: str, template: PromptTemplate, description: str = "") -> "PromptLibrary":
        """添加自定义模板."""
        template.name = name
        self._manager.register(template, description)
        return self

    def list_templates(self) -> List[str]:
        """列出所有模板名称."""
        return self._manager.list_templates()

    def has(self, name: str) -> bool:
        """检查模板是否存在."""
        return self._manager.has(name)

    def list_by_category(self, category: str) -> List[str]:
        """按类别筛选模板.

        类别：
        - 'system': 系统提示模板
        - 'react': ReAct 模板
        - 'tool': 工具模板
        - 'agent': 多 Agent 模板
        """
        prefixes = {
            "system": ["system_"],
            "react": ["react_"],
            "tool": ["tool_"],
            "agent": ["orchestrator_", "worker_", "reviewer_"],
        }
        prefix_list = prefixes.get(category, [])
        return [
            name for name in self._manager.list_templates()
            if any(name.startswith(p) for p in prefix_list)
        ]

    def list_by_language(self, language: str) -> List[str]:
        """按语言筛选模板.

        Args:
            language: 'en' 或 'zh'.
        """
        suffix = f"_{language}"
        return [
            name for name in self._manager.list_templates()
            if name.endswith(suffix)
        ]

    def stats(self) -> Dict[str, Any]:
        """返回库统计信息."""
        s = self._manager.stats()
        s["categories"] = {
            cat: len(self.list_by_category(cat))
            for cat in ["system", "react", "tool", "agent"]
        }
        s["languages"] = {
            lang: len(self.list_by_language(lang))
            for lang in ["en", "zh"]
        }
        return s

    def __repr__(self) -> str:
        return f"PromptLibrary(templates={len(self._manager)})"

    def __len__(self) -> int:
        return len(self._manager)

    def __contains__(self, name: str) -> bool:
        return name in self._manager


# ═══════════════════════════════════════════════════════════════
#  Convenience Functions
# ═══════════════════════════════════════════════════════════════

# 全局单例（惰性初始化）
_library_instance: Optional[PromptLibrary] = None


def get_library() -> PromptLibrary:
    """获取全局 PromptLibrary 单例实例."""
    global _library_instance
    if _library_instance is None:
        _library_instance = PromptLibrary()
    return _library_instance


def get_template(name: str) -> PromptTemplate:
    """从全局库获取模板."""
    return get_library().get(name)


def render_template(name: str, **kwargs: Any) -> str:
    """从全局库渲染模板.

    注意: 如果模板变量名也是 ``name``，请使用 ``get_library().render()`` 直接调用.
    """
    return get_library().render(name, **kwargs)
