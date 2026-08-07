"""工具使用示例 — 使用 MockLLM 演示 Agent 调用工具.

本示例展示:
1. Agent 如何通过工具调用执行搜索操作
2. Agent 如何读取文件
3. 权限系统的工作（auto / confirm / block）
4. FunctionTool 自定义工具的使用

运行方式:
    python examples/tool_use_demo.py
"""

import asyncio
import sys
import os
import tempfile

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suyi import (
    AgentLoop, MockLLM, LLMResponse, ToolCall,
    get_builtin_tools, PermissionManager,
    BashTool, ReadFileTool, WriteFileTool, SearchTool,
    PERMISSION_AUTO, PERMISSION_CONFIRM, PERMISSION_BLOCK,
)
from suyi.core.loop import FunctionTool
from suyi.cli.repl import adapt_agent_tool
from suyi.cli import formatter as fmt
from suyi.cli.formatter import (
    print_title, print_separator, green, yellow, cyan, red, dim, bold,
    format_tool_call, format_key_value, format_list_item,
    info, success, warning, error,
)


async def demo_search_tool():
    """演示 Agent 使用搜索工具.

    MockLLM 先发出一个 search 工具调用，然后基于工具结果给出最终答案.
    """
    print_title("1. 搜索工具调用", cyan)

    # 创建 MockLLM，预设两步响应：
    # 第一步：调用 search 工具（Thought + Action）
    # 第二步：基于搜索结果给出最终答案（Final Answer）
    mock_llm = MockLLM([
        LLMResponse.action(
            "search",
            {"query": "Python asyncio"},
            content="我需要搜索 Python asyncio 的相关信息.",
        ),
        LLMResponse.text(
            "根据搜索结果，Python asyncio 是一个用于编写并发代码的库，"
            "使用 async/await 语法。它特别适合 I/O 密集型任务，"
            "如网络请求、文件操作和数据库查询。"
        ),
    ])

    # 获取内置工具（SearchTool 默认返回 mock 结果）
    # 使用适配器将 AgentTool 转换为 AgentLoop 兼容的 Tool 接口
    tools = [adapt_agent_tool(t) for t in get_builtin_tools()]

    # 创建 AgentLoop
    loop = AgentLoop(llm=mock_llm, tools=tools)

    # 运行对话
    result = await loop.run("帮我搜索 Python asyncio 的信息")

    # 显示结果
    print(f"\n  {bold('用户:')} 帮我搜索 Python asyncio 的信息")

    # 显示工具调用历史
    for msg in result.history:
        if msg.get("role") == "tool":
            tool_name = msg.get("name", "unknown")
            content = str(msg.get("content", ""))
            # 截断过长的工具输出
            display = content[:100] + "..." if len(content) > 100 else content
            print(f"  {green('✓')} {yellow(tool_name)}: {dim(display)}")

    print(f"\n  {bold('Suyi:')} {result.content}")
    print()
    print(dim(f"  轮数: {result.turns_used} | 工具调用: {sum(1 for m in result.history if m.get('role') == 'tool')} 次"))


async def demo_read_file_tool():
    """演示 Agent 使用文件读取工具.

    先创建一个临时文件，然后让 Agent 读取它.
    """
    print_title("2. 文件读取工具", cyan)

    # 创建临时文件
    tmpdir = tempfile.mkdtemp(prefix="suyi_tool_")
    test_file = os.path.join(tmpdir, "test.txt")
    with open(test_file, "w") as f:
        f.write("Hello from Suyi!\nThis is a test file.\nLine 3 of content.")

    # 创建 MockLLM：先读取文件，再总结内容
    mock_llm = MockLLM([
        LLMResponse.action(
            "read_file",
            {"path": test_file},
            content="让我读取这个文件的内容.",
        ),
        LLMResponse.text(
            f"文件内容已读取。该文件包含 3 行文本，"
            f"主要内容是一句问候语和一些测试内容。"
        ),
    ])

    # 创建 AgentLoop（只使用 ReadFileTool，适配为 Tool 接口）
    read_tool = adapt_agent_tool(ReadFileTool())
    loop = AgentLoop(llm=mock_llm, tools=[read_tool])

    # 运行对话
    result = await loop.run(f"请读取文件 {test_file} 并总结内容")

    print(f"\n  {bold('用户:')} 请读取文件并总结内容")
    print(f"  {bold('Suyi:')} {result.content}")
    print()
    print(dim(f"  文件路径: {test_file}"))


