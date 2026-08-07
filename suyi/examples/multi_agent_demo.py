"""多Agent示例 — 使用 MockLLM 演示 OrchestratorAgent 分解任务.

本示例展示:
1. OrchestratorAgent 的任务分解 → 并行调度 → 结果聚合流程
2. Pipeline 模式（串行数据流：A → B → C）
3. Blackboard 模式（共享黑板，Agent 间通过共享空间通信）
4. Voting 模式（多 Agent 投票决策）

运行方式:
    python examples/multi_agent_demo.py
"""

import asyncio
import sys
import os

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suyi import (
    AgentInstance, AgentConfig,
    OrchestratorAgent, SubAgentConfig,
    Pipeline, PipelineStage,
    Blackboard, BlackboardEntry,
    Voting, Vote, VoteResult, VotingStrategy,
    MockLLM, LLMResponse,
)
from suyi.core.loop import FunctionTool
from suyi.cli import formatter as fmt
from suyi.cli.formatter import (
    print_title, print_separator, green, yellow, cyan, red, dim, bold,
    format_key_value, format_list_item,
    info, success, warning, error,
)


async def demo_orchestrator():
    """演示 OrchestratorAgent 的任务分解与并行调度.

    编排者将复杂任务分解为子任务，分配给子 Agent 并行执行，
    最后聚合结果.
    """
    print_title("1. OrchestratorAgent 任务分解", cyan)

    # 创建工具池（子 Agent 可使用的工具）
    def search_fn(**kwargs):
        return f"搜索结果: 找到了关于 {kwargs.get('query', '')} 的信息."

    def analyze_fn(**kwargs):
        return f"分析结果: {kwargs.get('data', '')} 的关键要点已提取."

    tool_pool = {
        "search": FunctionTool("search", "搜索信息", search_fn),
        "analyze": FunctionTool("analyze", "分析数据", analyze_fn),
    }

    # 编排者的 LLM：
    # 第一次调用 → 分解任务（输出 SUBTASK: 行）
    # 第二次调用 → 聚合结果
    orch_llm = MockLLM([
        LLMResponse.text(
            "SUBTASK: 搜索 Python asyncio 的最佳实践\n"
            "SUBTASK: 分析搜索结果的关键要点"
        ),
        LLMResponse.text(
            "综合研究结果：Python asyncio 的最佳实践包括使用 "
            "async/await 语法、合理管理任务生命周期、以及避免 "
            "阻塞操作。关键要点是理解事件循环的工作机制。"
        ),
    ])

    # 创建编排者
    orchestrator = OrchestratorAgent(
        llm=orch_llm,
        tool_pool=tool_pool,
        max_workers=4,
    )

    # 注册子 Agent 配置
    # 研究员：可以使用 search 工具
    orchestrator.register_subagent(
        SubAgentConfig(
            name="researcher",
            description="信息检索专家",
            tool_names=["search"],
        ),
        # 子 Agent 的 LLM：调用 search 工具后给出结果
        llm=MockLLM([
            LLMResponse.action("search", {"query": "Python asyncio"}, content="搜索中..."),
            LLMResponse.text("找到 3 篇关于 asyncio 最佳实践的文章。"),
        ]),
    )

    # 分析师：可以使用 analyze 工具
    orchestrator.register_subagent(
        SubAgentConfig(
            name="analyst",
            description="数据分析专家",
            tool_names=["analyze"],
        ),
        llm=MockLLM([
            LLMResponse.action("analyze", {"data": "asyncio articles"}, content="分析中..."),
            LLMResponse.text("关键要点：1) 使用 async/await 2) 管理任务 3) 避免阻塞。"),
        ]),
    )

    # 运行编排
    print(f"\n  {bold('任务:')} 研究 Python asyncio 并分析关键要点")
    print(dim("  正在分解任务..."))

    result = await orchestrator.run("研究 Python asyncio 并分析关键要点")

    # 显示分解的子任务
    print(f"\n  {bold('分解的子任务:')}")
    for i, subtask in enumerate(orchestrator.last_subtasks, 1):
        print(f"    {yellow(str(i))}. [{subtask.subagent_name}] {subtask.description}")

    # 显示子任务结果
    print(f"\n  {bold('子任务结果:')}")
    for sr in result.subtask_results:
        status = green("✓") if sr.success else red("✗")
        print(f"    {status} [{sr.subagent_name}] {sr.content[:60]}...")

    # 显示聚合结果
    print(f"\n  {bold('最终答案:')}")
    print(f"  {result.content}")
    print()
    print(dim(f"  子任务数: {result.subtask_count} | 失败: {result.failed_count} | 成功: {result.success}"))


