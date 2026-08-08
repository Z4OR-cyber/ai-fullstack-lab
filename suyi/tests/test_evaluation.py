"""
Tests for Suyi Evaluation Framework — metrics, benchmark, A/B testing.

Covers:
    - Metrics: TaskCompletion, ToolUsage, Latency, TokenEfficiency,
               ReasoningQuality, Hallucination, MetricSuite
    - Benchmark: BenchmarkCase, BenchmarkSuite, BenchmarkRunner, BenchmarkReport
    - ABTest: StatisticalSignificance, ABTest, ABTestResult
"""

import asyncio
import json
import os
import tempfile
import time

import numpy as np
import pytest

from suyi.evaluation import (
    # Metrics
    MetricBase,
    MetricResult,
    MetricSuite,
    SuiteReport,
    TraceRecord,
    TaskCompletionMetric,
    ToolUsageMetric,
    LatencyMetric,
    TokenEfficiencyMetric,
    ReasoningQualityMetric,
    HallucinationMetric,
    get_default_metrics,
    # Benchmark
    BenchmarkCase,
    CaseResult,
    BenchmarkSuite,
    BenchmarkRunner,
    BenchmarkReport,
    # AB Testing
    ABTest,
    ABTestResult,
    StatisticalSignificance,
)
from suyi.core.loop import LLMResponse, MockLLM, AgentLoop, ToolResult


# ═══════════════════════════════════════════════════════════════
#  Helper: Create sample traces
# ═══════════════════════════════════════════════════════════════


def make_trace(
    completed: bool = True,
    tool_calls=None,
    expected_tools=None,
    final_answer: str = "The answer is 42.",
    expected_answer: str = "",
    latency: float = 2.0,
    token_usage=None,
    reasoning_steps=None,
    tool_outputs=None,
) -> TraceRecord:
    """Create a sample TraceRecord for testing."""
    return TraceRecord(
        task="Test task",
        completed=completed,
        tool_calls=tool_calls or [],
        expected_tools=expected_tools or [],
        final_answer=final_answer,
        expected_answer=expected_answer,
        latency=latency,
        token_usage=token_usage or {"prompt": 100, "completion": 50, "total": 150},
        reasoning_steps=reasoning_steps if reasoning_steps is not None else [
            "First, I need to think about the problem.",
            "Then, I should search for information.",
            "Therefore, the answer is 42.",
        ],
        tool_outputs=tool_outputs or [],
    )


# ═══════════════════════════════════════════════════════════════
#  TraceRecord Tests
# ═══════════════════════════════════════════════════════════════


class TestTraceRecord:
    """Test TraceRecord data structure."""

    def test_default_creation(self):
        trace = TraceRecord(task="hello")
        assert trace.task == "hello"
        assert trace.id.startswith("trace_")
        assert trace.timestamp > 0
        assert trace.tool_calls == []
        assert trace.completed is False

    def test_to_dict(self):
        trace = make_trace()
        d = trace.to_dict()
        assert d["task"] == "Test task"
        assert d["completed"] is True
        assert "id" in d

    def test_from_dict(self):
        trace = make_trace()
        d = trace.to_dict()
        restored = TraceRecord.from_dict(d)
        assert restored.task == trace.task
        assert restored.completed == trace.completed
        assert restored.id == trace.id

    def test_custom_id(self):
        trace = TraceRecord(task="test", id="custom_123")
        assert trace.id == "custom_123"


# ═══════════════════════════════════════════════════════════════
#  MetricResult Tests
# ═══════════════════════════════════════════════════════════════


class TestMetricResult:
    """Test MetricResult data structure."""

    def test_creation(self):
        r = MetricResult(name="test", score=0.85, raw_value=42)
        assert r.name == "test"
        assert r.score == 0.85
        assert r.raw_value == 42

    def test_to_dict(self):
        r = MetricResult(name="test", score=0.5, details={"a": 1})
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["score"] == 0.5
        assert d["details"] == {"a": 1}

    def test_to_json(self):
        r = MetricResult(name="test", score=0.9)
        j = json.loads(r.to_json())
        assert j["name"] == "test"
        assert j["score"] == 0.9

    def test_repr(self):
        r = MetricResult(name="latency", score=0.75)
        assert "latency" in repr(r)
        assert "0.750" in repr(r)


