#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
  阶段十二 · RAG 学习路线图 · 第 3 题
  文档分块策略 — Chunking Methods 详解与实现
============================================================================

学习目标
--------
1. 理解为什么需要文档分块（Chunking）以及它对 RAG 效果的影响
2. 掌握 6 种主流分块策略并从零实现：
   a. 固定长度分块（Fixed-Size Chunking）
   b. 句子分块（Sentence-Based Chunking）
   c. 递归字符分块（Recursive Character Splitting）
   d. 滑动窗口分块（Sliding Window Chunking）
   e. 语义分块（Semantic Chunking — 基于嵌入相似度）
   f. 文档结构感知分块（Structure-Aware Chunking — Markdown/Code）
3. 理解 chunk_size 和 chunk_overlap 的权衡
4. 实现分块质量评估指标
5. 构建一个统一的分块管线，支持策略切换和参数调优

知识点
------
- 分块对检索质量的影响（太大→噪声多，太小→语义不完整）
- Token 计数 vs 字符计数
- 重叠（Overlap）的作用：保持上下文连续性
- 语义边界检测
- 文档结构解析（标题、段落、代码块）
- 分块元数据管理

难度等级：★★★☆☆（中级）

运行方式
--------
    python 03_document_chunking.py

依赖
----
    仅依赖 numpy + 标准库（re, json, math, dataclasses, typing），无需额外安装

