"""文档分块器 — 支持固定大小、句子、语义三种分块策略。

分块策略:
    1. FixedSizeChunker  — 按字符数固定大小分块，支持重叠
    2. SentenceChunker   — 按句子边界分块，合并相邻句子到目标大小
    3. SemanticChunker   — 基于段落和标题的语义分块

所有分块器返回统一的 Chunk 列表。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 分块结果数据结构 ──────────────────────────────────────────

@dataclass
class Chunk:
    """分块结果。

    Attributes:
        content: 分块文本内容。
        index: 分块在原文中的序号（从 0 开始）。
        start: 起始字符偏移。
        end: 结束字符偏移。
        metadata: 附加元数据（如来源文档、标题等）。
    """

    content: str
    index: int = 0
    start: int = 0
    end: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"Chunk(idx={self.index}, len={len(self.content)}, '{preview}...')"


# ── 分块器基类 ────────────────────────────────────────────────

class BaseChunker:
    """分块器抽象基类。"""

    def chunk(self, text: str) -> List[Chunk]:
        """对文本进行分块。"""
        raise NotImplementedError

    def chunk_document(self, text: str, source: str = "") -> List[Chunk]:
        """对文档进行分块，附带来源信息。"""
        chunks = self.chunk(text)
        for c in chunks:
            c.metadata["source"] = source
        return chunks


# ── 1. 固定大小分块器 ─────────────────────────────────────────

class FixedSizeChunker(BaseChunker):
    """固定大小分块器 — 按字符数分块，支持重叠。

    Args:
        chunk_size: 每块最大字符数。
        overlap: 相邻块之间的重叠字符数。
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 0) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> List[Chunk]:
        """按固定大小分块。"""
        if not text:
            return []

        chunks: List[Chunk] = []
        step = self.chunk_size - self.overlap
        idx = 0
        pos = 0

        while pos < len(text):
            end = min(pos + self.chunk_size, len(text))
            chunk_text = text[pos:end]
            chunks.append(Chunk(
                content=chunk_text,
                index=idx,
                start=pos,
                end=end,
            ))
            idx += 1
            if end >= len(text):
                break
            pos += step

        return chunks


# ── 2. 句子分块器 ─────────────────────────────────────────────

class SentenceChunker(BaseChunker):
    """句子分块器 — 按句子边界分块，合并相邻句子到目标大小。

    Args:
        target_size: 每块目标字符数。
        overlap_sentences: 相邻块之间的重叠句子数。
    """

    # 中英文句子结束符
    _SENTENCE_PATTERN = re.compile(r'[。！？\.!?]\s*')

    def __init__(self, target_size: int = 400, overlap_sentences: int = 1) -> None:
        if target_size <= 0:
            raise ValueError("target_size must be positive")
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences must be non-negative")
        self.target_size = target_size
        self.overlap_sentences = overlap_sentences

    def _split_sentences(self, text: str) -> List[tuple[str, int, int]]:
        """将文本拆分为句子，返回 (sentence, start, end) 列表。"""
        sentences: List[tuple[str, int, int]] = []
        pos = 0
        for match in self._SENTENCE_PATTERN.finditer(text):
            end = match.end()
            sentence = text[pos:end].strip()
            if sentence:
                sentences.append((sentence, pos, end))
            pos = end
        # 处理最后一段无结束符的文本
        if pos < len(text):
            remainder = text[pos:].strip()
            if remainder:
                sentences.append((remainder, pos, len(text)))
        return sentences

    def chunk(self, text: str) -> List[Chunk]:
        """按句子分块。"""
        if not text or not text.strip():
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            return [Chunk(content=text.strip(), index=0, start=0, end=len(text))]

        chunks: List[Chunk] = []
        current_sentences: List[tuple[str, int, int]] = []
        current_size = 0
        idx = 0

        for sent, start, end in sentences:
            if current_size + len(sent) > self.target_size and current_sentences:
                # 当前块已满，创建 Chunk
                chunk_text = "".join(s[0] for s in current_sentences)
                chunks.append(Chunk(
                    content=chunk_text,
                    index=idx,
                    start=current_sentences[0][1],
                    end=current_sentences[-1][2],
                ))
                idx += 1

                # 重叠：保留最后 N 个句子
                if self.overlap_sentences > 0:
                    overlap = current_sentences[-self.overlap_sentences:]
                    current_sentences = list(overlap)
                    current_size = sum(len(s[0]) for s in current_sentences)
                else:
                    current_sentences = []
                    current_size = 0

            current_sentences.append((sent, start, end))
            current_size += len(sent)

        # 处理剩余句子
        if current_sentences:
            chunk_text = "".join(s[0] for s in current_sentences)
            chunks.append(Chunk(
                content=chunk_text,
                index=idx,
                start=current_sentences[0][1],
                end=current_sentences[-1][2],
            ))

        return chunks


# ── 3. 语义分块器 ─────────────────────────────────────────────

class SemanticChunker(BaseChunker):
    """语义分块器 — 基于段落和标题的分块。

    识别 Markdown 风格的标题（# / ## / ###）和空行分隔的段落，
    将同一标题下的段落归为一个分块。

    Args:
        max_chunk_size: 单个分块最大字符数，超出时进一步拆分。
    """

    _HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def __init__(self, max_chunk_size: int = 1000) -> None:
        if max_chunk_size <= 0:
            raise ValueError("max_chunk_size must be positive")
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str) -> List[Chunk]:
        """按语义结构分块。"""
        if not text or not text.strip():
            return []

        # 检测标题位置
        headings = list(self._HEADING_PATTERN.finditer(text))

        if not headings:
            # 无标题，按段落分块
            return self._chunk_by_paragraphs(text, "")

        chunks: List[Chunk] = []
        idx = 0

        # 标题之前的文本
        if headings[0].start() > 0:
            pre_text = text[:headings[0].start()].strip()
            if pre_text:
                sub_chunks = self._chunk_by_paragraphs(pre_text, "", 0)
                for sc in sub_chunks:
                    sc.index = idx
                    idx += 1
                    chunks.append(sc)

        # 每个标题下的内容
        for i, heading in enumerate(headings):
            heading_level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            section_start = heading.start()
            section_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            section_text = text[section_start:section_end]

            sub_chunks = self._chunk_by_paragraphs(
                section_text, heading_text, section_start
            )
            for sc in sub_chunks:
                sc.index = idx
                sc.metadata["heading"] = heading_text
                sc.metadata["heading_level"] = heading_level
                idx += 1
                chunks.append(sc)

        return chunks

    def _chunk_by_paragraphs(
        self,
        text: str,
        heading: str,
        offset: int = 0,
    ) -> List[Chunk]:
        """按段落分割文本，段落过长时进一步拆分。"""
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunks: List[Chunk] = []
        current_parts: List[str] = []
        current_start = offset
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_start = text.find(para, current_size) + offset if current_parts else offset
            # 简化：直接用累积偏移
            if current_size + len(para) > self.max_chunk_size and current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(Chunk(
                    content=chunk_text,
                    start=current_start,
                    end=current_start + len(chunk_text),
                    metadata={"heading": heading} if heading else {},
                ))
                current_parts = [para]
                current_size = len(para)
            else:
                current_parts.append(para)
                current_size += len(para)

        if current_parts:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(Chunk(
                content=chunk_text,
                start=current_start,
                end=current_start + len(chunk_text),
                metadata={"heading": heading} if heading else {},
            ))

        return chunks


__all__ = [
    "Chunk",
    "BaseChunker",
    "FixedSizeChunker",
    "SentenceChunker",
    "SemanticChunker",
]
