"""严重程度评级模块

定义安全漏洞的严重程度等级，从 Critical（最严重）到 Info（信息性）。
评级标准参考 CVSS 通用漏洞评分系统。
"""

from enum import Enum


class Severity(str, Enum):
    """漏洞严重程度枚举

    Attributes:
        CRITICAL: 严重 - 可被远程利用，直接导致系统被攻破（如SQL注入、RCE）
        HIGH: 高危 - 可导致敏感数据泄露或权限提升（如硬编码密钥、SSRF）
        MEDIUM: 中危 - 需要特定条件才能利用（如弱加密、信息泄露）
        LOW: 低危 - 影响有限，难以直接利用
        INFO: 信息 - 最佳实践建议或代码质量问题
    """
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"

    @classmethod
    def from_value(cls, value: str) -> "Severity":
        """从字符串创建Severity枚举值"""
        for member in cls:
            if member.value.lower() == value.lower():
                return member
        return cls.INFO
