"""Tests for RAG Pipeline — 文档分块、检索管道、完整 RAG 流程。"""

import os
import tempfile
import pytest

from suyi.rag.chunker import (
    Chunk,
    BaseChunker,
    FixedSizeChunker,
    SentenceChunker,
    SemanticChunker,
)
from suyi.rag.retriever import RAGResult, RAGRetriever
from suyi.rag.pipeline import RAGPipeline, get_chunker


# ═════════════════════════════════════════════════════════════
#  Chunk 数据结构
# ═════════════════════════════════════════════════════════════

class TestChunk:
    """Chunk 数据结构测试。"""

    def test_creation(self):
        chunk = Chunk(content="Hello world", index=0, start=0, end=11)
        assert chunk.content == "Hello world"
        assert chunk.index == 0
        assert chunk.start == 0
        assert chunk.end == 11

    def test_default_metadata(self):
        chunk = Chunk(content="Test")
        assert chunk.metadata == {}

    def test_to_dict(self):
        chunk = Chunk(content="Test", index=1, start=5, end=9, metadata={"source": "doc.txt"})
        d = chunk.to_dict()
        assert d["content"] == "Test"
        assert d["index"] == 1
        assert d["start"] == 5
        assert d["end"] == 9
        assert d["metadata"]["source"] == "doc.txt"

    def test_repr(self):
        chunk = Chunk(content="Hello world content", index=2)
        r = repr(chunk)
        assert "Chunk" in r
        assert "idx=2" in r


# ═════════════════════════════════════════════════════════════
#  FixedSizeChunker
# ═════════════════════════════════════════════════════════════

class TestFixedSizeChunker:
    """固定大小分块器测试。"""

    def test_basic_chunking(self):
        chunker = FixedSizeChunker(chunk_size=10, overlap=0)
        text = "0123456789ABCDEF"
        chunks = chunker.chunk(text)
        assert len(chunks) == 2
        assert chunks[0].content == "0123456789"
        assert chunks[1].content == "ABCDEF"

    def test_overlap(self):
        chunker = FixedSizeChunker(chunk_size=10, overlap=5)
        text = "0123456789ABCDEF"
        chunks = chunker.chunk(text)
        assert len(chunks) == 3
        # 第二块应该从位置 5 开始（step = 10 - 5 = 5）
        assert chunks[1].start == 5

    def test_empty_text(self):
        chunker = FixedSizeChunker(chunk_size=10)
        assert chunker.chunk("") == []

    def test_short_text(self):
        chunker = FixedSizeChunker(chunk_size=100)
        chunks = chunker.chunk("Short")
        assert len(chunks) == 1
        assert chunks[0].content == "Short"

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            FixedSizeChunker(chunk_size=0)
        with pytest.raises(ValueError):
            FixedSizeChunker(chunk_size=10, overlap=10)

    def test_chunk_document(self):
        chunker = FixedSizeChunker(chunk_size=10)
        chunks = chunker.chunk_document("Hello World Test", source="readme.md")
        assert all(c.metadata.get("source") == "readme.md" for c in chunks)


# ═════════════════════════════════════════════════════════════
#  SentenceChunker
# ═════════════════════════════════════════════════════════════

class TestSentenceChunker:
    """句子分块器测试。"""

    def test_basic_sentence_split(self):
        chunker = SentenceChunker(target_size=50)
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        assert all(c.content for c in chunks)

    def test_chinese_sentences(self):
        chunker = SentenceChunker(target_size=20)
        text = "这是第一句话。这是第二句话。这是第三句话。"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2

    def test_empty_text(self):
        chunker = SentenceChunker(target_size=50)
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_no_sentence_boundary(self):
        chunker = SentenceChunker(target_size=100)
        text = "No sentence boundaries here just continuous text"
        chunks = chunker.chunk(text)
        assert len(chunks) == 1

    def test_overlap(self):
        chunker = SentenceChunker(target_size=30, overlap_sentences=1)
        text = "First sentence here. Second one. Third one. Fourth one."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2


# ═════════════════════════════════════════════════════════════
#  SemanticChunker
# ═════════════════════════════════════════════════════════════

class TestSemanticChunker:
    """语义分块器测试。"""

    def test_markdown_headings(self):
        chunker = SemanticChunker(max_chunk_size=500)
        text = "# Title\n\nPara one.\n\n## Subtitle\n\nPara two."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2
        assert chunks[0].metadata.get("heading") == "Title"
        assert chunks[1].metadata.get("heading") == "Subtitle"

    def test_no_headings(self):
        chunker = SemanticChunker(max_chunk_size=100)
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_empty_text(self):
        chunker = SemanticChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_heading_level(self):
        chunker = SemanticChunker()
        text = "### Deep heading\n\nContent here."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        assert chunks[0].metadata.get("heading_level") == 3

    def test_large_section_split(self):
        chunker = SemanticChunker(max_chunk_size=50)
        text = "# Title\n\n" + "Long paragraph. " * 20
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2


