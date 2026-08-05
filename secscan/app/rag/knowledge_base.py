"""安全知识库管理器模块

管理安全漏洞修复知识库，加载Markdown格式的知识文档，
将文档按章节分块，提供按漏洞类型(rule_id)和全文检索的接口。

知识文档存放于 app/data/security_kb/ 目录下，每种漏洞类型一份 .md 文件，
文件名以规则ID开头（如 SC001_SQL注入修复指南.md）。
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class KnowledgeChunk:
    """知识分块数据结构

    表示知识库中的一个检索单元，通常对应Markdown文档的一个章节。

    Attributes:
        chunk_id: 分块唯一标识，格式为 "{doc_id}_{序号}"
        doc_id: 所属文档ID，如 "SC001"
        title: 章节标题
        text: 分块文本内容
        source_file: 源文件名
    """
    chunk_id: str
    doc_id: str
    title: str
    text: str
    source_file: str


@dataclass
class KnowledgeDoc:
    """知识文档数据结构

    表示一份完整的漏洞修复知识文档。

    Attributes:
        doc_id: 文档ID，对应规则ID（如 "SC001"）
        title: 文档标题
        content: 完整文本内容
        chunks: 按章节分块后的片段列表
        file_path: 源文件路径
    """
    doc_id: str
    title: str
    content: str
    chunks: List[KnowledgeChunk] = field(default_factory=list)
    file_path: str = ""


class SecurityKnowledgeBase:
    """安全知识库

    加载 knowledge_dir 下的所有 .md 知识文档，解析为结构化数据。
    支持按漏洞类型(rule_id)获取完整文档，也支持获取所有分块用于向量检索。

    用法:
        kb = SecurityKnowledgeBase()
        kb.load()
        doc = kb.get_doc("SC001")       # 获取SQL注入修复文档
        chunks = kb.get_all_chunks()      # 获取所有分块
    """

    # 知识库默认目录（相对于本文件的位置：app/rag/ -> app/ -> app/data/security_kb/）
    DEFAULT_KB_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "security_kb"
    )

    def __init__(self, kb_dir: Optional[str] = None):
        """初始化知识库

        Args:
            kb_dir: 知识库目录路径，默认为 app/data/security_kb/
        """
        self.kb_dir = kb_dir or self.DEFAULT_KB_DIR
        self._documents: Dict[str, KnowledgeDoc] = {}
        self._all_chunks: List[KnowledgeChunk] = []
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """知识库是否已加载"""
        return self._loaded

    def load(self) -> None:
        """加载知识库目录下的所有 .md 文件

        遍历知识库目录，读取所有 .md 文件，按文件名前缀匹配规则ID，
        将每份文档按 Markdown 二级标题(##)分块。
        """
        self._documents.clear()
        self._all_chunks.clear()

        if not os.path.isdir(self.kb_dir):
            self._loaded = True
            return

        # 遍历目录下所有 .md 文件
        for filename in sorted(os.listdir(self.kb_dir)):
            if not filename.endswith(".md"):
                continue

            # 从文件名提取规则ID（如 "SC001_SQL注入修复指南.md" -> "SC001"）
            rule_id = filename.split("_")[0].upper()
            if not rule_id.startswith("SC"):
                continue

            filepath = os.path.join(self.kb_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except (IOError, UnicodeDecodeError):
                continue

            # 解析文档
            doc = self._parse_document(rule_id, content, filename)
            self._documents[rule_id] = doc
            self._all_chunks.extend(doc.chunks)

        self._loaded = True

    def _parse_document(self, doc_id: str, content: str, filename: str) -> KnowledgeDoc:
        """解析Markdown文档，提取标题并按章节分块

        将文档按 ## 二级标题拆分为多个知识分块。
        文档标题（# 一级标题）作为文档标题。

        Args:
            doc_id: 文档ID（规则ID）
            content: Markdown文本内容
            filename: 源文件名

        Returns:
            KnowledgeDoc 解析后的知识文档
        """
        lines = content.split("\n")
        doc_title = ""
        chunks: List[KnowledgeChunk] = []
        current_section_title = ""
        current_section_lines: List[str] = []
        chunk_index = 0

        for line in lines:
            # 一级标题作为文档标题
            if line.startswith("# ") and not line.startswith("## "):
                doc_title = line[2:].strip()
                continue

            # 二级标题作为分块边界
            if line.startswith("## "):
                # 保存上一个分块
                if current_section_lines:
                    chunk_text = "\n".join(current_section_lines).strip()
                    if chunk_text:
                        chunks.append(KnowledgeChunk(
                            chunk_id=f"{doc_id}_{chunk_index}",
                            doc_id=doc_id,
                            title=current_section_title,
                            text=chunk_text,
                            source_file=filename,
                        ))
                        chunk_index += 1

                # 开始新分块
                current_section_title = line[3:].strip()
                current_section_lines = [line]
            else:
                current_section_lines.append(line)

        # 保存最后一个分块
        if current_section_lines:
            chunk_text = "\n".join(current_section_lines).strip()
            if chunk_text:
                chunks.append(KnowledgeChunk(
                    chunk_id=f"{doc_id}_{chunk_index}",
                    doc_id=doc_id,
                    title=current_section_title,
                    text=chunk_text,
                    source_file=filename,
                ))

        return KnowledgeDoc(
            doc_id=doc_id,
            title=doc_title,
            content=content,
            chunks=chunks,
            file_path=filename,
        )

    def get_doc(self, rule_id: str) -> Optional[KnowledgeDoc]:
        """按规则ID获取知识文档

        Args:
            rule_id: 规则ID，如 "SC001"

        Returns:
            KnowledgeDoc 或 None（如果不存在）
        """
        if not self._loaded:
            self.load()
        return self._documents.get(rule_id.upper())

    def get_all_chunks(self) -> List[KnowledgeChunk]:
        """获取所有知识分块，用于向量检索

        Returns:
            所有文档的分块列表
        """
        if not self._loaded:
            self.load()
        return list(self._all_chunks)

    def get_chunks_by_doc(self, rule_id: str) -> List[KnowledgeChunk]:
        """按规则ID获取该文档的所有分块

        Args:
            rule_id: 规则ID，如 "SC001"

        Returns:
            该漏洞类型的知识分块列表
        """
        doc = self.get_doc(rule_id)
        if doc is None:
            return []
        return list(doc.chunks)

    @property
    def doc_count(self) -> int:
        """已加载的文档数量"""
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        """已加载的分块总数"""
        return len(self._all_chunks)

    def list_doc_ids(self) -> List[str]:
        """列出所有已加载的文档ID"""
        return sorted(self._documents.keys())
