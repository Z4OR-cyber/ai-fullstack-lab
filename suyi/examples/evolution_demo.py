"""自进化示例 — 模拟多次交互，触发学习引擎分析模式.

本示例展示:
1. 如何记录 Agent 交互（InteractionRecord）
2. 学习引擎如何从交互中提取行为模式
3. 策略更新和经验规则巩固
4. 行为评估器生成评估报告
5. 反馈收集和信号归一化
6. 完整的进化循环（EvolutionOrchestrator）

运行方式:
    python examples/evolution_demo.py
"""

import asyncio
import sys
import os
import tempfile
import time

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suyi.evolution import (
    InteractionRecord,
    LearningEngine,
    BehaviorEvaluator,
    FeedbackCollector,
    EvolutionOrchestrator,
    EvaluationReport,
    Pattern,
    BehaviorPolicy,
)
from suyi.cli import formatter as fmt
from suyi.cli.formatter import (
    print_title, print_separator, green, yellow, cyan, red, dim, bold,
    format_key_value, format_list_item,
    info, success, warning, error,
)


# ═══════════════════════════════════════════════════════════════
#  模拟交互数据生成
# ═══════════════════════════════════════════════════════════════

def generate_mock_interactions() -> list[InteractionRecord]:
    """生成模拟的交互记录数据.

    模拟一个 Agent 在多次任务中的工具使用模式：
    - 成功模式：search → read_file → 回答（高频高成功率）
    - 失败模式：bash → bash → 超时（低成功率）
    - 混合模式：search → analyze → 回答

    Returns:
        交互记录列表.
    """
    records = []

    # ── 成功模式：search → read_file（6 次，全部成功）──
    for i in range(6):
        records.append(InteractionRecord(
            task=f"查找并阅读文档 #{i+1}",
            tool_calls=[
                {"name": "search", "arguments": {"query": f"doc_{i}"}, "success": True, "output_summary": "找到文档"},
                {"name": "read_file", "arguments": {"path": f"doc_{i}.md"}, "success": True, "output_summary": "读取成功"},
            ],
            success=True,
            duration=2.5 + i * 0.3,
            tokens_used=150 + i * 10,
            tags=["research", "reading"],
        ))

    # ── 失败模式：bash → bash（4 次，全部失败/超时）──
    for i in range(4):
        records.append(InteractionRecord(
            task=f"执行复杂命令 #{i+1}",
            tool_calls=[
                {"name": "bash", "arguments": {"command": "complex_cmd"}, "success": False, "output_summary": "超时"},
                {"name": "bash", "arguments": {"command": "retry_cmd"}, "success": False, "output_summary": "再次超时"},
            ],
            success=False,
            duration=65.0 + i * 5,
            tokens_used=300 + i * 20,
            tags=["automation", "failed"],
        ))

    # ── 混合模式：search → analyze（3 次，2 成功 1 失败）──
    for i in range(3):
        success_flag = i < 2
        records.append(InteractionRecord(
            task=f"搜索并分析 #{i+1}",
            tool_calls=[
                {"name": "search", "arguments": {"query": f"topic_{i}"}, "success": True, "output_summary": "找到结果"},
                {"name": "analyze", "arguments": {"data": "result"}, "success": success_flag, "output_summary": "分析完成" if success_flag else "分析失败"},
            ],
            success=success_flag,
            duration=5.0 + i * 1.5,
            tokens_used=200 + i * 30,
            tags=["research", "analysis"],
        ))

    return records


# ═══════════════════════════════════════════════════════════════
#  示例函数
# ═══════════════════════════════════════════════════════════════

def demo_learning_engine():
    """演示学习引擎：从交互记录中提取模式."""
    print_title("1. 学习引擎 — 模式提取", cyan)

    storage_dir = tempfile.mkdtemp(prefix="suyi_learn_")
    engine = LearningEngine(storage_dir=storage_dir)

    # 生成并记录交互
    records = generate_mock_interactions()
    engine.record_interactions(records)

    print(f"\n  {dim('已记录')} {len(records)} {dim('条交互记录')}")

    # 提取模式
    patterns = engine.extract_patterns()

    print(f"\n  {bold('提取到的行为模式:')}")
    print(f"  {'模式':<30} {'频率':>4} {'成功率':>6} {'类型':>8}")
    print(f"  {dim('─' * 55)}")

    for p in patterns[:10]:  # 只显示前 10 个
        seq = " → ".join(p.tool_sequence)
        if len(seq) > 28:
            seq = seq[:25] + "..."
        type_color = green if p.pattern_type == "success" else (red if p.pattern_type == "failure" else yellow)
        print(f"  {seq:<30} {p.frequency:>4} {p.success_rate:>5.0%}  {type_color(p.pattern_type):>8}")

    # 显示成功和失败模式
    success_patterns = engine.get_success_patterns()
    failure_patterns = engine.get_failure_patterns()

    print(f"\n  {green('成功模式')}: {len(success_patterns)} 个 (success_rate >= 70%)")
    print(f"  {red('失败模式')}: {len(failure_patterns)} 个 (success_rate < 30%)")

    return engine


