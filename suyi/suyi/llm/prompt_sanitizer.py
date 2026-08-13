"""
Prompt Sanitizer — 自动脱敏 LLM prompt 中的敏感信息。

在调用外部 LLM API 前，自动检测并脱敏 prompt 中的：
    - API Key（OpenAI/DeepSeek/GitHub/Kimi/Google/Anthropic/Bearer）
    - 文件路径（Windows/Unix home/App data/Coze Drive）
    - 邮箱地址
    - IP 地址（排除 127.0.0.1 / 0.0.0.0）
    - 密码模式（password= / secret= / token=）
    - 数据库连接串中的密码

Usage::

    from suyi.llm import PromptSanitizer

    sanitizer = PromptSanitizer()
    clean = sanitizer.sanitize("my key is sk-abc123...")
    # → "my key is [REDACTED]"

    # 清洗 messages 列表
    messages = [{"role": "user", "content": "check /home/user/.ssh/id_rsa"}]
    clean_messages = sanitizer.sanitize_messages(messages)

    # 自定义脱敏字符串
    sanitizer = PromptSanitizer(redact_str="***")

    # dry_run 模式：只记录不替换
    sanitizer = PromptSanitizer(dry_run=True)

    # 只启用部分检测类型
    sanitizer = PromptSanitizer(enabled_patterns={"api_key", "email"})

    # 获取清洗报告
    clean, report = sanitizer.sanitize_with_report("text with sk-abc123...")
"""

from __future__ import annotations

import re
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  数据结构定义
# ═══════════════════════════════════════════════════════════════


class PatternType(str, Enum):
    """敏感信息检测类型。"""

    API_KEY = "api_key"
    FILE_PATH = "file_path"
    EMAIL = "email"
    IP = "ip"
    PASSWORD = "password"
    DB_CONN = "db_conn"


@dataclass
class RedactionRecord:
    """单条脱敏记录。

    Attributes:
        type:            检测类型（api_key / file_path / email / ip / password / db_conn）
        original_pattern: 匹配的模式名称（如 openai_sk, github_pat 等）
        position:        匹配在文本中的起始位置
        context:         匹配周围的文本片段（用于调试）
        redacted:         是否实际执行了替换（dry_run 模式下为 False）
    """

    type: str
    original_pattern: str
    position: int
    context: str
    redacted: bool = True


@dataclass
class _PatternDef:
    """单个正则模式定义（内部使用）。

    Attributes:
        type:            检测类型
        name:            模式名称
        pattern:         正则表达式字符串
        replacement_mode: 替换模式 — "full" 替换整个匹配, "group" 替换指定分组
        replace_group:   replacement_mode="group" 时，要替换的分组索引（1-based）
    """

    type: str
    name: str
    pattern: str
    replacement_mode: str = "full"
    replace_group: int = 0


# ═══════════════════════════════════════════════════════════════
#  模式定义（按优先级排列）
# ═══════════════════════════════════════════════════════════════

# ── 优先级 1: API Key ──────────────────────────────────────────

_API_KEY_PATTERNS: list[_PatternDef] = [
    _PatternDef(PatternType.API_KEY.value, "openai_sk",
                r"sk-[a-zA-Z0-9]{20,}"),
    _PatternDef(PatternType.API_KEY.value, "github_pat",
                r"ghp_[a-zA-Z0-9]{20,}"),
    _PatternDef(PatternType.API_KEY.value, "kimi_ak",
                r"ak-[a-zA-Z0-9]{20,}"),
    _PatternDef(PatternType.API_KEY.value, "google_api",
                r"AIza[a-zA-Z0-9_-]{30,}"),
    _PatternDef(PatternType.API_KEY.value, "google_oauth",
                r"AQ\.[a-zA-Z0-9_-]{30,}"),
    _PatternDef(PatternType.API_KEY.value, "bearer_token",
                r"Bearer\s+[a-zA-Z0-9._/=+-]+"),
    _PatternDef(PatternType.API_KEY.value, "anthropic",
                r"sk-ant-[a-zA-Z0-9_-]{20,}"),
]

# ── 优先级 2: 文件路径 ─────────────────────────────────────────

