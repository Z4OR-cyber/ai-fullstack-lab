"""Tests for Agent Relay Pipeline — 声明式接力链。"""

import pytest

from suyi.agents.pipeline import (
    DataSchema,
    PipelineStep,
    PipelineExecutionResult,
    AgentPipeline,
)
from suyi.agents.base import AgentInstance, AgentConfig
from suyi.core.loop import MockLLM, LLMResponse


def _make_agent(name: str, responses=None):
    """创建测试用 agent。"""
    if responses is None:
        responses = [LLMResponse.text(f"Output from {name}")]
    config = AgentConfig(name=name, description=f"Test agent {name}")
    return AgentInstance(config=config, llm=MockLLM(responses))


class TestDataSchema:
    """DataSchema 数据契约测试。"""

    def test_validate_pass(self):
        """验证通过。"""
        schema = DataSchema(
            required_fields=["text"],
            field_types={"text": str},
        )
        valid, msg = schema.validate({"text": "hello"})
        assert valid is True
        assert msg == ""

    def test_validate_missing_required(self):
        """缺少必填字段。"""
        schema = DataSchema(required_fields=["text"])
        valid, msg = schema.validate({})
        assert valid is False
        assert "text" in msg

    def test_validate_wrong_type(self):
        """字段类型错误。"""
        schema = DataSchema(
            required_fields=["count"],
            field_types={"count": int},
        )
        valid, msg = schema.validate({"count": "not_an_int"})
        assert valid is False
        assert "count" in msg

    def test_validate_optional_fields(self):
        """可选字段不报错。"""
        schema = DataSchema(
            required_fields=["a"],
            optional_fields=["b"],
        )
        valid, _ = schema.validate({"a": 1})
        assert valid is True

    def test_repr(self):
        assert "DataSchema" in repr(DataSchema(required_fields=["x"]))


class TestPipelineStep:
    """PipelineStep 步骤定义测试。"""

    def test_creation(self):
        step = PipelineStep(
            name="extract",
            agent_id="extractor",
            on_success_next="analyze",
            on_failure_next=None,
        )
        assert step.name == "extract"
        assert step.agent_id == "extractor"
        assert step.on_success_next == "analyze"

    def test_repr(self):
        step = PipelineStep(name="test", agent_id="agent1")
        assert "PipelineStep" in repr(step)


