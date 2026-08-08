"""Tests for Auto Wiki Layer — 自动知识整理。"""

import os
import tempfile

import pytest

from suyi.memory.auto_wiki import WikiPage, AutoWiki
from suyi.memory.structured_facts import StructuredFact, FactSource


class TestWikiPage:
    """WikiPage 模型测试。"""

    def test_creation(self):
        """基本创建。"""
        page = WikiPage(
            title="Python",
            summary="Python is a programming language.",
            content="Python is a high-level programming language.",
        )
        assert page.title == "Python"
        assert page.id
        assert page.created_at > 0

    def test_serialization(self):
        """序列化和反序列化。"""
        page = WikiPage(
            title="Test",
            summary="Summary",
            content="Content",
            related_entities=["A", "B"],
            tags=["test"],
        )
        d = page.to_dict()
        restored = WikiPage.from_dict(d)
        assert restored.title == page.title
        assert restored.summary == page.summary
        assert restored.related_entities == page.related_entities


class TestAutoWiki:
    """AutoWiki 自动知识整理测试。"""

    def test_add_session(self):
        """从会话提取概念。"""
        wiki = AutoWiki()
        messages = [
            {"role": "user", "content": "Tell me about Python programming language"},
            {"role": "assistant", "content": "Python is a high-level programming language with dynamic typing"},
            {"role": "user", "content": "How does Python handle memory management?"},
        ]
        stats = wiki.add_session(messages)
        assert stats["messages_processed"] == 3
        assert stats["concepts_extracted"] > 0

    def test_add_facts(self):
        """从结构化事实构建 Wiki。"""
        wiki = AutoWiki()
        facts = [
            StructuredFact(entity="Python", attribute="typing", value="dynamic",
                          source=FactSource.USER_STATEMENT.value),
            StructuredFact(entity="Python", attribute="version", value="3.12",
                          source=FactSource.USER_STATEMENT.value),
            StructuredFact(entity="Rust", attribute="typing", value="static",
                          source=FactSource.USER_STATEMENT.value),
        ]
        stats = wiki.add_facts(facts)
        assert stats["facts_processed"] == 3
        assert stats["pages_created"] == 2  # Python + Rust
        assert len(wiki) == 2

    def test_add_facts_update_existing(self):
        """更新已存在的 Wiki 页面。"""
        wiki = AutoWiki()
        facts1 = [
            StructuredFact(entity="Python", attribute="typing", value="dynamic"),
        ]
        wiki.add_facts(facts1)
        assert len(wiki) == 1

        facts2 = [
            StructuredFact(entity="Python", attribute="version", value="3.12"),
        ]
        stats = wiki.add_facts(facts2)
        assert stats["pages_updated"] == 1
        assert len(wiki) == 1  # 仍然是 1 个页面

        page = wiki.get_page("Python")
        assert "version" in page.content

    def test_retrieve(self):
        """检索 Wiki 页面。"""
        wiki = AutoWiki()
        facts = [
            StructuredFact(entity="Python", attribute="typing", value="dynamic"),
            StructuredFact(entity="Rust", attribute="typing", value="static"),
        ]
        wiki.add_facts(facts)

        results = wiki.retrieve("Python typing")
        assert len(results) > 0
        assert results[0]["layer"] == "wiki"
        assert "score" in results[0]

    def test_build_wiki(self):
        """从会话概念构建 Wiki。"""
        wiki = AutoWiki()
        # 添加多个包含相同概念的会话
        for _ in range(5):
            wiki.add_session([
                {"role": "user", "content": "Tell me about Python programming"}
            ])

        stats = wiki.build_wiki()
        assert stats["pages_before"] == 0
        assert "top_concepts" in stats

    def test_delete_page(self):
        """删除页面。"""
        wiki = AutoWiki()
        facts = [StructuredFact(entity="Python", attribute="x", value="y")]
        wiki.add_facts(facts)
        page = wiki.get_page("Python")
        assert wiki.delete_page(page.id) is True
        assert len(wiki) == 0

    def test_get_page(self):
        """获取页面。"""
        wiki = AutoWiki()
        facts = [StructuredFact(entity="Test", attribute="x", value="y")]
        wiki.add_facts(facts)
        assert wiki.get_page("Test") is not None
        assert wiki.get_page("nonexistent") is None

    def test_persistence(self):
        """JSON 持久化。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "wiki.json")
            wiki = AutoWiki(storage_path=path)
            facts = [StructuredFact(entity="Python", attribute="x", value="y")]
            wiki.add_facts(facts)

            wiki2 = AutoWiki(storage_path=path)
            assert len(wiki2) == 1

    def test_empty_retrieve(self):
        """空存储检索。"""
        wiki = AutoWiki()
        assert wiki.retrieve("anything") == []

    def test_repr(self):
        """repr 方法。"""
        wiki = AutoWiki()
        assert "AutoWiki" in repr(wiki)
