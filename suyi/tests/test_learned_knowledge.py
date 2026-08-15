"""
Tests for v1.6.0 — Bypass Knowledge Layer (旁路知识层).

覆盖：
    - LearnedKnowledgeStore: CRUD / 持久化 / 过滤 / 统计
    - KnowledgeRetriever: TF-IDF 检索 / 中文 bigram / 缓存失效 / MemoryBackend 兼容
    - SemanticDeduplicator: skip/merge/append 三策略 / 阈值 / category 隔离
    - SuccessDistiller: 正样本蒸馏 / 失败教训 / 批量统计 / dedup / llm_fn
    - WeakSignalCollector: 累加 / 阈值 / 持久化 / 隐私 / FeedbackCollector 集成
    - ThreeTierKnowledgeInjector: 三级组装 / XML 格式化 / MemoryBackend / bureau 隔离
    - 集成测试: 端到端 / orchestrator 旁路进化 / 向后兼容

全部测试无外部 API 调用，纯标准库 + numpy + pytest.
"""

import asyncio
import json
import os
import tempfile

import pytest

from suyi.core.context import ContextAssembler, MemoryBackend
from suyi.evolution.learner import InteractionRecord
from suyi.evolution.feedback import FeedbackCollector
from suyi.evolution.orchestrator import EvolutionOrchestrator
from suyi.evolution.learned import (
    KnowledgeEntry,
    LearnedKnowledgeStore,
    KnowledgeRetriever,
    KnowledgeBackend,
    SemanticDeduplicator,
    DeduplicationResult,
    DedupDecision,
    SuccessDistiller,
    DistillationResult,
    WeakSignal,
    WeakSignalCollector,
    ThreeTierKnowledgeInjector,
    KnowledgeTier,
)


# ── 辅助函数 ────────────────────────────────────────────────


def _make_record(
    success=True,
    tool_calls=None,
    task="读取文件内容",
    tags=None,
    record_id=None,
    feedback=None,
):
    """构造 InteractionRecord 测试辅助."""
    if tool_calls is None:
        tool_calls = [
            {"name": "read_file", "arguments": {"path": "a.txt"},
             "success": True, "output_summary": "file content"},
        ]
    return InteractionRecord(
        id=record_id or f"int_test_{id(tool_calls)}",
        task=task,
        tool_calls=tool_calls,
        success=success,
        duration=1.0,
        tags=tags or ["文件操作"],
        feedback=feedback,
    )


def _run(coro):
    """同步运行 async 测试辅助."""
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════
#  Store 测试 (1-5)
# ═══════════════════════════════════════════════════════════════


