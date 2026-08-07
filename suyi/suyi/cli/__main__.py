"""Suyi CLI 入口点 — 支持 ``python -m suyi.cli`` 启动.

命令行参数:
    --config      配置文件路径
    --provider    LLM 提供商名称
    --model       模型名称
    --mock        使用 MockLLM 演示模式（无需 API key）
    --skills-dir  技能库目录路径

使用示例::

    # Mock 模式（推荐首次体验）
    python -m suyi.cli --mock

    # 指定模型
    python -m suyi.cli --provider openai --model gpt-4

    # 指定技能库
    python -m suyi.cli --mock --skills-dir ./my_skills
"""

import sys
import asyncio

from .repl import run_repl, run_repl_sync


def main() -> None:
    """CLI 主入口函数."""
    # 使用 run_repl_sync 兼容 Windows
    # run_repl 内部会解析 argparse 参数
    run_repl_sync()


if __name__ == "__main__":
    main()