# ═══════════════════════════════════════════════════════════════
#  TaskCompletionMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestTaskCompletionMetric:
    """Test TaskCompletionMetric."""

    @pytest.fixture
    def metric(self):
        return TaskCompletionMetric()

    def test_completed_no_expected(self, metric):
        trace = make_trace(completed=True)
        result = metric.compute(trace)
        assert result.score == 1.0
        assert result.raw_value is True

    def test_not_completed(self, metric):
        trace = make_trace(completed=False)
        result = metric.compute(trace)
        assert result.score == 0.0

    def test_with_expected_answer_match(self, metric):
        trace = make_trace(
            completed=True,
            final_answer="The temperature is 25 degrees.",
            expected_answer="25 degrees",
        )
        result = metric.compute(trace)
        assert result.score > 0.5
        assert "answer_similarity" in result.details

    def test_with_expected_answer_mismatch(self, metric):
        trace = make_trace(
            completed=True,
            final_answer="The weather is nice today.",
            expected_answer="25 degrees celsius sunny",
        )
        result = metric.compute(trace)
        # Low similarity should reduce score
        assert result.score < 1.0

    def test_batch(self, metric):
        traces = [make_trace(completed=True), make_trace(completed=False)]
        results = metric.compute_batch(traces)
        assert len(results) == 2

    def test_aggregate(self, metric):
        traces = [make_trace(completed=True), make_trace(completed=False)]
        results = metric.compute_batch(traces)
        agg = metric.aggregate(results)
        assert agg.score == 0.5
        assert agg.details["count"] == 2


# ═══════════════════════════════════════════════════════════════
#  ToolUsageMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestToolUsageMetric:
    """Test ToolUsageMetric."""

    @pytest.fixture
    def metric(self):
        return ToolUsageMetric()

    def test_no_tool_calls_completed(self, metric):
        trace = make_trace(completed=True, tool_calls=[])
        result = metric.compute(trace)
        assert result.score > 0

    def test_correct_tool_selection(self, metric):
        trace = make_trace(
            tool_calls=[{"name": "search", "arguments": {}, "success": True}],
            expected_tools=["search"],
        )
        result = metric.compute(trace)
        assert result.score > 0.8
        assert result.details["tool_selection_score"] == 1.0

    def test_wrong_tool_selection(self, metric):
        trace = make_trace(
            tool_calls=[{"name": "calc", "arguments": {}, "success": True}],
            expected_tools=["search"],
        )
        result = metric.compute(trace)
        assert result.details["tool_selection_score"] == 0.0

    def test_tool_failures(self, metric):
        trace = make_trace(
            tool_calls=[
                {"name": "search", "arguments": {}, "success": True},
                {"name": "search", "arguments": {}, "success": False},
            ],
        )
        result = metric.compute(trace)
        assert result.details["success_rate"] == 0.5
        assert result.score < 1.0

    def test_extra_tool_penalty(self, metric):
        trace = make_trace(
            tool_calls=[
                {"name": "search", "arguments": {}, "success": True},
                {"name": "calc", "arguments": {}, "success": True},
                {"name": "write", "arguments": {}, "success": True},
            ],
            expected_tools=["search"],
        )
        result = metric.compute(trace)
        assert result.details["tool_selection_score"] < 1.0

    def test_call_efficiency(self, metric):
        trace = make_trace(
            tool_calls=[
                {"name": f"tool_{i}", "arguments": {}, "success": True}
                for i in range(10)
            ],
        )
        result = metric.compute(trace)
        assert result.details["call_efficiency"] < 0.5


