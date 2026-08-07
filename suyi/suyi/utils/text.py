"""文本处理工具函数.

提供 HTML 清洗、摘要提取、消息分割、XML 标签生成等功能.
"""

import re

from .token_counter import TokenCounter


def strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本内容.

    同时压缩连续空白为单个空格，去除首尾空白.

    Args:
        text: 可能包含 HTML 标签的文本.

    Returns:
        去除标签后的纯文本.

    Examples:
        >>> strip_html("<p>hello <b>world</b></p>")
        'hello world'
        >>> strip_html("no tags here")
        'no tags here'
    """
    if not text:
        return ""
    # 去除 HTML 标签
    cleaned = re.sub(r"<[^>]+>", "", text)
    # 压缩连续空白
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_summary(text: str, max_length: int = 200) -> str:
    """从文本中提取摘要，限制在 max_length 字符以内.

    优先在句子边界处截断（中文句号、英文句号、感叹号、问号），
    如果找不到合适的边界则直接截断并添加省略号.

    Args:
        text: 原始文本.
        max_length: 摘要最大字符数.

    Returns:
        截取后的摘要文本，可能以 ``...`` 结尾.

    Examples:
        >>> extract_summary("hello world", 100)
        'hello world'
        >>> extract_summary("aaa. bbb. ccc.", 8)
        'aaa. ...'
    """
    if not text or len(text) <= max_length:
        return text or ""

    # 在 max_length 范围内寻找句子边界
    snippet = text[:max_length]
    boundaries = ["。", ". ", "！", "？", "!", "?", "\n"]
    best_pos = -1

    for boundary in boundaries:
        pos = snippet.rfind(boundary)
        if pos > max_length * 0.5 and pos > best_pos:
            best_pos = pos + len(boundary)

    if best_pos > 0:
        return text[:best_pos].rstrip() + "..."
    return snippet.rstrip() + "..."


def split_messages(history: list, max_tokens: int) -> list:
    """按 token 限制将消息历史分割为多个块.

    每个块的消息总 token 数不超过 ``max_tokens``.
    单条消息超过限制时，该消息单独成块.

    Args:
        history: 消息列表，每条消息为 ``{"role": str, "content": str}`` 格式的字典.
        max_tokens: 每个块的最大 token 数.

    Returns:
        消息块列表，每个块是一个消息列表.

    Examples:
        >>> msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        >>> chunks = split_messages(msgs, 100)
        >>> len(chunks)
        1
    """
    if not history:
        return []

    # 每条消息的 role 标记开销（近似值）
    ROLE_OVERHEAD = 4

    chunks = []
    current_chunk = []
    current_tokens = 0

    for msg in history:
        content = msg.get("content", "")
        if isinstance(content, list):
            # 结构化内容，拼接为字符串
            content_text = " ".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        else:
            content_text = str(content)

        msg_tokens = TokenCounter.count(content_text) + ROLE_OVERHEAD

        # 当前块放不下且已有内容 → 开新块
        if current_tokens + msg_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(msg)
        current_tokens += msg_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def encode_xml_tag(tag: str, content: str) -> str:
    """生成 XML 标签包裹的内容.

    用于在 prompt 中结构化嵌入信息.

    Args:
        tag: XML 标签名.
        content: 标签内容.

    Returns:
        XML 标签字符串.

    Examples:
        >>> print(encode_xml_tag("result", "success"))
        <result>
        success
        </result>
    """
    if content is None:
        content = ""
    return f"<{tag}>\n{content}\n</{tag}>"
