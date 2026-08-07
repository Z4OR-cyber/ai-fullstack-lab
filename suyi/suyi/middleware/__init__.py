"""Suyi 中间件链模块（Phase 2）.

提供四种中间件，按优先级排序组成默认链:

    优先级 10 — SummarizationMiddleware  对话压缩
    优先级 20 — MemoryInjectMiddleware    记忆注入
    优先级 30 — LoopDetectionMiddleware   循环检测
    优先级 40 — ClarificationMiddleware   澄清请求

排序原则（来自设计文档）:
    - 压缩排最前：先给上下文减负，后面所有处理都受益
    - 记忆注入排第二：在压缩后注入相关记忆
    - 循环检测排第三：监控 LLM 输出是否陷入死循环
    - 澄清排最后：所有中间件处理完再决定要不要问用户

使用示例::

    from suyi.middleware import get_default_middleware

    # 不带记忆管理器
    chain = get_default_middleware()
    print([m.name for m in chain])
    # ['SummarizationMiddleware', 'LoopDetectionMiddleware', 'ClarificationMiddleware']

    # 带记忆管理器
    from suyi import MemoryManager
    chain = get_default_middleware(memory_manager=MemoryManager())
    print([m.name for m in chain])
    # ['SummarizationMiddleware', 'MemoryInjectMiddleware',
    #  'LoopDetectionMiddleware', 'ClarificationMiddleware']
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.loop import Middleware, LoopState
from .base import MiddlewareBase
from .summarization import SummarizationMiddleware
from .memory_inject import MemoryInjectMiddleware
from .loop_detection import LoopDetectionMiddleware
from .clarification import ClarificationMiddleware

__all__ = [
    # 基类
    "MiddlewareBase",
    "Middleware",
    "LoopState",
    # 中间件
    "SummarizationMiddleware",
    "MemoryInjectMiddleware",
    "LoopDetectionMiddleware",
    "ClarificationMiddleware",
    # 工厂函数
    "get_default_middleware",
]


def get_default_middleware(
    memory_manager: Optional[Any] = None,
) -> list[Middleware]:
    """返回默认中间件链，按优先级排序.

    排序顺序:
        1. SummarizationMiddleware   (priority=10)  对话压缩
        2. MemoryInjectMiddleware    (priority=20)  记忆注入（仅当提供 memory_manager）
        3. LoopDetectionMiddleware   (priority=30)  循环检测
        4. ClarificationMiddleware   (priority=40)  澄清请求

    参数:
        memory_manager: 可选的 MemoryManager 实例.
                         提供时启用记忆注入中间件.

    返回:
        按优先级排序的中间件列表
    """
    chain: list[Middleware] = []

    # 1. 对话压缩（最先执行）
    chain.append(SummarizationMiddleware())

    # 2. 记忆注入（仅在提供 memory_manager 时启用）
    if memory_manager is not None:
        chain.append(MemoryInjectMiddleware(memory_manager))

    # 3. 循环检测
    chain.append(LoopDetectionMiddleware())

    # 4. 澄清请求（最后执行）
    chain.append(ClarificationMiddleware())

    return chain
