"""基础对话示例 — 使用 MockLLM 演示单轮和多轮对话.

本示例展示:
1. 如何使用 MockLLM 创建预设响应
2. 单轮对话的基本流程
3. 多轮对话中记忆系统的作用
4. LoopResult 的基本属性

运行方式:
    python examples/basic_chat.py
"""

import asyncio
import sys
import os

# 将项目根目录加入 sys.path，确保能导入 suyi 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suyi import (
    AgentLoop, MockLLM, LLMResponse,
    MemoryManager, get_builtin_tools, get_default_middleware,
)
from suyi.cli import formatter as fmt
from suyi.cli.formatter import (
    print_title, print_separator, green, yellow, cyan, dim, bold,
    format_key_value, info, success,
)


async def demo_single_turn():
    """演示单轮对话.

    MockLLM 预设一条文本响应，AgentLoop 处理用户消息后直接返回最终答案.
    """
    print_title("1. 单轮对话", cyan)

    # 创建 MockLLM，预设一条纯文本响应（无工具调用 → 最终答案）
    mock_llm = MockLLM([
        LLMResponse.text(
            "你好！我是 Suyi，一个自进化的 AI Agent 框架。"
            "我可以进行多轮对话、使用工具、甚至自我学习优化。"
        ),
    ])

    # 创建 AgentLoop（不使用工具和中间件，最简配置）
    loop = AgentLoop(llm=mock_llm)

    # 运行对话
    result = await loop.run("你好，请介绍一下你自己")

    # 显示结果
    print(f"\n  {bold('用户:')} 你好，请介绍一下你自己")
    print(f"  {bold('Suyi:')} {result.content}")
    print()
    print(dim(f"  轮数: {result.turns_used} | 完整: {result.is_complete} | 原因: {result.stop_reason}"))


async def demo_multi_turn():
    """演示多轮对话.

    使用同一个 MockLLM 实例处理多条消息，展示多轮对话流程.
    """
    print_title("2. 多轮对话", cyan)

    # 创建 MockLLM，预设多轮响应
    # 第一轮：回答问题
    # 第二轮：基于"记忆"回答后续问题（实际是预设响应）
    mock_llm = MockLLM([
        LLMResponse.text("Python 是一种高级编程语言，以简洁和易读著称。"),
        LLMResponse.text("Python 的 GIL（全局解释器锁）限制了多线程的真正并行执行。"),
    ])

    # 使用记忆管理器，展示记忆系统的工作
    import tempfile
    memory_manager = MemoryManager(storage_dir=tempfile.mkdtemp(prefix="suyi_demo_"))
    middleware = get_default_middleware(memory_manager)

    # 创建带中间件的 AgentLoop
    loop = AgentLoop(
        llm=mock_llm,
        middleware_chain=middleware,
    )

    # 第一轮对话
    print(f"\n  {bold('用户:')} 什么是 Python？")
    result1 = await loop.run("什么是 Python？")
    print(f"  {bold('Suyi:')} {result1.content}")

    # 将第一轮对话记录到记忆系统
    memory_manager.add_message("user", "什么是 Python？")
    memory_manager.add_message("assistant", result1.content)

    # 第二轮对话
    print(f"\n  {bold('用户:')} Python 有什么限制？")
    result2 = await loop.run("Python 有什么限制？")
    print(f"  {bold('Suyi:')} {result2.content}")

    # 显示记忆系统状态
    print()
    print(dim("  --- 记忆系统状态 ---"))
    status = memory_manager.get_status()
    print(format_key_value("Working Memory 消息数", status["working"]["messages"], indent=4))
    print(format_key_value("对话轮次", status["working"]["turn_count"], indent=4))


async def demo_with_memory():
    """演示记忆系统的存储和检索.

    向语义记忆中添加知识，然后检索相关内容.
    """
    print_title("3. 记忆系统", cyan)

    import tempfile
    mgr = MemoryManager(storage_dir=tempfile.mkdtemp(prefix="suyi_mem_"))

    # 添加语义记忆（知识库）
    mgr.add_memory("Python asyncio 使用 async/await 语法编写并发代码", tags=["python", "asyncio"])
    mgr.add_memory("Rust 使用所有权模型实现内存安全，无需垃圾回收", tags=["rust", "memory"])
    mgr.add_memory("Go 使用 goroutine 和 channel 实现轻量级并发", tags=["go", "concurrency"])

    print(f"\n  {dim('已添加 3 条语义记忆')}")

    # 检索相关记忆
    results = mgr.retrieve_relevant("Python 并发编程")

    print(f"\n  {bold('检索 "Python 并发编程" 的结果:')}")
    for i, r in enumerate(results, 1):
        content = r.get("content", "")[:60]
        score = r.get("score", 0)
        layer = r.get("layer", "?")
        print(f"  {yellow(str(i))}. [{layer}] {content}... {dim(f'(score: {score:.3f})')}")

    # 显示记忆状态
    print()
    print(dim("  --- 记忆系统状态 ---"))
    status = mgr.get_status()
    print(format_key_value("Semantic 条目数", status["semantic"]["entries"], indent=4))
    print(format_key_value("词汇表大小", status["semantic"]["vocabulary"], indent=4))


async def main():
    """运行所有基础对话示例."""
    print()
    print(fmt.banner("Suyi 基础对话示例", fmt.Color.bright_cyan))
    print()
    print(dim("本示例使用 MockLLM，无需 API key 即可运行."))
    print_separator(color=fmt.Color.dim)
    print()

    await demo_single_turn()
    print()

    await demo_multi_turn()
    print()

    await demo_with_memory()
    print()

    print_separator(color=fmt.Color.dim)
    print(success("基础对话示例完成！"))


if __name__ == "__main__":
    asyncio.run(main())
