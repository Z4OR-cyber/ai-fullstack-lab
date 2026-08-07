"""Suyi Guardrails 模块 — 内容过滤、输出验证、中间件集成.

提供安全过滤和输出验证:

    ContentFilter       — 输入/输出内容过滤（PII / 敏感词 / 注入攻击 / 有害内容）
    OutputValidator     — LLM 输出格式验证（JSON / 代码安全 / URL）
    GuardrailsMiddleware — 中间件集成（priority=15，在压缩之后，记忆注入之前）

使用示例::

    from suyi.guardrails import ContentFilter, OutputValidator, GuardrailsMiddleware

    # 内容过滤
    f = ContentFilter()
    result = f.filter_input("我的邮箱是 test@example.com")
    # FilterResult(passed=True, action='redact', reason='PII detected', ...)

    # 输出验证
    v = OutputValidator()
    result = v.validate('{"name": "test"}')
    # ValidationResult(valid=True, ...)

    # 中间件集成
    mw = GuardrailsMiddleware(filter=ContentFilter(), validator=OutputValidator())
"""

from .filters import ContentFilter, FilterResult, FilterAction, Strictness
from .validator import OutputValidator, ValidationResult, ValidationIssue
from .middleware import GuardrailsMiddleware

__all__ = [
    "ContentFilter",
    "FilterResult",
    "FilterAction",
    "Strictness",
    "OutputValidator",
    "ValidationResult",
    "ValidationIssue",
    "GuardrailsMiddleware",
]