async def demo_permission_system():
    """演示权限系统的工作.

    展示三种权限级别：
    - auto: 只读操作，自动执行（如 ls）
    - confirm: 需要确认的操作（如 rm）
    - block: 硬限制，禁止执行（如 rm -rf /）
    """
    print_title("3. 权限系统", cyan)

    bash = BashTool()
    read_file = ReadFileTool()
    write_file = WriteFileTool()

    print(f"\n  {bold('内置工具权限级别:')}")
    print(format_key_value("read_file", green("auto"), indent=4))
    print(format_key_value("bash (默认)", yellow("confirm"), indent=4))
    print(format_key_value("write_file", yellow("confirm"), indent=4))

    # 展示 BashTool 的运行时风险评估
    print(f"\n  {bold('BashTool 运行时风险评估:')}")
    test_cases = [
        ("ls -la", "安全命令"),
        ("cat file.txt", "安全命令"),
        ("git status", "安全命令"),
        ("rm file.txt", "需确认"),
        ("rm -rf /", "危险命令"),
        ("mkfs /dev/sda1", "危险命令"),
    ]

    for cmd, expected in test_cases:
        from suyi.tools.base import ToolContext
        ctx = ToolContext()
        risk = bash.assess_risk({"command": cmd}, ctx)
        if risk == PERMISSION_AUTO:
            risk_str = green("auto")
        elif risk == PERMISSION_CONFIRM:
            risk_str = yellow("confirm")
        elif risk == PERMISSION_BLOCK:
            risk_str = red("block")
        else:
            risk_str = dim("None (→confirm)")
        print(f"    {yellow(cmd):<22} → {risk_str}  {dim(f'({expected})')}")

    # 展示权限回调
    print(f"\n  {bold('权限回调演示:')}")
    print(dim("    当工具权限为 'confirm' 时，需要 permission_callback 确认."))

    # 创建一个自动批准所有请求的回调
    async def auto_approve(tool_name: str, arguments: dict) -> bool:
        print(f"    {dim(f'[权限回调] {tool_name}({arguments}) → 已批准')}")
        return True

    # 使用需要确认的工具
    mock_llm = MockLLM([
        LLMResponse.action("bash", {"command": "echo Hello"}, content="执行 echo 命令."),
        LLMResponse.text("命令执行成功，输出了 Hello."),
    ])

    loop = AgentLoop(
        llm=mock_llm,
        tools=[adapt_agent_tool(bash)],
        permission_callback=auto_approve,
    )

    result = await loop.run("执行 echo Hello 命令")
    print(f"\n  {bold('结果:')} {result.content}")


async def demo_custom_tool():
    """演示自定义工具的使用.

    使用 FunctionTool 包装一个自定义函数作为 Agent 工具.
    """
    print_title("4. 自定义工具", cyan)

    # 定义一个自定义计算器工具
    def calculate(expression: str) -> str:
        """安全地计算数学表达式."""
        try:
            # 只允许数字和基本运算符
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return "错误: 表达式包含非法字符"
            result = eval(expression)  # noqa: S307 — 已做字符过滤
            return f"{expression} = {result}"
        except Exception as e:
            return f"计算错误: {e}"

    # 包装为 FunctionTool
    calc_tool = FunctionTool(
        name="calculate",
        description="计算数学表达式. 输入: {'expression': str}",
        func=calculate,
    )

    # 创建 MockLLM：先调用计算器，再回答
    mock_llm = MockLLM([
        LLMResponse.action(
            "calculate",
            {"expression": "2 * (3 + 4)"},
            content="让我计算这个表达式.",
        ),
        LLMResponse.text("计算结果为 14。2 * (3 + 4) = 2 * 7 = 14。"),
    ])

    loop = AgentLoop(llm=mock_llm, tools=[calc_tool])

    result = await loop.run("计算 2 * (3 + 4) 等于多少？")

    print(f"\n  {bold('用户:')} 计算 2 * (3 + 4) 等于多少？")

    # 显示工具调用
    for msg in result.history:
        if msg.get("role") == "tool":
            print(f"  {green('✓')} {yellow('calculate')}: {dim(msg.get('content', ''))}")

    print(f"\n  {bold('Suyi:')} {result.content}")


async def main():
    """运行所有工具使用示例."""
    print()
    print(fmt.banner("Suyi 工具使用示例", fmt.Color.bright_cyan))
    print()
    print(dim("本示例使用 MockLLM，无需 API key 即可运行."))
    print_separator(color=fmt.Color.dim)
    print()

    await demo_search_tool()
    print()

    await demo_read_file_tool()
    print()

    await demo_permission_system()
    print()

    await demo_custom_tool()
    print()

    print_separator(color=fmt.Color.dim)
    print(success("工具使用示例完成！"))


if __name__ == "__main__":
    asyncio.run(main())