作者：koze
日期：2025
============================================================================
"""

import re
import math
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable, Any
from enum import Enum

import numpy as np

# ============================================================================
# 第一部分：概念讲解（注释形式）
# ============================================================================
#
# 为什么需要文档分块？
# ────────────────────
# 在 RAG 系统中，我们先将文档分成小块（chunk），然后对每个块生成嵌入向量。
# 分块质量直接影响检索效果：
#
#   块太大 → 嵌入向量表示的信息太杂，检索时噪声多，相似度不准
#   块太小 → 语义不完整，检索到的块缺乏上下文，LLM 无法回答
#   块大小合适 → 每块表达一个完整语义单元，检索精准，上下文充分
#
# 常见分块参数：
#   chunk_size: 每块的目标大小（字符数或 token 数）
#   chunk_overlap: 相邻块之间的重叠部分（保持上下文连续性）
#
# 经验值：
#   - 通用文本：chunk_size=500-1000 chars, overlap=50-200 chars
#   - 技术文档：chunk_size=800-1200 chars, overlap=100-200 chars
#   - 代码：按函数/类边界分块，不强制大小
#   - 问答对：每个 Q&A 作为一个块
#
# ============================================================================


# ============================================================================
# 第二部分：基础数据结构
# ============================================================================

class ChunkingStrategy(Enum):
    """分块策略枚举"""
    FIXED_SIZE = "fixed_size"
    SENTENCE = "sentence"
    RECURSIVE = "recursive"
    SLIDING_WINDOW = "sliding_window"
    SEMANTIC = "semantic"
    STRUCTURE_AWARE = "structure_aware"


@dataclass
class Chunk:
    """一个文档块"""
    content: str
    index: int                    # 在文档中的序号
    start_char: int               # 在原文中的起始字符位置
    end_char: int                 # 在原文中的结束字符位置
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.content)

    def __repr__(self) -> str:
        preview = self.content[:50].replace('\n', ' ')
        return f"Chunk(idx={self.index}, len={len(self.content)}, text='{preview}...')"


@dataclass
class ChunkingConfig:
    """分块配置"""
    chunk_size: int = 800          # 目标块大小（字符数）
    chunk_overlap: int = 100       # 块之间的重叠
    min_chunk_size: int = 50       # 最小块大小（小于此值合并到前一块）
    separator: str = "\n\n"        # 默认分隔符
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE

    def validate(self):
        """验证配置合理性"""
        assert self.chunk_size > 0, "chunk_size must be positive"
        assert self.chunk_overlap >= 0, "chunk_overlap must be non-negative"
        assert self.chunk_overlap < self.chunk_size, "overlap must be smaller than chunk_size"
        assert self.min_chunk_size > 0, "min_chunk_size must be positive"


# ============================================================================
# 第三部分：Token 估算工具
# ============================================================================

class TokenEstimator:
    """
    简易 Token 估算器
    实际生产中应使用 tiktoken 或 transformers tokenizer
    这里用近似公式：1 token ≈ 4 字符（英文）/ 1.5 字符（中文）
    """

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算文本的 token 数"""
        if not text:
            return 0
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 非中文字符
        other_chars = len(text) - chinese_chars
        # 估算：中文1字≈1token，英文4字符≈1token
        return chinese_chars + (other_chars // 4 if other_chars > 0 else 0)

    @staticmethod
    def estimate_chars_from_tokens(tokens: int, chinese_ratio: float = 0.3) -> int:
        """根据 token 数估算字符数"""
        # 加权平均：中文1字1token，英文4字1token
        avg_chars_per_token = chinese_ratio * 1 + (1 - chinese_ratio) * 4
        return int(tokens * avg_chars_per_token)


# ============================================================================
# 第四部分：六种分块策略实现
# ============================================================================

class BaseChunker:
    """分块器基类"""

    def __init__(self, config: ChunkingConfig):
        self.config = config
        config.validate()

    def chunk(self, text: str) -> List[Chunk]:
        """分块主方法，子类实现"""
        raise NotImplementedError

    def _merge_small_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """合并过小的块到前一块"""
        if not chunks:
            return chunks
        result = [chunks[0]]
        for chunk in chunks[1:]:
            if len(chunk) < self.config.min_chunk_size and result:
                # 合并到前一块
                prev = result[-1]
                merged = Chunk(
                    content=prev.content + self.config.separator + chunk.content,
                    index=prev.index,
                    start_char=prev.start_char,
                    end_char=chunk.end_char,
                    metadata={**prev.metadata, "merged": True}
                )
                result[-1] = merged
            else:
                result.append(chunk)
        # 重新编号
        for i, c in enumerate(result):
            c.index = i
        return result


class FixedSizeChunker(BaseChunker):
    """
    策略1：固定长度分块
    最简单的策略：按固定字符数切割，带可选重叠
    优点：实现简单，速度极快
    缺点：可能在句子/段落中间截断，破坏语义
    """

    def chunk(self, text: str) -> List[Chunk]:
        chunks = []
        size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        step = size - overlap

        start = 0
        idx = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk_text = text[start:end]
            chunks.append(Chunk(
                content=chunk_text,
                index=idx,
                start_char=start,
                end_char=end,
                metadata={"strategy": "fixed_size", "tokens": TokenEstimator.estimate_tokens(chunk_text)}
            ))
            idx += 1
            if end >= len(text):
                break
            start += step

        return self._merge_small_chunks(chunks)


class SentenceChunker(BaseChunker):
    """
    策略2：句子分块
    先分句，再按句子累积到目标大小
    优点：不会在句子中间截断
    缺点：句子长度不均，块大小可能偏离目标
    """

    # 句子结束符模式（支持中英文，中文不需要空格分隔）
    SENTENCE_PATTERN = re.compile(r'(?<=[.!?])\s+|(?<=[。！？\n])')

    def _split_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """分句，返回 (句子, 起始位置, 结束位置)"""
        sentences = []
        pos = 0
        for match in self.SENTENCE_PATTERN.finditer(text):
            end = match.start()
            if end > pos:
                sentences.append((text[pos:end].strip(), pos, end))
            pos = match.end()
        if pos < len(text):
            sentences.append((text[pos:].strip(), pos, len(text)))
        return [s for s in sentences if s[0]]

    def chunk(self, text: str) -> List[Chunk]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks = []
        current_sentences = []
        current_len = 0
        current_start = sentences[0][1]
        idx = 0

        for sent_text, sent_start, sent_end in sentences:
            if current_len + len(sent_text) > self.config.chunk_size and current_sentences:
                # 输出当前块
                chunk_content = " ".join(s[0] for s in current_sentences)
                chunks.append(Chunk(
                    content=chunk_content,
                    index=idx,
                    start_char=current_start,
                    end_char=current_sentences[-1][2],
                    metadata={"strategy": "sentence", "sentence_count": len(current_sentences)}
                ))
                idx += 1

                # 处理重叠：保留最后几句
                overlap_len = 0
                keep = []
                for s in reversed(current_sentences):
                    if overlap_len + len(s[0]) > self.config.chunk_overlap:
                        break
                    keep.insert(0, s)
                    overlap_len += len(s[0])
                current_sentences = keep
                current_len = sum(len(s[0]) for s in current_sentences)
                current_start = current_sentences[0][1] if current_sentences else sent_start

            current_sentences.append((sent_text, sent_start, sent_end))
            current_len += len(sent_text)

        # 最后一块
        if current_sentences:
            chunk_content = " ".join(s[0] for s in current_sentences)
            chunks.append(Chunk(
                content=chunk_content,
                index=idx,
                start_char=current_start,
                end_char=current_sentences[-1][2],
                metadata={"strategy": "sentence", "sentence_count": len(current_sentences)}
            ))

        return self._merge_small_chunks(chunks)


class RecursiveChunker(BaseChunker):
    """
    策略3：递归字符分块（LangChain RecursiveCharacterTextSplitter 的原理）
    按分隔符优先级递归拆分：
      1. 先按段落分隔符（\n\n）拆分
      2. 如果块仍太大，按换行符（\n）拆分
      3. 如果还太大，按句号拆分
      4. 最后按字符数硬切
    优点：尽可能保持语义边界，同时控制块大小
    缺点：实现稍复杂
    """

    SEPARATORS = ["\n\n", "\n", ". ", "。", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """递归拆分文本"""
        if len(text) <= self.config.chunk_size:
            return [text]

        for i, sep in enumerate(separators):
            if sep == "":
                # 最后手段：硬切
                return [text[j:j+self.config.chunk_size]
                        for j in range(0, len(text), self.config.chunk_size)]

            parts = text.split(sep)
            if len(parts) == 1:
                continue

            # 尝试合并 parts 到接近 chunk_size
            merged = []
            current = ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) <= self.config.chunk_size:
                    current = candidate
                else:
                    if current:
                        merged.append(current)
                    # 如果单个 part 仍然太大，递归用更细的分隔符
                    if len(part) > self.config.chunk_size:
                        sub_parts = self._split_text(part, separators[i+1:])
                        merged.extend(sub_parts)
                        current = ""
                    else:
                        current = part
            if current:
                merged.append(current)

            return merged

        return [text]

    def chunk(self, text: str) -> List[Chunk]:
        if not text or not text.strip():
            return []
        parts = self._split_text(text, self.SEPARATORS)

        # 添加重叠
        chunks = []
        idx = 0
        char_pos = 0

        for i, part in enumerate(parts):
            # 找到在原文中的位置
            start = text.find(part, char_pos)
            if start == -1:
                start = char_pos
            end = start + len(part)
            char_pos = end

            # 添加重叠：从前一块末尾取 overlap 字符
            if chunks and self.config.chunk_overlap > 0:
                prev_content = chunks[-1].content
                overlap_text = prev_content[-self.config.chunk_overlap:]
                part = overlap_text + part
                start = max(0, start - self.config.chunk_overlap)

            chunks.append(Chunk(
                content=part,
                index=idx,
                start_char=start,
                end_char=end,
                metadata={"strategy": "recursive", "tokens": TokenEstimator.estimate_tokens(part)}
            ))
            idx += 1

        return self._merge_small_chunks(chunks)


class SlidingWindowChunker(BaseChunker):
    """
    策略4：滑动窗口分块
    固定窗口大小，按步长滑动
    与固定长度分块类似，但更强调窗口概念
    优点：实现简单，块大小完全一致，适合需要统一长度的场景
    缺点：同样可能在语义边界截断
    """

    def chunk(self, text: str) -> List[Chunk]:
        if not text or not text.strip():
            return []
        chunks = []
        size = self.config.chunk_size
        step = size - self.config.chunk_overlap
        idx = 0

        if len(text) <= size:
            return [Chunk(
                content=text,
                index=0,
                start_char=0,
                end_char=len(text),
                metadata={"strategy": "sliding_window", "window": size}
            )]

        for start in range(0, len(text), step):
            end = min(start + size, len(text))
            if end == len(text) and start > 0 and end - start < self.config.min_chunk_size:
                break  # 最后一小块太短，跳过
            chunk_text = text[start:end]
            chunks.append(Chunk(
                content=chunk_text,
                index=idx,
                start_char=start,
                end_char=end,
                metadata={
                    "strategy": "sliding_window",
                    "window": size,
                    "step": step,
                    "overlap": self.config.chunk_overlap
                }
            ))
            idx += 1
            if end >= len(text):
                break

        return chunks


class SemanticChunker(BaseChunker):
    """
    策略5：语义分块（Semantic Chunking）
    基于相邻句子的语义相似度变化来决定分块点
    当相邻句子的相似度低于阈值时，认为语义发生了跳转，在此处分块

    原理：
    1. 先分句
    2. 计算每对相邻句子的余弦相似度
    3. 当相似度低于阈值（或相似度下降幅度超过阈值）时分块

    优点：自适应语义边界，不依赖固定大小
    缺点：需要嵌入模型，计算开销大

    注意：这里用 TF-IDF 近似代替预训练嵌入，实际生产中应使用 sentence-transformers
    """

    def __init__(self, config: ChunkingConfig, similarity_threshold: float = 0.3):
        super().__init__(config)
        self.similarity_threshold = similarity_threshold

    def _simple_tfidf_vectors(self, sentences: List[str]) -> np.ndarray:
        """用 TF-IDF 生成句子向量（近似嵌入）"""
        # 构建词表
        vocab = set()
        for sent in sentences:
            words = re.findall(r'\w+', sent.lower())
            vocab.update(words)
        vocab = sorted(vocab)
        vocab_idx = {w: i for i, w in enumerate(vocab)}

        # 计算 IDF
        n_docs = len(sentences)
        idf = np.zeros(len(vocab))
        for w in vocab:
            count = sum(1 for s in sentences if w in s.lower())
            idf[vocab_idx[w]] = math.log((n_docs + 1) / (count + 1)) + 1

        # 生成 TF-IDF 向量
        vectors = np.zeros((len(sentences), len(vocab)))
        for i, sent in enumerate(sentences):
            words = re.findall(r'\w+', sent.lower())
            for w in words:
                vectors[i, vocab_idx[w]] += 1
            # L2 归一化
            norm = np.linalg.norm(vectors[i])
            if norm > 0:
                vectors[i] = vectors[i] / norm * idf

        return vectors

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def chunk(self, text: str) -> List[Chunk]:
        # 1. 分句
        sentence_splitter = SentenceChunker(self.config)
        sentences = sentence_splitter._split_sentences(text)
        if not sentences:
            return []

        sent_texts = [s[0] for s in sentences]

        # 2. 生成向量
        vectors = self._simple_tfidf_vectors(sent_texts)

        # 3. 计算相邻句子相似度
        if len(sent_texts) <= 1:
            return [Chunk(
                content=text,
                index=0,
                start_char=0,
                end_char=len(text),
                metadata={"strategy": "semantic"}
            )]

        similarities = []
        for i in range(len(sent_texts) - 1):
            sim = self._cosine_similarity(vectors[i], vectors[i+1])
            similarities.append(sim)

        # 4. 识别分块点（相似度低于阈值）
        split_points = [0]
        for i, sim in enumerate(similarities):
            if sim < self.similarity_threshold:
                split_points.append(i + 1)
        split_points.append(len(sent_texts))

        # 5. 生成块
        chunks = []
        idx = 0
        for i in range(len(split_points) - 1):
            start_sent = split_points[i]
            end_sent = split_points[i + 1]
            chunk_sentences = sentences[start_sent:end_sent]
            if not chunk_sentences:
                continue

            content = " ".join(s[0] for s in chunk_sentences)
            chunks.append(Chunk(
                content=content,
                index=idx,
                start_char=chunk_sentences[0][1],
                end_char=chunk_sentences[-1][2],
                metadata={
                    "strategy": "semantic",
                    "sentence_count": len(chunk_sentences),
                    "avg_similarity": float(np.mean(similarities[start_sent:end_sent-1])) if end_sent - start_sent > 1 else 1.0
                }
            ))
            idx += 1

        return self._merge_small_chunks(chunks)


class StructureAwareChunker(BaseChunker):
    """
    策略6：文档结构感知分块
    解析文档结构（标题、段落、代码块、列表），按结构边界分块
    特别适合 Markdown 文档和技术文档

    规则：
    - 按 Markdown 标题（# ## ###）分节
    - 代码块（```...```）不拆分
    - 列表项尽量保持在同一块
    - 每节如果太大，递归拆分
    """

    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')
    LIST_PATTERN = re.compile(r'^[\s]*[-*+]\s+', re.MULTILINE)

    def _parse_structure(self, text: str) -> List[Dict[str, Any]]:
        """解析文档结构，返回结构化段落列表"""
        sections = []
        # 按标题分节
        heading_matches = list(self.HEADING_PATTERN.finditer(text))

        if not heading_matches:
            # 无标题，按段落分
            paragraphs = text.split('\n\n')
            pos = 0
            for para in paragraphs:
                if para.strip():
                    start = text.find(para, pos)
                    sections.append({
                        'type': 'paragraph',
                        'content': para.strip(),
                        'start': start if start != -1 else pos,
                        'end': (start if start != -1 else pos) + len(para),
                        'level': 0
                    })
                    pos += len(para) + 2
            return sections

        # 标题前的内容
        if heading_matches[0].start() > 0:
            pre_content = text[:heading_matches[0].start()].strip()
            if pre_content:
                sections.append({
                    'type': 'preamble',
                    'content': pre_content,
                    'start': 0,
                    'end': heading_matches[0].start(),
                    'level': 0
                })

        # 按标题分节
        for i, match in enumerate(heading_matches):
            level = len(match.group(1))
            title = match.group(2)
            start = match.start()
            end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(text)
            content = text[start:end].strip()

            sections.append({
                'type': 'heading',
                'content': content,
                'start': start,
                'end': end,
                'level': level,
                'title': title
            })

        return sections

    def _protect_code_blocks(self, text: str) -> Tuple[str, Dict[str, str]]:
        """保护代码块不被拆分"""
        placeholders = {}
        def replace_code(match):
            key = f"__CODE_BLOCK_{len(placeholders)}__"
            placeholders[key] = match.group(0)
            return key

        protected = self.CODE_BLOCK_PATTERN.sub(replace_code, text)
        return protected, placeholders

    def _restore_code_blocks(self, text: str, placeholders: Dict[str, str]) -> str:
        """恢复代码块"""
        for key, code in placeholders.items():
            text = text.replace(key, code)
        return text

    def chunk(self, text: str) -> List[Chunk]:
        # 保护代码块
        protected_text, placeholders = self._protect_code_blocks(text)

        # 解析结构
        sections = self._parse_structure(protected_text)

        chunks = []
        idx = 0

        for section in sections:
            content = section['content']
            # 恢复代码块
            content = self._restore_code_blocks(content, placeholders)

            if len(content) <= self.config.chunk_size:
                chunks.append(Chunk(
                    content=content,
                    index=idx,
                    start_char=section['start'],
                    end_char=section['end'],
                    metadata={
                        "strategy": "structure_aware",
                        "type": section['type'],
                        "level": section.get('level', 0),
                        "title": section.get('title', '')
                    }
                ))
                idx += 1
            else:
                # 太大，用递归分块器二次拆分
                sub_config = ChunkingConfig(
                    chunk_size=self.config.chunk_size,
                    chunk_overlap=self.config.chunk_overlap,
                    min_chunk_size=self.config.min_chunk_size,
                    strategy=ChunkingStrategy.RECURSIVE
                )
                sub_chunker = RecursiveChunker(sub_config)
                sub_chunks = sub_chunker.chunk(content)
                for sc in sub_chunks:
                    sc.index = idx
                    sc.metadata = {
                        "strategy": "structure_aware",
                        "type": section['type'],
                        "level": section.get('level', 0),
                        "title": section.get('title', ''),
                        "sub_chunked": True
                    }
                    chunks.append(sc)
                    idx += 1

        return self._merge_small_chunks(chunks)


# ============================================================================
# 第五部分：分块质量评估
# ============================================================================

class ChunkEvaluator:
    """
    分块质量评估器
    评估指标：
    1. 块大小分布（均值、标准差、最小/最大值）
    2. 大小一致性（变异系数 CV）
    3. 语义完整性（句子截断率）
    4. 重叠有效率
    5. Token 分布
    """

    @staticmethod
    def evaluate(chunks: List[Chunk], original_text: str) -> Dict[str, Any]:
        if not chunks:
            return {"error": "No chunks to evaluate"}

        sizes = [len(c) for c in chunks]
        tokens = [TokenEstimator.estimate_tokens(c.content) for c in chunks]

        # 句子截断率
        sentence_endings = re.findall(r'[.!?。！？]', original_text)
        chunk_endings = sum(
            1 for c in chunks
            if c.content and c.content[-1] in '.!?。！？'
        )
        sentence_completion = chunk_endings / len(chunks) if chunks else 0

        # 覆盖率
        total_chunk_chars = sum(sizes)
        coverage = total_chunk_chars / len(original_text) if original_text else 0

        return {
            "chunk_count": len(chunks),
            "size_stats": {
                "mean": float(np.mean(sizes)),
                "std": float(np.std(sizes)),
                "min": int(min(sizes)),
                "max": int(max(sizes)),
                "cv": float(np.std(sizes) / np.mean(sizes)) if np.mean(sizes) > 0 else 0,
            },
            "token_stats": {
                "mean": float(np.mean(tokens)),
                "std": float(np.std(tokens)),
                "min": int(min(tokens)),
                "max": int(max(tokens)),
                "total": int(sum(tokens)),
            },
            "sentence_completion_rate": sentence_completion,
            "coverage": coverage,
            "overlap_chars": total_chunk_chars - len(original_text) if total_chunk_chars > len(original_text) else 0,
        }


# ============================================================================
# 第六部分：统一分块管线
# ============================================================================

class ChunkingPipeline:
    """
    统一分块管线
    支持策略切换、参数调优、批量处理
    """

    STRATEGY_MAP = {
        ChunkingStrategy.FIXED_SIZE: FixedSizeChunker,
        ChunkingStrategy.SENTENCE: SentenceChunker,
        ChunkingStrategy.RECURSIVE: RecursiveChunker,
        ChunkingStrategy.SLIDING_WINDOW: SlidingWindowChunker,
        ChunkingStrategy.SEMANTIC: SemanticChunker,
        ChunkingStrategy.STRUCTURE_AWARE: StructureAwareChunker,
    }

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()

    def chunk(self, text: str, strategy: Optional[ChunkingStrategy] = None) -> List[Chunk]:
        """分块"""
        config = ChunkingConfig(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            min_chunk_size=self.config.min_chunk_size,
            strategy=strategy or self.config.strategy
        )
        chunker_cls = self.STRATEGY_MAP[config.strategy]
        chunker = chunker_cls(config)
        return chunker.chunk(text)

    def chunk_batch(self, texts: List[str], strategy: Optional[ChunkingStrategy] = None) -> List[List[Chunk]]:
        """批量分块"""
        return [self.chunk(text, strategy) for text in texts]

    def compare_strategies(self, text: str) -> Dict[str, Dict[str, Any]]:
        """对比所有策略的分块效果"""
        results = {}
        for strategy in ChunkingStrategy:
            try:
                chunks = self.chunk(text, strategy)
                eval_result = ChunkEvaluator.evaluate(chunks, text)
                results[strategy.value] = eval_result
            except Exception as e:
                results[strategy.value] = {"error": str(e)}
        return results

    def to_dict(self, chunks: List[Chunk]) -> List[Dict]:
        """转为可序列化格式"""
        return [
            {
                "content": c.content,
                "index": c.index,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "metadata": c.metadata
            }
            for c in chunks
        ]


# ============================================================================
# 第七部分：测试用例
# ============================================================================

import unittest

class TestChunking(unittest.TestCase):
    """分块策略测试"""

    def setUp(self):
        self.short_text = "Hello world. This is a test. Short text for testing."
        self.long_text = (
            "Artificial intelligence is transforming the world. "
            "Machine learning models are becoming more powerful every day. "
            "Deep learning has revolutionized computer vision and natural language processing. "
            "Large language models like GPT can generate human-like text. "
            "Retrieval-augmented generation combines search with generation. "
            "Vector databases store embeddings for fast similarity search. "
            "Document chunking is a critical step in RAG pipelines. "
            "The quality of chunks directly affects retrieval performance. "
            "Semantic chunking adapts to content boundaries automatically. "
            "Fixed-size chunking is simple but may break semantic units."
        ) * 3  # 重复3次使文本更长

        self.markdown_text = """# Introduction

This is the introduction paragraph. It contains some overview text about the topic.

## Background

The background section provides context. It explains why this topic matters.

### History

The history goes back many years. Key milestones are discussed here.

## Main Content

The main content starts here. It has multiple paragraphs.

```python
def example_function():
    return "This is a code block that should not be split"
```

## Conclusion

This is the conclusion. It wraps up the document.

# Appendix

Additional information in the appendix.
"""

    # --- 测试 Chunk 数据结构 ---
    def test_chunk_creation(self):
        c = Chunk(content="test", index=0, start_char=0, end_char=4)
        self.assertEqual(c.content, "test")
        self.assertEqual(len(c), 4)
        self.assertEqual(c.metadata, {})

    # --- 测试 TokenEstimator ---
    def test_token_estimator_english(self):
        tokens = TokenEstimator.estimate_tokens("Hello world")
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 10)

    def test_token_estimator_chinese(self):
        tokens = TokenEstimator.estimate_tokens("你好世界")
        self.assertEqual(tokens, 4)  # 4个中文字=4 tokens

    def test_token_estimator_empty(self):
        self.assertEqual(TokenEstimator.estimate_tokens(""), 0)

    # --- 测试固定长度分块 ---
    def test_fixed_size_basic(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=0, min_chunk_size=1)
        chunker = FixedSizeChunker(config)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 1)
        for c in chunks[:-1]:
            self.assertLessEqual(len(c.content), 50)

    def test_fixed_size_with_overlap(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=20, min_chunk_size=1)
        chunker = FixedSizeChunker(config)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 1)
        # 有重叠时总字符数应大于原文
        total = sum(len(c.content) for c in chunks)
        self.assertGreater(total, len(self.long_text))

    # --- 测试句子分块 ---
    def test_sentence_basic(self):
        config = ChunkingConfig(chunk_size=100, chunk_overlap=0, min_chunk_size=1)
        chunker = SentenceChunker(config)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 0)
        # 每块应该以句号结尾（最后一块除外可能）
        for c in chunks:
            self.assertGreater(len(c.content), 0)

    def test_sentence_chinese(self):
        text = "这是第一句话。这是第二句话。这是第三句话。这是第四句话。这是第五句话。这是第六句话。"
        config = ChunkingConfig(chunk_size=20, chunk_overlap=0, min_chunk_size=1)
        chunker = SentenceChunker(config)
        chunks = chunker.chunk(text)
        self.assertGreater(len(chunks), 1)

    # --- 测试递归分块 ---
    def test_recursive_basic(self):
        config = ChunkingConfig(chunk_size=100, chunk_overlap=0, min_chunk_size=1)
        chunker = RecursiveChunker(config)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertGreater(len(c.content), 0)

    def test_recursive_respects_boundaries(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=0, min_chunk_size=1)
        chunker = RecursiveChunker(config)
        chunks = chunker.chunk("Para one.\n\nPara two.\n\nPara three.")
        self.assertGreaterEqual(len(chunks), 1)

    # --- 测试滑动窗口 ---
    def test_sliding_window_basic(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=20, min_chunk_size=5)
        chunker = SlidingWindowChunker(config)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 1)
        # 除最后一块外，其他块大小应一致
        for c in chunks[:-1]:
            self.assertEqual(len(c.content), 50)

    def test_sliding_window_short_text(self):
        config = ChunkingConfig(chunk_size=1000, chunk_overlap=100, min_chunk_size=10)
        chunker = SlidingWindowChunker(config)
        chunks = chunker.chunk(self.short_text)
        self.assertEqual(len(chunks), 1)

    # --- 测试语义分块 ---
    def test_semantic_basic(self):
        config = ChunkingConfig(chunk_size=200, chunk_overlap=0, min_chunk_size=10)
        chunker = SemanticChunker(config, similarity_threshold=0.1)
        chunks = chunker.chunk(self.long_text)
        self.assertGreater(len(chunks), 0)

    def test_semantic_topic_shift(self):
        text = (
            "Python is a programming language. It is widely used for data science. "
            "The weather today is sunny and warm. I went to the beach yesterday. "
            "Machine learning models require large datasets. Neural networks have many layers."
        )
        config = ChunkingConfig(chunk_size=500, chunk_overlap=0, min_chunk_size=5)
        chunker = SemanticChunker(config, similarity_threshold=0.15)
        chunks = chunker.chunk(text)
        # 应该在话题转换处分块
        self.assertGreater(len(chunks), 1)

    # --- 测试结构感知分块 ---
    def test_structure_aware_markdown(self):
        config = ChunkingConfig(chunk_size=500, chunk_overlap=0, min_chunk_size=10)
        chunker = StructureAwareChunker(config)
        chunks = chunker.chunk(self.markdown_text)
        self.assertGreater(len(chunks), 1)
        # 应该按标题分块
        heading_chunks = [c for c in chunks if c.metadata.get('type') == 'heading']
        self.assertGreater(len(heading_chunks), 0)

    def test_structure_aware_code_protection(self):
        config = ChunkingConfig(chunk_size=200, chunk_overlap=0, min_chunk_size=1)
        chunker = StructureAwareChunker(config)
        chunks = chunker.chunk(self.markdown_text)
        # 代码块不应被拆分（检查每个chunk中代码块标记成对出现或不存在）
        for c in chunks:
            code_count = c.content.count('```')
            self.assertEqual(code_count % 2, 0, f"Chunk {c.index} has unbalanced code blocks: {code_count} markers")

    # --- 测试分块评估 ---
    def test_evaluator(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=10, min_chunk_size=5)
        chunker = FixedSizeChunker(config)
        chunks = chunker.chunk(self.long_text)
        result = ChunkEvaluator.evaluate(chunks, self.long_text)
        self.assertIn("chunk_count", result)
        self.assertIn("size_stats", result)
        self.assertGreater(result["chunk_count"], 1)

    # --- 测试统一管线 ---
    def test_pipeline_all_strategies(self):
        pipeline = ChunkingPipeline(ChunkingConfig(chunk_size=100, chunk_overlap=20, min_chunk_size=5))
        for strategy in ChunkingStrategy:
            chunks = pipeline.chunk(self.long_text, strategy)
            self.assertGreater(len(chunks), 0, f"Strategy {strategy} produced no chunks")

    def test_pipeline_compare(self):
        pipeline = ChunkingPipeline(ChunkingConfig(chunk_size=100, chunk_overlap=20, min_chunk_size=5))
        results = pipeline.compare_strategies(self.long_text)
        self.assertEqual(len(results), len(ChunkingStrategy))
        for strategy_name, eval_result in results.items():
            self.assertNotIn("error", eval_result, f"Strategy {strategy_name} failed")

    def test_pipeline_batch(self):
        pipeline = ChunkingPipeline(ChunkingConfig(chunk_size=50, chunk_overlap=0, min_chunk_size=1))
        texts = [self.short_text, self.long_text]
        results = pipeline.chunk_batch(texts)
        self.assertEqual(len(results), 2)
        for chunks in results:
            self.assertGreater(len(chunks), 0)

    # --- 测试配置验证 ---
    def test_config_validation(self):
        with self.assertRaises(AssertionError):
            ChunkingConfig(chunk_size=0).validate()
        with self.assertRaises(AssertionError):
            ChunkingConfig(chunk_size=100, chunk_overlap=100).validate()
        with self.assertRaises(AssertionError):
            ChunkingConfig(chunk_size=100, chunk_overlap=50, min_chunk_size=0).validate()

    # --- 测试小块合并 ---
    def test_merge_small_chunks(self):
        config = ChunkingConfig(chunk_size=50, chunk_overlap=0, min_chunk_size=20)
        chunker = FixedSizeChunker(config)
        # 文本长度恰好产生小块
        text = "A" * 45 + " " + "B" * 5  # 第二块只有5字符，应被合并
        chunks = chunker.chunk(text)
        # 最后一个小块应该被合并到前一块
        self.assertGreaterEqual(len(chunks[-1].content), 20)

    # --- 测试空文本 ---
    def test_empty_text(self):
        pipeline = ChunkingPipeline()
        for strategy in ChunkingStrategy:
            chunks = pipeline.chunk("", strategy)
            self.assertEqual(len(chunks), 0, f"Strategy {strategy} should return empty list for empty text")