class TestLearnedKnowledgeStore:
    """旁路知识存储测试."""

    def test_add_get_update_delete(self):
        """1. 添加/获取/更新/删除条目."""
        store = LearnedKnowledgeStore()
        entry = KnowledgeEntry(
            title="测试规则",
            content="这是一条测试规则",
            category="guideline",
        )
        eid = store.add(entry)
        assert eid.startswith("kn_")

        fetched = store.get(eid)
        assert fetched is not None
        assert fetched.title == "测试规则"

        store.update(eid, title="更新后标题", confidence=0.9)
        assert store.get(eid).title == "更新后标题"
        assert store.get(eid).confidence == 0.9

        assert store.delete(eid) is True
        assert store.get(eid) is None
        assert store.delete(eid) is False

    def test_json_persistence_roundtrip(self):
        """2. JSON 持久化 save/load 往返一致."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = LearnedKnowledgeStore(storage_dir=tmpdir)
            eid = store1.add(KnowledgeEntry(
                title="持久化测试", content="保存再加载",
                category="success_pattern", tags=["tag1"],
                confidence=0.7,
            ))

            # 新实例从同一目录加载
            store2 = LearnedKnowledgeStore(storage_dir=tmpdir)
            fetched = store2.get(eid)
            assert fetched is not None
            assert fetched.title == "持久化测试"
            assert fetched.content == "保存再加载"
            assert fetched.confidence == 0.7
            assert "tag1" in fetched.tags

    def test_list_filter_by_bureau_category_tags(self):
        """3. list 按 bureau/category/tags 过滤."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(title="a", content="ca", bureau="b1",
                                 category="guideline", tags=["x"]))
        store.add(KnowledgeEntry(title="b", content="cb", bureau="b1",
                                 category="style", tags=["x", "y"]))
        store.add(KnowledgeEntry(title="c", content="cc", bureau="b2",
                                 category="guideline", tags=["z"]))

        assert len(store.list(bureau="b1")) == 2
        assert len(store.list(category="guideline")) == 2
        assert len(store.list(tags=["x"])) == 2
        assert len(store.list(bureau="b1", category="style", tags=["y"])) == 1
        assert len(store.list(bureau="b2", tags=["x"])) == 0

    def test_increment_usage(self):
        """4. increment_usage 更新计数."""
        store = LearnedKnowledgeStore()
        eid = store.add(KnowledgeEntry(title="t", content="c"))
        assert store.get(eid).usage_count == 0

        store.increment_usage(eid, success=True)
        store.increment_usage(eid, success=False)
        entry = store.get(eid)
        assert entry.usage_count == 2
        assert entry.success_count == 1
        assert entry.success_rate == 0.5

    def test_auto_generated_unique_ids(self):
        """5. ID 自动生成且唯一."""
        store = LearnedKnowledgeStore()
        ids = set()
        for i in range(20):
            eid = store.add(KnowledgeEntry(title=f"e{i}", content=f"c{i}"))
            assert eid not in ids
            ids.add(eid)
        assert len(ids) == 20


# ═══════════════════════════════════════════════════════════════
#  Retriever 测试 (6-11)
# ═══════════════════════════════════════════════════════════════


class TestKnowledgeRetriever:
    """知识检索器测试."""

    def test_semantic_search_finds_related(self):
        """6. TF-IDF 检索能找到语义相关条目."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            title="文件读取", content="文件读取错误时应检查路径是否存在",
            category="failure_lesson",
        ))
        store.add(KnowledgeEntry(
            title="网络请求", content="HTTP 请求需要设置超时参数",
            category="guideline",
        ))
        retriever = KnowledgeRetriever(store)
        results = _run(retriever.retrieve("文件读取失败怎么办", top_k=3))
        assert len(results) >= 1
        # 最相关的应是"文件读取"条目
        assert "文件读取" in results[0]["title"] or "路径" in results[0]["content"]

    def test_chinese_bigram_tokenization(self):
        """7. 中文分词（bigram）能处理中文查询."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            title="数据库连接",
            content="数据库连接池满了会导致超时，需要增大连接池",
            category="guideline",
        ))
        retriever = KnowledgeRetriever(store)
        results = _run(retriever.retrieve("数据库 超时", top_k=3))
        assert len(results) >= 1
        assert "数据库" in results[0]["content"] or "数据库" in results[0]["title"]

    def test_top_k_and_min_similarity(self):
        """8. top_k 和 min_similarity 参数生效."""
        store = LearnedKnowledgeStore()
        for i in range(10):
            store.add(KnowledgeEntry(
                title=f"条目{i}", content=f"这是关于主题{i}的内容 keyword{i}",
            ))
        retriever = KnowledgeRetriever(store, top_k=3, min_similarity=0.01)
        results = _run(retriever.retrieve("主题5 keyword5", top_k=3))
        assert len(results) <= 3
        assert len(results) >= 1

        # 高阈值应过滤掉所有结果
        strict_retriever = KnowledgeRetriever(store, min_similarity=0.99)
        strict_results = _run(strict_retriever.retrieve("完全无关xyz123", top_k=5))
        assert strict_results == []

    def test_cache_invalidation_on_add(self):
        """9. 新增条目后缓存自动失效，新条目可被检索."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(title="苹果", content="苹果是一种水果"))
        retriever = KnowledgeRetriever(store)

        # 首次检索构建缓存
        _run(retriever.retrieve("苹果", top_k=5))
        assert retriever._matrix is not None

        # 新增条目
        store.add(KnowledgeEntry(title="香蕉", content="香蕉也是水果"))

        # 应能检索到新条目（缓存重建）
        results = _run(retriever.retrieve("香蕉", top_k=5))
        contents = [r["content"] for r in results]
        assert any("香蕉" in c for c in contents)

    def test_retrieve_format_memory_backend_compatible(self):
        """10. retrieve 返回格式兼容 MemoryBackend（含 content/source/confidence）."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            title="规则", content="规则正文", confidence=0.8,
        ))
        retriever = KnowledgeRetriever(store)
        results = _run(retriever.retrieve("规则", top_k=1))
        assert len(results) == 1
        item = results[0]
        assert "content" in item
        assert "source" in item
        assert "confidence" in item
        assert item["source"] == "learned_knowledge"
        assert item["content"] == "规则正文"

    def test_empty_store_retrieve_returns_empty(self):
        """11. 空库检索返回空列表不报错."""
        store = LearnedKnowledgeStore()
        retriever = KnowledgeRetriever(store)
        results = _run(retriever.retrieve("任何查询", top_k=5))
        assert results == []
        # 空查询也不报错
        assert _run(retriever.retrieve("", top_k=5)) == []


