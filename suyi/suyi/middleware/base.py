"""中间件基类 — 重新导出 Phase 1 的 Middleware 并扩展优先级支持.

本模块从 ``evoagent.core.loop`` 重新导出 ``Middleware`` 和 ``LoopState``，
并提供 ``MiddlewareBase`` 扩展基类，增加 ``name``、``priority`` 属性
和 ``__repr__`` 方法，用于自动排序和调试.

优先级规则（数字越小优先级越高）:
    10 — 压缩中间件（最先执行，为后续减负）
    20 — 记忆注入（在压缩后注入相关记忆）
    30 — 循环检测（监控 LLM 输出是否陷入死循环）
    40 — 澄清中间件（最后执行，决定是否需要用户澄清）
"""

from __future__ import annotations

from ..core.loop import Middleware, LoopState

__all__ = ["MiddlewareBase", "Middleware", "LoopState"]


class MiddlewareBase(Middleware):
    """扩展的中间件基类，增加 name、priority 属性和 __repr__ 方法.

    所有 Phase 2 中间件应继承此类（而非直接继承 ``Middleware``），
    以获得统一的优先级排序和调试信息.

    属性:
        name:     中间件名称（默认使用类名）
        priority: 优先级（数字越小越高，默认 50）
    """

    @property
    def name(self) -> str:
        """中间件名称，默认使用类名."""
        return self.__class__.__name__

    @property
    def priority(self) -> int:
        """优先级，数字越小优先级越高. 默认 50（中等）."""
        return 50

    def __repr__(self) -> str:
        """返回中间件的字符串表示，包含名称和优先级."""
        return f"<{self.name}(priority={self.priority})>"