# ============================================================================
# 第八部分：演示主函数
# ============================================================================

def demo():
    """分块策略演示"""

    print("=" * 70)
    print("  RAG 文档分块策略演示")
    print("=" * 70)

    # 示例文本
    sample_text = """
# RAG 系统架构

Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval with text generation. It addresses the knowledge cutoff problem of large language models.

## 核心组件

RAG 系统包含三个核心组件：

1. **文档处理管线**：负责文档的加载、分块和向量化
2. **检索引擎**：基于向量数据库的相似度搜索
3. **生成模块**：LLM 根据检索到的上下文生成回答

## 分块策略

文档分块是 RAG 中最关键的预处理步骤。好的分块策略应该：

- 保持语义完整性
- 控制块大小在合理范围
- 支持重叠以保持上下文
- 适应不同文档类型

```python
# 示例：简单的分块代码
def simple_chunk(text, size=500):
    return [text[i:i+size] for i in range(0, len(text), size)]
```

## 向量检索

分块后，每个块被转换为向量并存储在向量数据库中。检索时，查询向量与所有块向量计算相似度，返回最相关的块。

### 距离度量

常用的距离度量包括：

- 余弦相似度
- 欧氏距离（L2）
- 内积

### 索引加速

暴力搜索在小数据集上可用，但对于大规模数据需要索引加速：

- IVF（倒排文件索引）
- HNSW（分层可导航小世界图）

## 总结

RAG 系统的效果取决于文档分块、嵌入质量和检索精度。选择合适的分块策略是构建高质量 RAG 系统的第一步。
""".strip()

    config = ChunkingConfig(chunk_size=300, chunk_overlap=50, min_chunk_size=20)
    pipeline = ChunkingPipeline(config)

    print(f"\n原文长度: {len(sample_text)} 字符")
    print(f"估算 Token: {TokenEstimator.estimate_tokens(sample_text)}")
    print(f"配置: chunk_size={config.chunk_size}, overlap={config.chunk_overlap}")

    # 对比所有策略
    print("\n" + "=" * 70)
    print("  策略对比")
    print("=" * 70)

    results = pipeline.compare_strategies(sample_text)

    print(f"\n{'策略':<20} {'块数':>4} {'平均大小':>8} {'大小标准差':>10} {'句子完整率':>10} {'覆盖率':>8}")
    print("-" * 70)

    for strategy_name, eval_result in results.items():
        if "error" in eval_result:
            print(f"{strategy_name:<20} ERROR: {eval_result['error'][:40]}")
            continue
        print(f"{strategy_name:<20} {eval_result['chunk_count']:>4} "
              f"{eval_result['size_stats']['mean']:>8.1f} "
              f"{eval_result['size_stats']['std']:>10.1f} "
              f"{eval_result['sentence_completion_rate']:>10.2f} "
              f"{eval_result['coverage']:>8.2f}")

    # 展示结构感知分块结果
    print("\n" + "=" * 70)
    print("  结构感知分块结果（Markdown 文档）")
    print("=" * 70)

    chunks = pipeline.chunk(sample_text, ChunkingStrategy.STRUCTURE_AWARE)
    for c in chunks:
        title = c.metadata.get('title', '(无标题)')
        chunk_type = c.metadata.get('type', 'unknown')
        level = c.metadata.get('level', 0)
        indent = "  " * level
        preview = c.content[:80].replace('\n', ' ')
        print(f"\n[Chunk {c.index}] {indent}type={chunk_type}, title='{title}', size={len(c.content)}")
        print(f"  {preview}...")

    # 展示语义分块结果
    print("\n" + "=" * 70)
    print("  语义分块结果")
    print("=" * 70)

    chunks = pipeline.chunk(sample_text, ChunkingStrategy.SEMANTIC)
    for c in chunks:
        avg_sim = c.metadata.get('avg_similarity', 0)
        preview = c.content[:80].replace('\n', ' ')
        print(f"\n[Chunk {c.index}] size={len(c.content)}, avg_sim={avg_sim:.3f}")
        print(f"  {preview}...")

    print("\n" + "=" * 70)
    print("  演示完成！")
    print("=" * 70)


if __name__ == "__main__":
    # 运行演示
    demo()

    # 运行测试
    print("\n运行测试...\n")
    unittest.main(verbosity=2, exit=False)