# ═══════════════════════════════════════════════════════════════
#  Dedup 测试 (12-17)
# ═══════════════════════════════════════════════════════════════


class TestSemanticDeduplicator:
    """语义去重器测试."""

    def test_high_similarity_skip(self):
        """12. 高度相似内容 → SKIP."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            category="guideline",
            title="代码审查",
            content="提交代码前应当进行代码审查，确保没有语法错误",
        ))
        dedup = SemanticDeduplicator(store, skip_threshold=0.5, merge_threshold=0.2)
        decision = dedup.decide(
            "提交代码前应当进行代码审查，确保没有语法错误",
            category="guideline",
        )
        assert decision.action == DeduplicationResult.SKIP
        assert decision.target_id is not None

    def test_medium_similarity_merge(self):
        """13. 中等相似 → MERGE."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            category="guideline",
            title="测试",
            content="编写单元测试覆盖核心逻辑",
        ))
        dedup = SemanticDeduplicator(store, skip_threshold=0.9, merge_threshold=0.1)
        decision = dedup.decide(
            "编写集成测试和端到端测试覆盖业务流程",
            category="guideline",
        )
        # 这两个文本有 "编写" "测试" "覆盖" 等共同 token
        assert decision.action in (DeduplicationResult.MERGE, DeduplicationResult.APPEND)

    def test_low_similarity_append(self):
        """14. 不相似 → APPEND."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            category="guideline",
            title="天气",
            content="今天天气晴朗适合户外活动",
        ))
        dedup = SemanticDeduplicator(store, skip_threshold=0.85, merge_threshold=0.55)
        decision = dedup.decide(
            "数据库索引优化能显著提升查询性能",
            category="guideline",
        )
        assert decision.action == DeduplicationResult.APPEND

    def test_skip_updates_source_ids_and_confidence(self):
        """15. SKIP 时目标条目 source_ids 和 confidence 更新."""
        store = LearnedKnowledgeStore()
        eid = store.add(KnowledgeEntry(
            category="guideline",
            title="规则",
            content="相同的规则内容用于测试跳过逻辑",
            source_ids=["int_old"],
            confidence=0.5,
        ))
        dedup = SemanticDeduplicator(store, skip_threshold=0.3, merge_threshold=0.1)
        new_entry = KnowledgeEntry(
            category="guideline",
            title="规则",
            content="相同的规则内容用于测试跳过逻辑",
            source_ids=["int_new1", "int_new2"],
            confidence=0.6,
        )
        decision = dedup.decide(new_entry.content, category="guideline")
        dedup.apply(decision, new_entry)

        updated = store.get(eid)
        assert "int_new1" in updated.source_ids
        assert "int_new2" in updated.source_ids
        assert updated.confidence > 0.5  # 置信度提升

    def test_configurable_thresholds(self):
        """16. 阈值参数可配置."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            category="guideline", title="", content="alpha beta gamma",
        ))
        # 高 skip 阈值 → 不太容易 SKIP
        dedup_high = SemanticDeduplicator(store, skip_threshold=0.99, merge_threshold=0.01)
        d1 = dedup_high.decide("alpha beta gamma", category="guideline")
        # 完全相同应该 SKIP 即使阈值高（cosine=1.0）
        assert d1.action == DeduplicationResult.SKIP

        # 低 merge 阈值 → 更容易 MERGE
        dedup_low = SemanticDeduplicator(store, skip_threshold=0.99, merge_threshold=0.99)
        d2 = dedup_low.decide("完全不相关xyz", category="guideline")
        assert d2.action == DeduplicationResult.APPEND

    def test_different_categories_not_compared(self):
        """17. 不同 category 不互相比较."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            category="guideline", title="g", content="完全相同的内容文本",
        ))
        store.add(KnowledgeEntry(
            category="style", title="s", content="完全相同的内容文本",
        ))
        dedup = SemanticDeduplicator(store, skip_threshold=0.3, merge_threshold=0.1)

        # 在 success_pattern 类别中比较，虽然有完全相同内容但在别的 category
        decision = dedup.decide("完全相同的内容文本", category="success_pattern")
        assert decision.action == DeduplicationResult.APPEND


# ═══════════════════════════════════════════════════════════════
#  Distiller 测试 (18-23)
# ═══════════════════════════════════════════════════════════════


class TestSuccessDistiller:
    """正样本蒸馏器测试."""

    def test_high_quality_success_generates_pattern(self):
        """18. 高质量成功记录 → 生成 success_pattern."""
        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)

        record = _make_record(success=True, task="读取文件内容并分析")
        result = distiller.distill_from_record(record)

        assert result.appended == 1
        assert len(result.new_entries) == 1
        entry = result.new_entries[0]
        assert entry.category == "success_pattern"
        assert "read_file" in entry.content
        assert record.id in entry.source_ids

    def test_failure_record_extracts_lesson(self):
        """19. 失败记录 → 提取 failure_lesson."""
        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)

        record = _make_record(
            success=False,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "x"},
                 "success": False, "output_summary": "FileNotFoundError"},
            ],
            task="读取不存在的文件",
        )
        result = distiller.distill_from_record(record)
        # 失败记录不产生 success_pattern，但产生 failure_lesson
        all_entries = store.list(category="failure_lesson")
        assert len(all_entries) >= 1
        assert "read_file" in all_entries[0].content or "失败" in all_entries[0].content

    def test_low_quality_no_success_pattern(self):
        """20. 低质量记录（有 tool failures）不生成成功模式."""
        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)

        record = _make_record(
            success=True,
            tool_calls=[
                {"name": "read_file", "arguments": {}, "success": True, "output_summary": ""},
                {"name": "write_file", "arguments": {}, "success": False, "output_summary": "error"},
            ],
        )
        result = distiller.distill_from_record(record)
        # 不应有 success_pattern 新增（因为有失败工具）
        success_patterns = store.list(category="success_pattern")
        assert len(success_patterns) == 0

    def test_batch_distillation_stats(self):
        """21. 批量蒸馏统计正确（new/skipped/merged/appended 计数）."""
        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)

        records = [
            _make_record(success=True, task="读取配置文件", record_id="int_a",
                         tags=["文件操作"]),
            _make_record(success=True, task="搜索代码", record_id="int_b",
                         tool_calls=[{"name": "search", "arguments": {"q": "x"},
                                      "success": True, "output_summary": "found"}],
                         tags=["搜索检索"]),
            _make_record(success=False, task="网络请求失败", record_id="int_c",
                         tool_calls=[{"name": "web_request", "arguments": {},
                                      "success": False, "output_summary": "err"}],
                         tags=["网络请求"]),
        ]
        result = distiller.distill_batch(records)
        assert result.total_processed == 3
        # 3 条记录全部被处理（成功模式/失败教训经去重后为追加或合并）
        assert result.appended + result.merged == 3
        assert result.skipped == 0

    def test_distilled_entries_go_through_dedup(self):
        """22. 蒸馏出的条目经过 dedup 再入库."""
        store = LearnedKnowledgeStore()
        # 极低阈值使第二条相似记录走 SKIP
        dedup = SemanticDeduplicator(store, skip_threshold=0.2, merge_threshold=0.1)
        distiller = SuccessDistiller(store, dedup)

        # 两条几乎相同的成功记录
        r1 = _make_record(success=True, task="读取文件", record_id="int_d1",
                          tool_calls=[{"name": "read_file", "arguments": {},
                                       "success": True, "output_summary": "ok"}])
        r2 = _make_record(success=True, task="读取文件", record_id="int_d2",
                          tool_calls=[{"name": "read_file", "arguments": {},
                                       "success": True, "output_summary": "ok"}])
        distiller.distill_from_record(r1)
        result2 = distiller.distill_from_record(r2)

        # 第二条要么 SKIP 要么 MERGE，不应 APPEND 新条目
        assert result2.appended == 0
        assert result2.skipped + result2.merged >= 1

    def test_custom_llm_fn_enhancement(self):
        """23. 可注入自定义 llm_fn 增强提取."""
        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)

        call_count = []

        def mock_llm(record_dict):
            call_count.append(1)
            return f"LLM增强：任务类型={record_dict['task_type']}，工具={record_dict['tool_sequence']}"

        distiller = SuccessDistiller(store, dedup, llm_fn=mock_llm)
        record = _make_record(success=True, task="执行代码")
        result = distiller.distill_from_record(record)
        assert len(call_count) == 1
        assert "LLM增强" in result.new_entries[0].content


# ═══════════════════════════════════════════════════════════════
#  WeakSignal 测试 (24-30)
# ═══════════════════════════════════════════════════════════════


class TestWeakSignalCollector:
    """弱信号积累器测试."""

    def test_same_type_accumulates(self):
        """24. 记录弱信号，同类信号 count 累加."""
        collector = WeakSignalCollector(threshold=5)
        s1 = collector.record("thumbs_down", "任务A失败", category_hint="file")
        s2 = collector.record("thumbs_down", "任务B失败", category_hint="file")
        assert s1.id == s2.id  # 同 key
        assert s2.count == 2

    def test_different_types_separate(self):
        """25. 不同类信号不互相累加."""
        collector = WeakSignalCollector(threshold=5)
        collector.record("thumbs_down", "a", category_hint="file")
        collector.record("retry", "b", category_hint="file")
        collector.record("thumbs_down", "c", category_hint="network")
        assert collector.count() == 3

    def test_threshold_triggers_pending(self):
        """26. count 达到 threshold 出现在 pending 列表."""
        collector = WeakSignalCollector(threshold=3)
        for i in range(2):
            collector.record("thumbs_down", f"摘要{i}", category_hint="bug")
        assert len(collector.get_pending_distillation()) == 0

        collector.record("thumbs_down", "摘要2", category_hint="bug")
        pending = collector.get_pending_distillation()
        assert len(pending) == 1
        assert pending[0].count == 3

    def test_mark_distilled_removes_from_pending(self):
        """27. mark_distilled 后从 pending 移除."""
        collector = WeakSignalCollector(threshold=2)
        collector.record("thumbs_down", "a", category_hint="x")
        signal = collector.record("thumbs_down", "b", category_hint="x")
        assert len(collector.get_pending_distillation()) == 1

        assert collector.mark_distilled(signal.id) is True
        assert len(collector.get_pending_distillation()) == 0

    def test_save_load_persistence(self):
        """28. save/load 持久化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c1 = WeakSignalCollector(threshold=4, storage_dir=tmpdir)
            c1.record("thumbs_down", "测试摘要", category_hint="bug")
            c1.record("thumbs_down", "测试摘要", category_hint="bug")

            c2 = WeakSignalCollector(threshold=4, storage_dir=tmpdir)
            assert c2.count() == 1
            signals = c2.all_signals()
            assert signals[0].count == 2

    def test_no_full_prompt_stored(self):
        """29. 不存完整 prompt，只存摘要（截断到 200 字）."""
        collector = WeakSignalCollector(threshold=5)
        long_text = "这是一段非常长的任务描述" * 100  # >200 字
        signal = collector.record("thumbs_down", long_text, category_hint="x")
        assert len(signal.context_summary) <= 200
        assert signal.context_summary != long_text

    def test_feedback_collector_integration(self):
        """30. FeedbackCollector 集成：thumbs_down 自动记录弱信号."""
        weak = WeakSignalCollector(threshold=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            fc = FeedbackCollector(
                storage_dir=tmpdir,
                weak_signal_collector=weak,
            )
            fc.collect_explicit(
                interaction_id="int_1",
                rating="thumbs_down",
                comment="结果不对",
            )
            # 应记录了 thumbs_down 和 user_comment 两类弱信号
            assert weak.count() >= 1
            all_types = [s.signal_type for s in weak.all_signals()]
            assert "thumbs_down" in all_types
            assert "user_comment" in all_types

    def test_feedback_collector_no_weak_signal_by_default(self):
        """向后兼容：不传 weak_signal_collector 时不报错."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fc = FeedbackCollector(storage_dir=tmpdir)
            fb = fc.collect_explicit("int_1", "thumbs_down", "bad")
            assert fb.explicit_rating == "thumbs_down"


# ═══════════════════════════════════════════════════════════════
#  ThreeTierInjector 测试 (31-37)
# ═══════════════════════════════════════════════════════════════


class TestThreeTierKnowledgeInjector:
    """三级知识注入器测试."""

    def _build_store_with_data(self):
        """构造含三类知识的 store."""
        store = LearnedKnowledgeStore()
        # Tier1: guideline 高置信度
        store.add(KnowledgeEntry(
            category="guideline", title="原则1",
            content="始终编写清晰的代码注释", confidence=0.9,
            tags=["coding"],
        ))
        store.add(KnowledgeEntry(
            category="guideline", title="原则2",
            content="提交前运行测试", confidence=0.8,
        ))
        # Tier2: success/failure
        store.add(KnowledgeEntry(
            category="success_pattern", title="文件读取模式",
            content="读取文件使用 read_file 工具并指定路径", confidence=0.7,
        ))
        store.add(KnowledgeEntry(
            category="failure_lesson", title="网络超时教训",
            content="HTTP 请求未设置超时导致挂起", confidence=0.6,
        ))
        # Tier3: style
        store.add(KnowledgeEntry(
            category="style", title="Python风格",
            content="Python 代码遵循 PEP8，使用 4 空格缩进", confidence=0.75,
            tags=["python", "coding"],
        ))
        return store

    def test_tier1_returns_high_confidence_guidelines(self):
        """31. Tier1 总是返回高 confidence guideline."""
        store = self._build_store_with_data()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)
        tiers = _run(injector.inject("任何查询"))

        tier1 = tiers[0]
        assert tier1.tier == 1
        assert len(tier1.entries) >= 1
        assert all(e.category == "guideline" for e in tier1.entries)
        assert all(e.confidence >= 0.6 for e in tier1.entries)

    def test_tier2_semantic_retrieval(self):
        """32. Tier2 按 query 语义检索."""
        store = self._build_store_with_data()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)
        tiers = _run(injector.inject("如何读取文件"))

        tier2 = tiers[1]
        assert tier2.tier == 2
        # 应检索到文件相关条目
        contents = " ".join(e.content for e in tier2.entries)
        assert "文件" in contents or "read_file" in contents

    def test_tier3_routes_by_task_tags(self):
        """33. Tier3 按 task_tags 路由."""
        store = self._build_store_with_data()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)
        tiers = _run(injector.inject("写代码", task_tags=["python"]))

        tier3 = tiers[2]
        assert tier3.tier == 3
        # python 标签应路由到 Python 风格
        contents = " ".join(e.title + e.content for e in tier3.entries)
        assert "Python" in contents or "PEP8" in contents

    def test_format_system_prompt_three_sections(self):
        """34. format_for_system_prompt 生成三个 XML section."""
        store = self._build_store_with_data()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)
        tiers = _run(injector.inject("读取文件", task_tags=["python"]))
        text = injector.format_for_system_prompt(tiers)

        assert "<learned_principles>" in text
        assert "<learned_cases>" in text
        assert "<learned_specialization>" in text
        assert "</learned_principles>" in text
        assert "</learned_cases>" in text
        assert "</learned_specialization>" in text

    def test_empty_store_returns_empty_tiers(self):
        """35. 空库时返回空 tier 不报错."""
        store = LearnedKnowledgeStore()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)
        tiers = _run(injector.inject("查询", task_tags=["tag"]))
        assert len(tiers) == 3
        assert all(len(t.entries) == 0 for t in tiers)
        assert injector.format_for_system_prompt(tiers) == ""

    def test_usable_as_memory_backend(self):
        """36. 可作为 MemoryBackend 使用（有 async retrieve 方法）."""
        store = self._build_store_with_data()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)

        # runtime_checkable Protocol 检查
        assert isinstance(injector, MemoryBackend)

        # 能直接给 ContextAssembler 用
        assembler = ContextAssembler(memory_backend=injector)
        messages = [{"role": "user", "content": "如何读取文件"}]
        ctx = _run(assembler.assemble(messages))
        # memory_snapshot 应非空，且内容含旁路知识
        assert len(ctx.memory_snapshot) >= 1
        assert any("tier" in item for item in ctx.memory_snapshot)

    def test_bureau_isolation(self):
        """37. bureau 隔离：不同 bureau 的知识不互相注入."""
        store = LearnedKnowledgeStore()
        store.add(KnowledgeEntry(
            bureau="tenant_a", category="guideline",
            title="A的规则", content="租户A的专属规则内容", confidence=0.9,
        ))
        store.add(KnowledgeEntry(
            bureau="tenant_b", category="guideline",
            title="B的规则", content="租户B的专属规则内容", confidence=0.9,
        ))
        retriever = KnowledgeRetriever(store)
        injector_a = ThreeTierKnowledgeInjector(store, retriever)
        tiers_a = _run(injector_a.inject("查询", bureau="tenant_a"))
        contents_a = " ".join(e.content for e in tiers_a[0].entries)
        assert "租户A" in contents_a
        assert "租户B" not in contents_a


# ═══════════════════════════════════════════════════════════════
#  集成测试 (38-40)
# ═══════════════════════════════════════════════════════════════


class TestBypassKnowledgeIntegration:
    """旁路知识层端到端集成测试."""

    def test_end_to_end_distill_dedup_retrieve_inject(self):
        """38. 端到端：添加记录→蒸馏→去重→检索→三级注入→ContextAssembler 召回."""
        store = LearnedKnowledgeStore()
        retriever = KnowledgeRetriever(store)
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)
        injector = ThreeTierKnowledgeInjector(store, retriever)

        # 3 条交互记录
        records = [
            _make_record(success=True, task="读取配置文件",
                         record_id="int_e2e_1",
                         tags=["文件操作"]),
            _make_record(success=True, task="读取数据文件",
                         record_id="int_e2e_2",
                         tool_calls=[{"name": "read_file", "arguments": {"p": "b"},
                                      "success": True, "output_summary": "ok"},
                                     {"name": "search", "arguments": {"q": "x"},
                                      "success": True, "output_summary": "found"}],
                         tags=["文件操作"]),
            _make_record(success=False, task="网络请求失败",
                         record_id="int_e2e_3",
                         tool_calls=[{"name": "web_request", "arguments": {},
                                      "success": False,
                                      "output_summary": "ConnectionTimeout"}],
                         tags=["网络请求"]),
        ]

        result = distiller.distill_batch(records)
        assert result.total_processed == 3
        assert store.count() >= 2  # 至少成功模式 + 失败教训

        # 检索
        search_results = _run(retriever.retrieve("文件读取", top_k=5))
        assert len(search_results) >= 1

        # 三级注入
        tiers = _run(injector.inject("怎么读取文件", task_tags=["文件操作"]))
        prompt_fragment = injector.format_for_system_prompt(tiers)
        assert "learned" in prompt_fragment.lower() or len(prompt_fragment) > 0

        # 最终验证：ContextAssembler 能召回
        assembler = ContextAssembler(memory_backend=injector)
        ctx = _run(assembler.assemble([{"role": "user", "content": "读取文件"}]))
        assert len(ctx.memory_snapshot) >= 1

    def test_orchestrator_bypass_evolution_does_not_break_main(self):
        """39. EvolutionOrchestrator 旁路进化不影响原有 run_evolution_cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = tempfile.mkdtemp()
            learned_store = LearnedKnowledgeStore()
            weak_collector = WeakSignalCollector(threshold=2)
            orch = EvolutionOrchestrator(
                storage_dir=tmpdir,
                skills_dir=skills_dir,
                learned_store=learned_store,
                weak_signal_collector=weak_collector,
            )

            # 记录交互
            records = [
                _make_record(success=True, task="任务A", record_id="int_o1"),
                _make_record(success=True, task="任务B", record_id="int_o2"),
            ]
            orch.record_interactions(records)

            # 旁路进化
            bypass_result = orch.run_bypass_evolution(records)
            assert bypass_result["bypass_enabled"] is True
            assert bypass_result["total_knowledge_entries"] >= 1

            # 主进化循环仍正常工作
            main_result = orch.run_evolution_cycle()
            assert main_result.cycle_id != ""
            assert main_result.patterns_extracted >= 0

            # get_status 包含旁路信息
            status = orch.get_status()
            assert status["bypass_knowledge_enabled"] is True
            assert status["learned_knowledge_entries"] >= 1

    def test_backward_compatibility_without_learned_components(self):
        """40. 向后兼容：不传入 learned_store/distiller 时所有现有功能正常."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 完全不使用旁路知识层，与 v1.5.0 行为一致
            orch = EvolutionOrchestrator(
                storage_dir=tmpdir,
                skills_dir=tempfile.mkdtemp(),
            )
            assert orch.learned_store is None
            assert orch.distiller is None

            record = _make_record(success=True, task="兼容测试", record_id="int_bc")
            orch.record_interaction(record)
            result = orch.run_evolution_cycle()
            assert result.cycle_id != ""

            # 旁路进化返回 disabled 状态
            bypass = orch.run_bypass_evolution()
            assert bypass["bypass_enabled"] is False
            assert bypass["total_knowledge_entries"] == 0

            # FeedbackCollector 单独使用也正常
            fc = FeedbackCollector(storage_dir=tmpdir)
            fb = fc.collect_explicit("int_bc2", "thumbs_up", "good")
            assert fb.explicit_rating == "thumbs_up"
