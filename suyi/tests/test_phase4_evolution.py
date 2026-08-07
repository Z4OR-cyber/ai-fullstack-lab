"""Suyi Phase 4 — 自进化引擎测试.

测试学习引擎模式提取和策略更新、技能生成器产出格式、
评估器多维度评分、反馈收集和信号传递，
以及完整的进化循环.

所有测试使用 MockLLM 和模拟数据，不依赖外部 API.
"""

import json
import os
import tempfile
import time
import pytest

from suyi.evolution import (
    InteractionRecord,
    Pattern,
    BehaviorPolicy,
    LearningEngine,
    ToolSequence,
    GeneratedSkill,
    SkillGenerator,
    EvaluationMetrics,
    EvaluationReport,
    BehaviorEvaluator,
    Feedback,
    FeedbackSignal,
    FeedbackCollector,
    EvolutionOrchestrator,
)


# ═══════════════════════════════════════════════════════════════
#  Test Helpers
# ═══════════════════════════════════════════════════════════════


def make_interaction(
    task: str = "test task",
    tools: list = None,
    success: bool = True,
    duration: float = 5.0,
    tokens: int = 200,
    version: str = "default",
    tags: list = None,
    feedback: dict = None,
) -> InteractionRecord:
    """创建测试用交互记录."""
    if tools is None:
        tools = [
            {"name": "search", "arguments": {"query": "test"}, "success": True, "output_summary": "found"},
            {"name": "read_file", "arguments": {"path": "/tmp/test"}, "success": True, "output_summary": "read"},
        ]
    return InteractionRecord(
        task=task,
        tool_calls=tools,
        success=success,
        duration=duration,
        tokens_used=tokens,
        version=version,
        tags=tags or [],
        feedback=feedback,
    )


def make_batch_interactions(n: int = 10, success_rate: float = 0.8, version: str = "v1") -> list:
    """创建一批测试用交互记录."""
    records = []
    for i in range(n):
        success = (i / n) < success_rate
        tools = [
            {"name": "search", "arguments": {"query": f"query_{i}"}, "success": True, "output_summary": "ok"},
            {"name": "read_file", "arguments": {"path": f"/tmp/file_{i}"}, "success": success, "output_summary": "ok" if success else "err"},
        ]
        if not success:
            tools.append({"name": "write_file", "arguments": {"path": "/tmp/out"}, "success": False, "output_summary": "failed"})
        records.append(make_interaction(
            task=f"task_{i}",
            tools=tools,
            success=success,
            duration=2.0 + i * 0.5,
            tokens=100 + i * 20,
            version=version,
            tags=["python"] if i % 2 == 0 else ["javascript"],
        ))
    return records


# ═══════════════════════════════════════════════════════════════
#  Test: Learning Engine
# ═══════════════════════════════════════════════════════════════