def demo_policy_update(engine: LearningEngine):
    """演示策略更新和经验规则巩固."""
    print_title("2. 策略更新与经验规则", cyan)

    # 更新策略
    policy = engine.update_policy()

    print(f"\n  {bold('策略版本:')} {cyan(policy.version)}")
    print(f"  {bold('更新时间:')} {dim(time.ctime(policy.updated_at))}")

    # 工具偏好
    print(f"\n  {bold('工具偏好分数:')}")
    for tool, score in sorted(policy.tool_preferences.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20)
        print(f"    {yellow(tool):<14} {score:.3f} {green(bar)}")

    # 推荐序列
    print(f"\n  {bold('推荐工具序列:')}")
    if policy.preferred_sequences:
        for seq in policy.preferred_sequences:
            seq_str = " → ".join(seq["sequence"])
            print(f"    {green('✓')} {seq_str} {dim(f'(成功率: {seq["success_rate"]:.0%}, 频率: {seq["frequency"]})')}")
    else:
        print(f"    {dim('（无）')}")

    # 避免序列
    print(f"\n  {bold('应避免的工具序列:')}")
    if policy.avoidance_sequences:
        for seq in policy.avoidance_sequences:
            seq_str = " → ".join(seq["sequence"])
            print(f"    {red('✗')} {seq_str} {dim(f'(失败率: {seq["failure_rate"]:.0%}, 频率: {seq["frequency"]})')}")
    else:
        print(f"    {dim('（无）')}")

    # 经验规则
    rules = engine.consolidate_rules()
    print(f"\n  {bold('巩固的经验规则:')}")
    if rules:
        for i, rule in enumerate(rules, 1):
            tools = " → ".join(rule["condition"]["tool_sequence"])
            conf = rule["confidence"]
            print(f"    {yellow(str(i))}. {tools}")
            print(f"       {dim(f'置信度: {conf:.2f} | 预期成功率: {rule["action"]["expected_success_rate"]:.0%}')}")
    else:
        print(f"    {dim('（无）')}")

    # 统计信息
    print(f"\n  {bold('统计信息:')}")
    stats = policy.stats
    for key, value in stats.items():
        print(f"    {key}: {value}")

    return policy


def demo_evaluation(records: list[InteractionRecord]):
    """演示行为评估器：多维度评估 Agent 表现."""
    print_title("3. 行为评估", cyan)

    storage_dir = tempfile.mkdtemp(prefix="suyi_eval_")
    evaluator = BehaviorEvaluator(storage_dir=storage_dir)

    # 批量评估
    report = evaluator.evaluate_batch(records, version="v1")

    print(f"\n  {bold('评估报告 ID:')} {dim(report.id)}")
    print(f"  {bold('版本:')} {report.version}")
    print(f"  {bold('交互数:')} {report.interaction_count}")

    # 评估指标
    metrics = report.metrics
    print(f"\n  {bold('多维度评估指标:')}")
    print(f"  {dim('─' * 40)}")
    print(f"  {'维度':<20} {'分数':>8} {'进度条':>20}")
    print(f"  {dim('─' * 40)}")

    dimensions = [
        ("完成率", metrics.completion_rate),
        ("效率分数", metrics.efficiency_score),
        ("质量分数", metrics.quality_score),
        ("用户满意度", metrics.user_satisfaction),
        ("综合分数", metrics.overall_score),
    ]

    for name, score in dimensions:
        bar = "█" * int(score * 20)
        color = green if score >= 0.7 else (yellow if score >= 0.5 else red)
        print(f"  {name:<20} {score:>7.2%}  {color(bar)}")

    # 详细统计
    print(f"\n  {bold('详细统计:')}")
    details = metrics.details
    for key, value in details.items():
        print(f"    {key}: {value}")

    # 改进建议
    print(f"\n  {bold('改进建议:')}")
    for i, rec_text in enumerate(report.recommendations, 1):
        print(f"  {yellow(str(i))}. {rec_text}")

    return report


