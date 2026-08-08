"""Agent Relay Pipeline — 声明式接力链。

实现声明式接力链 Pipeline，每个 Step 定义:
    - agent_id: 执行该步骤的 agent 标识
    - input_schema: 输入数据契约
    - output_schema: 输出数据契约
    - on_success_next: 成功时跳转的下一步骤
    - on_failure_next: 失败时跳转的下一步骤

运行时自动进行数据契约校验和上下文传递。

与 patterns.Pipeline 的区别:
    - patterns.Pipeline 是简单的串行管道（A→B→C）
    - pipeline.Pipeline 支持条件跳转、数据契约校验、上下文传递
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .base import AgentInstance
from ..core.loop import LoopResult


# ── 数据契约 ──────────────────────────────────────────────────

@dataclass
class DataSchema:
    """数据契约定义。

    Attributes:
        required_fields: 必填字段列表。
        optional_fields: 可选字段列表。
        field_types: 字段类型映射 (field_name → type)。
    """

    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, type] = field(default_factory=dict)

    def validate(self, data: Dict[str, Any]) -> tuple[bool, str]:
        """验证数据是否符合契约。

        Args:
            data: 待验证的数据字典。

        Returns:
            (是否通过, 错误信息)。
        """
        # 检查必填字段
        for field_name in self.required_fields:
            if field_name not in data:
                return False, f"Missing required field: {field_name}"

        # 检查字段类型
        for field_name, expected_type in self.field_types.items():
            if field_name in data:
                actual_value = data[field_name]
                if actual_value is not None and not isinstance(actual_value, expected_type):
                    return False, (
                        f"Field '{field_name}' has type {type(actual_value).__name__}, "
                        f"expected {expected_type.__name__}"
                    )

        return True, ""

    def __repr__(self) -> str:
        return (
            f"DataSchema(required={self.required_fields}, "
            f"optional={self.optional_fields})"
        )


# ── Pipeline Step ─────────────────────────────────────────────

@dataclass
class PipelineStep:
    """接力链中的一个步骤。

    Attributes:
        name: 步骤名称。
        agent_id: 执行该步骤的 agent 标识（用于在 registry 中查找）。
        input_schema: 输入数据契约。
        output_schema: 输出数据契约。
        on_success_next: 成功时的下一步骤名称（None 表示结束）。
        on_failure_next: 失败时的下一步骤名称（None 表示终止）。
        transform_input: 可选的输入转换函数。
        transform_output: 可选的输出转换函数。
    """

    name: str
    agent_id: str
    input_schema: Optional[DataSchema] = None
    output_schema: Optional[DataSchema] = None
    on_success_next: Optional[str] = None
    on_failure_next: Optional[str] = None
    transform_input: Optional[Callable[[Dict[str, Any]], str]] = None
    transform_output: Optional[Callable[[str], Dict[str, Any]]] = None

    def __repr__(self) -> str:
        return (
            f"PipelineStep(name={self.name!r}, "
            f"agent_id={self.agent_id!r}, "
            f"success→{self.on_success_next!r}, "
            f"failure→{self.on_failure_next!r})"
        )


# ── Pipeline 执行结果 ─────────────────────────────────────────

@dataclass
class PipelineExecutionResult:
    """接力链执行结果。

    Attributes:
        success: 是否所有步骤成功完成。
        final_output: 最终输出。
        step_results: 各步骤的执行结果。
        context: 传递的上下文数据。
        execution_path: 实际执行路径（步骤名称列表）。
        failed_step: 失败的步骤名称。
        error: 错误信息。
    """

    success: bool
    final_output: Any = None
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    execution_path: List[str] = field(default_factory=list)
    failed_step: str = ""
    error: str = ""

    def __repr__(self) -> str:
        return (
            f"PipelineExecutionResult(success={self.success}, "
            f"steps={len(self.execution_path)}, "
            f"path={self.execution_path})"
        )


# ── Agent Relay Pipeline ──────────────────────────────────────

class AgentPipeline:
    """声明式接力链 Pipeline。

    通过 PipelineStep 声明式定义接力链，
    运行时自动进行数据契约校验和上下文传递。

    Usage::

        steps = [
            PipelineStep(
                name="extract",
                agent_id="extractor",
                input_schema=DataSchema(required_fields=["text"]),
                output_schema=DataSchema(required_fields=["entities"]),
                on_success_next="analyze",
                on_failure_next=None,
            ),
            PipelineStep(
                name="analyze",
                agent_id="analyzer",
                input_schema=DataSchema(required_fields=["entities"]),
                output_schema=DataSchema(required_fields=["analysis"]),
                on_success_next=None,
                on_failure_next=None,
            ),
        ]

        agents = {
            "extractor": extractor_agent,
            "analyzer": analyzer_agent,
        }

        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = await pipeline.run(initial_input="...", context={"text": "..."})
    """

    def __init__(
        self,
        steps: List[PipelineStep],
        agent_registry: Dict[str, AgentInstance],
        max_iterations: int = 50,
    ) -> None:
        """初始化 Pipeline。

        Args:
            steps: 步骤列表。
            agent_registry: agent 注册表 (agent_id → AgentInstance)。
            max_iterations: 最大迭代次数（防止无限循环）。
        """
        if not steps:
            raise ValueError("Pipeline requires at least one step.")

        self.steps = steps
        self.agent_registry = agent_registry
        self.max_iterations = max_iterations

        # 构建步骤名称 → 步骤的映射
        self._step_map: Dict[str, PipelineStep] = {s.name: s for s in steps}

        # 第一个步骤作为入口
        self._entry_step = steps[0].name

    def set_entry(self, step_name: str) -> None:
        """设置入口步骤。"""
        if step_name not in self._step_map:
            raise ValueError(f"Step '{step_name}' not found.")
        self._entry_step = step_name

    async def run(
        self,
        initial_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineExecutionResult:
        """执行接力链。

        Args:
            initial_input: 初始输入文本。
            context: 初始上下文数据。

        Returns:
            PipelineExecutionResult。
        """
        ctx: Dict[str, Any] = dict(context or {})
        ctx["_initial_input"] = initial_input

        current_step_name = self._entry_step
        current_input = initial_input
        step_results: List[Dict[str, Any]] = []
        execution_path: List[str] = []

        for iteration in range(self.max_iterations):
            if current_step_name is None:
                # 正常结束
                break

            if current_step_name not in self._step_map:
                return PipelineExecutionResult(
                    success=False,
                    final_output=current_input,
                    step_results=step_results,
                    context=ctx,
                    execution_path=execution_path,
                    failed_step=current_step_name,
                    error=f"Step '{current_step_name}' not found in pipeline.",
                )

            step = self._step_map[current_step_name]
            execution_path.append(step.name)

            # 数据契约校验: 输入
            if step.input_schema:
                valid, msg = step.input_schema.validate(ctx)
                if not valid:
                    return PipelineExecutionResult(
                        success=False,
                        final_output=current_input,
                        step_results=step_results,
                        context=ctx,
                        execution_path=execution_path,
                        failed_step=step.name,
                        error=f"Input schema validation failed: {msg}",
                    )

            # 获取 agent
            agent = self.agent_registry.get(step.agent_id)
            if agent is None:
                return PipelineExecutionResult(
                    success=False,
                    final_output=current_input,
                    step_results=step_results,
                    context=ctx,
                    execution_path=execution_path,
                    failed_step=step.name,
                    error=f"Agent '{step.agent_id}' not found in registry.",
                )

            # 应用输入转换
            if step.transform_input:
                try:
                    current_input = step.transform_input(ctx)
                except Exception as e:
                    return PipelineExecutionResult(
                        success=False,
                        final_output=current_input,
                        step_results=step_results,
                        context=ctx,
                        execution_path=execution_path,
                        failed_step=step.name,
                        error=f"Input transform failed: {e}",
                    )

            # 执行 agent
            try:
                loop_result: LoopResult = await agent.run(current_input)
                output = loop_result.content
                step_success = loop_result.is_complete
                error_msg = "" if step_success else loop_result.stop_reason
            except Exception as e:
                output = ""
                step_success = False
                error_msg = str(e)

            # 应用输出转换
            if step.transform_output and step_success:
                try:
                    output_dict = step.transform_output(output)
                    ctx.update(output_dict)
                except Exception as e:
                    return PipelineExecutionResult(
                        success=False,
                        final_output=output,
                        step_results=step_results,
                        context=ctx,
                        execution_path=execution_path,
                        failed_step=step.name,
                        error=f"Output transform failed: {e}",
                    )

            # 记录步骤结果
            step_results.append({
                "step": step.name,
                "agent_id": step.agent_id,
                "success": step_success,
                "input": current_input[:200] if current_input else "",
                "output": output[:200] if output else "",
                "error": error_msg,
            })

            if not step_success:
                # 失败: 检查 on_failure_next
                if step.on_failure_next is None:
                    return PipelineExecutionResult(
                        success=False,
                        final_output=output,
                        step_results=step_results,
                        context=ctx,
                        execution_path=execution_path,
                        failed_step=step.name,
                        error=error_msg or "Step failed.",
                    )
                current_step_name = step.on_failure_next
                current_input = output
                continue

            # 数据契约校验: 输出
            if step.output_schema:
                valid, msg = step.output_schema.validate(ctx)
                if not valid:
                    return PipelineExecutionResult(
                        success=False,
                        final_output=output,
                        step_results=step_results,
                        context=ctx,
                        execution_path=execution_path,
                        failed_step=step.name,
                        error=f"Output schema validation failed: {msg}",
                    )

            # 成功: 跳转到下一步
            current_input = output
            current_step_name = step.on_success_next

        # 检查是否超出最大迭代次数
        if iteration >= self.max_iterations - 1 and current_step_name is not None:
            return PipelineExecutionResult(
                success=False,
                final_output=current_input,
                step_results=step_results,
                context=ctx,
                execution_path=execution_path,
                failed_step=current_step_name or "",
                error=f"Pipeline exceeded max iterations ({self.max_iterations}).",
            )

        return PipelineExecutionResult(
            success=True,
            final_output=current_input,
            step_results=step_results,
            context=ctx,
            execution_path=execution_path,
        )

    def run_sync(
        self,
        initial_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineExecutionResult:
        """同步执行便捷方法。"""
        return asyncio.run(self.run(initial_input, context))

    def validate(self) -> List[str]:
        """验证 Pipeline 配置的完整性。

        Returns:
            错误信息列表（空列表表示无错误）。
        """
        errors: List[str] = []

        # 检查步骤名称唯一
        names = [s.name for s in self.steps]
        if len(names) != len(set(names)):
            errors.append("Duplicate step names found.")

        # 检查 on_success_next 和 on_failure_next 引用的步骤存在
        for step in self.steps:
            if step.on_success_next and step.on_success_next not in self._step_map:
                errors.append(
                    f"Step '{step.name}': on_success_next '{step.on_success_next}' not found."
                )
            if step.on_failure_next and step.on_failure_next not in self._step_map:
                errors.append(
                    f"Step '{step.name}': on_failure_next '{step.on_failure_next}' not found."
                )

        # 检查 agent_id 存在
        for step in self.steps:
            if step.agent_id not in self.agent_registry:
                errors.append(
                    f"Step '{step.name}': agent_id '{step.agent_id}' not in registry."
                )

        # 检查无死循环（简单检测: on_success_next 不能指向自己）
        for step in self.steps:
            if step.on_success_next == step.name:
                errors.append(
                    f"Step '{step.name}': on_success_next points to itself."
                )

        return errors

    def __repr__(self) -> str:
        return f"AgentPipeline(steps={len(self.steps)}, entry={self._entry_step!r})"


__all__ = [
    "DataSchema",
    "PipelineStep",
    "PipelineExecutionResult",
    "AgentPipeline",
]
