"""Message Classifier — 平凡消息分类器。

识别 trivial 消息（如 "好的"、"谢谢"、"嗯嗯" 等），
这些消息跳过记忆写入但保留在会话历史中。

分类策略:
    1. 规则匹配: 预定义的 trivial 词汇/模式
    2. 轻量判断: 长度、标点、重复字符等特征
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


# ── 平凡消息规则集 ────────────────────────────────────────────

# 精确匹配的 trivial 消息（不区分大小写）
_TRIVIAL_EXACT: frozenset[str] = frozenset({
    # 中文
    "好的", "好", "嗯", "嗯嗯", "嗯嗯嗯", "哦", "哦哦", "啊", "啊哈",
    "谢谢", "感谢", "多谢", "谢了", "辛苦了", "麻烦了",
    "收到", "明白", "了解", "知道了", "懂了", "理解了",
    "可以", "行", "行吧", "好吧", "OK", "ok", "Ok",
    "对", "是", "是的", "对滴",
    "不用了", "没了", "没有", "没了没了",
    "继续", "请继续", "接着说",
    "没问题", "没事", "没关系", "无所谓",
    "哈哈", "哈哈哈", "哈哈哈哈", "嘿嘿", "呵呵",
    "666", "牛", "厉害",
    # 英文
    "ok", "okay", "sure", "yes", "yeah", "yep", "yup",
    "thanks", "thank you", "thx", "ty",
    "got it", "understood", "roger", "acknowledged",
    "cool", "nice", "great", "awesome",
    "lol", "haha", "hahaha",
    "fine", "alright", "right",
    "no", "nope", "nah",
    "k", "kk",
    "done", "finished",
    "next", "continue", "go on",
    "idk", "dunno",
})

# 正则模式: 重复字符（如 "嗯嗯嗯嗯嗯", "哈哈哈..."）
_TRIVIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(.)\1{2,}$"),                    # 单字符重复 3+ 次
    re.compile(r"^[\s\d\.\,\!\?\;\:]+$"),         # 纯标点/空白/数字
    re.compile(r"^(ha)+[ha]*\.?$", re.IGNORECASE), # haha 重复
    re.compile(r"^(嗯|哈|哦|啊|嘿|呵|呀|哇|哎|嘿)+[~！。]*$"),  # 中文语气词组合
    re.compile(r"^(好|行|对|是|可以)+[的呀吧了]*[~！。]*$"),    # 简短确认
]

# 最大长度阈值: 超过此长度的消息不会被认为是 trivial
_MAX_TRIVIAL_LENGTH = 30


class MessageClassifier:
    """平凡消息分类器。

    判断一条消息是否为 trivial（不需要写入记忆）。

    Usage::

        classifier = MessageClassifier()
        if classifier.is_trivial("好的"):
            # 跳过记忆写入
            pass
        else:
            # 写入记忆
            pass
    """

    def __init__(
        self,
        custom_trivial: Optional[set[str]] = None,
        custom_patterns: Optional[list[re.Pattern[str]]] = None,
        max_trivial_length: int = _MAX_TRIVIAL_LENGTH,
    ) -> None:
        """初始化分类器。

        Args:
            custom_trivial: 自定义 trivial 词汇集合。
            custom_patterns: 自定义 trivial 正则模式。
            max_trivial_length: 最大 trivial 消息长度。
        """
        self._trivial_exact = set(_TRIVIAL_EXACT)
        if custom_trivial:
            self._trivial_exact.update(custom_trivial)

        self._trivial_patterns = list(_TRIVIAL_PATTERNS)
        if custom_patterns:
            self._trivial_patterns.extend(custom_patterns)

        self.max_trivial_length = max_trivial_length

    def is_trivial(self, message: str) -> bool:
        """判断消息是否为 trivial。

        Args:
            message: 消息文本。

        Returns:
            True 如果是 trivial 消息。
        """
        if not message:
            return True

        # 去除首尾空白
        text = message.strip()
        if not text:
            return True

        # 长度检查: 超过阈值则不是 trivial
        if len(text) > self.max_trivial_length:
            return False

        # 精确匹配
        if text.lower() in self._trivial_exact:
            return True

        # 正则模式匹配
        for pattern in self._trivial_patterns:
            if pattern.match(text):
                return True

        return False

    def classify(self, message: str) -> Dict[str, Any]:
        """分类消息，返回详细分类信息。

        Args:
            message: 消息文本。

        Returns:
            分类结果字典:
                - is_trivial: 是否为 trivial
                - reason: 分类原因
                - length: 消息长度
                - message: 原始消息
        """
        text = message.strip() if message else ""

        if not text:
            return {
                "is_trivial": True,
                "reason": "empty_message",
                "length": 0,
                "message": message,
            }

        if len(text) > self.max_trivial_length:
            return {
                "is_trivial": False,
                "reason": "too_long",
                "length": len(text),
                "message": message,
            }

        if text.lower() in self._trivial_exact:
            return {
                "is_trivial": True,
                "reason": "exact_match",
                "length": len(text),
                "message": message,
            }

        for i, pattern in enumerate(self._trivial_patterns):
            if pattern.match(text):
                return {
                    "is_trivial": True,
                    "reason": f"pattern_match_{i}",
                    "length": len(text),
                    "message": message,
                }

        return {
            "is_trivial": False,
            "reason": "not_trivial",
            "length": len(text),
            "message": message,
        }

    def add_trivial_word(self, word: str) -> None:
        """添加自定义 trivial 词汇。"""
        self._trivial_exact.add(word.lower())

    def add_trivial_pattern(self, pattern: str) -> None:
        """添加自定义 trivial 正则模式。"""
        self._trivial_patterns.append(re.compile(pattern))

    def __repr__(self) -> str:
        return (
            f"MessageClassifier("
            f"trivial_words={len(self._trivial_exact)}, "
            f"patterns={len(self._trivial_patterns)})"
        )


__all__ = ["MessageClassifier"]