class TestLearningEngine:
    """学习引擎测试."""

    def test_init(self):
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        assert engine is not None
        assert engine.get_interaction_count() == 0

    def test_record_interaction(self):
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        record = make_interaction()
        engine.record_interaction(record)
        assert engine.get_interaction_count() == 1
        assert engine.get_interactions()[0].task == "test task"

    def test_record_batch(self):
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(5)
        engine.record_interactions(records)
        assert engine.get_interaction_count() == 5

    def test_extract_patterns_nonempty(self):
        """测试模式提取能从交互记录中提取模式."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(10, success_rate=0.8)
        engine.record_interactions(records)
        patterns = engine.extract_patterns()
        assert len(patterns) > 0
        # 验证 Pattern 结构
        for p in patterns:
            assert isinstance(p, Pattern)
            assert p.frequency > 0
            assert 0.0 <= p.success_rate <= 1.0
            assert p.avg_duration > 0
            assert p.confidence >= 0.0
            assert p.pattern_type in ("success", "failure", "neutral")

    def test_extract_patterns_sorted_by_frequency(self):
        """模式应按频率降序排列."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(10)
        engine.record_interactions(records)
        patterns = engine.extract_patterns()
        for i in range(len(patterns) - 1):
            assert patterns[i].frequency >= patterns[i + 1].frequency

    def test_success_and_failure_patterns(self):
        """测试成功和失败模式分类."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        # 添加成功交互
        for _ in range(5):
            engine.record_interaction(make_interaction(
                tools=[{"name": "search", "arguments": {}, "success": True, "output_summary": ""}],
                success=True,
            ))
        # 添加失败交互
        for _ in range(5):
            engine.record_interaction(make_interaction(
                tools=[{"name": "bash", "arguments": {}, "success": False, "output_summary": ""}],
                success=False,
            ))
        patterns = engine.extract_patterns()
        success_pats = engine.get_success_patterns()
        failure_pats = engine.get_failure_patterns()
        assert len(success_pats) > 0
        assert len(failure_pats) > 0

    def test_update_policy(self):
        """测试策略更新."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(10, success_rate=0.8)
        engine.record_interactions(records)
        engine.extract_patterns()
        policy = engine.update_policy()
        assert isinstance(policy, BehaviorPolicy)
        assert policy.version.startswith("v")
        assert len(policy.tool_preferences) > 0
        assert policy.stats["total_interactions"] == 10

    def test_tool_preferences_range(self):
        """工具偏好分数应在 [0, 1] 范围内."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(10)
        engine.record_interactions(records)
        engine.extract_patterns()
        policy = engine.update_policy()
        for tool, pref in policy.tool_preferences.items():
            assert 0.0 <= pref <= 1.0, f"{tool}: {pref} out of range"

    def test_consolidate_rules(self):
        """测试经验规则巩固."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        # 添加高频高成功率交互
        for _ in range(5):
            engine.record_interaction(make_interaction(
                task="search and read",
                tools=[
                    {"name": "search", "arguments": {"q": "test"}, "success": True, "output_summary": "ok"},
                    {"name": "read_file", "arguments": {"path": "/tmp/f"}, "success": True, "output_summary": "ok"},
                ],
                success=True,
                tags=["research"],
            ))
        engine.extract_patterns()
        rules = engine.consolidate_rules()
        assert len(rules) > 0
        for rule in rules:
            assert "rule_id" in rule
            assert "condition" in rule
            assert "action" in rule
            assert "confidence" in rule
            assert rule["confidence"] > 0

    def test_persistence(self):
        """测试 JSON 持久化."""
        storage_dir = tempfile.mkdtemp()
        engine = LearningEngine(storage_dir=storage_dir)
        engine.record_interaction(make_interaction())
        engine.extract_patterns()
        engine.update_policy()
        engine.save()

        # 验证文件存在
        assert os.path.isfile(os.path.join(storage_dir, "interactions.json"))
        assert os.path.isfile(os.path.join(storage_dir, "patterns.json"))
        assert os.path.isfile(os.path.join(storage_dir, "policy.json"))

        # 重新加载
        engine2 = LearningEngine(storage_dir=storage_dir)
        assert engine2.get_interaction_count() == 1
        assert len(engine2.get_patterns()) > 0

    def test_empty_extract(self):
        """空交互时提取模式应返回空列表."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        patterns = engine.extract_patterns()
        assert patterns == []

    def test_ngram_extraction(self):
        """测试 n-gram 频率统计."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        # 3次相同序列
        for _ in range(3):
            engine.record_interaction(make_interaction(
                tools=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "write_file", "arguments": {}, "success": True, "output_summary": ""},
                ],
                success=True,
            ))
        patterns = engine.extract_patterns()
        # 应该能找到 search → read_file → write_file 序列
        seq_found = any(
            "search" in p.tool_sequence and "read_file" in p.tool_sequence
            for p in patterns
        )
        assert seq_found

    def test_kmeans_clustering(self):
        """测试 k-means 聚类能发现行为群组."""
        engine = LearningEngine(storage_dir=tempfile.mkdtemp())
        # 群组1: search + read, 成功
        for _ in range(4):
            engine.record_interaction(make_interaction(
                tools=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                ],
                success=True,
                duration=3.0,
            ))
        # 群组2: bash + write, 失败
        for _ in range(4):
            engine.record_interaction(make_interaction(
                tools=[
                    {"name": "bash", "arguments": {}, "success": False, "output_summary": ""},
                    {"name": "write_file", "arguments": {}, "success": False, "output_summary": ""},
                ],
                success=False,
                duration=15.0,
            ))
        patterns = engine.extract_patterns()
        assert len(patterns) > 0