# ═══════════════════════════════════════════════════════════════
#  LatencyMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestLatencyMetric:
    """Test LatencyMetric."""

    def test_fast_response(self):
        metric = LatencyMetric(min_latency=1.0, max_latency=30.0)
        trace = make_trace(latency=0.5)
        result = metric.compute(trace)
        assert result.score == 1.0

    def test_slow_response(self):
        metric = LatencyMetric(min_latency=1.0, max_latency=30.0)
        trace = make_trace(latency=35.0)
        result = metric.compute(trace)
        assert result.score == 0.0

    def test_medium_response(self):
        metric = LatencyMetric(min_latency=1.0, max_latency=30.0)
        trace = make_trace(latency=15.5)  # midpoint
        result = metric.compute(trace)
        assert 0.4 < result.score < 0.6

    def test_aggregate_with_percentiles(self):
        metric = LatencyMetric()
        traces = [make_trace(latency=l) for l in [1, 5, 10, 20, 30]]
        results = metric.compute_batch(traces)
        agg = metric.aggregate(results)
        assert "p90_latency" in agg.details
        assert "median_latency" in agg.details
        assert agg.details["count"] == 5


# ═══════════════════════════════════════════════════════════════
#  TokenEfficiencyMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestTokenEfficiencyMetric:
    """Test TokenEfficiencyMetric."""

    def test_low_token_usage(self):
        metric = TokenEfficiencyMetric(max_tokens=8192)
        trace = make_trace(token_usage={"prompt": 50, "completion": 20, "total": 70})
        result = metric.compute(trace)
        assert result.score > 0.9

    def test_high_token_usage(self):
        metric = TokenEfficiencyMetric(max_tokens=8192)
        trace = make_trace(token_usage={"prompt": 5000, "completion": 4000, "total": 9000})
        result = metric.compute(trace)
        assert result.score < 0.3

    def test_zero_tokens(self):
        metric = TokenEfficiencyMetric()
        trace = make_trace(token_usage={"prompt": 0, "completion": 0, "total": 0})
        result = metric.compute(trace)
        assert result.score == 0.0

    def test_ratio_check(self):
        metric = TokenEfficiencyMetric(max_tokens=10000, ideal_ratio=0.3)
        trace = make_trace(token_usage={"prompt": 700, "completion": 300, "total": 1000})
        result = metric.compute(trace)
        assert result.details["completion_ratio"] == 0.3
        assert result.details["ratio_score"] == 1.0


# ═══════════════════════════════════════════════════════════════
#  ReasoningQualityMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestReasoningQualityMetric:
    """Test ReasoningQualityMetric."""

    @pytest.fixture
    def metric(self):
        return ReasoningQualityMetric()

    def test_no_steps(self, metric):
        trace = make_trace(reasoning_steps=[])
        result = metric.compute(trace)
        assert result.score == 0.0

    def test_good_reasoning(self, metric):
        trace = make_trace(reasoning_steps=[
            "First, I need to analyze the problem because it's complex.",
            "Then, I should search for relevant information.",
            "Therefore, I can conclude the answer based on the observation.",
        ])
        result = metric.compute(trace)
        assert result.score > 0.5
        assert result.details["marker_score"] > 0

    def test_too_few_steps(self, metric):
        trace = make_trace(reasoning_steps=["Just do it."])
        result = metric.compute(trace)
        assert result.details["count_score"] < 1.0

    def test_too_many_steps(self, metric):
        trace = make_trace(reasoning_steps=[f"Step {i}" for i in range(15)])
        result = metric.compute(trace)
        assert result.details["count_score"] < 1.0

    def test_coherent_steps(self, metric):
        trace = make_trace(reasoning_steps=[
            "I need to search for the weather data.",
            "The weather data shows it is raining.",
            "Since it is raining, I should bring an umbrella.",
        ])
        result = metric.compute(trace)
        assert result.details["coherence_score"] > 0.0


# ═══════════════════════════════════════════════════════════════
#  HallucinationMetric Tests
# ═══════════════════════════════════════════════════════════════