_FILE_PATH_PATTERNS: list[_PatternDef] = [
    _PatternDef(PatternType.FILE_PATH.value, "windows_path",
                r"[A-Z]:\\[^\s\"'<>]+"),
    _PatternDef(PatternType.FILE_PATH.value, "unix_home",
                r"/home/[^\s\"'<>]+"),
    _PatternDef(PatternType.FILE_PATH.value, "app_data",
                r"/app/data/[^\s\"'<>]+"),
    _PatternDef(PatternType.FILE_PATH.value, "coze_drive",
                r"/Coze/Drive/[^\s\"'<>]+"),
]

# ── 优先级 3: 邮箱地址 ────────────────────────────────────────

_EMAIL_PATTERN = _PatternDef(
    PatternType.EMAIL.value, "email",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)

# ── 优先级 4: IP 地址（排除 127.0.0.1 / 0.0.0.0）──────────────

_IP_PATTERN = _PatternDef(
    PatternType.IP.value, "ipv4",
    r"\b(?!(?:127\.0\.0\.1|0\.0\.0\.0)\b)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
)

# ── 优先级 5: 密码模式 ─────────────────────────────────────────

_PASSWORD_PATTERNS: list[_PatternDef] = [
    _PatternDef(PatternType.PASSWORD.value, "password_kv",
                r"(password)\s*[:=]\s*(\S+)", "group", 2),
    _PatternDef(PatternType.PASSWORD.value, "secret_kv",
                r"(secret)\s*[:=]\s*(\S+)", "group", 2),
    _PatternDef(PatternType.PASSWORD.value, "token_kv",
                r"(token)\s*[:=]\s*(\S+)", "group", 2),
]

# ── 优先级 6: 数据库连接串 ────────────────────────────────────

_DB_CONN_PATTERNS: list[_PatternDef] = [
    _PatternDef(PatternType.DB_CONN.value, "db_conn",
                r"(postgres|mysql|mongodb)(://[^:]+:)([^@]+)(@)",
                "group", 3),
]

# ── 所有模式（按优先级排列）──────────────────────────────────

_ALL_PATTERNS: list[_PatternDef] = (
    _API_KEY_PATTERNS
    + _FILE_PATH_PATTERNS
    + [_EMAIL_PATTERN]
    + [_IP_PATTERN]
    + _PASSWORD_PATTERNS
    + _DB_CONN_PATTERNS
)

# 所有检测类型名称集合
ALL_PATTERN_TYPES: frozenset[str] = frozenset(pt.value for pt in PatternType)


# ═══════════════════════════════════════════════════════════════
#  PromptSanitizer
# ═══════════════════════════════════════════════════════════════