# ═════════════════════════════════════════════════════════════
#  RAGRetriever
# ═════════════════════════════════════════════════════════════

class TestRAGRetriever:
    """RAG 检索器测试。"""

    def test_add_and_retrieve(self):
        retriever = RAGRetriever()
        retriever.add_document("Python is a programming language", source="doc1")
        retriever.add_document("Java is also a programming language", source="doc2")
        results = retriever.retrieve("Python programming")
        assert len(results) > 0
        assert "Python" in results[0].content or "programming" in results[0].content.lower()

    def test_empty_retriever(self):
        retriever = RAGRetriever()
        results = retriever.retrieve("anything")
        assert results == []

    def test_add_chunks(self):
        retriever = RAGRetriever()
        chunks = [
            Chunk(content="Machine learning basics", index=0, metadata={"source": "ml.md"}),
            Chunk(content="Deep learning advanced", index=1, metadata={"source": "ml.md"}),
        ]
        retriever.add_chunks(chunks, source="ml.md")
        assert retriever.chunk_count == 2
        assert retriever.document_count == 1

    def test_stats(self):
        retriever = RAGRetriever()
        retriever.add_document("Test content", source="test.txt")
        stats = retriever.get_stats()
        assert stats["total_chunks"] > 0
        assert stats["total_documents"] == 1
        assert "test.txt" in stats["documents"]

    def test_clear(self):
        retriever = RAGRetriever()
        retriever.add_document("Content", source="doc")
        retriever.clear()
        assert retriever.chunk_count == 0
        assert retriever.document_count == 0

    def test_retrieve_logs(self):
        retriever = RAGRetriever()
        retriever.add_document("Python guide", source="guide.md")
        retriever.retrieve("Python")
        assert len(retriever.retrieve_logs) == 1
        assert retriever.retrieve_logs[0]["query"] == "Python"


# ═════════════════════════════════════════════════════════════
#  RAGPipeline
# ═════════════════════════════════════════════════════════════

class TestRAGPipeline:
    """RAG 完整管道测试。"""

    def test_ingest_and_retrieve(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Python is a high-level programming language with dynamic typing.", source="intro.md")
        results = pipeline.retrieve("Python programming")
        assert len(results) > 0

    def test_augment(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Python supports multiple paradigms including OOP and functional.", source="doc.md")
        augmented = pipeline.augment("What paradigms does Python support?")
        assert "Retrieved Context" in augmented
        assert "Query" in augmented

    def test_augment_with_system_prompt(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Test content about AI", source="ai.md")
        augmented = pipeline.augment("What is AI?", system_prompt="You are a helpful assistant.")
        assert "You are a helpful assistant" in augmented
        assert "Retrieved Context" in augmented

    def test_augment_no_results(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        augmented = pipeline.augment("query", results=[])
        assert augmented == ""

    def test_query(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Machine learning is a subset of artificial intelligence.", source="ml.md")
        result = pipeline.query("machine learning")
        assert "query" in result
        assert "results" in result
        assert "augmented_prompt" in result
        assert result["result_count"] > 0

    def test_get_chunker_factory(self):
        chunker = get_chunker("fixed", chunk_size=200)
        assert isinstance(chunker, FixedSizeChunker)
        chunker2 = get_chunker("sentence", target_size=200)
        assert isinstance(chunker2, SentenceChunker)
        chunker3 = get_chunker("semantic")
        assert isinstance(chunker3, SemanticChunker)

    def test_get_chunker_invalid(self):
        with pytest.raises(ValueError):
            get_chunker("invalid_strategy")

    def test_stats(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Test content", source="test.md")
        stats = pipeline.get_stats()
        assert stats["chunker"] == "FixedSizeChunker"
        assert stats["document_count"] == 1

    def test_clear(self):
        pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
        pipeline.ingest("Test", source="doc.md")
        pipeline.clear()
        assert pipeline.document_count == 0

    def test_ingest_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("This is a test document about Python programming.")
            f.flush()
            path = f.name
        try:
            pipeline = RAGPipeline(chunker="fixed", chunk_size=100)
            chunks = pipeline.ingest_file(path)
            assert len(chunks) > 0
        finally:
            os.unlink(path)

    def test_ingest_file_not_found(self):
        pipeline = RAGPipeline()
        with pytest.raises(FileNotFoundError):
            pipeline.ingest_file("/nonexistent/file.txt")

    def test_custom_chunker_instance(self):
        custom = SemanticChunker(max_chunk_size=200)
        pipeline = RAGPipeline(chunker=custom)
        assert pipeline.chunker is custom