class TestAgentPipeline:
    """AgentPipeline 接力链测试。"""

    def test_simple_pipeline(self):
        """简单串行管道。"""
        agents = {
            "a1": _make_agent("a1", [LLMResponse.text("Step 1 done")]),
            "a2": _make_agent("a2", [LLMResponse.text("Step 2 done")]),
        }
        steps = [
            PipelineStep(name="s1", agent_id="a1", on_success_next="s2"),
            PipelineStep(name="s2", agent_id="a2", on_success_next=None),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = pipeline.run_sync("Initial input")

        assert result.success is True
        assert len(result.execution_path) == 2
        assert result.execution_path == ["s1", "s2"]

    def test_pipeline_with_schema_validation(self):
        """带数据契约校验的管道。"""
        agents = {
            "a1": _make_agent("a1", [LLMResponse.text("output")]),
        }
        steps = [
            PipelineStep(
                name="s1",
                agent_id="a1",
                input_schema=DataSchema(required_fields=["text"]),
                on_success_next=None,
                transform_input=lambda ctx: ctx.get("text", ""),
            ),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)

        # 有必填字段
        result = pipeline.run_sync("input", context={"text": "hello"})
        assert result.success is True

        # 缺少必填字段
        result2 = pipeline.run_sync("input", context={})
        assert result2.success is False
        assert "Input schema validation failed" in result2.error

    def test_pipeline_failure_handling(self):
        """失败处理。"""
        # 创建一个会抛出异常的 mock LLM
        class FailingLLM:
            async def chat(self, messages, tools, system_prompt):
                raise RuntimeError("LLM error")
            def add_response(self, *args):
                pass

        config = AgentConfig(name="a1", description="Test agent a1")
        agents = {"a1": AgentInstance(config=config, llm=FailingLLM())}
        steps = [
            PipelineStep(
                name="s1",
                agent_id="a1",
                on_success_next=None,
                on_failure_next=None,
            ),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = pipeline.run_sync("input")

        assert result.success is False
        assert result.failed_step == "s1"

    def test_pipeline_failure_redirect(self):
        """失败时跳转到备用步骤。"""
        # 创建一个会抛出异常的 mock LLM
        class FailingLLM:
            async def chat(self, messages, tools, system_prompt):
                raise RuntimeError("LLM error")
            def add_response(self, *args):
                pass

        agents = {
            "a1": AgentInstance(
                config=AgentConfig(name="a1", description="Test agent a1"),
                llm=FailingLLM(),
            ),
            "a2": _make_agent("a2", [LLMResponse.text("Fallback done")]),
        }
        steps = [
            PipelineStep(
                name="s1",
                agent_id="a1",
                on_success_next=None,
                on_failure_next="s2",
            ),
            PipelineStep(
                name="s2",
                agent_id="a2",
                on_success_next=None,
                on_failure_next=None,
            ),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = pipeline.run_sync("input")

        assert "s2" in result.execution_path

    def test_pipeline_context_passing(self):
        """上下文传递。"""
        agents = {
            "a1": _make_agent("a1", [LLMResponse.text("step1_output")]),
            "a2": _make_agent("a2", [LLMResponse.text("step2_output")]),
        }
        steps = [
            PipelineStep(
                name="s1",
                agent_id="a1",
                on_success_next="s2",
                transform_output=lambda out: {"step1_result": out},
            ),
            PipelineStep(
                name="s2",
                agent_id="a2",
                on_success_next=None,
                transform_input=lambda ctx: ctx.get("step1_result", ""),
            ),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = pipeline.run_sync("input", context={"initial": "data"})

        assert result.success is True
        assert "step1_result" in result.context
        assert result.context["initial"] == "data"

    def test_pipeline_missing_agent(self):
        """缺少 agent 时报错。"""
        steps = [
            PipelineStep(name="s1", agent_id="nonexistent", on_success_next=None),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry={})
        result = pipeline.run_sync("input")

        assert result.success is False
        assert "not found in registry" in result.error

    def test_pipeline_missing_step(self):
        """引用不存在的步骤。"""
        agents = {"a1": _make_agent("a1")}
        steps = [
            PipelineStep(name="s1", agent_id="a1", on_success_next="nonexistent"),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        result = pipeline.run_sync("input")

        assert result.success is False
        assert "not found" in result.error

    def test_validate_no_errors(self):
        """验证配置无错误。"""
        agents = {"a1": _make_agent("a1")}
        steps = [
            PipelineStep(name="s1", agent_id="a1", on_success_next=None),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        errors = pipeline.validate()
        assert len(errors) == 0

    def test_validate_with_errors(self):
        """验证配置有错误。"""
        agents = {"a1": _make_agent("a1")}
        steps = [
            PipelineStep(
                name="s1",
                agent_id="a1",
                on_success_next="nonexistent",
            ),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        errors = pipeline.validate()
        assert len(errors) > 0

    def test_set_entry(self):
        """设置入口步骤。"""
        agents = {
            "a1": _make_agent("a1"),
            "a2": _make_agent("a2"),
        }
        steps = [
            PipelineStep(name="s1", agent_id="a1", on_success_next="s2"),
            PipelineStep(name="s2", agent_id="a2", on_success_next=None),
        ]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        pipeline.set_entry("s2")
        assert pipeline._entry_step == "s2"

    def test_empty_steps_raises(self):
        """空步骤列表抛出异常。"""
        with pytest.raises(ValueError):
            AgentPipeline(steps=[], agent_registry={})

    def test_repr(self):
        """repr 方法。"""
        agents = {"a1": _make_agent("a1")}
        steps = [PipelineStep(name="s1", agent_id="a1")]
        pipeline = AgentPipeline(steps=steps, agent_registry=agents)
        assert "AgentPipeline" in repr(pipeline)
