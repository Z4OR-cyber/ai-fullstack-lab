"""进化编排器 — 串联完整的自进化循环.

将学习引擎、技能生成器、评估器和反馈收集器串联，
形成完整的自进化闭环：

    交互 → 学习 → 生成 → 评估 → 反馈 → 更新

Usage::

    orchestrator = EvolutionOrchestrator(
        storage_dir="data/evolution",
        skills_dir="skills/generated",
    )

    # 记录交互
    orchestrator.record_interaction(record)

    # 运行完整进化循环
    result = orchestrator.run_evolution_cycle()

    # result 包含：
    # - extracted patterns
    # - updated policy
    # - generated skills
    # - evaluation report
    # - feedback stats
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .learner import (
    InteractionRecord,
    Pattern,
    BehaviorPolicy,
    LearningEngine,
)
from .skill_generator import (
    ToolSequence,
    GeneratedSkill,
    SkillGenerator,
)
from .evaluator import (
    EvaluationMetrics,
    EvaluationReport,
    BehaviorEvaluator,
)
from .feedback import (
    Feedback,
    FeedbackSignal,
    FeedbackCollector,
)


@dataclass
class EvolutionResult:
    """一次进化循环的完整结果.

    Attributes:
        cycle_id: 循环唯一标识符.
        timestamp: 循环执行时间戳.
        patterns_extracted: 提取的模式数量.
        policy_version: 更新后的策略版本.
        policy: 更新后的行为策略.
        skills_generated: 生成的技能列表.
        skills_activated: 激活的技能数量.
        evaluation_report: 评估报告.
        feedback_stats: 反馈统计.
        experience_rules: 新巩固的经验规则.
        duration: 循环耗时（秒）.
    """

    cycle_id: str = ""
    timestamp: float = 0.0
    patterns_extracted: int = 0
    policy_version: str = ""
    policy: Optional[BehaviorPolicy] = None
    skills_generated: List[GeneratedSkill] = field(default_factory=list)
    skills_activated: int = 0
    evaluation_report: Optional[EvaluationReport] = None
    feedback_stats: Dict[str, Any] = field(default_factory=dict)
    experience_rules: List[Dict[str, Any]] = field(default_factory=list)
    duration: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "patterns_extracted": self.patterns_extracted,
            "policy_version": self.policy_version,
            "policy": self.policy.to_dict() if self.policy else None,
            "skills_generated": [s.to_dict() for s in self.skills_generated],
            "skills_activated": self.skills_activated,
            "evaluation_report": (
                self.evaluation_report.to_dict() if self.evaluation_report else None
            ),
            "feedback_stats": self.feedback_stats,
            "experience_rules": self.experience_rules,
            "duration": round(self.duration, 3),
        }


class EvolutionOrchestrator:
    """进化编排器 — 串联完整的自进化循环.

    将四个模块串联，形成闭环：

    1. **学习**：从交互记录提取模式，更新策略.
    2. **生成**：从高价值模式生成新技能.
    3. **评估**：多维度评估当前表现.
    4. **反馈**：收集反馈信号，传递给学习引擎.
    5. **巩固**：将高频成功模式巩固为经验规则.

    Attributes:
        learner: 学习引擎.
        generator: 技能生成器.
        evaluator: 行为评估器.
        feedback_collector: 反馈收集器.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        skills_dir: Optional[str] = None,
    ):
        """
        Args:
            storage_dir: 数据持久化目录.
            skills_dir: 技能库目录.
        """
        if storage_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "evolution")

        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.learner = LearningEngine(storage_dir=storage_dir)
        self.generator = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=storage_dir,
        )
        self.evaluator = BehaviorEvaluator(storage_dir=storage_dir)
        self.feedback_collector = FeedbackCollector(storage_dir=storage_dir)

        self._cycle_count: int = 0

    # ── 交互记录 ──────────────────────────────────────────

    def record_interaction(self, record: InteractionRecord) -> None:
        """记录一次交互.

        同时将隐式反馈传递给反馈收集器.

        Args:
            record: 交互记录.
        """
        self.learner.record_interaction(record)
        self.feedback_collector.collect_from_interaction(record)

    def record_interactions(self, records: List[InteractionRecord]) -> None:
        """批量记录交互.

        Args:
            records: 交互记录列表.
        """
        for record in records:
            self.record_interaction(record)

    def collect_explicit_feedback(
        self,
        interaction_id: str,
        rating: str,
        comment: Optional[str] = None,
    ) -> Feedback:
        """收集显式反馈.

        Args:
            interaction_id: 交互记录 ID.
            rating: 评分（thumbs_up / thumbs_down / neutral）.
            comment: 可选文本评论.

        Returns:
            Feedback 实例.
        """
        return self.feedback_collector.collect_explicit(
            interaction_id, rating, comment
        )

    # ── 完整进化循环 ──────────────────────────────────────

    def run_evolution_cycle(self) -> EvolutionResult:
        """运行完整的自进化循环.

        执行顺序：
        1. 反馈信号传递给学习引擎
        2. 提取行为模式
        3. 更新行为策略
        4. 巩固经验规则
        5. 从高价值模式生成技能
        6. 验证并激活技能
        7. 多维度评估
        8. 持久化所有状态

        Returns:
            EvolutionResult 完整结果.
        """
        start_time = time.time()
        self._cycle_count += 1
        cycle_id = f"cycle_{self._cycle_count}_{int(start_time)}"

        result = EvolutionResult(
            cycle_id=cycle_id,
            timestamp=start_time,
        )

        # Step 1: 反馈信号传递
        self.feedback_collector.pass_to_learner(self.learner)

        # Step 2: 提取模式
        patterns = self.learner.extract_patterns()
        result.patterns_extracted = len(patterns)

        # Step 3: 更新策略
        policy = self.learner.update_policy()
        result.policy = policy
        result.policy_version = policy.version

        # Step 4: 巩固经验规则
        new_rules = self.learner.consolidate_rules()
        result.experience_rules = new_rules

        # Step 5: 生成技能
        generated_skills = self.generator.generate_from_patterns(patterns)
        result.skills_generated = generated_skills

        # Step 6: 验证并激活
        activated = 0
        for skill in generated_skills:
            if self.generator.validate_skill(skill):
                if self.generator.activate_skill(skill.name):
                    activated += 1
        result.skills_activated = activated

        # Step 7: 评估
        interactions = self.learner.get_interactions()
        report = self.evaluator.evaluate_batch(
            interactions, version=policy.version
        )
        result.evaluation_report = report

        # Step 8: 反馈统计
        result.feedback_stats = self.feedback_collector.get_stats()

        # Step 9: 持久化
        self.learner.save()

        result.duration = time.time() - start_time
        return result

    # ── 版本对比 ──────────────────────────────────────────

    def compare_versions(
        self,
        interactions_a: List[InteractionRecord],
        version_a: str,
        interactions_b: List[InteractionRecord],
        version_b: str,
    ) -> Dict[str, Any]:
        """A/B 版本对比评估.

        Args:
            interactions_a: 版本 A 的交互记录.
            version_a: 版本 A 标签.
            interactions_b: 版本 B 的交互记录.
            version_b: 版本 B 标签.

        Returns:
            对比结果字典.
        """
        return self.evaluator.compare_versions(
            interactions_a, version_a,
            interactions_b, version_b,
        )

    # ── 状态查询 ──────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """返回进化引擎的整体状态.

        Returns:
            状态信息字典.
        """
        return {
            "cycles_run": self._cycle_count,
            "total_interactions": self.learner.get_interaction_count(),
            "total_patterns": len(self.learner.get_patterns()),
            "total_experience_rules": len(self.learner.get_experience_rules()),
            "policy_version": self.learner.get_policy().version,
            "generated_skills": len(self.generator.get_generated_skills()),
            "active_skills": len(self.generator.get_active_skills()),
            "feedback_stats": self.feedback_collector.get_stats(),
        }
