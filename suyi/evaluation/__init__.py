"""Suyi Evaluation 模块 — Agent 评估框架.

提供多维度评估指标、基准测试框架和 A/B 测试：

    MetricSuite              — 指标组合器（6 个内置指标）
    BenchmarkSuite / Runner  — 基准测试套件与执行器
    ABTest / ABTestResult    — A/B 测试与统计分析

内置指标：
    TaskCompletionMetric     — 任务完成率
    ToolUsageMetric          — 工具使用效率
    LatencyMetric            — 响应延迟
    TokenEfficiencyMetric    — Token 使用效率
    ReasoningQualityMetric   — 推理质量
    HallucinationMetric      — 幻觉检测

使用示例::

    from suyi.evaluation import MetricSuite, BenchmarkRunner, ABTest

    # 指标评估
    suite = MetricSuite()
    suite.add(TaskCompletionMetric())
    results = suite.evaluate(trace)

    # 基准测试
    runner = BenchmarkRunner()
    report = await runner.run(suite_obj, agent=my_agent)

    # A/B 测试
    test = ABTest(name="prompt_v2", variant_a_name="v1", variant_b_name="v2")
    test.add_results_a([0.85, 0.90])
    test.add_results_b([0.92, 0.95])
    result = test.analyze()
    print(result.is_significant())
"""

from .metrics import (
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
)
from .benchmark import (
    BenchmarkCase,
    CaseResult,
    BenchmarkSuite,
    BenchmarkRunner,
    BenchmarkReport,
)
from .ab_testing import (
    ABTest,
    ABTestResult,
    StatisticalSignificance,
)

__all__ = [
    # Metrics
    "MetricBase",
    "MetricResult",
    "MetricSuite",
    "SuiteReport",
    "TraceRecord",
    "TaskCompletionMetric",
    "ToolUsageMetric",
    "LatencyMetric",
    "TokenEfficiencyMetric",
    "ReasoningQualityMetric",
    "HallucinationMetric",
    "get_default_metrics",
    # Benchmark
    "BenchmarkCase",
    "CaseResult",
    "BenchmarkSuite",
    "BenchmarkRunner",
    "BenchmarkReport",
    # A/B Testing
    "ABTest",
    "ABTestResult",
    "StatisticalSignificance",
]