# ═══════════════════════════════════════════════════════════════
#  Test: Skill Generator
# ═══════════════════════════════════════════════════════════════


class TestSkillGenerator:
    """技能自动生成器测试."""

    def test_init(self):
        gen = SkillGenerator(
            skills_dir=tempfile.mkdtemp(),
            storage_dir=tempfile.mkdtemp(),
        )
        assert gen is not None

    def test_find_reusable_sequences(self):
        """测试可复用序列识别."""
        gen = SkillGenerator(
            skills_dir=tempfile.mkdtemp(),
            storage_dir=tempfile.mkdtemp(),
        )
        interactions = []
        for _ in range(5):
            interactions.append(make_interaction(
                tools=[
                    {"name": "search", "arguments": {"query": "q"}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {"path": "f"}, "success": True, "output_summary": ""},
                ],
                success=True,
            ))
        sequences = gen.find_reusable_sequences(interactions)
        assert len(sequences) > 0
        assert sequences[0].frequency >= 3
        assert sequences[0].success_rate >= 0.6

    def test_generate_skill_md_format(self):
        """测试生成的 SKILL.md 格式正确."""
        gen = SkillGenerator(
            skills_dir=tempfile.mkdtemp(),
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file", "write_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=3.5,
            example_arguments=[
                [{"query": "test"}, {"path": "/tmp/f"}, {"path": "/tmp/out"}],
            ],
            context_tags=["python", "automation"],
        )
        name, content = gen.generate_skill_md(seq)
        # 验证 front matter
        assert content.startswith("---\n")
        assert "name:" in content
        assert "description:" in content
        assert "generated: true" in content
        # 验证 body
        assert "# " in content
        assert "## 使用步骤" in content
        assert "search" in content
        assert "read_file" in content
        assert "write_file" in content

    def test_generate_skill_md_compatible_with_loader(self):
        """测试生成的 SKILL.md 能被 SkillLoader 正确解析."""
        from suyi.skills.loader import SkillLoader

        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.8,
            avg_duration=2.0,
            example_arguments=[[{"query": "q"}, {"path": "f"}]],
            context_tags=["test"],
        )
        name, content = gen.generate_skill_md(seq)

        # 写入文件
        skill_dir = os.path.join(skills_dir, name)
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write(content)

        # 用 SkillLoader 加载
        loader = SkillLoader(skills_dir)
        loaded = loader.load_skill(name)
        assert loaded is not None
        assert loaded.name == name
        assert loaded.description != ""
        assert len(loaded.body) > 0

    def test_generate_from_patterns(self):
        """测试从 Pattern 列表批量生成技能."""
        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        patterns = [
            Pattern(
                tool_sequence=["search", "read_file"],
                frequency=5,
                success_rate=0.9,
                avg_duration=2.0,
                confidence=0.8,
                pattern_type="success",
            ),
            Pattern(
                tool_sequence=["bash"],
                frequency=2,
                success_rate=0.2,
                avg_duration=10.0,
                confidence=0.3,
                pattern_type="failure",
            ),
        ]
        generated = gen.generate_from_patterns(patterns)
        # 只有高频高成功率的模式会生成技能
        assert len(generated) >= 1
        for skill in generated:
            assert isinstance(skill, GeneratedSkill)
            assert skill.status == "pending"
            assert os.path.isfile(os.path.join(skill.skill_dir, "SKILL.md"))

    def test_validate_skill(self):
        """测试技能验证."""
        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=2.0,
            example_arguments=[[{"query": "q"}, {"path": "f"}]],
            context_tags=["test"],
        )
        generated = gen.generate_from_sequences([seq])
        assert len(generated) > 0

        skill = generated[0]
        result = gen.validate_skill(skill)
        assert result is True
        assert skill.status == "validated"
        assert skill.validation_result is not None
        assert skill.validation_result["loadable"] is True

    def test_activate_skill(self):
        """测试技能激活."""
        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=2.0,
            example_arguments=[[{"query": "q"}, {"path": "f"}]],
            context_tags=["test"],
        )
        generated = gen.generate_from_sequences([seq])
        skill = generated[0]
        gen.validate_skill(skill)
        assert gen.activate_skill(skill.name) is True
        assert skill.status == "active"
        # 激活未验证的技能应失败
        assert gen.activate_skill("nonexistent") is False

    def test_skill_registry_persistence(self):
        """测试技能注册表持久化."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=storage_dir,
        )
        seq = ToolSequence(
            tools=["search"],
            frequency=3,
            success_rate=0.8,
            avg_duration=1.0,
        )
        gen.generate_from_sequences([seq])

        # 重新加载
        gen2 = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=storage_dir,
        )
        assert len(gen2.get_generated_skills()) > 0


# ═══════════════════════════════════════════════════════════════
#  Test: Evaluator
# ═══════════════════════════════════════════════════════════════


class TestBehaviorEvaluator:
    """行为评估器测试."""

    def test_init(self):
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        assert evaluator is not None

    def test_evaluate_single(self):
        """测试单次交互评估."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        record = make_interaction(success=True, duration=5.0, tokens=200)
        metrics = evaluator.evaluate_single(record)
        assert isinstance(metrics, EvaluationMetrics)
        assert metrics.completion_rate == 1.0
        assert 0.0 <= metrics.efficiency_score <= 1.0
        assert 0.0 <= metrics.quality_score <= 1.0
        assert 0.0 <= metrics.user_satisfaction <= 1.0
        assert 0.0 <= metrics.overall_score <= 1.0

    def test_evaluate_single_failure(self):
        """测试失败交互的评估."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        record = make_interaction(
            success=False,
            tools=[{"name": "bash", "arguments": {}, "success": False, "output_summary": "err"}],
        )
        metrics = evaluator.evaluate_single(record)
        assert metrics.completion_rate == 0.0
        assert metrics.user_satisfaction < 0.5

    def test_evaluate_batch(self):
        """测试批量评估."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(20, success_rate=0.75, version="v1")
        report = evaluator.evaluate_batch(records, version="v1")
        assert isinstance(report, EvaluationReport)
        assert report.interaction_count == 20
        assert report.version == "v1"
        assert 0.0 <= report.metrics.overall_score <= 1.0
        assert len(report.recommendations) > 0

    def test_metrics_dimensions(self):
        """测试多维度评分."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(15, success_rate=0.8)
        report = evaluator.evaluate_batch(records)
        m = report.metrics
        # 完成率应接近 0.8
        assert 0.6 <= m.completion_rate <= 1.0
        # 效率、质量、满意度都应在合理范围
        assert m.efficiency_score > 0
        assert m.quality_score > 0
        assert m.user_satisfaction > 0

    def test_overall_score_weighted(self):
        """测试综合分数是加权平均."""
        metrics = EvaluationMetrics(
            completion_rate=1.0,
            efficiency_score=0.5,
            quality_score=0.8,
            user_satisfaction=0.6,
        )
        overall = metrics.compute_overall()
        expected = (
            1.0 * 0.35 + 0.5 * 0.25 + 0.8 * 0.20 + 0.6 * 0.20
        )
        assert abs(overall - round(expected, 4)) < 0.001

    def test_compare_versions(self):
        """测试 A/B 版本对比."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        # 版本 A: 低成功率
        records_a = make_batch_interactions(10, success_rate=0.4, version="v1")
        # 版本 B: 高成功率
        records_b = make_batch_interactions(10, success_rate=0.9, version="v2")

        comparison = evaluator.compare_versions(records_a, "v1", records_b, "v2")
        assert comparison["version_a"] == "v1"
        assert comparison["version_b"] == "v2"
        assert comparison["winner"] == "v2"
        assert comparison["differences"]["completion_rate"]["improvement"] is True

    def test_report_json(self):
        """测试报告 JSON 序列化."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        records = make_batch_interactions(5)
        report = evaluator.evaluate_batch(records)
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["version"] == "default"
        assert "metrics" in parsed
        assert "recommendations" in parsed

    def test_report_persistence(self):
        """测试报告持久化."""
        storage_dir = tempfile.mkdtemp()
        evaluator = BehaviorEvaluator(storage_dir=storage_dir)
        records = make_batch_interactions(5)
        report = evaluator.evaluate_batch(records)

        # 验证报告文件存在
        report_files = [
            f for f in os.listdir(storage_dir)
            if f.startswith("report_") and f.endswith(".json")
        ]
        assert len(report_files) > 0

        # 重新加载
        evaluator2 = BehaviorEvaluator(storage_dir=storage_dir)
        evaluator2.load_reports()
        assert len(evaluator2.get_reports()) > 0

    def test_recommendations_generated(self):
        """测试改进建议生成."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        # 低质量交互
        records = []
        for _ in range(10):
            records.append(make_interaction(
                success=False,
                duration=50.0,
                tokens=7000,
                tools=[{"name": "bash", "arguments": {}, "success": False, "output_summary": "err"}] * 5,
            ))
        report = evaluator.evaluate_batch(records)
        assert len(report.recommendations) > 0
        # 应该有关于完成率的建议
        assert any("完成率" in r for r in report.recommendations)

    def test_empty_batch(self):
        """测试空批量评估."""
        evaluator = BehaviorEvaluator(storage_dir=tempfile.mkdtemp())
        report = evaluator.evaluate_batch([], version="empty")
        assert report.interaction_count == 0
        assert len(report.recommendations) > 0


