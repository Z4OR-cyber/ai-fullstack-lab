"""
Structured Goal — 结构化目标模板（Hermes /goal 四要素公式）.

设计要点：
    - 基于 Hermes 的 /goal 命令四要素公式，将模糊的目标拆解为结构化要素
    - 四要素：result（期望结果）、info_sources（信息源）、constraints（约束条件）、deliverables（交付物）
    - 可选维度：priority（优先级）、timeout（超时）、tags（标签）
    - to_prompt() 生成可直接喂给 LLM 的结构化 prompt
    - validate() 验证目标完整性
    - 纯标准库：dataclass + enum，无外部依赖

Usage::

    from suyi.core.goal import StructuredGoal

    goal = StructuredGoal(
        result="生成一份市场分析",
        info_sources=["行业报告", "竞品官网"],
        constraints=["字数不超过3000", "必须中文"],
        deliverables=["markdown文档", "数据表格"],
        priority="high",
    )
    prompt = goal.to_prompt()
    issues = goal.validate()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    """目标优先级枚举。"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class StructuredGoal:
    """
    结构化目标。

    四要素（必填）：
        result:         期望结果 — 最终要得到什么
        info_sources:   信息源 — 从哪里获取信息
        constraints:    约束条件 — 有什么限制
        deliverables:   交付物 — 最终产出什么

    可选维度：
        priority:       优先级 (low/normal/high/critical)
        timeout:        超时时间（秒）
        tags:           标签列表

    Attributes:
        result:         期望结果描述
        info_sources:   信息源列表
        constraints:    约束条件列表
        deliverables:   交付物列表
        priority:       优先级，默认 "normal"
        timeout:        超时时间（秒），默认 None
        tags:           标签列表，默认空
    """

    # 四要素（必填）
    result: str
    info_sources: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)

    # 可选维度
    priority: str = "normal"
    timeout: Optional[int] = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """验证 priority 值的合法性。"""
        valid = {p.value for p in Priority}
        if self.priority not in valid:
            raise ValueError(
                f"priority 必须为 {valid} 之一，收到: {self.priority!r}"
            )

    # ── 核心方法 ────────────────────────────────────────────────

    def to_prompt(self) -> str:
        """
        将 Goal 转换为结构化 prompt 文本。

        格式清晰，可直接喂给 LLM。包含四要素和可选维度。
        空列表的维度会被标注为"未指定"。

        Returns:
            格式化后的 prompt 字符串
        """
        lines: list[str] = []
        lines.append("# 任务目标")
        lines.append("")
        lines.append(f"## 期望结果")
        lines.append(self.result if self.result else "（未指定）")
        lines.append("")

        # 信息源
        lines.append("## 信息源")
        if self.info_sources:
            for src in self.info_sources:
                lines.append(f"- {src}")
        else:
            lines.append("- （未指定）")
        lines.append("")

        # 约束条件
        lines.append("## 约束条件")
        if self.constraints:
            for c in self.constraints:
                lines.append(f"- {c}")
        else:
            lines.append("- （无特殊约束）")
        lines.append("")

        # 交付物
        lines.append("## 交付物")
        if self.deliverables:
            for d in self.deliverables:
                lines.append(f"- {d}")
        else:
            lines.append("- （未指定）")
        lines.append("")

        # 可选维度（只在有值时输出）
        if self.priority and self.priority != "normal":
            lines.append(f"## 优先级")
            lines.append(f"{self.priority}")
            lines.append("")

        if self.timeout is not None:
            lines.append(f"## 超时限制")
            lines.append(f"{self.timeout} 秒")
            lines.append("")

        if self.tags:
            lines.append(f"## 标签")
            lines.append(f"{', '.join(self.tags)}")
            lines.append("")

        return "\n".join(lines)

    def validate(self) -> list[str]:
        """
        验证 Goal 完整性，返回缺失项列表。

        空列表 = 有效目标。

        验证规则：
            - result 不能为空
            - priority 必须合法
            - timeout 必须为正整数（如果指定了的话）

        Returns:
            缺失/无效项的描述列表，空列表表示验证通过
        """
        issues: list[str] = []

        if not self.result or not self.result.strip():
            issues.append("缺少期望结果(result)")

        if not self.info_sources:
            issues.append("缺少信息源(info_sources)")

        if not self.constraints:
            issues.append("缺少约束条件(constraints)")

        if not self.deliverables:
            issues.append("缺少交付物(deliverables)")

        # priority 合法性
        valid_priorities = {p.value for p in Priority}
        if self.priority not in valid_priorities:
            issues.append(f"priority 值无效: {self.priority!r}")

        # timeout 合法性
        if self.timeout is not None:
            if not isinstance(self.timeout, int) or self.timeout <= 0:
                issues.append(f"timeout 必须为正整数，收到: {self.timeout!r}")

        return issues

    # ── 序列化 ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """
        序列化为字典。

        Returns:
            包含所有字段的字典，可用于 JSON 序列化
        """
        return {
            "result": self.result,
            "info_sources": list(self.info_sources),
            "constraints": list(self.constraints),
            "deliverables": list(self.deliverables),
            "priority": self.priority,
            "timeout": self.timeout,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict) -> StructuredGoal:
        """
        从字典反序列化。

        Args:
            d: 字典数据

        Returns:
            StructuredGoal 实例

        Raises:
            KeyError: 缺少必填字段 result
            ValueError: priority 值无效
        """
        return cls(
            result=d["result"],
            info_sources=d.get("info_sources", []),
            constraints=d.get("constraints", []),
            deliverables=d.get("deliverables", []),
            priority=d.get("priority", "normal"),
            timeout=d.get("timeout"),
            tags=d.get("tags", []),
        )

    # ── 显示 ────────────────────────────────────────────────────

    def __str__(self) -> str:
        """简洁的人类可读格式。"""
        parts = [f"Goal: {self.result}"]

        # 信息源数量
        src_count = len(self.info_sources)
        parts.append(f"sources={src_count}")

        # 约束数量
        con_count = len(self.constraints)
        parts.append(f"constraints={con_count}")

        # 交付物数量
        del_count = len(self.deliverables)
        parts.append(f"deliverables={del_count}")

        # 优先级（非默认时才显示）
        if self.priority and self.priority != "normal":
            parts.append(f"priority={self.priority}")

        # 超时
        if self.timeout is not None:
            parts.append(f"timeout={self.timeout}s")

        # 标签
        if self.tags:
            parts.append(f"tags=[{', '.join(self.tags)}]")

        return " | ".join(parts)
