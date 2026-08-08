"""基准测试框架 — 结构化的 Agent 性能测试.

核心组件::

    ┌──────────────────────────────────────────────────────┐
    │  BenchmarkCase   — 单个测试用例（输入+期望+评估标准）    │
    │  BenchmarkSuite  — 测试套件管理（用例集合）              │
    │  BenchmarkRunner — 执行器（支持并行运行）                │
    │  BenchmarkReport — 结果报告生成（JSON + Markdown）       │
    └──────────────────────────────────────────────────────┘

设计原则：
- **异步执行**：所有运行方法使用 async/await.
- **可注入 Agent**：接受任何实现 ``run(user_message) -> result`` 接口的对象.
- **指标集成**：与 ``metrics.py`` 深度集成，自动计算所有指标.
- **JSON + Markdown 报告**：生成机器可读和人类可读的双格式报告.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np

from .metrics import (
    MetricBase,
    MetricResult,
    MetricSuite,
    TraceRecord,
    get_default_metrics,
)


# ═══════════════════════════════════════════════════════════════
#  Benchmark Case
# ═══════════════════════════════════════════════════════════════


@dataclass
class BenchmarkCase:
    """单个基准测试用例.

    Attributes:
        id:            用例唯一标识符（自动生成）.
        name:          用例名称.
        input:         用户输入消息.
        expected_answer:  期望的输出文本（可选）.
        expected_tools:   期望使用的工具名称列表（可选）.
        expected_completed: 期望任务是否完成（默认 True）.
        tags:          标签列表（用于分类和筛选）.
        timeout:       超时时间（秒），超时视为失败.
        metadata:      额外元数据.
    """

    name: str = ""
    input: str = ""
    expected_answer: str = ""
    expected_tools: List[str] = field(default_factory=list)
    expected_completed: bool = True
    tags: List[str] = field(default_factory=list)
    timeout: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"case_{uuid.uuid4().hex[:12]}"
        if not self.name:
            self.name = self.input[:50] if self.input else self.id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BenchmarkCase":
        return cls(**d)

    def __repr__(self) -> str:
        return f"BenchmarkCase(name={self.name!r}, id={self.id})"


# ═══════════════════════════════════════════════════════════════
#  Case Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class CaseResult:
    """单个测试用例的执行结果.

    Attributes:
        case_id:     对应的 BenchmarkCase ID.
        case_name:   用例名称.
        trace:       执行轨迹记录.
        metrics:     指标评估结果（指标名 → MetricResult）.
        error:       执行错误信息（如有）.
        timed_out:   是否超时.
        duration:    实际执行时间（秒）.
    """

    case_id: str
    case_name: str
    trace: Optional[TraceRecord] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timed_out: bool = False
    duration: float = 0.0

    @property
    def passed(self) -> bool:
        """是否通过（无错误、无超时、任务完成）."""
        if self.error or self.timed_out:
            return False
        if self.trace is None:
            return False
        return self.trace.completed

    @property
    def overall_score(self) -> float:
        """所有指标的平均分数."""
        if not self.metrics:
            return 0.0
        scores = []
        for v in self.metrics.values():
            if isinstance(v, dict):
                scores.append(v.get("score", 0.0))
            elif isinstance(v, MetricResult):
                scores.append(v.score)
        return round(float(np.mean(scores)), 4) if scores else 0.0

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "passed": self.passed,
            "overall_score": self.overall_score,
            "error": self.error,
            "timed_out": self.timed_out,
            "duration": round(self.duration, 4),
            "trace": self.trace.to_dict() if self.trace else None,
            "metrics": {
                k: v.to_dict() if isinstance(v, MetricResult) else v
                for k, v in self.metrics.items()
            },
        }


# ═══════════════════════════════════════════════════════════════
#  Benchmark Suite
# ═══════════════════════════════════════════════════════════════


class BenchmarkSuite:
    """基准测试套件 — 管理一组测试用例.

    Usage::

        suite = BenchmarkSuite(name="core_tests")
        suite.add_case(BenchmarkCase(
            name="search_test",
            input="Search for weather in Beijing",
            expected_tools=["search"],
            expected_answer="sunny",
        ))
        suite.add_case(...)

        runner = BenchmarkRunner()
        report = await runner.run(suite, agent=my_agent)
    """

    def __init__(
        self,
        name: str = "default",
        cases: Optional[List[BenchmarkCase]] = None,
        description: str = "",
    ):
        self.name = name
        self.description = description
        self._cases: List[BenchmarkCase] = cases or []

    def add_case(self, case: BenchmarkCase) -> "BenchmarkSuite":
        """添加测试用例，返回 self 以支持链式调用."""
        self._cases.append(case)
        return self

    def add_cases(self, cases: List[BenchmarkCase]) -> "BenchmarkSuite":
        """批量添加测试用例."""
        self._cases.extend(cases)
        return self

    def remove_case(self, case_id: str) -> "BenchmarkSuite":
        """按 ID 移除测试用例."""
        self._cases = [c for c in self._cases if c.id != case_id]
        return self

    @property
    def cases(self) -> List[BenchmarkCase]:
        return list(self._cases)

    @property
    def size(self) -> int:
        return len(self._cases)

    def filter_by_tag(self, tag: str) -> List[BenchmarkCase]:
        """按标签筛选测试用例."""
        return [c for c in self._cases if tag in c.tags]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "size": self.size,
            "cases": [c.to_dict() for c in self._cases],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BenchmarkSuite":
        cases = [BenchmarkCase.from_dict(c) for c in d.get("cases", [])]
        return cls(
            name=d.get("name", "default"),
            description=d.get("description", ""),
            cases=cases,
        )


# ═══════════════════════════════════════════════════════════════
#  Benchmark Report
# ═══════════════════════════════════════════════════════════════


@dataclass
class BenchmarkReport:
    """基准测试结果报告.

    Attributes:
        suite_name:   测试套件名称.
        results:      每个用例的结果列表.
        summary:      汇总统计.
        timestamp:    报告时间戳.
        id:           报告唯一标识符.
    """

    suite_name: str = ""
    results: List[CaseResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"bench_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def compute_summary(self) -> Dict[str, Any]:
        """计算汇总统计."""
        total = len(self.results)
        if total == 0:
            return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        scores = [r.overall_score for r in self.results]
        durations = [r.duration for r in self.results]

        # 各指标的汇总
        metric_summaries: Dict[str, Dict[str, float]] = {}
        for result in self.results:
            for metric_name, metric_val in result.metrics.items():
                if isinstance(metric_val, MetricResult):
                    if metric_name not in metric_summaries:
                        metric_summaries[metric_name] = []
                    metric_summaries[metric_name].append(metric_val.score)
                elif isinstance(metric_val, dict):
                    score = metric_val.get("score", 0.0)
                    if metric_name not in metric_summaries:
                        metric_summaries[metric_name] = []
                    metric_summaries[metric_name].append(score)

        aggregated_metrics = {}
        for name, score_list in metric_summaries.items():
            arr = np.array(score_list)
            aggregated_metrics[name] = {
                "mean": round(float(np.mean(arr)), 4),
                "std": round(float(np.std(arr)), 4),
                "min": round(float(np.min(arr)), 4),
                "max": round(float(np.max(arr)), 4),
            }

        self.summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 4),
            "overall_score": round(float(np.mean(scores)), 4) if scores else 0.0,
            "avg_duration": round(float(np.mean(durations)), 4) if durations else 0.0,
            "metric_summaries": aggregated_metrics,
        }
        return self.summary

    def to_dict(self) -> dict:
        if not self.summary:
            self.compute_summary()
        return {
            "id": self.id,
            "suite_name": self.suite_name,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        """生成 Markdown 格式的报告."""
        if not self.summary:
            self.compute_summary()

        s = self.summary
        lines = [
            f"# Benchmark Report: {self.suite_name}",
            "",
            f"- **Report ID:** {self.id}",
            f"- **Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))}",
            f"- **Total Cases:** {s.get('total', 0)}",
            f"- **Passed:** {s.get('passed', 0)}",
            f"- **Failed:** {s.get('failed', 0)}",
            f"- **Pass Rate:** {s.get('pass_rate', 0):.1%}",
            f"- **Overall Score:** {s.get('overall_score', 0):.3f}",
            f"- **Avg Duration:** {s.get('avg_duration', 0):.2f}s",
            "",
            "## Metric Summaries",
            "",
            "| Metric | Mean | Std | Min | Max |",
            "|--------|------|-----|-----|-----|",
        ]

        for name, stats in s.get("metric_summaries", {}).items():
            lines.append(
                f"| {name} | {stats['mean']:.4f} | {stats['std']:.4f} | "
                f"{stats['min']:.4f} | {stats['max']:.4f} |"
            )

        lines.extend(["", "## Case Results", "",
                       "| Case | Passed | Score | Duration | Error |",
                       "|------|--------|-------|----------|-------|"])

        for r in self.results:
            error = r.error or ""
            lines.append(
                f"| {r.case_name} | {'✅' if r.passed else '❌'} | "
                f"{r.overall_score:.3f} | {r.duration:.2f}s | {error} |"
            )

        return "\n".join(lines)

    def save(self, filepath: str) -> None:
        """保存报告到文件（JSON 和 Markdown）."""
        base = filepath
        if base.endswith(".json"):
            json_path = base
            md_path = base[:-5] + ".md"
        else:
            json_path = base + ".json"
            md_path = base + ".md"

        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())


# ═══════════════════════════════════════════════════════════════
#  Benchmark Runner
# ═══════════════════════════════════════════════════════════════


class BenchmarkRunner:
    """基准测试执行器.

    执行 BenchmarkSuite 中的所有用例，收集执行轨迹，计算指标.

    Args:
        metrics: 使用的指标组合，默认为全部内置指标.
        parallel: 是否并行执行用例（默认 False，串行更可预测）.
        max_concurrent: 并行时最大并发数.

    Usage::

        runner = BenchmarkRunner()
        report = await runner.run(suite, agent=my_agent)

        # 保存报告
        report.save("reports/benchmark")
    """

    def __init__(
        self,
        metrics: Optional[MetricSuite] = None,
        parallel: bool = False,
        max_concurrent: int = 5,
    ):
        self.metric_suite = metrics or get_default_metrics()
        self.parallel = parallel
        self.max_concurrent = max_concurrent

    async def run(
        self,
        suite: BenchmarkSuite,
        agent: Any,
        trace_extractor: Optional[Callable] = None,
    ) -> BenchmarkReport:
        """执行整个测试套件.

        Args:
            suite: 要执行的测试套件.
            agent: Agent 对象，需实现 ``async run(user_message: str) -> result`` 方法.
            trace_extractor: 可选的轨迹提取函数，
                ``async (case, agent_result) -> TraceRecord``.
                如果未提供，使用默认提取逻辑.

        Returns:
            BenchmarkReport 实例.
        """
        if self.parallel and suite.size > 1:
            results = await self._run_parallel(suite, agent, trace_extractor)
        else:
            results = await self._run_sequential(suite, agent, trace_extractor)

        report = BenchmarkReport(
            suite_name=suite.name,
            results=results,
        )
        report.compute_summary()
        return report

    async def run_single(
        self,
        case: BenchmarkCase,
        agent: Any,
        trace_extractor: Optional[Callable] = None,
    ) -> CaseResult:
        """执行单个测试用例."""
        start_time = time.time()

        try:
            # 执行超时控制
            agent_result = await asyncio.wait_for(
                agent.run(case.input),
                timeout=case.timeout,
            )
            duration = time.time() - start_time

            # 提取轨迹
            if trace_extractor:
                trace = await trace_extractor(case, agent_result)
            else:
                trace = self._default_trace_extraction(case, agent_result, duration)

            # 计算指标
            metric_results = self.metric_suite.evaluate(trace)
            # 转换为可序列化格式
            metrics_dict = {k: v for k, v in metric_results.items()}

            return CaseResult(
                case_id=case.id,
                case_name=case.name,
                trace=trace,
                metrics=metrics_dict,
                duration=duration,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return CaseResult(
                case_id=case.id,
                case_name=case.name,
                error=f"Timeout after {case.timeout}s",
                timed_out=True,
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return CaseResult(
                case_id=case.id,
                case_name=case.name,
                error=str(e),
                duration=duration,
            )

    # ── 内部方法 ──────────────────────────────────────────

    async def _run_sequential(
        self,
        suite: BenchmarkSuite,
        agent: Any,
        trace_extractor: Optional[Callable],
    ) -> List[CaseResult]:
        """串行执行所有用例."""
        results = []
        for case in suite.cases:
            result = await self.run_single(case, agent, trace_extractor)
            results.append(result)
        return results

    async def _run_parallel(
        self,
        suite: BenchmarkSuite,
        agent: Any,
        trace_extractor: Optional[Callable],
    ) -> List[CaseResult]:
        """并行执行所有用例（使用信号量限制并发）."""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_with_limit(case: BenchmarkCase) -> CaseResult:
            async with semaphore:
                return await self.run_single(case, agent, trace_extractor)

        tasks = [run_with_limit(case) for case in suite.cases]
        return await asyncio.gather(*tasks)

    def _default_trace_extraction(
        self,
        case: BenchmarkCase,
        agent_result: Any,
        duration: float,
    ) -> TraceRecord:
        """默认的轨迹提取逻辑.

        尝试从 agent_result 中提取常见字段.
        agent_result 可以是:
        - LoopResult (suyi.core.loop.LoopResult)
        - 字符串
        - 字典
        - 任意具有 ``content`` 属性的对象
        """
        # 从结果中提取最终回答
        final_answer = ""
        completed = False
        history: list = []
        token_usage: dict = {}

        if hasattr(agent_result, "content"):
            final_answer = agent_result.content or ""
            completed = getattr(agent_result, "is_complete", True)
            history = getattr(agent_result, "history", [])
        elif isinstance(agent_result, str):
            final_answer = agent_result
            completed = True
        elif isinstance(agent_result, dict):
            final_answer = agent_result.get("content", "")
            completed = agent_result.get("completed", True)
            history = agent_result.get("history", [])
            token_usage = agent_result.get("token_usage", {})

        # 从历史中提取工具调用信息
        tool_calls: List[Dict[str, Any]] = []
        tool_outputs: List[str] = []
        reasoning_steps: List[str] = []

        for msg in history:
            role = msg.get("role", "")
            if role == "assistant":
                content = msg.get("content", "")
                if content:
                    reasoning_steps.append(content)
                if "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", tc)
                        tool_calls.append({
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", {}),
                            "success": True,
                        })
            elif role == "tool":
                tool_outputs.append(msg.get("content", ""))

        # 如果期望答案不为空，做简单匹配判断完成
        if case.expected_answer and final_answer:
            expected_lower = case.expected_answer.lower()
            actual_lower = final_answer.lower()
            if expected_lower not in actual_lower:
                completed = False

        return TraceRecord(
            task=case.input,
            completed=completed and case.expected_completed,
            tool_calls=tool_calls,
            expected_tools=case.expected_tools,
            final_answer=final_answer,
            expected_answer=case.expected_answer,
            latency=duration,
            token_usage=token_usage,
            reasoning_steps=reasoning_steps,
            tool_outputs=tool_outputs,
        )
