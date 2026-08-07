"""Prompt 模板系统 — 变量插值、继承和组合.

核心组件::

    ┌──────────────────────────────────────────────────────┐
    │  PromptTemplate — 基础模板类，支持 {variable} 插值      │
    │  SystemPrompt   — 系统提示模板                          │
    │  ReActPrompt    — ReAct 循环专用模板                    │
    │  ToolPrompt     — 工具描述模板                          │
    └──────────────────────────────────────────────────────┘

设计原则：
- **简洁插值**：使用 Python ``str.format()`` 风格的 ``{variable}`` 语法.
- **模板继承**：子模板可继承父模板并覆盖/扩展部分内容.
- **模板组合**：支持将多个模板组合为一个更大的模板.
- **变量验证**：渲染时自动检查缺失变量.
- **类型安全**：所有模板方法返回字符串.

Usage::

    # 基础模板
    tpl = PromptTemplate("Hello, {name}! You are {role}.")
    rendered = tpl.render(name="Alice", role="admin")
    # "Hello, Alice! You are admin."

    # 系统提示
    sys = SystemPrompt(
        identity="You are a helpful assistant.",
        rules=["Be concise.", "Be accurate."],
    )
    text = sys.render()

    # ReAct 提示
    react = ReActPrompt()
    text = react.render(tools_desc="...", history_desc="...", budget_desc="...")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ═══════════════════════════════════════════════════════════════
#  Prompt Template
# ═══════════════════════════════════════════════════════════════


class PromptTemplate:
    """基础 Prompt 模板类，支持 ``{variable}`` 插值.

    Attributes:
        template:  模板字符串，包含 ``{variable}`` 占位符.
        name:      模板名称.
        variables: 模板中使用的变量名列表（自动提取）.
    """

    # 匹配 {variable} 占位符的正则（排除 {{ }} 转义）
    _VAR_PATTERN = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")

    def __init__(
        self,
        template: str,
        name: str = "",
        description: str = "",
    ):
        self.template = template
        self.name = name or self.__class__.__name__
        self.description = description
        self._variables: List[str] = self._extract_variables(template)

    @classmethod
    def _extract_variables(cls, template: str) -> List[str]:
        """从模板字符串中提取变量名."""
        matches = cls._VAR_PATTERN.findall(template)
        # 去重并保持顺序
        seen: Set[str] = set()
        result: List[str] = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    @property
    def variables(self) -> List[str]:
        """模板中定义的变量名列表."""
        return list(self._variables)

    def render(self, **kwargs: Any) -> str:
        """渲染模板，填充变量.

        Args:
            **kwargs: 变量名 → 值的映射.

        Returns:
            渲染后的字符串.

        Raises:
            KeyError: 如果缺少必需变量（且未设置默认值）.
        """
        # 检查缺失变量
        provided = set(kwargs.keys())
        required = set(self._variables)
        missing = required - provided
        if missing:
            raise KeyError(
                f"Missing required variables for template '{self.name}': "
                f"{sorted(missing)}"
            )

        # 处理 {{ }} 转义 → 先替换为占位符，渲染后还原
        escaped_template = self.template.replace("{{", "\x00OPEN\x00").replace("}}", "\x00CLOSE\x00")

        try:
            result = escaped_template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Variable {e} not provided for template '{self.name}'") from e

        result = result.replace("\x00OPEN\x00", "{").replace("\x00CLOSE\x00", "}")
        return result

    def render_safe(self, **kwargs: Any) -> str:
        """安全渲染，缺失变量用空字符串替代.

        Returns:
            渲染后的字符串（缺失变量被替换为空）.
        """
        # 为缺失的变量提供空字符串默认值
        full_kwargs = {v: "" for v in self._variables}
        full_kwargs.update(kwargs)

        escaped_template = self.template.replace("{{", "\x00OPEN\x00").replace("}}", "\x00CLOSE\x00")
        result = escaped_template.format(**full_kwargs)
        result = result.replace("\x00OPEN\x00", "{").replace("\x00CLOSE\x00", "}")
        return result

    def partial(self, **kwargs: Any) -> "PromptTemplate":
        """部分渲染，返回一个新的模板（已填充的变量被固定）.

        只替换提供的变量，未提供的变量保持 ``{variable}`` 占位符.

        Usage::

            tpl = PromptTemplate("Hello {name}, you are {role}.")
            partial = tpl.partial(name="Alice")
            # partial.template == "Hello Alice, you are {role}."
            full = partial.render(role="admin")
        """
        # 构建新的模板：手动替换已提供的变量，保留未提供的占位符
        result = self.template

        # 处理转义的大括号
        result = result.replace("{{", "\x00OPEN\x00").replace("}}", "\x00CLOSE\x00")

        for var_name, var_value in kwargs.items():
            # 替换 {var_name} 为实际值
            result = result.replace("{" + var_name + "}", str(var_value))

        result = result.replace("\x00OPEN\x00", "{").replace("\x00CLOSE\x00", "}")

        return PromptTemplate(
            template=result,
            name=f"{self.name}_partial",
            description=self.description,
        )

    def validate(self, **kwargs: Any) -> List[str]:
        """验证提供的变量是否完整.

        Returns:
            缺失变量名列表（空列表表示验证通过）.
        """
        provided = set(kwargs.keys())
        required = set(self._variables)
        return sorted(required - provided)

    def compose(self, other: "PromptTemplate", separator: str = "\n\n") -> "PromptTemplate":
        """组合两个模板.

        Args:
            other: 另一个模板.
            separator: 分隔符.

        Returns:
            组合后的新模板.
        """
        combined_template = self.template + separator + other.template
        return PromptTemplate(
            template=combined_template,
            name=f"{self.name}+{other.name}",
            description=f"Composed: {self.name} + {other.name}",
        )

    def __repr__(self) -> str:
        return f"PromptTemplate(name={self.name!r}, vars={self._variables})"

    def __str__(self) -> str:
        return self.template

    def __len__(self) -> int:
        return len(self.template)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PromptTemplate):
            return False
        return self.template == other.template and self.name == other.name


# ═══════════════════════════════════════════════════════════════
#  System Prompt
# ═══════════════════════════════════════════════════════════════


class SystemPrompt(PromptTemplate):
    """系统提示模板.

    构建结构化的系统提示，包含身份、规则和约束.

    Attributes:
        identity: Agent 身份描述.
        rules: 行为规则列表.
        constraints: 约束条件列表.
        language: 输出语言 ('en' 或 'zh').
    """

    DEFAULT_TEMPLATE_EN = """You are an AI assistant.

