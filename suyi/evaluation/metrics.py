"""Agent 评估指标体系 — 多维度量化 Agent 表现.

评估维度::

    ┌──────────────────────────────────────────────────────┐
    │  TaskCompletionMetric   — 任务完成率                   │
    │  ToolUsageMetric        — 工具使用效率                  │
    │  LatencyMetric          — 响应延迟统计                  │
    │  TokenEfficiencyMetric  — Token 使用效率               │
    │  ReasoningQualityMetric — 推理质量评分                  │
    │  HallucinationMetric    — 幻觉检测                     │
    └──────────────────────────────────────────────────────┘

设计原则：
- **纯 numpy 统计**：所有统计计算使用 numpy，无额外依赖.
- **统一接口**：所有指标实现 ``MetricBase`` 接口，``compute()`` 返回 ``MetricResult``.
- **可组合**：``MetricSuite`` 支持批量计算多个指标.
- **可序列化**：所有结果支持 ``to_dict()`` / ``to_json()``，便于持久化.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  Metric Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetricResult:
    """单个指标的计算结果.

    Attributes:
        name:        指标名称.
        score:       归一化分数 (0.0–1.0)，1.0 表示最佳.
        raw_value:   原始值（未归一化的具体数值）.
        details:     详细统计信息字典.
        description: 人类可读的描述.
    """

    name: str
    score: float = 0.0
    raw_value: Any = None
    details: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def __repr__(self) -> str:
        return f"MetricResult(name={self.name!r}, score={self.score:.3f})"


# ═══════════════════════════════════════════════════════════════
#  Trace Record — 一次 Agent 执行的完整轨迹
# ═══════════════════════════════════════════════════════════════


@dataclass
class TraceRecord:
    """一次 Agent 执行的完整轨迹记录.

    所有指标都基于 TraceRecord 计算，统一数据来源.

    Attributes:
        task:           用户任务描述.
        completed:      任务是否完成.
        tool_calls:     工具调用列表，每项为
            ``{"name": str, "arguments": dict, "success": bool, "output": str}``.
        expected_tools: 期望使用的工具名称列表（可选，用于评估工具选择正确性）.
        final_answer:   Agent 的最终回答.
        expected_answer: 期望的正确答案（可选，用于评估完成度）.
        latency:        总响应延迟（秒）.
        token_usage:    Token 使用量字典
            ``{"prompt": int, "completion": int, "total": int}``.
        reasoning_steps: 推理步骤列表（每个步骤为一段思考文本）.
        tool_outputs:   工具返回的输出列表（用于幻觉检测对比）.
        timestamp:      Unix 时间戳.
        id:             唯一标识符.
    """

    task: str = ""
    completed: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    final_answer: str = ""
    expected_answer: str = ""
    latency: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    reasoning_steps: List[str] = field(default_factory=list)
    tool_outputs: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"trace_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TraceRecord":
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
#  Metric Base
# ═══════════════════════════════════════════════════════════════


class MetricBase:
    """所有指标类的基类.

    子类必须实现 ``compute(trace)`` 方法，返回 ``MetricResult``.
    可选实现 ``compute_batch(traces)`` 进行批量计算优化.
    """

    name: str = "base"
    description: str = "Base metric"

    def compute(self, trace: TraceRecord) -> MetricResult:
        """计算单个轨迹的指标."""
        raise NotImplementedError

    def compute_batch(self, traces: Sequence[TraceRecord]) -> List[MetricResult]:
        """批量计算指标，默认逐个调用 ``compute()``."""
        return [self.compute(t) for t in traces]

    def aggregate(self, results: Sequence[MetricResult]) -> MetricResult:
        """聚合多个结果为一个汇总结果.

        默认使用分数的平均值.
        """
        if not results:
            return MetricResult(name=self.name, score=0.0, description="No data")
        scores = np.array([r.score for r in results])
        raw_values = [r.raw_value for r in results if r.raw_value is not None]
        return MetricResult(
            name=self.name,
            score=round(float(np.mean(scores)), 4),
            raw_value=raw_values[0] if len(raw_values) == 1 else raw_values,
            details={
                "mean": round(float(np.mean(scores)), 4),
                "std": round(float(np.std(scores)), 4),
                "min": round(float(np.min(scores)), 4),
                "max": round(float(np.max(scores)), 4),
                "median": round(float(np.median(scores)), 4),
                "count": len(results),
            },
            description=self.description,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


# ═══════════════════════════════════════════════════════════════
#  Task Completion Metric
# ═══════════════════════════════════════════════════════════════


class TaskCompletionMetric(MetricBase):
    """任务完成率指标.

    评估维度：
    - ``completed`` 字段是否为 True（基础完成率）.
    - 如果提供了 ``expected_answer``，检查 ``final_answer`` 的相似度.
    """

    name = "task_completion"
    description = "Task completion rate"

    def compute(self, trace: TraceRecord) -> MetricResult:
        # 基础完成标志
        base_score = 1.0 if trace.completed else 0.0

        details: Dict[str, Any] = {"completed": trace.completed}

        # 如果有期望答案，计算答案相似度
        if trace.expected_answer and trace.final_answer:
            similarity = self._text_similarity(
                trace.expected_answer, trace.final_answer
            )
            details["answer_similarity"] = round(similarity, 4)
            # 综合分数：完成标志 60% + 答案相似度 40%
            score = round(0.6 * base_score + 0.4 * similarity, 4)
        else:
            score = base_score

        details["has_expected_answer"] = bool(trace.expected_answer)

        return MetricResult(
            name=self.name,
            score=score,
            raw_value=trace.completed,
            details=details,
            description=self.description,
        )

    @staticmethod
    def _text_similarity(expected: str, actual: str) -> float:
        """计算两段文本的 Jaccard 相似度（基于词集合）."""
        # 简单分词：按空格和标点分割
        def tokenize(text: str) -> set:
            tokens = set(re.findall(r"\w+", text.lower()))
            return tokens

        tokens_a = tokenize(expected)
        tokens_b = tokenize(actual)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)


# ═══════════════════════════════════════════════════════════════
#  Tool Usage Metric
# ═══════════════════════════════════════════════════════════════


class ToolUsageMetric(MetricBase):
    """工具使用效率指标.

    评估维度：
    - 正确工具选择率（实际使用的工具 vs 期望工具）.
    - 调用次数合理性.
    - 工具调用成功率.
    """

    name = "tool_usage"
    description = "Tool usage efficiency"

    def compute(self, trace: TraceRecord) -> MetricResult:
        tool_calls = trace.tool_calls
        n_calls = len(tool_calls)

        # 工具调用成功率
        if n_calls > 0:
            n_success = sum(1 for tc in tool_calls if tc.get("success", False))
            success_rate = n_success / n_calls
        else:
            success_rate = 1.0 if trace.completed else 0.0

        # 正确工具选择率
        if trace.expected_tools:
            actual_tools = set(tc.get("name", "") for tc in tool_calls)
            expected_set = set(trace.expected_tools)
            # 交集 / 期望集合大小
            correct_selection = len(actual_tools & expected_set) / len(expected_set)
            # 惩罚使用了不在期望列表中的工具
            extra_tools = len(actual_tools - expected_set)
            precision_penalty = max(0.0, 1.0 - 0.1 * extra_tools)
            tool_selection_score = correct_selection * precision_penalty
        else:
            tool_selection_score = 1.0  # 无期望时不扣分

        # 调用次数合理性：调用次数越少越好（对数衰减）
        if n_calls == 0:
            call_efficiency = 1.0 if trace.completed else 0.5
        else:
            call_efficiency = 1.0 / (1.0 + 0.2 * max(0, n_calls - 1))
            call_efficiency = max(0.0, min(1.0, call_efficiency))

        # 综合分数：选择率 40% + 成功率 40% + 调用效率 20%
        score = round(
            0.4 * tool_selection_score
            + 0.4 * success_rate
            + 0.2 * call_efficiency,
            4,
        )

        return MetricResult(
            name=self.name,
            score=score,
            raw_value={
                "call_count": n_calls,
                "success_rate": round(success_rate, 4),
                "selection_score": round(tool_selection_score, 4),
            },
            details={
                "total_calls": n_calls,
                "successful_calls": sum(
                    1 for tc in tool_calls if tc.get("success", False)
                ),
                "success_rate": round(success_rate, 4),
                "tool_selection_score": round(tool_selection_score, 4),
                "call_efficiency": round(call_efficiency, 4),
                "expected_tools": trace.expected_tools,
                "actual_tools": list(
                    set(tc.get("name", "") for tc in tool_calls)
                ),
            },
            description=self.description,
        )


# ═══════════════════════════════════════════════════════════════
#  Latency Metric
# ═══════════════════════════════════════════════════════════════


class LatencyMetric(MetricBase):
    """响应延迟统计指标.

    将延迟归一化到 0.0–1.0：
    - 延迟 ≤ ``min_latency`` → 1.0
    - 延迟 ≥ ``max_latency`` → 0.0
    - 之间线性插值
    """

    name = "latency"
    description = "Response latency"

    def __init__(
        self,
        min_latency: float = 1.0,
        max_latency: float = 30.0,
    ):
        """
        Args:
            min_latency: 最佳延迟基准（秒），延迟 ≤ 此值时得满分.
            max_latency: 最差延迟基准（秒），延迟 ≥ 此值时得零分.
        """
        self.min_latency = min_latency
        self.max_latency = max_latency

    def compute(self, trace: TraceRecord) -> MetricResult:
        latency = trace.latency

        if latency <= self.min_latency:
            score = 1.0
        elif latency >= self.max_latency:
            score = 0.0
        else:
            score = 1.0 - (latency - self.min_latency) / (
                self.max_latency - self.min_latency
            )

        return MetricResult(
            name=self.name,
            score=round(score, 4),
            raw_value=latency,
            details={
                "latency_seconds": round(latency, 4),
                "min_baseline": self.min_latency,
                "max_baseline": self.max_latency,
            },
            description=self.description,
        )

    def aggregate(self, results: Sequence[MetricResult]) -> MetricResult:
        """聚合延迟指标，增加百分位统计."""
        if not results:
            return MetricResult(name=self.name, score=0.0, description="No data")

        scores = np.array([r.score for r in results])
        latencies = np.array(
            [r.raw_value for r in results if r.raw_value is not None]
        )

        details = {
            "mean_score": round(float(np.mean(scores)), 4),
            "std_score": round(float(np.std(scores)), 4),
            "count": len(results),
        }

        if len(latencies) > 0:
            details.update({
                "mean_latency": round(float(np.mean(latencies)), 4),
                "median_latency": round(float(np.median(latencies)), 4),
                "p90_latency": round(float(np.percentile(latencies, 90)), 4),
                "p99_latency": round(float(np.percentile(latencies, 99)), 4),
                "min_latency": round(float(np.min(latencies)), 4),
                "max_latency": round(float(np.max(latencies)), 4),
            })

        return MetricResult(
            name=self.name,
            score=round(float(np.mean(scores)), 4),
            raw_value=latencies.tolist() if len(latencies) > 0 else None,
            details=details,
            description=self.description,
        )


# ═══════════════════════════════════════════════════════════════
#  Token Efficiency Metric
# ═══════════════════════════════════════════════════════════════


class TokenEfficiencyMetric(MetricBase):
    """Token 使用效率指标.

    评估维度：
    - 总 token 使用量相对于基准的归一化.
    - prompt/completion 比例合理性.
    """

    name = "token_efficiency"
    description = "Token usage efficiency"

    def __init__(
        self,
        max_tokens: int = 8192,
        ideal_ratio: float = 0.3,
    ):
        """
        Args:
            max_tokens: 最差基准 token 数，超过此值得零分.
            ideal_ratio: 理想的 completion/total 比例.
        """
        self.max_tokens = max_tokens
        self.ideal_ratio = ideal_ratio

    def compute(self, trace: TraceRecord) -> MetricResult:
        total = trace.token_usage.get("total", 0)
        prompt = trace.token_usage.get("prompt", 0)
        completion = trace.token_usage.get("completion", 0)

        # Token 用量归一化
        if total <= 0:
            # 零 token 消耗异常，直接返回零分
            return MetricResult(
                name=self.name,
                score=0.0,
                raw_value=0,
                details={
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "usage_score": 0.0,
                    "ratio_score": 0.0,
                    "completion_ratio": 0.0,
                    "reason": "Zero token usage",
                },
                description=self.description,
            )
        elif total >= self.max_tokens:
            usage_score = 0.0
        else:
            usage_score = 1.0 - (total / self.max_tokens)

        # prompt/completion 比例合理性
        if total > 0 and completion > 0:
            ratio = completion / total
            # 偏离理想比例越远，扣分越多
            ratio_score = 1.0 - abs(ratio - self.ideal_ratio)
            ratio_score = max(0.0, min(1.0, ratio_score))
        else:
            ratio_score = 0.5

        # 综合：用量 70% + 比例 30%
        score = round(0.7 * usage_score + 0.3 * ratio_score, 4)

        return MetricResult(
            name=self.name,
            score=score,
            raw_value=total,
            details={
                "total_tokens": total,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "usage_score": round(usage_score, 4),
                "ratio_score": round(ratio_score, 4),
                "completion_ratio": round(completion / total, 4) if total > 0 else 0.0,
            },
            description=self.description,
        )


# ═══════════════════════════════════════════════════════════════
#  Reasoning Quality Metric
# ═══════════════════════════════════════════════════════════════


class ReasoningQualityMetric(MetricBase):
    """推理质量评分指标.

    基于推理步骤的合理性评估：
    - 步骤数量合理性（太少或太多都扣分）.
    - 步骤之间的相关性（基于关键词重叠）.
    - 是否包含明确的推理标记（Thought, Action, Observation 等）.
    """

    name = "reasoning_quality"
    description = "Reasoning quality assessment"

    # ReAct 模式中的推理标记
    REASONING_MARKERS = [
        "thought", "action", "observation", "step",
        "because", "therefore", "so", "first", "then", "next",
        "分析", "步骤", "因此", "首先", "然后", "接下来", "因为",
    ]

    def compute(self, trace: TraceRecord) -> MetricResult:
        steps = trace.reasoning_steps
        n_steps = len(steps)

        if n_steps == 0:
            return MetricResult(
                name=self.name,
                score=0.0,
                raw_value=0,
                details={"reason": "No reasoning steps provided"},
                description=self.description,
            )

        # 步骤数量合理性：理想范围 3-8 步
        if n_steps < 3:
            count_score = n_steps / 3.0
        elif n_steps <= 8:
            count_score = 1.0
        else:
            count_score = max(0.0, 1.0 - 0.1 * (n_steps - 8))

        # 推理标记检测
        all_text = " ".join(steps).lower()
        markers_found = sum(
            1 for marker in self.REASONING_MARKERS if marker in all_text
        )
        marker_score = min(1.0, markers_found / 3.0)

        # 步骤间相关性（基于词重叠）
        step_tokens = [
            set(re.findall(r"\w+", step.lower())) for step in steps
        ]
        overlaps = []
        for i in range(1, len(step_tokens)):
            if step_tokens[i] and step_tokens[i - 1]:
                overlap = len(step_tokens[i] & step_tokens[i - 1])
                union = len(step_tokens[i] | step_tokens[i - 1])
                overlaps.append(overlap / union if union > 0 else 0.0)
        coherence_score = float(np.mean(overlaps)) if overlaps else 0.5

        # 综合：数量 30% + 标记 30% + 连贯性 40%
        score = round(
            0.3 * count_score + 0.3 * marker_score + 0.4 * coherence_score, 4
        )

        return MetricResult(
            name=self.name,
            score=score,
            raw_value=n_steps,
            details={
                "step_count": n_steps,
                "count_score": round(count_score, 4),
                "marker_score": round(marker_score, 4),
                "coherence_score": round(coherence_score, 4),
                "markers_found": markers_found,
            },
            description=self.description,
        )


# ═══════════════════════════════════════════════════════════════
#  Hallucination Metric
# ═══════════════════════════════════════════════════════════════


class HallucinationMetric(MetricBase):
    """幻觉检测指标.

    检测 Agent 输出与工具结果之间的一致性：
    - 检查 ``final_answer`` 中的事实声明是否在 ``tool_outputs`` 中有支撑.
    - 如果没有工具输出，则无法检测（返回中性分数）.
    - 幻觉率越高，分数越低.
    """

    name = "hallucination"
    description = "Hallucination detection (output vs tool results)"

    def compute(self, trace: TraceRecord) -> MetricResult:
        if not trace.tool_outputs:
            # 无工具输出，无法检测幻觉，给中性分数
            return MetricResult(
                name=self.name,
                score=0.5,
                raw_value=None,
                details={"reason": "No tool outputs to verify against"},
                description=self.description,
            )

        answer = trace.final_answer.lower()
        # 合并所有工具输出
        combined_output = " ".join(trace.tool_outputs).lower()

        # 提取最终答案中的数字声明（最常见的事实型幻觉来源）
        answer_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer))
        output_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", combined_output))

        # 数字一致性检查
        if answer_numbers:
            supported = answer_numbers & output_numbers
            unsupported = answer_numbers - output_numbers
            support_rate = len(supported) / len(answer_numbers)
        else:
            support_rate = 1.0
            unsupported = set()

        # 关键词覆盖率检查
        answer_tokens = set(re.findall(r"\w+", answer))
        output_tokens = set(re.findall(r"\w+", combined_output))

        # 过滤掉常见停用词
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "to", "of",
                      "in", "for", "and", "or", "not", "it", "this", "that"}
        answer_content_tokens = answer_tokens - stop_words
        output_content_tokens = output_tokens - stop_words

        if answer_content_tokens:
            keyword_coverage = len(answer_content_tokens & output_content_tokens) / len(
                answer_content_tokens
            )
        else:
            keyword_coverage = 1.0

        # 幻觉率 = 1 - 一致性
        hallucination_rate = 1.0 - (0.5 * support_rate + 0.5 * keyword_coverage)
        # 分数 = 1 - 幻觉率
        score = round(max(0.0, 1.0 - hallucination_rate), 4)

        return MetricResult(
            name=self.name,
            score=score,
            raw_value=round(hallucination_rate, 4),
            details={
                "hallucination_rate": round(hallucination_rate, 4),
                "number_support_rate": round(support_rate, 4),
                "keyword_coverage": round(keyword_coverage, 4),
                "unsupported_numbers": list(unsupported),
                "has_tool_outputs": True,
            },
            description=self.description,
        )


# ═══════════════════════════════════════════════════════════════
#  Metric Suite — 组合多个指标
# ═══════════════════════════════════════════════════════════════


class MetricSuite:
    """指标组合器 — 批量计算多个指标并生成汇总报告.

    Usage::

        suite = MetricSuite()
        suite.add(TaskCompletionMetric())
        suite.add(ToolUsageMetric())
        suite.add(LatencyMetric())

        # 单个轨迹
        results = suite.evaluate(trace)

        # 批量
        report = suite.evaluate_batch([trace1, trace2, ...])
    """

    def __init__(self, metrics: Optional[List[MetricBase]] = None):
        self._metrics: List[MetricBase] = metrics or []

    def add(self, metric: MetricBase) -> "MetricSuite":
        """添加指标，返回 self 以支持链式调用."""
        self._metrics.append(metric)
        return self

    def remove(self, name: str) -> "MetricSuite":
        """按名称移除指标."""
        self._metrics = [m for m in self._metrics if m.name != name]
        return self

    @property
    def metrics(self) -> List[MetricBase]:
        return list(self._metrics)

    @property
    def names(self) -> List[str]:
        return [m.name for m in self._metrics]

    def evaluate(self, trace: TraceRecord) -> Dict[str, MetricResult]:
        """评估单个轨迹，返回指标名 → 结果的映射."""
        return {m.name: m.compute(trace) for m in self._metrics}

    def evaluate_batch(
        self, traces: Sequence[TraceRecord]
    ) -> "SuiteReport":
        """批量评估多个轨迹，返回汇总报告."""
        # 每个指标的所有轨迹结果
        per_metric: Dict[str, List[MetricResult]] = {
            m.name: [] for m in self._metrics
        }

        for trace in traces:
            for metric in self._metrics:
                result = metric.compute(trace)
                per_metric[metric.name].append(result)

        # 聚合每个指标
        aggregated: Dict[str, MetricResult] = {}
        for metric in self._metrics:
            results = per_metric[metric.name]
            aggregated[metric.name] = metric.aggregate(results)

        return SuiteReport(
            metrics=aggregated,
            trace_count=len(traces),
            metric_names=self.names,
        )


@dataclass
class SuiteReport:
    """指标组合的汇总报告."""

    metrics: Dict[str, MetricResult]
    trace_count: int = 0
    metric_names: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """所有指标的平均分数."""
        if not self.metrics:
            return 0.0
        return round(
            float(np.mean([m.score for m in self.metrics.values()])), 4
        )

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "trace_count": self.trace_count,
            "metric_names": self.metric_names,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def __repr__(self) -> str:
        return (
            f"SuiteReport(overall={self.overall_score:.3f}, "
            f"traces={self.trace_count}, "
            f"metrics={list(self.metrics.keys())})"
        )


# ═══════════════════════════════════════════════════════════════
#  Default Metric Suite Factory
# ═══════════════════════════════════════════════════════════════


def get_default_metrics() -> MetricSuite:
    """返回包含所有内置指标的默认 MetricSuite."""
    return MetricSuite([
        TaskCompletionMetric(),
        ToolUsageMetric(),
        LatencyMetric(),
        TokenEfficiencyMetric(),
        ReasoningQualityMetric(),
        HallucinationMetric(),
    ])