async def demo_pipeline():
    """演示 Pipeline 模式（串行数据流）.

    三个 Agent 串联：提取 → 分析 → 报告.
    每个阶段的输出是下一个阶段的输入.
    """
    print_title("2. Pipeline 管道链", cyan)

    # 创建三个 Agent
    # Agent 1: 提取器 — 从原始文本中提取关键信息
    extractor = AgentInstance(
        config=AgentConfig(
            name="extractor",
            role="信息提取器",
            description="从文本中提取关键信息",
        ),
        llm=MockLLM([LLMResponse.text("提取到的关键信息：产品名称、价格、库存数量。")]),
    )

    # Agent 2: 分析师 — 分析提取的信息
    analyzer = AgentInstance(
        config=AgentConfig(
            name="analyzer",
            role="数据分析师",
            description="分析提取的数据",
        ),
        llm=MockLLM([LLMResponse.text("分析结论：库存充足，价格合理，建议立即上架。")]),
    )

    # Agent 3: 报告生成器 — 生成最终报告
    reporter = AgentInstance(
        config=AgentConfig(
            name="reporter",
            role="报告生成器",
            description="生成最终报告",
        ),
        llm=MockLLM([LLMResponse.text("【最终报告】基于提取和分析，建议立即上架该产品。")]),
    )

    # 构建 Pipeline
    pipeline = Pipeline([
        PipelineStage(agent=extractor, name="提取"),
        PipelineStage(agent=analyzer, name="分析"),
        PipelineStage(agent=reporter, name="报告"),
    ])

    # 运行 Pipeline
    input_text = "产品: Suyi Agent 框架, 价格: 免费, 库存: 无限"
    print(f"\n  {bold('输入:')} {input_text}")
    print(dim("  Pipeline 执行中 (提取 → 分析 → 报告)..."))

    result = await pipeline.run(input_text)

    # 显示各阶段输出
    print(f"\n  {bold('各阶段输出:')}")
    for stage_name, output in result.stage_outputs:
        print(f"    {cyan(stage_name)}: {output[:60]}...")

    # 显示最终输出
    print(f"\n  {bold('最终输出:')} {result.final_output}")
    print()
    print(dim(f"  阶段数: {len(result.stage_outputs)} | 成功: {result.success}"))


async def demo_blackboard():
    """演示 Blackboard 模式（共享黑板）.

    多个 Agent 通过共享黑板空间交换数据，实现松耦合协作.
    """
    print_title("3. Blackboard 共享黑板", cyan)

    # 创建黑板
    bb = Blackboard()

    # 订阅 "research" 分区的变更
    notifications = []
    def on_research_update(entry: BlackboardEntry):
        notifications.append(f"{entry.author} 写入了 {entry.key}")

    bb.subscribe("research", on_research_update)

    # Agent 1（研究员）写入研究结果
    bb.write(
        partition="research",
        key="findings",
        value={"topic": "AI Agents", "summary": "Agent 框架正在快速发展"},
        author="researcher",
    )
    print(f"\n  {bold('研究员')} 写入 research/findings")

    # Agent 2（分析师）读取研究员的结果并写入分析
    findings = bb.read("research", "findings")
    bb.write(
        partition="analysis",
        key="summary",
        value=f"基于 {findings['topic']} 的分析：技术成熟度提升",
        author="analyst",
    )
    print(f"  {bold('分析师')} 读取 findings → 写入 analysis/summary")

    # Agent 3（报告员）读取所有分区并生成报告
    all_research = bb.read_partition("research")
    all_analysis = bb.read_partition("analysis")
    print(f"  {bold('报告员')} 读取所有分区:")

    print(f"\n  {bold('黑板内容:')}")
    for partition in bb.list_partitions():
        print(f"    {cyan(partition)}:")
        for key in bb.list_keys(partition):
            entry = bb.read_entry(partition, key)
            value_str = str(entry.value)[:50]
            print(f"      {yellow(key)} = {value_str}... {dim(f'(by {entry.author}, v{entry.version})')}")

    # 显示通知
    print(f"\n  {bold('通知:')}")
    for n in notifications:
        print(f"    {dim('🔔')} {n}")

    print()
    print(dim(f"  分区数: {len(bb.list_partitions())} | 总条目: {bb.total_entries()}"))


async def demo_voting():
    """演示 Voting 模式（多 Agent 投票决策）.

    三个 Agent 对方案进行投票，使用不同策略比较结果.
    """
    print_title("4. Voting 投票决策", cyan)

    # 创建三种投票策略的投票实例
    strategies = [
        ("多数投票", VotingStrategy.MAJORITY),
        ("加权投票", VotingStrategy.WEIGHTED),
        ("置信度投票", VotingStrategy.CONFIDENCE),
    ]

    # 投票数据：三个 Agent 对两个方案投票
    votes_data = [
        ("agent_1", "方案A", 2.0, 0.9, "方案A 更成熟"),
        ("agent_2", "方案B", 1.0, 0.7, "方案B 更创新"),
        ("agent_3", "方案A", 1.5, 0.8, "同意方案A"),
    ]

    for strategy_name, strategy in strategies:
        voting = Voting(strategy=strategy)

        for voter, choice, weight, confidence, reason in votes_data:
            voting.add_vote(voter, choice, weight, confidence, reason)

        result = voting.decide()

        print(f"\n  {bold(strategy_name)}:")
        print(f"    获胜: {green(result.winner)}")
        print(f"    票数: {result.total_votes}")
        print(f"    详细统计:")
        for choice, tally in result.tallies.items():
            print(f"      {yellow(choice)}: {tally:.1f}")
        print(f"    优势: {result.margin:.1f} | 平局: {result.is_tie}")


async def main():
    """运行所有多Agent示例."""
    print()
    print(fmt.banner("Suyi 多Agent示例", fmt.Color.bright_cyan))
    print()
    print(dim("本示例使用 MockLLM，无需 API key 即可运行."))
    print_separator(color=fmt.Color.dim)
    print()

    await demo_orchestrator()
    print()

    await demo_pipeline()
    print()

    await demo_blackboard()
    print()

    await demo_voting()
    print()

    print_separator(color=fmt.Color.dim)
    print(success("多Agent示例完成！"))


if __name__ == "__main__":
    asyncio.run(main())