## Identity
{identity}

## Rules
{rules}

## Constraints
{constraints}"""

    DEFAULT_TEMPLATE_ZH = """你是一个 AI 助手。

## 身份
{identity}

## 规则
{rules}

## 约束
{constraints}"""

    def __init__(
        self,
        identity: str = "A helpful AI assistant.",
        rules: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        language: str = "en",
        name: str = "system_prompt",
        template: Optional[str] = None,
    ):
        self.identity_text = identity
        self.rules_list = rules or []
        self.constraints_list = constraints or []
        self.language = language

        if template:
            tpl = template
        elif language == "zh":
            tpl = self.DEFAULT_TEMPLATE_ZH
        else:
            tpl = self.DEFAULT_TEMPLATE_EN

        super().__init__(template=tpl, name=name)

    def render(self, **kwargs: Any) -> str:
        """渲染系统提示."""
        rules_text = "\n".join(
            f"- {rule}" for rule in self.rules_list
        ) if self.rules_list else "No specific rules."
        constraints_text = "\n".join(
            f"- {c}" for c in self.constraints_list
        ) if self.constraints_list else "No specific constraints."

        return super().render(
            identity=self.identity_text,
            rules=rules_text,
            constraints=constraints_text,
            **kwargs,
        )

    def add_rule(self, rule: str) -> "SystemPrompt":
        """添加一条规则."""
        self.rules_list.append(rule)
        return self

    def add_constraint(self, constraint: str) -> "SystemPrompt":
        """添加一条约束."""
        self.constraints_list.append(constraint)
        return self


# ═══════════════════════════════════════════════════════════════
#  ReAct Prompt
# ═══════════════════════════════════════════════════════════════


class ReActPrompt(PromptTemplate):
    """ReAct 循环专用模板.

    构建 ReAct (Reasoning + Acting) 模式的提示，
    包含工具描述、对话历史和预算约束.

    模板变量：
        tools_desc:    工具描述文本.
        history_desc:  对话历史文本.
        budget_desc:   预算约束文本.
        task_desc:     当前任务描述（可选）.
    """

    DEFAULT_TEMPLATE = """You operate in a ReAct (Reasoning + Acting) loop.