class TestHallucinationMetric:
    """Test HallucinationMetric."""

    @pytest.fixture
    def metric(self):
        return HallucinationMetric()

    def test_no_tool_outputs(self, metric):
        trace = make_trace(tool_outputs=[])
        result = metric.compute(trace)
        assert result.score == 0.5

    def test_consistent_output(self, metric):
        trace = make_trace(
            final_answer="The temperature is 25 degrees.",
            tool_outputs=["The weather data shows temperature is 25 degrees today."],
        )
        result = metric.compute(trace)
        assert result.score > 0.5
        assert result.details["hallucination_rate"] < 0.5

    def test_hallucinated_numbers(self, metric):
        trace = make_trace(
            final_answer="The temperature is 99 degrees.",
            tool_outputs=["The weather data shows temperature is 25 degrees."],
        )
        result = metric.compute(trace)
        assert result.details["hallucination_rate"] > 0.0
        assert "99" in result.details["unsupported_numbers"]

    def test_fully_supported(self, metric):
        trace = make_trace(
            final_answer="The temperature is 25 degrees and sunny.",
            tool_outputs=["The temperature is 25 degrees and it is sunny today."],
        )
        result = metric.compute(trace)
        assert result.score > 0.8
        assert result.details["number_support_rate"] == 1.0


# ═══════════════════════════════════════════════════════════════
#  MetricSuite Tests
# ═══════════════════════════════════════════════════════════════


class TestMetricSuite:
    """Test MetricSuite."""

    def test_add_remove(self):
        suite = MetricSuite()
        suite.add(TaskCompletionMetric())
        assert len(suite.metrics) == 1
        suite.add(LatencyMetric())
        assert len(suite.metrics) == 2
        suite.remove("latency")
        assert len(suite.metrics) == 1
        assert "latency" not in suite.names

    def test_evaluate_single(self):
        suite = MetricSuite()
        suite.add(TaskCompletionMetric())
        suite.add(LatencyMetric())
        trace = make_trace(completed=True, latency=2.0)
        results = suite.evaluate(trace)
        assert "task_completion" in results
        assert "latency" in results
        assert results["task_completion"].score == 1.0

    def test_evaluate_batch(self):
        suite = MetricSuite()
        suite.add(TaskCompletionMetric())
        traces = [make_trace(completed=True), make_trace(completed=False)]
        report = suite.evaluate_batch(traces)
        assert report.trace_count == 2
        assert "task_completion" in report.metrics
        assert report.overall_score > 0

    def test_default_metrics(self):
        suite = get_default_metrics()
        assert len(suite.metrics) == 6
        assert "task_completion" in suite.names
        assert "tool_usage" in suite.names
        assert "latency" in suite.names
        assert "token_efficiency" in suite.names
        assert "reasoning_quality" in suite.names
        assert "hallucination" in suite.names

    def test_chainable(self):
        suite = MetricSuite()
        result = suite.add(TaskCompletionMetric()).add(LatencyMetric())
        assert result is suite

    def test_report_to_json(self):
        suite = get_default_metrics()
        traces = [make_trace(completed=True)]
        report = suite.evaluate_batch(traces)
        j = json.loads(report.to_json())
        assert "overall_score" in j
        assert "metrics" in j


# ═══════════════════════════════════════════════════════════════
#  BenchmarkCase Tests
# ═══════════════════════════════════════════════════════════════


class TestBenchmarkCase:
    """Test BenchmarkCase."""

    def test_creation(self):
        case = BenchmarkCase(
            name="test1",
            input="What is 2+2?",
            expected_answer="4",
        )
        assert case.name == "test1"
        assert case.id.startswith("case_")

    def test_auto_name(self):
        case = BenchmarkCase(input="Search for weather")
        assert case.name == "Search for weather"

    def test_to_dict_from_dict(self):
        case = BenchmarkCase(name="test", input="hello", expected_answer="hi")
        d = case.to_dict()
        restored = BenchmarkCase.from_dict(d)
        assert restored.name == case.name
        assert restored.input == case.input

    def test_tags(self):
        case = BenchmarkCase(name="tagged", input="test", tags=["math", "easy"])
        assert "math" in case.tags