# ═══════════════════════════════════════════════════════════════
#  Test: Feedback
# ═══════════════════════════════════════════════════════════════


class TestFeedbackCollector:
    """反馈收集器测试."""

    def test_init(self):
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        assert collector is not None

    def test_collect_explicit(self):
        """测试显式反馈收集."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        fb = collector.collect_explicit("int_1", "thumbs_up", "Great!")
        assert fb.explicit_rating == "thumbs_up"
        assert fb.explicit_comment == "Great!"
        assert fb.has_explicit is True

    def test_collect_implicit(self):
        """测试隐式反馈收集."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        fb = collector.collect_implicit(
            "int_1", completion=True, retries=0, duration=5.0, tool_failures=0
        )
        assert fb.implicit_completion is True
        assert fb.implicit_retries == 0
        assert fb.has_implicit is True

    def test_collect_from_interaction(self):
        """测试从交互记录自动提取隐式反馈."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        record = make_interaction(
            success=True,
            duration=3.0,
            tools=[
                {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                {"name": "read_file", "arguments": {}, "success": False, "output_summary": "err"},
            ],
        )
        fb = collector.collect_from_interaction(record)
        assert fb.interaction_id == record.id
        assert fb.implicit_completion is True
        assert fb.implicit_tool_failures == 1

    def test_feedback_signal_explicit_positive(self):
        """测试显式正面反馈信号."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        collector.collect_explicit("int_1", "thumbs_up")
        collector.collect_implicit("int_1", completion=True, retries=0, duration=3.0)
        signal = collector.get_feedback_signal("int_1")
        assert signal is not None
        assert signal.explicit_signal > 0
        assert signal.implicit_signal > 0
        assert signal.combined > 0

    def test_feedback_signal_explicit_negative(self):
        """测试显式负面反馈信号."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        collector.collect_explicit("int_1", "thumbs_down", "Terrible")
        collector.collect_implicit("int_1", completion=False, retries=3, duration=30.0, tool_failures=2)
        signal = collector.get_feedback_signal("int_1")
        assert signal.explicit_signal < 0
        assert signal.implicit_signal < 0
        assert signal.combined < 0

    def test_feedback_signal_implicit_only(self):
        """测试纯隐式反馈信号."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        collector.collect_implicit("int_1", completion=True, retries=0, duration=2.0)
        signal = collector.get_feedback_signal("int_1")
        assert signal.explicit_signal == 0.0
        assert signal.implicit_signal > 0
        assert signal.weight == 0.5  # 纯隐式反馈权重降低

    def test_feedback_signal_range(self):
        """测试反馈信号范围 [-1, 1]."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        # 极端正面
        collector.collect_explicit("int_1", "thumbs_up")
        collector.collect_implicit("int_1", completion=True, retries=0, duration=1.0, tool_failures=0)
        signal = collector.get_feedback_signal("int_1")
        assert -1.0 <= signal.combined <= 1.0

        # 极端负面
        collector.collect_explicit("int_2", "thumbs_down")
        collector.collect_implicit("int_2", completion=False, retries=5, duration=60.0, tool_failures=5)
        signal2 = collector.get_feedback_signal("int_2")
        assert -1.0 <= signal2.combined <= 1.0

    def test_pass_to_learner(self):
        """测试反馈信号传递给学习引擎."""
        storage_dir = tempfile.mkdtemp()
        engine = LearningEngine(storage_dir=storage_dir)
        collector = FeedbackCollector(storage_dir=storage_dir)

        record = make_interaction()
        engine.record_interaction(record)
        collector.collect_explicit(record.id, "thumbs_up", "Good job")
        collector.collect_implicit(record.id, completion=True, retries=0, duration=3.0)

        updated = collector.pass_to_learner(engine)
        assert updated == 1
        # 验证交互记录上的 feedback 已更新
        interactions = engine.get_interactions()
        assert interactions[0].feedback is not None
        assert interactions[0].feedback["rating"] == "thumbs_up"

    def test_feedback_persistence(self):
        """测试反馈数据持久化."""
        storage_dir = tempfile.mkdtemp()
        collector = FeedbackCollector(storage_dir=storage_dir)
        collector.collect_explicit("int_1", "thumbs_up", "Great")
        collector.collect_implicit("int_1", completion=True, retries=0, duration=5.0)

        # 重新加载
        collector2 = FeedbackCollector(storage_dir=storage_dir)
        fb = collector2.get_feedback("int_1")
        assert fb is not None
        assert fb.explicit_rating == "thumbs_up"

    def test_feedback_stats(self):
        """测试反馈统计."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        collector.collect_explicit("int_1", "thumbs_up")
        collector.collect_implicit("int_1", completion=True, retries=0, duration=2.0)
        collector.collect_explicit("int_2", "thumbs_down")
        collector.collect_implicit("int_2", completion=False, retries=2, duration=20.0)

        stats = collector.get_stats()
        assert stats["total_feedbacks"] == 2
        assert stats["explicit_feedbacks"] == 2
        assert stats["positive"] >= 1
        assert stats["negative"] >= 1

    def test_combined_explicit_and_implicit(self):
        """测试同一交互同时收集显式和隐式反馈."""
        collector = FeedbackCollector(storage_dir=tempfile.mkdtemp())
        collector.collect_explicit("int_1", "thumbs_up")
        fb = collector.collect_implicit("int_1", completion=True, retries=0, duration=2.0)
        assert fb.has_explicit and fb.has_implicit