## Available Tools
{tools_desc}

## Conversation History
{history_desc}

## Budget Constraint
{budget_desc}

## Instructions
1. Think about what you need to do next (Thought).
2. If you need information or action, call a tool (Action).
3. Observe the tool result (Observation).
4. Repeat until you can provide a final answer.
5. When you have enough information, provide your final answer without tool calls.

{task_desc}"""

    def __init__(
        self,
        template: Optional[str] = None,
        name: str = "react_prompt",
    ):
        super().__init__(
            template=template or self.DEFAULT_TEMPLATE,
            name=name,
            description="ReAct loop prompt template",
        )

    def render(
        self,
        tools_desc: str = "",
        history_desc: str = "",
        budget_desc: str = "",
        task_desc: str = "",
        **kwargs: Any,
    ) -> str:
        """渲染 ReAct 提示."""
        return super().render(
            tools_desc=tools_desc,
            history_desc=history_desc,
            budget_desc=budget_desc,
            task_desc=task_desc,
            **kwargs,
        )


# ═══════════════════════════════════════════════════════════════
#  Tool Prompt
# ═══════════════════════════════════════════════════════════════


class ToolPrompt(PromptTemplate):
    """工具描述模板.

    生成结构化的工具描述文本，用于注入到系统提示或 LLM 调用中.

    模板变量：
        tool_name:        工具名称.
        tool_description: 工具描述.
        tool_parameters:  工具参数描述（JSON schema 文本）.
    """

    DEFAULT_TEMPLATE = """### Tool: {tool_name}
{tool_description}

Parameters:
{tool_parameters}"""

    def __init__(
        self,
        template: Optional[str] = None,
        name: str = "tool_prompt",
    ):
        super().__init__(
            template=template or self.DEFAULT_TEMPLATE,
            name=name,
            description="Tool description prompt template",
        )

    def render(
        self,
        tool_name: str = "",
        tool_description: str = "",
        tool_parameters: str = "",
        **kwargs: Any,
    ) -> str:
        """渲染工具描述."""
        return super().render(
            tool_name=tool_name,
            tool_description=tool_description,
            tool_parameters=tool_parameters,
            **kwargs,
        )

    @staticmethod
    def format_tools(tools: List[Dict[str, Any]]) -> str:
        """将工具列表格式化为描述文本.

        Args:
            tools: 工具列表，每项为
                ``{"name": str, "description": str, "parameters": dict}``.

        Returns:
            格式化后的工具描述文本.
        """
        import json
        lines: List[str] = []
        tpl = ToolPrompt()
        for tool in tools:
            params = tool.get("parameters", {})
            params_str = json.dumps(params, indent=2, ensure_ascii=False) if params else "{}"
            lines.append(tpl.render(
                tool_name=tool.get("name", ""),
                tool_description=tool.get("description", ""),
                tool_parameters=params_str,
            ))
        return "\n\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Multi-Agent Prompt
# ═══════════════════════════════════════════════════════════════


class MultiAgentPrompt(PromptTemplate):
    """多 Agent 协作模板.

    构建多 Agent 协作场景的提示，包含角色分配和协作规则.

    模板变量：
        orchestrator_desc: 协调者描述.
        agent_descriptions: 子 Agent 描述列表.
        collaboration_rules: 协作规则.
    """

    DEFAULT_TEMPLATE = """## Multi-Agent Collaboration

### Orchestrator
{orchestrator_desc}

### Available Agents
{agent_descriptions}

### Collaboration Rules
{collaboration_rules}"""

    def __init__(
        self,
        template: Optional[str] = None,
        name: str = "multi_agent_prompt",
    ):
        super().__init__(
            template=template or self.DEFAULT_TEMPLATE,
            name=name,
            description="Multi-agent collaboration prompt template",
        )

    def render(
        self,
        orchestrator_desc: str = "",
        agent_descriptions: str = "",
        collaboration_rules: str = "",
        **kwargs: Any,
    ) -> str:
        """渲染多 Agent 提示."""
        return super().render(
            orchestrator_desc=orchestrator_desc,
            agent_descriptions=agent_descriptions,
            collaboration_rules=collaboration_rules,
            **kwargs,
        )