# ═══════════════════════════════════════════════════════════════
#  BenchmarkSuite Tests
# ═══════════════════════════════════════════════════════════════


class TestBenchmarkSuite:
    """Test BenchmarkSuite."""

    def test_add_cases(self):
        suite = BenchmarkSuite(name="test")
        case1 = BenchmarkCase(name="c1", input="hello")
        case2 = BenchmarkCase(name="c2", input="world")
        suite.add_case(case1).add_case(case2)
        assert suite.size == 2

    def test_add_batch(self):
        suite = BenchmarkSuite(name="test")
        cases = [BenchmarkCase(name=f"c{i}", input=f"q{i}") for i in range(5)]
        suite.add_cases(cases)
        assert suite.size == 5

    def test_remove_case(self):
        suite = BenchmarkSuite(name="test")
        case = BenchmarkCase(name="c1", input="hello")
        suite.add_case(case)
        suite.remove_case(case.id)
        assert suite.size == 0

    def test_filter_by_tag(self):
        suite = BenchmarkSuite(name="test")
        suite.add_case(BenchmarkCase(name="c1", input="a", tags=["math"]))
        suite.add_case(BenchmarkCase(name="c2", input="b", tags=["code"]))
        suite.add_case(BenchmarkCase(name="c3", input="c", tags=["math", "easy"]))
        math_cases = suite.filter_by_tag("math")
        assert len(math_cases) == 2

    def test_to_dict_from_dict(self):
        suite = BenchmarkSuite(name="test", description="desc")
        suite.add_case(BenchmarkCase(name="c1", input="hello"))
        d = suite.to_dict()
        restored = BenchmarkSuite.from_dict(d)
        assert restored.name == "test"
        assert restored.size == 1


# ═══════════════════════════════════════════════════════════════
#  BenchmarkRunner Tests
# ═══════════════════════════════════════════════════════════════


class MockAgent:
    """Mock agent for benchmark testing."""

    def __init__(self, responses=None, fail=False):
        self._responses = responses or ["Done"]
        self._index = 0
        self.fail = fail

    async def run(self, user_message: str):
        if self.fail:
            raise RuntimeError("Agent failed")
        resp = self._responses[self._index % len(self._responses)]
        self._index += 1

        class Result:
            content = resp
            is_complete = True
            history = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": resp},
            ]

        return Result()


