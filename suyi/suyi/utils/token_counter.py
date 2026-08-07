"""Token estimation utilities.

Estimates token counts for mixed Chinese/English text without requiring
a tokenizer library. Uses heuristic character-to-token ratios:

- English / Latin scripts: ~4 characters per token
- CJK (Chinese, Japanese, Korean): ~1.5 characters per token

These ratios are approximations suitable for budget management — they do
not need to be exact, only proportional enough to trigger compression
thresholds at the right time.
"""

import re
from typing import Any, Dict, List


# CJK Unicode ranges (Chinese, Japanese, Korean)
_CJK_PATTERN = re.compile(
    r'[\u4e00-\u9fff'   # CJK Unified Ideographs
    r'\u3400-\u4dbf'     # CJK Extension A
    r'\u3040-\u309f'     # Hiragana
    r'\u30a0-\u30ff'     # Katakana
    r'\uac00-\ud7af]'    # Hangul Syllables
)


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses heuristic ratios:
    - CJK characters: ~1.5 characters per token
    - Other characters (English, punctuation, etc.): ~4 characters per token

    Args:
        text: The input text string.

    Returns:
        Estimated token count (0 for empty/None input).
    """
    if not text:
        return 0

    cjk_chars = len(_CJK_PATTERN.findall(text))
    other_chars = len(text) - cjk_chars

    cjk_tokens = cjk_chars / 1.5
    other_tokens = other_chars / 4.0

    return max(int(cjk_tokens + other_tokens), 1)


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate token count for a single message dict.

    Accounts for role overhead, content text, tool calls, and tool results.

    Args:
        message: A message dict with keys like ``role``, ``content``,
            optionally ``tool_calls`` and ``tool_results``.

    Returns:
        Estimated token count including ~4 tokens of formatting overhead.
    """
    # Base overhead for role label and JSON formatting
    tokens = 4

    # --- Content ---
    content = message.get('content', '')
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                tokens += estimate_tokens(part)
            elif isinstance(part, dict):
                tokens += estimate_tokens(str(part.get('text', part)))

    # --- Tool calls ---
    tool_calls = message.get('tool_calls') or []
    for tc in tool_calls:
        name = tc.get('name') or tc.get('function', {}).get('name', '')
        tokens += estimate_tokens(name) + 4
        args = tc.get('arguments') or tc.get('function', {}).get('arguments', '')
        if isinstance(args, str):
            tokens += estimate_tokens(args)
        elif isinstance(args, dict):
            tokens += estimate_tokens(str(args))

    # --- Tool results ---
    tool_results = message.get('tool_results') or []
    for tr in tool_results:
        output = tr.get('output') or tr.get('content', '')
        tokens += estimate_tokens(str(output)) + 4

    return tokens


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total token count for a list of messages.

    Args:
        messages: List of message dictionaries.

    Returns:
        Total estimated token count.
    """
    return sum(estimate_message_tokens(msg) for msg in messages)


class TokenCounter:
    """Token 估算器（类接口，兼容旧式调用）.

    提供 count() 静态方法，内部委托给 estimate_tokens() 函数.
    """

    @staticmethod
    def count(text: str) -> int:
        """估算文本的 token 数量.

        Args:
            text: 输入文本.

        Returns:
            估算的 token 数量.
        """
        return estimate_tokens(text)

    @staticmethod
    def count_message(message: Dict[str, Any]) -> int:
        """估算单条消息的 token 数量."""
        return estimate_message_tokens(message)

    @staticmethod
    def count_messages(messages: List[Dict[str, Any]]) -> int:
        """估算消息列表的总 token 数量."""
        return estimate_messages_tokens(messages)