# ═══════════════════════════════════════════════════════════════
#  Test: Full Evolution Cycle
# ═══════════════════════════════════════════════════════════════


class TestEvolutionOrchestrator:
    """完整进化循环测试."""

    def test_init(self):
        orch = EvolutionOrchestrator(
            storage_dir=tempfile.mkdtemp(),
            skills_dir=tempfile.mkdtemp(),
        )
        assert orch is not None
        assert orch.learner is not None
        assert orch.generator is not None
        assert orch.evaluator is not None
        assert orch.feedback_collector is not None

    def test_record_interaction(self):
        """测试通过编排器记录交互."""
        orch = EvolutionOrchestrator(
            storage_dir=tempfile.mkdtemp(),
            skills_dir=tempfile.mkdtemp(),
        )
        record = make_interaction()
        orch.record_interaction(record)
        assert orch.learner.get_interaction_count() == 1
        # 隐式反馈应自动收集
        fb = orch.feedback_collector.get_feedback(record.id)
        assert fb is not None

    def test_record_with_explicit_feedback(self):
        """测试记录交互并收集显式反馈."""
        orch = EvolutionOrchestrator(
            storage_dir=tempfile.mkdtemp(),
            skills_dir=tempfile.mkdtemp(),
        )
        record = make_interaction()
        orch.record_interaction(record)
        orch.collect_explicit_feedback(record.id, "thumbs_up", "Excellent")
        fb = orch.feedback_collector.get_feedback(record.id)
        assert fb.explicit_rating == "thumbs_up"

    def test_full_evolution_cycle(self):
        """测试完整进化循环：交互→学习→生成→评估→反馈→更新."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        # 记录一批交互
        records = make_batch_interactions(15, success_rate=0.8, version="v1")
        for record in records:
            orch.record_interaction(record)

        # 为部分交互添加显式反馈
        for i, record in enumerate(records[:8]):
            rating = "thumbs_up" if record.success else "thumbs_down"
            orch.collect_explicit_feedback(record.id, rating)

        # 运行进化循环
        result = orch.run_evolution_cycle()

        # 验证结果
        assert result.patterns_extracted > 0
        assert result.policy_version.startswith("v")
        assert result.policy is not None
        assert result.evaluation_report is not None
        assert result.evaluation_report.interaction_count == 15
        assert result.feedback_stats["total_feedbacks"] > 0
        assert result.duration > 0

    def test_multiple_cycles(self):
        """测试多次进化循环（增量学习）."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        # 第一轮
        for _ in range(5):
            orch.record_interaction(make_interaction(
                tools=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                ],
                success=True,
            ))
        result1 = orch.run_evolution_cycle()

        # 第二轮
        for _ in range(5):
            orch.record_interaction(make_interaction(
                tools=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                ],
                success=True,
            ))
        result2 = orch.run_evolution_cycle()

        # 版本号应递增
        assert result2.policy_version != result1.policy_version
        # 交互总数应增加
        assert orch.learner.get_interaction_count() == 10

    def test_evolution_generates_skills(self):
        """测试进化循环能生成技能."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        # 记录高频高成功率交互
        for _ in range(8):
            orch.record_interaction(make_interaction(
                task="search and read files",
                tools=[
                    {"name": "search", "arguments": {"query": "test"}, "success": True, "output_summary": "ok"},
                    {"name": "read_file", "arguments": {"path": "/tmp/f"}, "success": True, "output_summary": "ok"},
                ],
                success=True,
                tags=["file_ops"],
            ))

        result = orch.run_evolution_cycle()

        # 应该生成了技能
        assert len(result.skills_generated) > 0
        # 验证生成的技能文件存在
        for skill in result.skills_generated:
            assert os.path.isfile(os.path.join(skill.skill_dir, "SKILL.md"))

    def test_evolution_with_mixed_feedback(self):
        """测试混合反馈下的进化循环."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        # 成功交互 + 正面反馈
        for i in range(5):
            record = make_interaction(
                success=True,
                duration=3.0,
                tools=[
                    {"name": "search", "arguments": {}, "success": True, "output_summary": ""},
                    {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                ],
            )
            orch.record_interaction(record)
            orch.collect_explicit_feedback(record.id, "thumbs_up")

        # 失败交互 + 负面反馈
        for i in range(5):
            record = make_interaction(
                success=False,
                duration=20.0,
                tools=[
                    {"name": "bash", "arguments": {}, "success": False, "output_summary": ""},
                ],
            )
            orch.record_interaction(record)
            orch.collect_explicit_feedback(record.id, "thumbs_down")

        result = orch.run_evolution_cycle()

        # 评估报告应反映混合结果
        metrics = result.evaluation_report.metrics
        assert metrics.completion_rate == 0.5  # 5/10
        assert metrics.user_satisfaction < 0.7  # 混合反馈

    def test_orchestrator_status(self):
        """测试编排器状态查询."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        for _ in range(5):
            orch.record_interaction(make_interaction())

        status = orch.get_status()
        assert status["total_interactions"] == 5
        assert status["cycles_run"] == 0
        assert "feedback_stats" in status

    def test_version_comparison_via_orchestrator(self):
        """测试通过编排器进行版本对比."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        records_a = make_batch_interactions(10, success_rate=0.3, version="v1")
        records_b = make_batch_interactions(10, success_rate=0.9, version="v2")

        comparison = orch.compare_versions(records_a, "v1", records_b, "v2")
        assert comparison["winner"] == "v2"
        assert comparison["differences"]["completion_rate"]["delta"] > 0

    def test_evolution_result_serializable(self):
        """测试进化结果可序列化为 JSON."""
        storage_dir = tempfile.mkdtemp()
        skills_dir = tempfile.mkdtemp()
        orch = EvolutionOrchestrator(
            storage_dir=storage_dir,
            skills_dir=skills_dir,
        )

        for _ in range(5):
            orch.record_interaction(make_interaction())

        result = orch.run_evolution_cycle()
        result_dict = result.to_dict()
        # 验证可序列化
        json_str = json.dumps(result_dict, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["patterns_extracted"] > 0
        assert "policy" in parsed
        assert "evaluation_report" in parsed


# ═══════════════════════════════════════════════════════════════
#  Test: Integration with Phase 2 SkillLoader
# ═══════════════════════════════════════════════════════════════


class TestSkillLoaderIntegration:
    """与 Phase 2 SkillLoader 的集成测试."""

    def test_generated_skill_loads_in_loader(self):
        """生成的技能能被 SkillLoader 发现和加载."""
        from suyi.skills.loader import SkillLoader

        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=2.0,
            example_arguments=[[{"query": "q"}, {"path": "f"}]],
            context_tags=["test"],
        )
        gen.generate_from_sequences([seq])

        # 用 SkillLoader 发现
        loader = SkillLoader(skills_dir)
        menu = loader.get_menu()
        assert len(menu) > 0

        # 加载第一个技能
        skill_name = menu[0].name
        content = loader.load_skill(skill_name)
        assert content is not None
        assert content.description != ""

    def test_generated_skill_matches_query(self):
        """生成的技能能通过关键词匹配."""
        from suyi.skills.loader import SkillLoader

        skills_dir = tempfile.mkdtemp()
        gen = SkillGenerator(
            skills_dir=skills_dir,
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=2.0,
            example_arguments=[[{"query": "q"}, {"path": "f"}]],
            context_tags=["search", "read"],
        )
        gen.generate_from_sequences([seq])

        loader = SkillLoader(skills_dir)
        matched = loader.match_skills("search read", top_k=5)
        assert len(matched) > 0

    def test_generated_skill_passes_scanner(self):
        """生成的技能应通过安全扫描."""
        from suyi.skills.scanner import SkillScanner

        gen = SkillGenerator(
            skills_dir=tempfile.mkdtemp(),
            storage_dir=tempfile.mkdtemp(),
        )
        seq = ToolSequence(
            tools=["search", "read_file"],
            frequency=5,
            success_rate=0.9,
            avg_duration=2.0,
        )
        _, content = gen.generate_skill_md(seq)
        scanner = SkillScanner()
        risk = scanner.scan(content)
        assert risk != "dangerous"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