class TestBenchmarkRunner:
    """Test BenchmarkRunner."""

    @pytest.fixture
    def runner(self):
        return BenchmarkRunner()

    @pytest.fixture
    def suite(self):
        s = BenchmarkSuite(name="test_suite")
        s.add_case(BenchmarkCase(
            name="case1",
            input="What is the weather?",
            expected_answer="sunny",
            expected_tools=["search"],
        ))
        s.add_case(BenchmarkCase(
            name="case2",
            input="Calculate 2+2",
            expected_answer="4",
        ))
        return s

    @pytest.mark.asyncio
    async def test_run_sequential(self, runner, suite):
        agent = MockAgent(responses=["It is sunny today.", "The answer is 4."])
        report = await runner.run(suite, agent)
        assert len(report.results) == 2
        assert report.suite_name == "test_suite"

    @pytest.mark.asyncio
    async def test_run_single(self, runner):
        case = BenchmarkCase(name="c1", input="Hello", expected_answer="Hi")
        agent = MockAgent(responses=["Hi there"])
        result = await runner.run_single(case, agent)
        assert result.case_name == "c1"
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_timeout(self, runner):
        case = BenchmarkCase(name="timeout", input="test", timeout=0.01)
        agent = MockAgent()
        # Add artificial delay
        original_run = agent.run

        async def slow_run(msg):
            await asyncio.sleep(1)
            return await original_run(msg)

        agent.run = slow_run
        result = await runner.run_single(case, agent)
        assert result.timed_out is True
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_error_handling(self, runner):
        case = BenchmarkCase(name="error", input="test")
        agent = MockAgent(fail=True)
        result = await runner.run_single(case, agent)
        assert result.error is not None
        assert "Agent failed" in result.error
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_report_summary(self, runner, suite):
        agent = MockAgent(responses=["It is sunny today.", "The answer is 4."])
        report = await runner.run(suite, agent)
        summary = report.compute_summary()
        assert summary["total"] == 2
        assert "pass_rate" in summary
        assert "metric_summaries" in summary

    @pytest.mark.asyncio
    async def test_report_markdown(self, runner, suite):
        agent = MockAgent(responses=["It is sunny today.", "The answer is 4."])
        report = await runner.run(suite, agent)
        md = report.to_markdown()
        assert "# Benchmark Report" in md
        assert "test_suite" in md
        assert "## Case Results" in md

    @pytest.mark.asyncio
    async def test_report_json(self, runner, suite):
        agent = MockAgent(responses=["sunny", "4"])
        report = await runner.run(suite, agent)
        j = json.loads(report.to_json())
        assert j["suite_name"] == "test_suite"
        assert len(j["results"]) == 2

    @pytest.mark.asyncio
    async def test_report_save(self, runner, suite, tmp_path):
        agent = MockAgent(responses=["sunny", "4"])
        report = await runner.run(suite, agent)
        filepath = str(tmp_path / "benchmark_report")
        report.save(filepath)
        assert os.path.exists(filepath + ".json")
        assert os.path.exists(filepath + ".md")

    @pytest.mark.asyncio
    async def test_parallel_runner(self, suite):
        runner = BenchmarkRunner(parallel=True, max_concurrent=2)
        agent = MockAgent(responses=["sunny", "4"])
        report = await runner.run(suite, agent)
        assert len(report.results) == 2

    @pytest.mark.asyncio
    async def test_trace_extraction_with_string_result(self, runner):
        case = BenchmarkCase(name="c1", input="hello", expected_answer="world")

        class StringAgent:
            async def run(self, msg):
                return "world"

        result = await runner.run_single(case, StringAgent())
        assert result.trace is not None
        assert result.trace.final_answer == "world"

    @pytest.mark.asyncio
    async def test_trace_extraction_with_dict_result(self, runner):
        case = BenchmarkCase(name="c1", input="hello")

        class DictAgent:
            async def run(self, msg):
                return {"content": "answer", "completed": True, "history": [], "token_usage": {"total": 100}}

        result = await runner.run_single(case, DictAgent())
        assert result.trace is not None
        assert result.trace.final_answer == "answer"
        assert result.trace.token_usage["total"] == 100

    @pytest.mark.asyncio
    async def test_custom_trace_extractor(self, runner):
        case = BenchmarkCase(name="c1", input="hello")

        class SimpleAgent:
            async def run(self, msg):
                return "result"

        async def extractor(case, agent_result):
            return TraceRecord(
                task=case.input,
                completed=True,
                final_answer=agent_result,
                latency=1.0,
                tool_outputs=["some output"],
            )

        result = await runner.run_single(case, SimpleAgent(), trace_extractor=extractor)
        assert result.trace is not None
        assert result.trace.tool_outputs == ["some output"]

    @pytest.mark.asyncio
    async def test_case_result_passed(self):
        result = CaseResult(
            case_id="c1",
            case_name="test",
            trace=TraceRecord(task="t", completed=True),
            metrics={},
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_case_result_failed(self):
        result = CaseResult(
            case_id="c1",
            case_name="test",
            error="some error",
        )
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_default_trace_extraction_with_loop_result(self, runner):
        """Test that default extraction works with LoopResult-like objects."""
        case = BenchmarkCase(name="c1", input="hello", expected_answer="hello")

        class LoopResultAgent:
            async def run(self, msg):
                class LoopResult:
                    content = "hello world"
                    is_complete = True
                    history = [
                        {"role": "user", "content": msg},
                        {"role": "assistant", "content": "hello world"},
                    ]

                return LoopResult()

        result = await runner.run_single(case, LoopResultAgent())
        assert result.trace.final_answer == "hello world"
        assert result.trace.completed is True


# ═══════════════════════════════════════════════════════════════
#  StatisticalSignificance Tests
# ═══════════════════════════════════════════════════════════════


class TestStatisticalSignificance:
    """Test StatisticalSignificance utility class."""

    def test_welch_t_test_significant(self):
        # Clearly different groups
        a = [1.0, 1.1, 0.9, 1.0, 1.05]
        b = [2.0, 2.1, 1.9, 2.0, 2.05]
        t_stat, p_value = StatisticalSignificance.welch_t_test(a, b)
        assert abs(t_stat) > 10
        assert p_value < 0.05

    def test_welch_t_test_not_significant(self):
        # Similar groups
        a = [1.0, 1.1, 0.9, 1.0, 1.05]
        b = [1.0, 1.1, 0.9, 1.0, 1.05]
        t_stat, p_value = StatisticalSignificance.welch_t_test(a, b)
        assert abs(t_stat) < 1.0
        assert p_value > 0.05

    def test_welch_t_test_insufficient_data(self):
        t_stat, p_value = StatisticalSignificance.welch_t_test([1.0], [2.0])
        assert t_stat == 0.0
        assert p_value == 1.0

    def test_mann_whitney_u(self):
        a = [1, 2, 3, 4, 5]
        b = [6, 7, 8, 9, 10]
        u_stat, p_value = StatisticalSignificance.mann_whitney_u(a, b)
        assert u_stat == 0  # All of B ranks higher than A
        assert p_value < 0.05

    def test_mann_whitney_u_empty(self):
        u_stat, p_value = StatisticalSignificance.mann_whitney_u([], [])
        assert u_stat == 0.0
        assert p_value == 1.0

    def test_bootstrap_ci(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
        lower, upper = StatisticalSignificance.bootstrap_ci(data, n_bootstrap=1000)
        assert lower < upper
        # CI should contain the mean
        assert lower < 3.0 < upper

    def test_bootstrap_ci_empty(self):
        lower, upper = StatisticalSignificance.bootstrap_ci([])
        assert lower == 0.0
        assert upper == 0.0

    def test_cohens_d_large(self):
        a = [1.0, 1.0, 1.0, 1.0]
        b = [5.0, 5.0, 5.0, 5.0]
        d = StatisticalSignificance.cohens_d(a, b)
        assert d > 0.8  # Large effect

    def test_cohens_d_zero(self):
        a = [1.0, 1.0, 1.0, 1.0]
        b = [1.0, 1.0, 1.0, 1.0]
        d = StatisticalSignificance.cohens_d(a, b)
        assert d == 0.0

    def test_cohens_d_insufficient(self):
        d = StatisticalSignificance.cohens_d([1.0], [2.0])
        assert d == 0.0

    def test_power_analysis(self):
        # Large effect + decent sample → high power
        power = StatisticalSignificance.power_analysis(1.0, 50, 0.05)
        assert power > 0.8

    def test_power_analysis_zero_effect(self):
        power = StatisticalSignificance.power_analysis(0.0, 100, 0.05)
        assert power == 0.0


# ═══════════════════════════════════════════════════════════════
#  ABTest Tests
# ═══════════════════════════════════════════════════════════════


class TestABTest:
    """Test ABTest class."""

    def test_add_results(self):
        test = ABTest(name="test")
        test.add_result_a(0.8).add_result_b(0.9)
        test.add_results_a([0.85, 0.82])
        test.add_results_b([0.88, 0.91])
        assert test.sample_size_a == 3
        assert test.sample_size_b == 3

    def test_analyze_significant(self):
        test = ABTest(
            name="sig_test",
            variant_a_name="control",
            variant_b_name="treatment",
        )
        # Create clearly different groups
        test.add_results_a([0.80, 0.82, 0.78, 0.81, 0.79, 0.83, 0.80, 0.81])
        test.add_results_b([0.90, 0.92, 0.88, 0.91, 0.89, 0.93, 0.90, 0.91])

        result = test.analyze()
        assert result.is_significant()
        assert result.mean_b > result.mean_a
        assert result.delta > 0
        assert result.cohens_d > 0.8
        assert "Recommend" in result.recommendation

    def test_analyze_not_significant(self):
        test = ABTest(name="nonsig_test")
        test.add_results_a([0.80, 0.82, 0.78, 0.81, 0.79])
        test.add_results_b([0.81, 0.80, 0.82, 0.79, 0.81])

        result = test.analyze()
        assert not result.is_significant()
        assert result.p_value > 0.05

    def test_analyze_insufficient_data(self):
        test = ABTest(name="small_test")
        test.add_result_a(0.8)
        test.add_result_b(0.9)

        result = test.analyze()
        assert not result.is_significant()
        assert "Insufficient" in result.recommendation

    def test_result_summary(self):
        test = ABTest(name="summary_test")
        test.add_results_a([0.80, 0.82, 0.78, 0.81])
        test.add_results_b([0.85, 0.87, 0.83, 0.86])

        result = test.analyze()
        summary = result.summary()
        assert "A/B Test: summary_test" in summary
        assert "Variant A" in summary
        assert "Variant B" in summary

    def test_result_to_dict(self):
        test = ABTest(name="dict_test")
        test.add_results_a([0.8, 0.85])
        test.add_results_b([0.9, 0.95])

        result = test.analyze()
        d = result.to_dict()
        assert d["test_name"] == "dict_test"
        assert "mean_a" in d
        assert "mean_b" in d
        assert "p_value" in d

    def test_result_to_json(self):
        test = ABTest(name="json_test")
        test.add_results_a([0.8, 0.85])
        test.add_results_b([0.9, 0.95])

        result = test.analyze()
        j = json.loads(result.to_json())
        assert j["test_name"] == "json_test"

    def test_effect_size_label(self):
        result = ABTestResult(cohens_d=1.5)
        assert result.effect_size_label() == "large"

        result = ABTestResult(cohens_d=0.6)
        assert result.effect_size_label() == "medium"

        result = ABTestResult(cohens_d=0.3)
        assert result.effect_size_label() == "small"

        result = ABTestResult(cohens_d=0.1)
        assert result.effect_size_label() == "negligible"

    def test_to_dict_from_dict(self):
        test = ABTest(name="persist_test", variant_a_name="v1", variant_b_name="v2")
        test.add_results_a([0.8, 0.85])
        test.add_results_b([0.9, 0.95])

        d = test.to_dict()
        restored = ABTest.from_dict(d)
        assert restored.name == "persist_test"
        assert restored.sample_size_a == 2
        assert restored.sample_size_b == 2

    def test_degradation_recommendation(self):
        test = ABTest(name="degrade_test")
        test.add_results_a([0.90, 0.92, 0.88, 0.91, 0.89, 0.93, 0.90, 0.91])
        test.add_results_b([0.80, 0.82, 0.78, 0.81, 0.79, 0.83, 0.80, 0.81])

        result = test.analyze()
        assert result.is_significant()
        assert "worse" in result.recommendation.lower() or "degradation" in result.recommendation.lower()

    def test_ci_values(self):
        test = ABTest(name="ci_test")
        test.add_results_a([0.80, 0.82, 0.78, 0.81, 0.79])
        test.add_results_b([0.85, 0.87, 0.83, 0.86, 0.84])

        result = test.analyze()
        assert result.ci_a[0] < result.ci_a[1]
        assert result.ci_b[0] < result.ci_b[1]

    def test_relative_improvement(self):
        test = ABTest(name="rel_test")
        test.add_results_a([0.50, 0.52, 0.48, 0.51, 0.49])
        test.add_results_b([0.60, 0.62, 0.58, 0.61, 0.59])

        result = test.analyze()
        assert result.relative_improvement > 0.15  # ~20% improvement
