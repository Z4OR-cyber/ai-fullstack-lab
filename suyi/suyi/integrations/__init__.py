"""
Suyi Integrations Package.

第三方平台集成模块，提供统一的外部服务适配层。

当前包含:
    - bounty: 多平台漏洞赏金报告统一提交适配器
"""

from . import bounty

__all__ = ["bounty"]