def demo_feedback(records: list[InteractionRecord]):
    """演示反馈收集器：收集显式和隐式反馈."""
    print_title("4. 反馈收集", cyan)

    storage_dir = tempfile.mkdtemp(prefix="suyi_fb_")
    collector = FeedbackCollector(storage_dir=storage_dir)

    # 从交互记录中自动收集隐式反馈
    for record in records:
        collector.collect_from_interaction(record)

    # 为部分交互添加显式反馈
    for i, record in enumerate(records):
        if i < 5:
            # 前 5 条给 thumbs_up
            collector.collect_explicit(record.id, "thumbs_up", "做得好！")
        elif i < 8:
            # 接下来 3 条给 thumbs_down
            collector.collect_explicit(record.id, "thumbs_down", "太慢了")

    # 显示反馈统计
    stats = collector.get_stats()

    print(f"\n  {bold('反馈统计:')}")
    print(format_key_value("总反馈数", stats["total_feedbacks"]))
    print(format_key_value("显式反馈", stats["explicit_feedbacks"]))
    print(format_key_value("仅隐式反馈", stats["implicit_only"]))
    print(format_key_value("正面反馈", green(str(stats["positive"]))))
    print(format_key_value("负面反馈", red(str(stats["negative"]))))
    print(format_key_value("中性反馈", yellow(str(stats["neutral"]))))

    avg_signal = stats["average_signal"]
    signal_color = green if avg_signal > 0 else (red if avg_signal < 0 else yellow)
    print(format_key_value("平均信号", signal_color(f"{avg_signal:+.3f}")))

    # 显示部分反馈信号详情
    print(f"\n  {bold('反馈信号详情（前 5 条）:')}")
    for i, record in enumerate(records[:5]):
        signal = collector.get_feedback_signal(record.id)
        if signal:
            print(f"    {dim(f'#{i+1}')} explicit={signal.explicit_signal:+.1f} "
                  f"implicit={signal.implicit_signal:+.3f} "
                  f"combined={signal.combined:+.3f}")


def demo_full_evolution_cycle():
    """演示完整的进化循环."""
    print_title("5. 完整进化循环", cyan)

    storage_dir = tempfile.mkdtemp(prefix="suyi_evo_")
    skills_dir = tempfile.mkdtemp(prefix="suyi_skills_")

    orchestrator = EvolutionOrchestrator(
        storage_dir=storage_dir,
        skills_dir=skills_dir,
    )

    # 记录交互
    records = generate_mock_interactions()
    orchestrator.record_interactions(records)

    print(f"\n  {dim('已记录')} {len(records)} {dim('条交互记录')}")
    print(f"  {dim('运行完整进化循环...')}")
    print()

    # 运行进化循环
    result = orchestrator.run_evolution_cycle()

    # 显示结果摘要
    print(f"  {bold('进化循环结果:')}")
    print(f"  {dim('─' * 45)}")
    print(format_key_value("循环 ID", result.cycle_id))
    print(format_key_value("提取模式数", result.patterns_extracted))
    print(format_key_value("策略版本", result.policy_version))
    print(format_key_value("生成技能数", len(result.skills_generated)))
    print(format_key_value("激活技能数", result.skills_activated))
    print(format_key_value("新经验规则", len(result.experience_rules)))
    print(format_key_value("耗时", f"{result.duration:.3f}s"))

    # 评估报告
    if result.evaluation_report:
        metrics = result.evaluation_report.metrics
        print(f"\n  {bold('评估指标:')}")
        print(format_key_value("综合分数", f"{metrics.overall_score:.2%}"))
        print(format_key_value("完成率", f"{metrics.completion_rate:.2%}"))
        print(format_key_value("效率分数", f"{metrics.efficiency_score:.2%}"))
        print(format_key_value("质量分数", f"{metrics.quality_score:.2%}"))
        print(format_key_value("满意度", f"{metrics.user_satisfaction:.2%}"))

    # 反馈统计
    if result.feedback_stats:
        fb = result.feedback_stats
        print(f"\n  {bold('反馈统计:')}")
        print(format_key_value("总反馈", fb.get("total_feedbacks", 0)))
        print(format_key_value("正面", green(str(fb.get("positive", 0)))))
        print(format_key_value("负面", red(str(fb.get("negative", 0)))))
        avg = fb.get("average_signal", 0.0)
        print(format_key_value("平均信号", f"{avg:+.3f}"))

    # 进化引擎状态
    print(f"\n  {bold('进化引擎状态:')}")
    status = orchestrator.get_status()
    for key, value in status.items():
        if isinstance(value, dict):
            print(f"    {key}:")
            for k2, v2 in value.items():
                print(f"      {k2}: {v2}")
        else:
            print(f"    {key}: {value}")


def main():
    """运行所有自进化示例."""
    print()
    print(fmt.banner("Suyi 自进化示例", fmt.Color.bright_cyan))
    print()
    print(dim("本示例使用 MockLLM 和模拟数据，无需 API key 即可运行."))
    print_separator(color=fmt.Color.dim)
    print()

    # 1. 学习引擎
    engine = demo_learning_engine()
    print()

    # 2. 策略更新
    demo_policy_update(engine)
    print()

    # 3. 行为评估
    records = generate_mock_interactions()
    demo_evaluation(records)
    print()

    # 4. 反馈收集
    demo_feedback(records)
    print()

    # 5. 完整进化循环
    demo_full_evolution_cycle()
    print()

    print_separator(color=fmt.Color.dim)
    print(success("自进化示例完成！"))


if __name__ == "__main__":
    main()