class PromptSanitizer:
    """Prompt 敏感信息脱敏器。

    自动检测并脱敏 LLM prompt 中的 API Key、文件路径、邮箱、IP 地址、
    密码模式、数据库连接串等敏感信息。

    按优先级依次处理各类模式，高优先级模式先执行，其替换结果会影响
    低优先级模式的匹配（例如 API Key 中的 IP 子串不会被二次脱敏）。

    Args:
        redact_str:       脱敏替换字符串，默认 ``"[REDACTED]"``
        log_redactions:   是否记录脱敏日志，默认 ``True``
        dry_run:          只记录不替换，默认 ``False``
        enabled_patterns: 启用的检测类型集合，``None`` 表示全部启用。
                          可选值：``"api_key"``, ``"file_path"``, ``"email"``,
                          ``"ip"``, ``"password"``, ``"db_conn"``

    Example::

        >>> sanitizer = PromptSanitizer()
        >>> sanitizer.sanitize("key is sk-abcdef1234567890abcdXYZ")
        'key is [REDACTED]'
        >>> sanitizer.sanitize_messages(
        ...     [{"role": "user", "content": "check /home/user/data"}]
        ... )
        [{'role': 'user', 'content': 'check [REDACTED]'}]
    """

    def __init__(
        self,
        redact_str: str = "[REDACTED]",
        log_redactions: bool = True,
        dry_run: bool = False,
        enabled_patterns: Optional[set[str]] = None,
    ):
        self.redact_str = redact_str
        self.log_redactions = log_redactions
        self.dry_run = dry_run
        # None → 全部启用；空集合 → 全部禁用
        self.enabled_patterns: set[str] = (
            enabled_patterns if enabled_patterns is not None else set(ALL_PATTERN_TYPES)
        )
        # 预过滤启用的模式
        self._patterns: list[_PatternDef] = [
            p for p in _ALL_PATTERNS if p.type in self.enabled_patterns
        ]
        self._redaction_log: list[RedactionRecord] = []

    # ── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _get_context(text: str, start: int, end: int, window: int = 30) -> str:
        """获取匹配位置周围的文本片段（用于调试）。"""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end]

    def _apply_pattern(self, text: str, pattern_def: _PatternDef) -> str:
        """对文本应用单个正则模式，返回处理后的文本。"""
        compiled = re.compile(pattern_def.pattern)

        def _replacer(m: re.Match) -> str:
            pos = m.start()
            context = self._get_context(text, m.start(), m.end())

            if self.log_redactions:
                self._redaction_log.append(
                    RedactionRecord(
                        type=pattern_def.type,
                        original_pattern=pattern_def.name,
                        position=pos,
                        context=context,
                        redacted=not self.dry_run,
                    )
                )

            if self.dry_run:
                return m.group(0)

            if pattern_def.replacement_mode == "group":
                # 只替换指定分组，保留其余部分
                full_match = m.group(0)
                g_start = m.start(pattern_def.replace_group) - m.start()
                g_end = m.end(pattern_def.replace_group) - m.start()
                return full_match[:g_start] + self.redact_str + full_match[g_end:]
            else:
                return self.redact_str

        return compiled.sub(_replacer, text)

    # ── 公共 API ──────────────────────────────────────────────

    def sanitize(self, text: str) -> str:
        """清洗单个字符串，返回脱敏后的文本。

        按优先级依次应用所有启用的检测模式。每次调用后脱敏记录自动
        累计到内部日志，可通过 :meth:`get_redaction_log` 查询或
        :meth:`reset_log` 清空。

        Args:
            text: 待清洗的文本

        Returns:
            脱敏后的文本（``dry_run=True`` 时返回原文）
        """
        if not text:
            return text

        for pattern_def in self._patterns:
            text = self._apply_pattern(text, pattern_def)

        return text

    def sanitize_messages(self, messages: list[dict]) -> list[dict]:
        """清洗 chat messages 列表，返回新的列表（不修改原列表）。

        对每条消息的 ``content`` 字段执行 :meth:`sanitize`。
        非 ``str`` 类型的 content（如 ``None`` 或 list）将被跳过。

        Args:
            messages: 消息列表，每项为 ``{"role": ..., "content": ...}``

        Returns:
            新的消息列表，原列表不受影响
        """
        new_messages: list[dict] = []
        for msg in messages:
            new_msg = dict(msg)  # shallow copy — 足够安全，content 是 str
            content = new_msg.get("content")
            if isinstance(content, str):
                new_msg["content"] = self.sanitize(content)
            new_messages.append(new_msg)
        return new_messages

    def get_redaction_log(self) -> list[dict]:
        """获取本次清洗记录。

        Returns:
            脱敏记录列表，每项为::

                {
                    "type": "api_key",           # 检测类型
                    "original_pattern": "openai_sk",  # 模式名称
                    "position": 10,              # 匹配起始位置
                    "context": "...",             # 周围文本
                    "redacted": True,             # 是否实际替换
                }
        """
        return [asdict(r) for r in self._redaction_log]

    def reset_log(self) -> None:
        """清空清洗记录。"""
        self._redaction_log.clear()

    def sanitize_with_report(self, text: str) -> tuple[str, list[dict]]:
        """清洗并返回 (清洗后文本, 清洗报告)。

        清洗报告仅包含本次调用产生的脱敏记录。

        Args:
            text: 待清洗的文本

        Returns:
            ``(sanitized_text, report)`` 元组，report 格式同
            :meth:`get_redaction_log`
        """
        before_count = len(self._redaction_log)
        result = self.sanitize(text)
        new_records = self._redaction_log[before_count:]
        return result, [asdict(r) for r in new_records]
