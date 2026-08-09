"""
Tests for Suyi SQLite Persistence Backend.

Covers:
    - SQLiteBackend CRUD: get, set, delete, exists, list_keys
    - JSONBackend CRUD: same interface compatibility
    - FTS5 full-text search
    - Thread safety (concurrent reads/writes)
    - Batch writes
    - Transactions (commit and rollback)
    - JSON → SQLite migration (incremental and full)
    - Interface compatibility between JSONBackend and SQLiteBackend
    - Edge cases: large values, unicode, empty keys, overwrite
    - Factory: create_backend, create_backend_from_config
    - Config: PersistenceConfig integration
"""

import json
import os
import tempfile
import threading
import time

import pytest

from suyi.persistence import (
    JSONBackend,
    SQLiteBackend,
    create_backend,
    create_backend_from_config,
    register_backend,
    list_backends,
    migrate_json_to_sqlite,
    migrate_json_dir_to_sqlite,
)
from suyi.config import (
    SuyiConfig,
    PersistenceConfig,
    load_config_from_dict,
    get_default_config,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sqlite_backend(tmp_path):
    """临时SQLite后端（每个测试独立数据库文件）。"""
    db_path = str(tmp_path / "test.db")
    backend = SQLiteBackend(db_path=db_path)
    yield backend
    backend.close()


@pytest.fixture
def json_backend(tmp_path):
    """临时JSON后端。"""
    backend = JSONBackend(storage_dir=str(tmp_path), namespace="test")
    yield backend
    backend.close()


@pytest.fixture
def both_backends(tmp_path):
    """同时提供JSON和SQLite后端，用于兼容性测试。"""
    json_b = JSONBackend(storage_dir=str(tmp_path), namespace="compat")
    sqlite_b = SQLiteBackend(db_path=str(tmp_path / "compat.db"))
    yield json_b, sqlite_b
    json_b.close()
    sqlite_b.close()


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — CRUD Tests
# ═══════════════════════════════════════════════════════════════


class TestSQLiteCRUD:
    """测试SQLiteBackend的基本CRUD操作。"""

    def test_set_and_get(self, sqlite_backend):
        """set写入后get应返回相同的值。"""
        sqlite_backend.set("key1", {"name": "Alice", "age": 30})
        result = sqlite_backend.get("key1")
        assert result == {"name": "Alice", "age": 30}

    def test_get_nonexistent(self, sqlite_backend):
        """获取不存在的键应返回默认值。"""
        assert sqlite_backend.get("missing") is None
        assert sqlite_backend.get("missing", "default") == "default"

    def test_get_default_dict(self, sqlite_backend):
        """默认值可以是任意类型。"""
        assert sqlite_backend.get("missing", {"a": 1}) == {"a": 1}
        assert sqlite_backend.get("missing", [1, 2, 3]) == [1, 2, 3]

    def test_set_overwrite(self, sqlite_backend):
        """覆盖已存在的键应更新值。"""
        sqlite_backend.set("key1", {"v": 1})
        sqlite_backend.set("key1", {"v": 2})
        assert sqlite_backend.get("key1") == {"v": 2}

    def test_set_preserves_created_at(self, sqlite_backend):
        """覆盖时created_at应保持不变。"""
        sqlite_backend.set("key1", {"v": 1})
        conn = sqlite_backend._get_conn()
        row1 = conn.execute(
            f"SELECT created_at, updated_at FROM {sqlite_backend.table_name} WHERE key = ?",
            ("key1",),
        ).fetchone()
        time.sleep(0.01)
        sqlite_backend.set("key1", {"v": 2})
        row2 = conn.execute(
            f"SELECT created_at, updated_at FROM {sqlite_backend.table_name} WHERE key = ?",
            ("key1",),
        ).fetchone()
        assert row1["created_at"] == row2["created_at"]
        assert row2["updated_at"] >= row1["updated_at"]

    def test_delete_existing(self, sqlite_backend):
        """删除存在的键应返回True。"""
        sqlite_backend.set("key1", {"v": 1})
        assert sqlite_backend.delete("key1") is True
        assert sqlite_backend.get("key1") is None

    def test_delete_nonexistent(self, sqlite_backend):
        """删除不存在的键应返回False。"""
        assert sqlite_backend.delete("ghost") is False

    def test_exists_true(self, sqlite_backend):
        """exists对存在的键返回True。"""
        sqlite_backend.set("key1", {"v": 1})
        assert sqlite_backend.exists("key1") is True

    def test_exists_false(self, sqlite_backend):
        """exists对不存在的键返回False。"""
        assert sqlite_backend.exists("nope") is False

    def test_list_keys_empty(self, sqlite_backend):
        """空数据库list_keys返回空列表。"""
        assert sqlite_backend.list_keys() == []

    def test_list_keys_multiple(self, sqlite_backend):
        """list_keys返回所有键，排序。"""
        sqlite_backend.set("b_key", {"v": 2})
        sqlite_backend.set("a_key", {"v": 1})
        sqlite_backend.set("c_key", {"v": 3})
        keys = sqlite_backend.list_keys()
        assert keys == ["a_key", "b_key", "c_key"]

    def test_list_keys_with_pattern(self, sqlite_backend):
        """list_keys支持子串模式过滤。"""
        sqlite_backend.set("user_1", {"v": 1})
        sqlite_backend.set("user_2", {"v": 2})
        sqlite_backend.set("admin_1", {"v": 3})
        keys = sqlite_backend.list_keys(pattern="user")
        assert keys == ["user_1", "user_2"]

    def test_count(self, sqlite_backend):
        """count返回键总数。"""
        assert sqlite_backend.count() == 0
        sqlite_backend.set("a", {"v": 1})
        sqlite_backend.set("b", {"v": 2})
        assert sqlite_backend.count() == 2

    def test_clear(self, sqlite_backend):
        """clear清空所有数据并返回清除数量。"""
        sqlite_backend.set("a", {"v": 1})
        sqlite_backend.set("b", {"v": 2})
        cleared = sqlite_backend.clear()
        assert cleared == 2
        assert sqlite_backend.count() == 0

    def test_clear_empty(self, sqlite_backend):
        """清空空数据库返回0。"""
        assert sqlite_backend.clear() == 0


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — Data Type Tests
# ═══════════════════════════════════════════════════════════════


class TestSQLiteDataTypes:
    """测试SQLiteBackend对不同数据类型的支持。"""

    def test_unicode_content(self, sqlite_backend):
        """支持中文/Unicode内容。"""
        sqlite_backend.set("unicode_key", {"content": "你好世界，SQLite测试"})
        result = sqlite_backend.get("unicode_key")
        assert result["content"] == "你好世界，SQLite测试"

    def test_nested_dict(self, sqlite_backend):
        """支持深层嵌套字典。"""
        value = {
            "level1": {
                "level2": {
                    "level3": {"data": [1, 2, 3]},
                },
            },
        }
        sqlite_backend.set("nested", value)
        assert sqlite_backend.get("nested") == value

    def test_list_value(self, sqlite_backend):
        """支持列表值。"""
        sqlite_backend.set("list_key", [1, "two", {"three": 3}])
        assert sqlite_backend.get("list_key") == [1, "two", {"three": 3}]

    def test_string_value(self, sqlite_backend):
        """支持纯字符串值。"""
        sqlite_backend.set("str_key", "plain string")
        assert sqlite_backend.get("str_key") == "plain string"

    def test_number_value(self, sqlite_backend):
        """支持数字值。"""
        sqlite_backend.set("num_key", 42)
        assert sqlite_backend.get("num_key") == 42

    def test_boolean_value(self, sqlite_backend):
        """支持布尔值。"""
        sqlite_backend.set("bool_key", True)
        assert sqlite_backend.get("bool_key") is True

    def test_none_in_dict(self, sqlite_backend):
        """支持字典中包含None。"""
        sqlite_backend.set("none_key", {"field": None, "other": 1})
        result = sqlite_backend.get("none_key")
        assert result["field"] is None
        assert result["other"] == 1

    def test_large_value(self, sqlite_backend):
        """支持大值（10KB+）。"""
        large_text = "x" * 10000
        sqlite_backend.set("large", {"content": large_text})
        result = sqlite_backend.get("large")
        assert len(result["content"]) == 10000

    def test_empty_dict(self, sqlite_backend):
        """支持空字典。"""
        sqlite_backend.set("empty", {})
        assert sqlite_backend.get("empty") == {}

    def test_special_chars_in_key(self, sqlite_backend):
        """键名包含特殊字符。"""
        sqlite_backend.set("key-with-dashes", {"v": 1})
        sqlite_backend.set("key.with.dots", {"v": 2})
        sqlite_backend.set("key_with_underscores", {"v": 3})
        assert sqlite_backend.get("key-with-dashes") == {"v": 1}
        assert sqlite_backend.get("key.with.dots") == {"v": 2}
        assert sqlite_backend.get("key_with_underscores") == {"v": 3}


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — FTS5 Search Tests
# ═══════════════════════════════════════════════════════════════


class TestSQLiteSearch:
    """测试SQLiteBackend的FTS5全文搜索。"""

    def test_search_basic(self, sqlite_backend):
        """基本全文搜索。"""
        sqlite_backend.set("doc1", {"content": "The quick brown fox"})
        sqlite_backend.set("doc2", {"content": "The lazy dog"})
        results = sqlite_backend.search("fox")
        assert len(results) >= 1
        assert results[0]["key"] == "doc1"

    def test_search_multiple_results(self, sqlite_backend):
        """搜索返回多个结果。"""
        sqlite_backend.set("doc1", {"content": "machine learning basics"})
        sqlite_backend.set("doc2", {"content": "deep learning networks"})
        sqlite_backend.set("doc3", {"content": "cooking recipes"})
        results = sqlite_backend.search("learning")
        keys = {r["key"] for r in results}
        assert "doc1" in keys
        assert "doc2" in keys
        assert "doc3" not in keys

    def test_search_top_k(self, sqlite_backend):
        """top_k限制返回数量。"""
        for i in range(10):
            sqlite_backend.set(f"doc{i}", {"content": f"document number {i}"})
        results = sqlite_backend.search("document", top_k=3)
        assert len(results) <= 3

    def test_search_no_results(self, sqlite_backend):
        """搜索无匹配时返回空列表。"""
        sqlite_backend.set("doc1", {"content": "hello world"})
        results = sqlite_backend.search("nonexistent_term_xyz")
        assert results == []

    def test_search_empty_database(self, sqlite_backend):
        """空数据库搜索返回空列表。"""
        assert sqlite_backend.search("anything") == []

    def test_search_chinese(self, sqlite_backend):
        """支持中文全文搜索。"""
        sqlite_backend.set("doc1", {"content": "机器学习是人工智能的一个分支"})
        sqlite_backend.set("doc2", {"content": "深度学习使用神经网络"})
        results = sqlite_backend.search("学习")
        assert len(results) >= 1

    def test_search_result_structure(self, sqlite_backend):
        """搜索结果包含key、value、score字段。"""
        sqlite_backend.set("doc1", {"content": "test content"})
        results = sqlite_backend.search("test")
        assert len(results) >= 1
        r = results[0]
        assert "key" in r
        assert "value" in r
        assert "score" in r
        assert r["key"] == "doc1"
        assert r["value"] == {"content": "test content"}

    def test_search_after_update(self, sqlite_backend):
        """更新值后FTS索引应同步更新。"""
        sqlite_backend.set("doc1", {"content": "old content"})
        sqlite_backend.set("doc1", {"content": "new content"})
        # 搜索旧内容不应匹配
        results_old = sqlite_backend.search("old")
        keys_old = {r["key"] for r in results_old}
        assert "doc1" not in keys_old
        # 搜索新内容应匹配
        results_new = sqlite_backend.search("new")
        keys_new = {r["key"] for r in results_new}
        assert "doc1" in keys_new

    def test_search_after_delete(self, sqlite_backend):
        """删除后FTS索引应同步清除。"""
        sqlite_backend.set("doc1", {"content": "searchable text"})
        sqlite_backend.delete("doc1")
        results = sqlite_backend.search("searchable")
        assert results == []

    def test_search_multi_word_query(self, sqlite_backend):
        """多词查询（OR语义）。"""
        sqlite_backend.set("doc1", {"content": "python programming"})
        sqlite_backend.set("doc2", {"content": "java programming"})
        sqlite_backend.set("doc3", {"content": "cooking"})
        results = sqlite_backend.search("python java")
        keys = {r["key"] for r in results}
        assert "doc1" in keys
        assert "doc2" in keys

    def test_search_extracts_content_field(self, sqlite_backend):
        """FTS索引优先提取content字段。"""
        sqlite_backend.set("doc1", {
            "content": "searchable text here",
            "metadata": "non_searchable_field",
        })
        results = sqlite_backend.search("searchable")
        assert len(results) >= 1
        assert results[0]["key"] == "doc1"


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — Batch & Transaction Tests
# ═══════════════════════════════════════════════════════════════


class TestSQLiteBatch:
    """测试批量写入。"""

    def test_batch_set_basic(self, sqlite_backend):
        """批量写入多个键值对。"""
        items = {
            "key1": {"v": 1},
            "key2": {"v": 2},
            "key3": {"v": 3},
        }
        count = sqlite_backend.batch_set(items)
        assert count == 3
        assert sqlite_backend.get("key1") == {"v": 1}
        assert sqlite_backend.get("key2") == {"v": 2}
        assert sqlite_backend.get("key3") == {"v": 3}

    def test_batch_set_empty(self, sqlite_backend):
        """空批量写入返回0。"""
        assert sqlite_backend.batch_set({}) == 0

    def test_batch_set_overwrite(self, sqlite_backend):
        """批量写入覆盖已有键。"""
        sqlite_backend.set("key1", {"old": True})
        sqlite_backend.batch_set({"key1": {"new": True}, "key2": {"v": 2}})
        assert sqlite_backend.get("key1") == {"new": True}
        assert sqlite_backend.get("key2") == {"v": 2}

    def test_batch_set_large(self, sqlite_backend):
        """大批量写入（100条）。"""
        items = {f"batch_key_{i}": {"index": i} for i in range(100)}
        count = sqlite_backend.batch_set(items)
        assert count == 100
        assert sqlite_backend.count() == 100
        assert sqlite_backend.get("batch_key_50") == {"index": 50}

    def test_batch_set_fts_indexed(self, sqlite_backend):
        """批量写入的数据也被FTS索引。"""
        items = {
            "doc1": {"content": "batch search text one"},
            "doc2": {"content": "batch search text two"},
        }
        sqlite_backend.batch_set(items)
        results = sqlite_backend.search("batch")
        keys = {r["key"] for r in results}
        assert "doc1" in keys
        assert "doc2" in keys


class TestSQLiteTransaction:
    """测试事务支持。"""

    def test_transaction_commit(self, sqlite_backend):
        """事务正常提交。"""
        with sqlite_backend.transaction() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {sqlite_backend.table_name} "
                f"(key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("tx_key1", '{"v": 1}', "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
            )
            conn.execute(
                f"INSERT OR REPLACE INTO {sqlite_backend.table_name} "
                f"(key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("tx_key2", '{"v": 2}', "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
            )
        assert sqlite_backend.exists("tx_key1")
        assert sqlite_backend.exists("tx_key2")

    def test_transaction_rollback(self, sqlite_backend):
        """事务异常时回滚。"""
        sqlite_backend.set("existing", {"v": 1})
        with pytest.raises(ValueError, match="rollback test"):
            with sqlite_backend.transaction() as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO {sqlite_backend.table_name} "
                    f"(key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("tx_temp", '{"v": 99}', "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
                )
                raise ValueError("rollback test")
        # 回滚后tx_temp不应存在
        assert not sqlite_backend.exists("tx_temp")
        # 已有数据不受影响
        assert sqlite_backend.exists("existing")

    def test_transaction_nested_context(self, sqlite_backend):
        """事务上下文管理器可正确嵌套（使用RLock）。"""
        with sqlite_backend.transaction():
            sqlite_backend.set("nested_key", {"v": 1})
            with sqlite_backend.transaction():
                sqlite_backend.set("nested_key2", {"v": 2})
        assert sqlite_backend.exists("nested_key")
        assert sqlite_backend.exists("nested_key2")


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — Thread Safety Tests
# ═══════════════════════════════════════════════════════════════


