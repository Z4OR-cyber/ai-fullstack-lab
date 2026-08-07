"""内容过滤 — PII 检测、敏感词过滤、注入攻击检测、有害内容检测.

过滤类别:
    1. PII 检测: 邮箱 / 电话 / 身份证号 / 银行卡号（正则匹配）
    2. 敏感词过滤: 可配置词表，支持自定义添加
    3. 注入攻击检测: prompt injection 模式
    4. 有害内容检测: 暴力 / 自残 / 违法等关键词

过滤动作:
    - block:  阻止内容通过
    - redact: 脱敏后放行（将敏感信息替换为占位符）
    - warn:   警告但放行

严格程度:
    - strict:   所有检测到的问题都 block
    - moderate: PII redact，注入/有害 block，敏感词 warn
    - lenient:  仅注入/有害 block，其余 warn
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ── 过滤动作常量 ──────────────────────────────────────────────

class FilterAction:
    """过滤动作常量."""

    BLOCK: str = "block"       # 阻止内容通过
    REDACT: str = "redact"     # 脱敏后放行
    WARN: str = "warn"         # 警告但放行
    PASS: str = "pass"          # 通过（无问题）


# ── 严格程度 ──────────────────────────────────────────────────

class Strictness:
    """严格程度常量."""

    STRICT: str = "strict"
    MODERATE: str = "moderate"
    LENIENT: str = "lenient"


# ── PII 检测正则 ──────────────────────────────────────────────

# 邮箱
_PII_EMAIL: re.Pattern[str] = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# 电话号码（中国大陆手机号 + 座机格式）
_PII_PHONE: re.Pattern[str] = re.compile(
    r"(?<!\d)(1[3-9]\d{9})(?!\d)"              # 手机号
    r"|(?:0\d{2,3}-?\d{7,8})(?!\d)"            # 座机
)

# 身份证号（18位，最后一位可能是X）
_PII_ID_CARD: re.Pattern[str] = re.compile(
    r"(?<!\d)([1-9]\d{5}(?:19|20)\d{2}"
    r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?!\d)"
)

# 银行卡号（16-19位连续数字）
_PII_BANK_CARD: re.Pattern[str] = re.compile(
    r"(?<!\d)([1-9]\d{15,18})(?!\d)"
)

# PII 模式映射
_PII_PATTERNS: Dict[str, re.Pattern[str]] = {
    "email": _PII_EMAIL,
    "phone": _PII_PHONE,
    "id_card": _PII_ID_CARD,
    "bank_card": _PII_BANK_CARD,
}

# PII 脱敏替换
_PII_REDACTIONS: Dict[str, str] = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "id_card": "[REDACTED_ID]",
    "bank_card": "[REDACTED_CARD]",
}


# ── 注入攻击模式 ──────────────────────────────────────────────

_INJECTION_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.I),
    re.compile(r"forget\s+(?:all\s+)?(?:previous|prior)\s+(?:messages?|context)", re.I),
    re.compile(r"you\s+are\s+(?:now|actually)\s+(?:a|an)\s+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
    re.compile(r"<\s*/?\s*imagine\s*>", re.I),
    re.compile(r"(?:reveal|show|print)\s+(?:the\s+)?(?:system\s+)?prompt", re.I),
    re.compile(r"(?:act|pretend|roleplay)\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a|an)?\s*(?:different|new)\s+", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s*mode", re.I),
]

# ── 有害内容关键词 ────────────────────────────────────────────

_HARMFUL_KEYWORDS: Set[str] = {
    # 暴力
    "bomb", "explosive", "weapon", "kill", "murder", "assassinate",
    "poison", "firearm", "ammunition",
    # 自残
    "suicide", "self-harm", "cut myself", "overdose", "end my life",
    # 违法
    "illegal drug", "cocaine", "heroin", "methamphetamine",
    "money laundering", "tax evasion", "counterfeit",
    "hack into", "steal password", "identity theft",
    # 中文
    "炸弹", "爆炸物", "武器", "杀人", "谋杀",
    "自杀", "自残", "过量服药",
    "毒品", "可卡因", "海洛因",
    "洗钱", "逃税", "伪造",
    "黑入", "窃取密码", "身份盗窃",
}


# ── 结果类型 ──────────────────────────────────────────────────


@dataclass
class FilterResult:
    """过滤结果.

    Attributes:
        passed:           是否通过（True 表示可以继续处理）.
        action:           过滤动作（pass/warn/redact/block）.
        reason:           过滤原因说明.
        redacted_content: 脱敏后的内容（仅 redact 动作时有意义）.
        detected:         检测到的问题列表.
    """

    passed: bool = True
    action: str = FilterAction.PASS
    reason: str = ""
    redacted_content: str = ""
    detected: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "passed": self.passed,
            "action": self.action,
            "reason": self.reason,
            "redacted_content": self.redacted_content,
            "detected": self.detected,
        }


# ── 默认敏感词表 ──────────────────────────────────────────────

_DEFAULT_SENSITIVE_WORDS: Set[str] = {
    "password", "passwd", "secret", "api_key", "apikey",
    "private_key", "access_token", "refresh_token",
    "密码", "密钥", "私钥", "令牌",
}


# ── 内容过滤器 ────────────────────────────────────────────────


class ContentFilter:
    """内容过滤器 — 输入/输出内容过滤.

    支持四类检测:
        1. PII 检测（邮箱/电话/身份证号/银行卡号）
        2. 敏感词过滤（可配置词表）
        3. 注入攻击检测（prompt injection patterns）
        4. 有害内容检测（暴力/自残/违法关键词）

    Args:
        strictness:    严格程度（strict/moderate/lenient）.
        sensitive_words: 自定义敏感词列表（与默认词表合并）.
        enable_pii:        是否启用 PII 检测（默认 True）.
        enable_injection:  是否启用注入检测（默认 True）.
        enable_harmful:    是否启用有害内容检测（默认 True）.
        enable_sensitive:  是否启用敏感词检测（默认 True）.

    使用示例::

        f = ContentFilter(strictness="moderate")

        # 输入过滤
        result = f.filter_input("我的邮箱是 test@example.com")
        assert result.action == "redact"
        assert "[REDACTED_EMAIL]" in result.redacted_content

        # 输出过滤
        result = f.filter_output("Here's how to make a bomb...")
        assert result.action == "block"
    """

    def __init__(
        self,
        strictness: str = Strictness.MODERATE,
        sensitive_words: Optional[List[str]] = None,
        enable_pii: bool = True,
        enable_injection: bool = True,
        enable_harmful: bool = True,
        enable_sensitive: bool = True,
    ) -> None:
        self.strictness: str = strictness
        self.enable_pii: bool = enable_pii
        self.enable_injection: bool = enable_injection
        self.enable_harmful: bool = enable_harmful
        self.enable_sensitive: bool = enable_sensitive

        # 合并敏感词
        self._sensitive_words: Set[str] = set(_DEFAULT_SENSITIVE_WORDS)
        if sensitive_words:
            self._sensitive_words.update(sensitive_words)

    def add_sensitive_words(self, words: List[str]) -> None:
        """添加自定义敏感词.

        Args:
            words: 敏感词列表.
        """
        self._sensitive_words.update(words)

    def remove_sensitive_word(self, word: str) -> None:
        """移除敏感词.

        Args:
            word: 要移除的敏感词.
        """
        self._sensitive_words.discard(word)

    # ── 输入过滤 ──────────────────────────────────────────────

    def filter_input(self, content: str) -> FilterResult:
        """过滤输入内容.

        按顺序检测: 注入攻击 → PII → 敏感词 → 有害内容.

        Args:
            content: 输入内容.

        Returns:
            FilterResult.
        """
        detected: List[Dict[str, Any]] = []

        # 1. 注入攻击检测（输入侧重点）
        if self.enable_injection:
            injection_hits: List[str] = self._detect_injection(content)
            if injection_hits:
                detected.append({
                    "type": "injection",
                    "matches": injection_hits,
                })

        # 2. PII 检测
        if self.enable_pii:
            pii_hits: Dict[str, List[str]] = self._detect_pii(content)
            if pii_hits:
                for pii_type, matches in pii_hits.items():
                    detected.append({
                        "type": "pii",
                        "pii_type": pii_type,
                        "matches": matches,
                    })

        # 3. 敏感词检测
        if self.enable_sensitive:
            sensitive_hits: List[str] = self._detect_sensitive(content)
            if sensitive_hits:
                detected.append({
                    "type": "sensitive_word",
                    "matches": sensitive_hits,
                })

        # 4. 有害内容检测
        if self.enable_harmful:
            harmful_hits: List[str] = self._detect_harmful(content)
            if harmful_hits:
                detected.append({
                    "type": "harmful_content",
                    "matches": harmful_hits,
                })

        return self._build_result(content, detected)

    # ── 输出过滤 ──────────────────────────────────────────────

    def filter_output(self, content: str) -> FilterResult:
        """过滤输出内容.

        输出侧重检测: 有害内容 → PII → 敏感词.
        （输出侧通常不需要检测注入攻击）

        Args:
            content: 输出内容.

        Returns:
            FilterResult.
        """
        detected: List[Dict[str, Any]] = []

        # 1. 有害内容检测（输出侧重点）
        if self.enable_harmful:
            harmful_hits: List[str] = self._detect_harmful(content)
            if harmful_hits:
                detected.append({
                    "type": "harmful_content",
                    "matches": harmful_hits,
                })

        # 2. PII 检测（防止输出中泄露 PII）
        if self.enable_pii:
            pii_hits: Dict[str, List[str]] = self._detect_pii(content)
            if pii_hits:
                for pii_type, matches in pii_hits.items():
                    detected.append({
                        "type": "pii",
                        "pii_type": pii_type,
                        "matches": matches,
                    })

        # 3. 敏感词检测
        if self.enable_sensitive:
            sensitive_hits: List[str] = self._detect_sensitive(content)
            if sensitive_hits:
                detected.append({
                    "type": "sensitive_word",
                    "matches": sensitive_hits,
                })

        return self._build_result(content, detected)

    # ── 检测方法 ──────────────────────────────────────────────

    def _detect_pii(self, content: str) -> Dict[str, List[str]]:
        """检测 PII 信息.

        Args:
            content: 内容字符串.

        Returns:
            PII 类型到匹配列表的映射.
        """
        results: Dict[str, List[str]] = {}
        for pii_type, pattern in _PII_PATTERNS.items():
            matches: List[str] = pattern.findall(content)
            if matches:
                # flatten if tuples (from alternation groups)
                flat: List[str] = []
                for m in matches:
                    if isinstance(m, tuple):
                        flat.extend(s for s in m if s)
                    else:
                        flat.append(m)
                if flat:
                    results[pii_type] = flat
        return results

    def _detect_injection(self, content: str) -> List[str]:
        """检测注入攻击模式.

        Args:
            content: 内容字符串.

        Returns:
            匹配到的注入模式列表.
        """
        hits: List[str] = []
        for pattern in _INJECTION_PATTERNS:
            matches: List[str] = pattern.findall(content)
            if matches:
                hits.extend(matches if isinstance(matches[0], str) else
                           [m[0] if isinstance(m, tuple) else str(m) for m in matches])
        # 去重
        return list(set(hits)) if hits else []

    def _detect_sensitive(self, content: str) -> List[str]:
        """检测敏感词.

        Args:
            content: 内容字符串.

        Returns:
            匹配到的敏感词列表.
        """
        content_lower: str = content.lower()
        hits: List[str] = []
        for word in self._sensitive_words:
            if word.lower() in content_lower:
                hits.append(word)
        return hits

    def _detect_harmful(self, content: str) -> List[str]:
        """检测有害内容.

        Args:
            content: 内容字符串.

        Returns:
            匹配到的有害关键词列表.
        """
        content_lower: str = content.lower()
        hits: List[str] = []
        for keyword in _HARMFUL_KEYWORDS:
            if keyword.lower() in content_lower:
                hits.append(keyword)
        return hits

    # ── 结果构建 ──────────────────────────────────────────────

    def _build_result(
        self, content: str, detected: List[Dict[str, Any]]
    ) -> FilterResult:
        """根据检测结果和严格程度构建 FilterResult.

        Args:
            content: 原始内容.
            detected: 检测到的问题列表.

        Returns:
            FilterResult.
        """
        if not detected:
            return FilterResult(
                passed=True,
                action=FilterAction.PASS,
                reason="No issues detected",
                redacted_content=content,
                detected=[],
            )

        # 分类问题
        has_injection: bool = any(
            d["type"] == "injection" for d in detected
        )
        has_harmful: bool = any(
            d["type"] == "harmful_content" for d in detected
        )
        has_pii: bool = any(d["type"] == "pii" for d in detected)
        has_sensitive: bool = any(
            d["type"] == "sensitive_word" for d in detected
        )

        # 根据严格程度决定动作
        action: str = FilterAction.WARN
        reason_parts: List[str] = []

        if self.strictness == Strictness.STRICT:
            # 严格模式：所有问题都 block
            action = FilterAction.BLOCK
            if has_injection:
                reason_parts.append("injection attack detected")
            if has_harmful:
                reason_parts.append("harmful content detected")
            if has_pii:
                reason_parts.append("PII detected")
            if has_sensitive:
                reason_parts.append("sensitive words detected")

        elif self.strictness == Strictness.MODERATE:
            # 中等模式：注入/有害 block，PII redact，敏感词 warn
            if has_injection or has_harmful:
                action = FilterAction.BLOCK
                if has_injection:
                    reason_parts.append("injection attack detected")
                if has_harmful:
                    reason_parts.append("harmful content detected")
            elif has_pii:
                action = FilterAction.REDACT
                reason_parts.append("PII detected and redacted")
            elif has_sensitive:
                action = FilterAction.WARN
                reason_parts.append("sensitive words detected")

        else:  # LENIENT
            # 宽松模式：仅注入/有害 block，其余 warn
            if has_injection or has_harmful:
                action = FilterAction.BLOCK
                if has_injection:
                    reason_parts.append("injection attack detected")
                if has_harmful:
                    reason_parts.append("harmful content detected")
            else:
                action = FilterAction.WARN
                if has_pii:
                    reason_parts.append("PII detected")
                if has_sensitive:
                    reason_parts.append("sensitive words detected")

        # 生成脱敏内容
        redacted: str = content
        if action in (FilterAction.REDACT, FilterAction.WARN):
            if has_pii:
                redacted = self._redact_pii(redacted)

        return FilterResult(
            passed=action != FilterAction.BLOCK,
            action=action,
            reason="; ".join(reason_parts) if reason_parts else "issues detected",
            redacted_content=redacted,
            detected=detected,
        )

    def _redact_pii(self, content: str) -> str:
        """脱敏 PII 信息.

        将 PII 替换为占位符.

        Args:
            content: 原始内容.

        Returns:
            脱敏后的内容.
        """
        result: str = content
        for pii_type, pattern in _PII_PATTERNS.items():
            placeholder: str = _PII_REDACTIONS[pii_type]
            result = pattern.sub(placeholder, result)
        return result