class TestSQLiteThreadSafety:
    """测试线程安全。"""

    def test_concurrent_reads(self, sqlite_backend):
        """多线程并发读取。"""
        sqlite_backend.set("key1", {"content": "shared data"})
        results = []
        errors = []

        def reader():
            try:
                for _ in range(50):
                    val = sqlite_backend.get("key1")
                    results.append(val)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 250
        assert all(r == {"content": "shared data"} for r in results)

    def test_concurrent_writes(self, sqlite_backend):
        """多线程并发写入不同键。"""
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    sqlite_backend.set(f"t{thread_id}_k{i}", {"v": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert sqlite_backend.count() == 80

    def test_concurrent_mixed(self, sqlite_backend):
        """多线程混合读写。"""
        sqlite_backend.set("shared", {"content": "base"})
        errors = []

        def reader():
            try:
                for _ in range(30):
                    sqlite_backend.get("shared")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    sqlite_backend.set(f"w_key_{i}", {"v": i})
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reader) for _ in range(3)]
            + [threading.Thread(target=writer) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert sqlite_backend.count() >= 1  # at least "shared"

    def test_concurrent_batch(self, sqlite_backend):
        """多线程并发批量写入。"""
        errors = []

        def batch_writer(tid):
            try:
                items = {f"batch_{tid}_{i}": {"v": i} for i in range(10)}
                sqlite_backend.batch_set(items)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=batch_writer, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert sqlite_backend.count() == 40


# ═══════════════════════════════════════════════════════════════
#  JSONBackend — CRUD Tests
# ═══════════════════════════════════════════════════════════════


class TestJSONBackendCRUD:
    """测试JSONBackend的基本CRUD操作。"""

    def test_set_and_get(self, json_backend):
        json_backend.set("key1", {"name": "Bob"})
        assert json_backend.get("key1") == {"name": "Bob"}

    def test_get_nonexistent(self, json_backend):
        assert json_backend.get("missing") is None
        assert json_backend.get("missing", "default") == "default"

    def test_delete(self, json_backend):
        json_backend.set("key1", {"v": 1})
        assert json_backend.delete("key1") is True
        assert json_backend.get("key1") is None

    def test_delete_nonexistent(self, json_backend):
        assert json_backend.delete("ghost") is False

    def test_exists(self, json_backend):
        json_backend.set("key1", {"v": 1})
        assert json_backend.exists("key1") is True
        assert json_backend.exists("nope") is False

    def test_list_keys(self, json_backend):
        json_backend.set("b", {"v": 2})
        json_backend.set("a", {"v": 1})
        assert json_backend.list_keys() == ["a", "b"]

    def test_list_keys_pattern(self, json_backend):
        json_backend.set("user_1", {"v": 1})
        json_backend.set("user_2", {"v": 2})
        json_backend.set("admin", {"v": 3})
        assert json_backend.list_keys(pattern="user") == ["user_1", "user_2"]

    def test_search(self, json_backend):
        json_backend.set("doc1", {"content": "hello world"})
        json_backend.set("doc2", {"content": "foo bar"})
        results = json_backend.search("hello")
        assert len(results) >= 1
        assert results[0]["key"] == "doc1"

    def test_count(self, json_backend):
        json_backend.set("a", {"v": 1})
        json_backend.set("b", {"v": 2})
        assert json_backend.count() == 2

    def test_clear(self, json_backend):
        json_backend.set("a", {"v": 1})
        json_backend.set("b", {"v": 2})
        cleared = json_backend.clear()
        assert cleared == 2
        assert json_backend.count() == 0

    def test_batch_set(self, json_backend):
        items = {"k1": {"v": 1}, "k2": {"v": 2}}
        assert json_backend.batch_set(items) == 2
        assert json_backend.get("k1") == {"v": 1}


# ═══════════════════════════════════════════════════════════════
#  Interface Compatibility Tests
# ═══════════════════════════════════════════════════════════════


class TestInterfaceCompatibility:
    """测试JSONBackend和SQLiteBackend接口兼容性。"""

    def test_same_methods(self, both_backends):
        """两个后端具有相同的方法集合。"""
        json_b, sqlite_b = both_backends
        json_methods = {
            m for m in dir(json_b)
            if not m.startswith("_") and callable(getattr(json_b, m))
        }
        sqlite_methods = {
            m for m in dir(sqlite_b)
            if not m.startswith("_") and callable(getattr(sqlite_b, m))
        }
        # SQLiteBackend应包含JSONBackend的所有核心方法
        core_methods = {"get", "set", "delete", "exists", "list_keys", "search", "batch_set", "transaction", "count", "clear", "close"}
        assert core_methods.issubset(json_methods)
        assert core_methods.issubset(sqlite_methods)

    @pytest.mark.parametrize("key,value", [
        ("simple", {"v": 1}),
        ("nested", {"a": {"b": {"c": 3}}}),
        ("list", [1, 2, 3]),
        ("string", "hello"),
        ("number", 42),
        ("unicode", {"content": "你好"}),
    ])
    def test_get_set_compatibility(self, both_backends, key, value):
        """相同键值在两个后端中行为一致。"""
        json_b, sqlite_b = both_backends
        json_b.set(key, value)
        sqlite_b.set(key, value)
        assert json_b.get(key) == sqlite_b.get(key)

    def test_delete_compatibility(self, both_backends):
        """delete行为一致。"""
        json_b, sqlite_b = both_backends
        json_b.set("key1", {"v": 1})
        sqlite_b.set("key1", {"v": 1})
        assert json_b.delete("key1") == sqlite_b.delete("key1")
        assert json_b.delete("key1") == sqlite_b.delete("key1")  # 第二次都返回False

    def test_exists_compatibility(self, both_backends):
        """exists行为一致。"""
        json_b, sqlite_b = both_backends
        json_b.set("key1", {"v": 1})
        sqlite_b.set("key1", {"v": 1})
        assert json_b.exists("key1") == sqlite_b.exists("key1")
        assert json_b.exists("nope") == sqlite_b.exists("nope")

    def test_list_keys_compatibility(self, both_backends):
        """list_keys行为一致。"""
        json_b, sqlite_b = both_backends
        for key in ["a", "b", "c"]:
            json_b.set(key, {"v": 1})
            sqlite_b.set(key, {"v": 1})
        assert json_b.list_keys() == sqlite_b.list_keys()

    def test_count_compatibility(self, both_backends):
        """count行为一致。"""
        json_b, sqlite_b = both_backends
        for i in range(5):
            json_b.set(f"k{i}", {"v": i})
            sqlite_b.set(f"k{i}", {"v": i})
        assert json_b.count() == sqlite_b.count()


# ═══════════════════════════════════════════════════════════════
#  Migration Tests
# ═══════════════════════════════════════════════════════════════


class TestMigration:
    """测试JSON → SQLite迁移。"""

    def test_migrate_from_json_backend(self, tmp_path):
        """从JSONBackend迁移到SQLiteBackend。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="migrate")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "migrate.db"))

        # 写入JSON数据
        json_b.set("key1", {"content": "first document"})
        json_b.set("key2", {"content": "second document"})
        json_b.set("key3", {"content": "third document"})

        report = migrate_json_to_sqlite(json_b, sqlite_b, incremental=False)

        assert report["total"] == 3
        assert report["migrated"] == 3
        assert report["skipped"] == 0
        assert report["failed"] == 0
        assert len(report["errors"]) == 0
        assert sqlite_b.get("key1") == {"content": "first document"}
        assert sqlite_b.get("key2") == {"content": "second document"}
        assert sqlite_b.get("key3") == {"content": "third document"}

        json_b.close()
        sqlite_b.close()

    def test_migrate_incremental(self, tmp_path):
        """增量迁移只导入新数据。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="incr")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "incr.db"))

        # 先全量迁移
        json_b.set("key1", {"v": 1})
        json_b.set("key2", {"v": 2})
        report1 = migrate_json_to_sqlite(json_b, sqlite_b, incremental=True)
        assert report1["migrated"] == 2
        assert report1["skipped"] == 0

        # 添加新数据后增量迁移
        json_b.set("key3", {"v": 3})
        report2 = migrate_json_to_sqlite(json_b, sqlite_b, incremental=True)
        assert report2["migrated"] == 1
        assert report2["skipped"] == 2
        assert sqlite_b.get("key3") == {"v": 3}

        json_b.close()
        sqlite_b.close()

    def test_migrate_full_overwrite(self, tmp_path):
        """全量迁移覆盖已有数据。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="overwrite")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "overwrite.db"))

        json_b.set("key1", {"v": "new"})
        sqlite_b.set("key1", {"v": "old"})

        report = migrate_json_to_sqlite(json_b, sqlite_b, incremental=False)
        assert report["migrated"] == 1
        assert sqlite_b.get("key1") == {"v": "new"}

        json_b.close()
        sqlite_b.close()

    def test_migrate_from_directory(self, tmp_path):
        """从JSON文件目录迁移。"""
        json_dir = str(tmp_path / "json_data")
        os.makedirs(json_dir)

        # 写入JSON文件
        for i in range(3):
            path = os.path.join(json_dir, f"file_{i}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"content": f"document {i}"}, f)

        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "dir_migrate.db"))
        report = migrate_json_dir_to_sqlite(json_dir, sqlite_b, incremental=False)

        assert report["total"] == 3
        assert report["migrated"] == 3
        assert sqlite_b.get("file_0") == {"content": "document 0"}
        assert sqlite_b.get("file_1") == {"content": "document 1"}
        assert sqlite_b.get("file_2") == {"content": "document 2"}

        sqlite_b.close()

    def test_migrate_empty_source(self, tmp_path):
        """空源迁移。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="empty")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "empty.db"))

        report = migrate_json_to_sqlite(json_b, sqlite_b, incremental=False)
        assert report["total"] == 0
        assert report["migrated"] == 0

        json_b.close()
        sqlite_b.close()

    def test_migrate_log(self, tmp_path):
        """迁移日志包含事件记录。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="log")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "log.db"))

        json_b.set("key1", {"v": 1})
        report = migrate_json_to_sqlite(json_b, sqlite_b, log=True)

        assert len(report["log"]) > 0
        events = [e["event"] for e in report["log"]]
        assert "migration_start" in events
        assert "migration_complete" in events

        json_b.close()
        sqlite_b.close()

    def test_migrate_report_structure(self, tmp_path):
        """迁移报告包含所有必要字段。"""
        json_b = JSONBackend(storage_dir=str(tmp_path), namespace="report")
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "report.db"))

        json_b.set("k1", {"v": 1})
        report = migrate_json_to_sqlite(json_b, sqlite_b)

        required_fields = {"total", "migrated", "skipped", "failed", "errors", "duration_s", "log"}
        assert required_fields.issubset(report.keys())
        assert isinstance(report["duration_s"], float)
        assert report["duration_s"] >= 0

        json_b.close()
        sqlite_b.close()

    def test_migrate_directory_not_found(self, tmp_path):
        """目录不存在时抛出FileNotFoundError。"""
        sqlite_b = SQLiteBackend(db_path=str(tmp_path / "nf.db"))
        with pytest.raises(FileNotFoundError):
            migrate_json_dir_to_sqlite("/nonexistent/path/xyz", sqlite_b)
        sqlite_b.close()


# ═══════════════════════════════════════════════════════════════
#  Factory Tests
# ═══════════════════════════════════════════════════════════════


class TestFactory:
    """测试后端工厂。"""

    def test_create_json_backend(self, tmp_path):
        backend = create_backend(backend_type="json", storage_dir=str(tmp_path))
        assert isinstance(backend, JSONBackend)
        backend.close()

    def test_create_sqlite_backend(self, tmp_path):
        backend = create_backend(backend_type="sqlite", db_path=str(tmp_path / "f.db"))
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_create_with_alias(self, tmp_path):
        """支持别名创建。"""
        backend = create_backend(backend_type="sqlite3", db_path=str(tmp_path / "alias.db"))
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_create_invalid_backend(self):
        with pytest.raises(ValueError, match="不支持的后端类型"):
            create_backend(backend_type="redis")

    def test_create_from_config_json(self, tmp_path):
        config = SuyiConfig(
            persistence=PersistenceConfig(
                backend="json",
                storage_dir=str(tmp_path),
            )
        )
        backend = create_backend_from_config(config)
        assert isinstance(backend, JSONBackend)
        backend.close()

    def test_create_from_config_sqlite(self, tmp_path):
        config = SuyiConfig(
            persistence=PersistenceConfig(
                backend="sqlite",
                db_path=str(tmp_path / "cfg.db"),
            )
        )
        backend = create_backend_from_config(config)
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_create_from_config_no_persistence(self):
        """无persistence属性时返回默认JSON后端。"""
        config = get_default_config()
        backend = create_backend_from_config(config)
        assert isinstance(backend, JSONBackend)
        backend.close()

    def test_register_custom_backend(self, tmp_path):
        """注册自定义后端类型。"""

        class CustomBackend(JSONBackend):
            pass

        register_backend("custom", CustomBackend)
        backend = create_backend(backend_type="custom", storage_dir=str(tmp_path))
        assert isinstance(backend, CustomBackend)
        backend.close()

    def test_list_backends(self):
        """list_backends返回所有支持的类型。"""
        backends = list_backends()
        assert "json" in backends
        assert "sqlite" in backends


# ═══════════════════════════════════════════════════════════════
#  Config Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestPersistenceConfig:
    """测试PersistenceConfig配置。"""

    def test_defaults(self):
        config = PersistenceConfig()
        assert config.backend == "json"
        assert config.storage_dir == "./data"
        assert config.db_path == "./data/suyi.db"
        assert config.namespace == "default"

    def test_sqlite_config(self):
        config = PersistenceConfig(backend="sqlite", db_path="/tmp/test.db")
        assert config.backend == "sqlite"
        assert config.db_path == "/tmp/test.db"

    def test_in_suyi_config(self):
        config = SuyiConfig()
        assert isinstance(config.persistence, PersistenceConfig)
        assert config.persistence.backend == "json"

    def test_to_dict(self):
        config = SuyiConfig(
            persistence=PersistenceConfig(backend="sqlite", db_path="/tmp/x.db")
        )
        d = config.to_dict()
        assert "persistence" in d
        assert d["persistence"]["backend"] == "sqlite"
        assert d["persistence"]["db_path"] == "/tmp/x.db"

    def test_load_from_dict(self):
        config = load_config_from_dict({
            "persistence": {
                "backend": "sqlite",
                "db_path": "/tmp/from_dict.db",
                "namespace": "my_ns",
            }
        })
        assert config.persistence.backend == "sqlite"
        assert config.persistence.db_path == "/tmp/from_dict.db"
        assert config.persistence.namespace == "my_ns"

    def test_load_from_dict_unknown_keys(self):
        """未知键被忽略。"""
        config = load_config_from_dict({
            "persistence": {
                "backend": "json",
                "unknown_field": "value",
            }
        })
        assert config.persistence.backend == "json"

    def test_round_trip(self):
        """配置序列化/反序列化保持一致。"""
        original = SuyiConfig(
            persistence=PersistenceConfig(
                backend="sqlite",
                db_path="/tmp/rt.db",
                storage_dir="/tmp/rt_data",
                namespace="rt_ns",
            )
        )
        d = original.to_dict()
        restored = load_config_from_dict(d)
        assert restored.persistence.backend == "sqlite"
        assert restored.persistence.db_path == "/tmp/rt.db"
        assert restored.persistence.storage_dir == "/tmp/rt_data"
        assert restored.persistence.namespace == "rt_ns"

    def test_default_config_has_persistence(self):
        """默认配置包含persistence字段。"""
        config = get_default_config()
        assert hasattr(config, "persistence")
        assert config.persistence.backend == "json"


# ═══════════════════════════════════════════════════════════════
#  SQLiteBackend — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestSQLiteEdgeCases:
    """测试边缘情况。"""

    def test_custom_table_name(self, tmp_path):
        """自定义表名。"""
        backend = SQLiteBackend(
            db_path=str(tmp_path / "custom.db"),
            table_name="my_table",
        )
        backend.set("key1", {"v": 1})
        assert backend.get("key1") == {"v": 1}
        assert backend.table_name == "my_table"
        assert backend.fts_table == "my_table_fts"
        backend.close()

    def test_reopen_database(self, tmp_path):
        """重新打开数据库后数据仍在。"""
        db_path = str(tmp_path / "reopen.db")
        backend1 = SQLiteBackend(db_path=db_path)
        backend1.set("persistent_key", {"content": "survives restart"})
        backend1.close()

        backend2 = SQLiteBackend(db_path=db_path)
        assert backend2.get("persistent_key") == {"content": "survives restart"}
        backend2.close()

    def test_repr(self, sqlite_backend):
        """repr包含数据库路径和计数。"""
        sqlite_backend.set("k", {"v": 1})
        r = repr(sqlite_backend)
        assert "SQLiteBackend" in r
        assert "count=1" in r

    def test_database_file_created(self, tmp_path):
        """初始化后数据库文件存在。"""
        db_path = str(tmp_path / "exists.db")
        backend = SQLiteBackend(db_path=db_path)
        assert os.path.exists(db_path)
        backend.close()

    def test_concurrent_search_and_write(self, sqlite_backend):
        """并发搜索和写入不冲突。"""
        sqlite_backend.set("doc1", {"content": "searchable content"})
        errors = []

        def searcher():
            try:
                for _ in range(20):
                    sqlite_backend.search("searchable")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(20):
                    sqlite_backend.set(f"concurrent_{i}", {"content": f"item {i}"})
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=searcher)
        t2 = threading.Thread(target=writer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    def test_long_key_name(self, sqlite_backend):
        """超长键名。"""
        long_key = "k" * 500
        sqlite_backend.set(long_key, {"v": 1})
        assert sqlite_backend.get(long_key) == {"v": 1}
        assert sqlite_backend.exists(long_key)

    def test_empty_string_value(self, sqlite_backend):
        """空字符串值。"""
        sqlite_backend.set("empty_str", "")
        assert sqlite_backend.get("empty_str") == ""

    def test_json_serializable_only(self, sqlite_backend):
        """不可JSON序列化的值会抛出异常。"""
        with pytest.raises(TypeError):
            sqlite_backend.set("bad", object())

    def test_namespace_isolation(self, tmp_path):
        """不同namespace的JSON后端数据隔离。"""
        b1 = JSONBackend(storage_dir=str(tmp_path), namespace="ns1")
        b2 = JSONBackend(storage_dir=str(tmp_path), namespace="ns2")
        b1.set("key1", {"from": "ns1"})
        b2.set("key1", {"from": "ns2"})
        assert b1.get("key1") == {"from": "ns1"}
        assert b2.get("key1") == {"from": "ns2"}
        b1.close()
        b2.close()

    def test_close_idempotent(self, sqlite_backend):
        """close可多次调用。"""
        sqlite_backend.close()
        sqlite_backend.close()  # 不应抛出异常
