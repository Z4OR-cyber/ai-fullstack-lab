"""
SQLite持久化后端 — 替换JSON文件存储。

提供两种后端实现，共享同一接口：

    JSONBackend  — 基于JSON文件的键值存储（参考实现）。
    SQLiteBackend — 基于SQLite的键值存储，支持FTS5全文搜索。

接口方法（两者一致）::

    get(key, default=None)     -> 值或默认值
    set(key, value)            -> None
    delete(key)                -> bool
    exists(key)                -> bool
    list_keys(pattern=None)    -> list[str]
    search(query, top_k=10)    -> list[dict]
    batch_set(items)           -> int   (仅SQLiteBackend)
    transaction()              -> 上下文管理器 (仅SQLiteBackend)
    count()                    -> int
    clear()                    -> int
    close()                    -> None

SQLiteBackend 表结构::

    kv_store (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,        -- JSON序列化
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )

    kv_store_fts (              -- FTS5虚拟表
        content,                -- 被索引的文本
        key UNINDEXED            -- 对应主表键
    )

设计要点
--------
- 自动建表、自动迁移
- 线程安全：每线程独立连接 + WAL模式 + 写锁
- FTS5全文搜索（自动降级为LIKE）
- 批量写入与事务支持
- 仅使用Python标准库
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union


# ----------------------------------------------------------------------
#  工具函数
# ----------------------------------------------------------------------

def _iso_timestamp() -> str:
    """返回ISO-8601 UTC时间戳字符串。"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _extract_search_text(value: Any) -> str:
    """从值中提取用于全文索引的文本。

    优先提取 ``content`` 字段；若不存在则序列化整个值。
    """
    if isinstance(value, dict):
        content = value.get("content", "")
        if content:
            return str(content)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _safe_key(key: str) -> str:
    """将键名中的路径分隔符替换为下划线，确保文件系统安全。"""
    return key.replace("/", "_").replace("\\", "_")


# ----------------------------------------------------------------------
#  JSONBackend — JSON文件键值存储（参考实现）
# ----------------------------------------------------------------------

class JSONBackend:
    """JSON文件后端 — 基于JSON文件的键值存储。

    每个键存储为独立JSON文件::

        <storage_dir>/<namespace>/<key>.json

    作为 ``SQLiteBackend`` 的参考实现和接口基准，确保两者行为一致。

    Args:
        storage_dir: 根存储目录，默认 ``./data``。
        namespace:   命名空间子目录，用于隔离不同用途的数据。
    """

    def __init__(
        self,
        storage_dir: str = "./data",
        namespace: str = "default",
    ) -> None:
        self.storage_dir = storage_dir
        self.namespace = namespace
        self._dir = os.path.join(storage_dir, namespace)
        os.makedirs(self._dir, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    #  核心CRUD
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """获取键对应的值。

        Args:
            key:     键名。
            default: 键不存在时返回的默认值。

        Returns:
            反序列化后的值，或 *default*。
        """
        path = self._key_path(key)
        if not os.path.exists(path):
            return default
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    def set(self, key: str, value: Any) -> None:
        """设置键值对，覆盖已有值。"""
        path = self._key_path(key)
        with self._lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)

    def delete(self, key: str) -> bool:
        """删除键值对。

        Returns:
            ``True`` 若键存在且已删除，``False`` 若键不存在。
        """
        path = self._key_path(key)
        with self._lock:
            if os.path.exists(path):
                os.remove(path)
                return True
            return False

    def exists(self, key: str) -> bool:
        """检查键是否存在。"""
        return os.path.exists(self._key_path(key))

    def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """列出所有键，可选按子串模式过滤。

        Args:
            pattern: 子串匹配模式，``None`` 表示全部。

        Returns:
            排序后的键列表。
        """
        if not os.path.isdir(self._dir):
            return []
        keys: List[str] = []
        for fname in os.listdir(self._dir):
            if fname.endswith(".json"):
                key = fname[:-5]
                if pattern is None or pattern in key:
                    keys.append(key)
        return sorted(keys)

    # ------------------------------------------------------------------
    #  搜索
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """简单子串搜索（JSON后端降级实现）。

        遍历所有值，返回包含查询子串的结果。

        Args:
            query:  搜索查询字符串。
            top_k:  最大返回数量。

        Returns:
            结果列表，每项包含 ``key``、``value``、``score``。
        """
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()
        for key in self.list_keys():
            value = self.get(key)
            if value is None:
                continue
            text = json.dumps(value, ensure_ascii=False).lower()
            if query_lower in text:
                results.append({"key": key, "value": value, "score": 1.0})
                if len(results) >= top_k:
                    break
        return results

    # ------------------------------------------------------------------
    #  批量操作与统计
    # ------------------------------------------------------------------

    def batch_set(self, items: Dict[str, Any]) -> int:
        """批量写入键值对。

        Args:
            items: 键值对字典。

        Returns:
            写入数量。
        """
        count = 0
        for key, value in items.items():
            self.set(key, value)
            count += 1
        return count

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """事务上下文管理器（JSON后端为空操作）。"""
        # JSON后端无真正事务，提供兼容接口
        yield self

    def count(self) -> int:
        """返回键的总数。"""
        return len(self.list_keys())

    def clear(self) -> int:
        """清空所有数据。

        Returns:
            被清除的键数量。
        """
        keys = self.list_keys()
        for key in keys:
            self.delete(key)
        return len(keys)

    # ------------------------------------------------------------------
    #  生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        """关闭后端（JSON后端无需操作）。"""
        pass

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _key_path(self, key: str) -> str:
        """返回键对应的文件路径。"""
        return os.path.join(self._dir, f"{_safe_key(key)}.json")

    def __repr__(self) -> str:
        return f"JSONBackend(dir={self._dir!r}, keys={self.count()})"


# ----------------------------------------------------------------------
#  SQLiteBackend — SQLite持久化后端
# ----------------------------------------------------------------------

class SQLiteBackend:
    """SQLite持久化后端 — 支持FTS5全文搜索的键值存储。

    表结构::

        kv_store (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,        -- JSON序列化
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )

        kv_store_fts (              -- FTS5虚拟表
            content,                -- 被索引的文本
            key UNINDEXED            -- 对应主表键
        )

    特性:
        - 自动建表和索引
        - 线程安全：每线程独立连接 + WAL模式 + 写锁
        - FTS5全文搜索（自动降级为LIKE）
        - 批量写入
        - 事务支持

    Args:
        db_path:    数据库文件路径，默认 ``./data/suyi.db``。
        table_name: 主表名称，默认 ``kv_store``。
    """

    def __init__(
        self,
        db_path: str = "./data/suyi.db",
        table_name: str = "kv_store",
    ) -> None:
        self.db_path = db_path
        self.table_name = table_name
        self.fts_table = f"{table_name}_fts"

        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # 每线程连接存储
        self._local = threading.local()
        # 写锁（保护写操作和FTS索引更新）
        self._write_lock = threading.RLock()

        # 初始化数据库
        self._init_db()

    # ------------------------------------------------------------------
    #  连接管理
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（惰性创建）。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # WAL模式：允许多线程并发读，单写者
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            # 较短的忙等待，避免长时间阻塞
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _maybe_commit(self) -> None:
        """若不在事务上下文中则提交，否则跳过（由事务管理器统一提交）。"""
        depth = getattr(self._local, "_tx_depth", 0)
        if depth == 0:
            self._get_conn().commit()

    def _init_db(self) -> None:
        """初始化数据库表结构（幂等操作）。"""
        conn = self._get_conn()
        # 主表
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # FTS5虚拟表（全文搜索）
        self._fts_available = True
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.fts_table}
                USING fts5(
                    content,
                    key UNINDEXED
                )
            """)
        except sqlite3.OperationalError:
            # FTS5不可用 — 降级为普通表 + LIKE索引
            self._fts_available = False
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.fts_table} (
                    content TEXT,
                    key     TEXT
                )
            """)
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.fts_table}_content
                ON {self.fts_table}(content)
            """)
        # Phase 13: memory_quality table — stores quality scores for memories
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_quality (
                memory_id           TEXT PRIMARY KEY,
                source              TEXT NOT NULL DEFAULT 'C',
                result              TEXT NOT NULL DEFAULT 'SPECULATIVE',
                confidence          REAL NOT NULL DEFAULT 0.5,
                evidence_count      INTEGER NOT NULL DEFAULT 0,
                contradiction_count INTEGER NOT NULL DEFAULT 0,
                memory_weight       REAL NOT NULL DEFAULT 0.5,
                decay_tau_days      REAL,
                is_anti_pattern     INTEGER NOT NULL DEFAULT 0,
                reinforcement_count INTEGER NOT NULL DEFAULT 0,
                contradiction_total INTEGER NOT NULL DEFAULT 0,
                reference_count     INTEGER NOT NULL DEFAULT 0,
                last_reinforced     TEXT,
                is_user_pinned      INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_quality_source
            ON memory_quality(source)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_quality_result
            ON memory_quality(result)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_quality_weight
            ON memory_quality(memory_weight)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_quality_anti
            ON memory_quality(is_anti_pattern)
        """)

        # Phase 13: evolution_log table — tracks quality/forgetting events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                memory_id   TEXT,
                action      TEXT,
                details     TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evolution_log_event
            ON evolution_log(event_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evolution_log_memory
            ON evolution_log(memory_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evolution_log_created
            ON evolution_log(created_at)
        """)

        # Phase 14: loop_templates table — stores reusable Loop execution templates
        conn.execute("""
            CREATE TABLE IF NOT EXISTS loop_templates (
                id                         TEXT PRIMARY KEY,
                task_signature             TEXT NOT NULL,
                task_description           TEXT,
                phases_json                TEXT,
                tools_json                 TEXT,
                tool_order_json            TEXT,
                reflection_points_json     TEXT,
                max_iterations             INTEGER,
                termination_conditions_json TEXT,
                success_count              INTEGER DEFAULT 0,
                failure_count              INTEGER DEFAULT 0,
                success_rate               REAL DEFAULT 0.0,
                avg_iterations             REAL DEFAULT 0.0,
                avg_cost                   REAL DEFAULT 0.0,
                source_quality             TEXT,
                result_quality             TEXT,
                confidence                 REAL DEFAULT 0.5,
                evidence_count             INTEGER DEFAULT 0,
                contradiction_count        INTEGER DEFAULT 0,
                created_at                 TEXT NOT NULL,
                last_used                  TEXT NOT NULL,
                use_count                  INTEGER DEFAULT 0,
                parent_id                  TEXT,
                mutations_json             TEXT,
                variants_json              TEXT,
                is_active                  INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_loop_templates_signature
            ON loop_templates(task_signature)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_loop_templates_active
            ON loop_templates(is_active)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_loop_templates_parent
            ON loop_templates(parent_id)
        """)

        # Phase 14: loop_templates_fts — FTS5 full-text search for templates
        # Standalone FTS table (same pattern as kv_store_fts), manually
        # maintained.  Falls back to LIKE when FTS5 is unavailable.
        self._loop_fts_available = True
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS loop_templates_fts
                USING fts5(
                    task_signature,
                    task_description,
                    template_id UNINDEXED
                )
            """)
        except sqlite3.OperationalError:
            # FTS5不可用 — 降级为普通表 + LIKE
            self._loop_fts_available = False
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_templates_fts (
                    task_signature   TEXT,
                    task_description TEXT,
                    template_id      TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loop_templates_fts_sig
                ON loop_templates_fts(task_signature)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loop_templates_fts_desc
                ON loop_templates_fts(task_description)
            """)

        conn.commit()

    # ------------------------------------------------------------------
    #  核心CRUD
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """获取键对应的值。

        Args:
            key:     键名。
            default: 键不存在时返回的默认值。

        Returns:
            反序列化后的值，或 *default*。
        """
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT value FROM {self.table_name} WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])

    def set(self, key: str, value: Any) -> None:
        """设置键值对，同时更新FTS5索引。

        若键已存在则更新 ``updated_at`` 并保留 ``created_at``。
        """
        serialized = json.dumps(value, ensure_ascii=False)
        now = _iso_timestamp()
        text = _extract_search_text(value)

        with self._write_lock:
            conn = self._get_conn()
            # 检查是否已存在（保留created_at）
            existing = conn.execute(
                f"SELECT created_at FROM {self.table_name} WHERE key = ?",
                (key,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now

            # 写入主表
            conn.execute(
                f"""INSERT OR REPLACE INTO {self.table_name}
                    (key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?)""",
                (key, serialized, created_at, now),
            )
            # 更新FTS索引：先删除旧记录再插入
            self._update_fts(conn, key, text)
            self._maybe_commit()

    def delete(self, key: str) -> bool:
        """删除键值对。

        Returns:
            ``True`` 若键存在且已删除，``False`` 若键不存在。
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE key = ?",
                (key,),
            )
            conn.execute(
                f"DELETE FROM {self.fts_table} WHERE key = ?",
                (key,),
            )
            self._maybe_commit()
            return cursor.rowcount > 0

    def exists(self, key: str) -> bool:
        """检查键是否存在。"""
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT 1 FROM {self.table_name} WHERE key = ?",
            (key,),
        ).fetchone()
        return row is not None

    def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """列出所有键，可选按子串模式过滤。

        Args:
            pattern: 子串匹配模式，``None`` 表示全部。

        Returns:
            排序后的键列表。
        """
        conn = self._get_conn()
        if pattern:
            like_pattern = f"%{pattern}%"
            rows = conn.execute(
                f"SELECT key FROM {self.table_name} WHERE key LIKE ? ORDER BY key",
                (like_pattern,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT key FROM {self.table_name} ORDER BY key",
            ).fetchall()
        return [row["key"] for row in rows]

    # ------------------------------------------------------------------
    #  FTS5全文搜索
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """FTS5全文搜索。

        使用BM25排序算法返回最相关的结果。
        若FTS5不可用，自动降级为LIKE子串搜索。

        Args:
            query:  搜索查询字符串。
            top_k:  最大返回数量。

        Returns:
            结果列表，每项包含 ``key``、``value``、``score``。
            score越高表示越相关（BM25已取负值转换）。
        """
        conn = self._get_conn()
        if self._fts_available:
            return self._search_fts(conn, query, top_k)
        return self._search_like(conn, query, top_k)

    def _search_fts(
        self,
        conn: sqlite3.Connection,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用FTS5 MATCH进行全文搜索，若无结果则降级为LIKE。"""
        # 对查询进行FTS5安全转义
        safe_query = self._escape_fts_query(query)
        if not safe_query:
            return []

        try:
            rows = conn.execute(
                f"""SELECT f.key,
                           bm25({self.fts_table}) AS score
                    FROM {self.fts_table} f
                    WHERE {self.fts_table} MATCH ?
                    ORDER BY score ASC
                    LIMIT ?""",
                (safe_query, top_k),
            ).fetchall()
        except sqlite3.OperationalError:
            # MATCH语法不匹配，降级为LIKE
            return self._search_like(conn, query, top_k)

        results: List[Dict[str, Any]] = []
        for row in rows:
            value = self.get(row["key"])
            # bm25返回负值（越小越相关），转换为正分数
            score = -row["score"] if row["score"] < 0 else row["score"]
            results.append({
                "key": row["key"],
                "value": value,
                "score": round(score, 4),
            })

        # FTS5 MATCH无结果时降级为LIKE（兼容CJK等特殊分词场景）
        if not results:
            return self._search_like(conn, query, top_k)
        return results

    def _search_like(
        self,
        conn: sqlite3.Connection,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """LIKE降级搜索（FTS5不可用时使用）。"""
        like_pattern = f"%{query}%"
        rows = conn.execute(
            f"""SELECT key FROM {self.fts_table}
                WHERE content LIKE ?
                LIMIT ?""",
            (like_pattern, top_k),
        ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            value = self.get(row["key"])
            results.append({
                "key": row["key"],
                "value": value,
                "score": 1.0,
            })
        return results

    @staticmethod
    def _escape_fts_query(query: str) -> str:
        """将用户查询转换为安全的FTS5 MATCH表达式。

        策略：将每个词用双引号包裹，用OR连接（任一匹配即可）。
        若查询为空则返回空字符串。
        """
        if not query or not query.strip():
            return ""
        # 分词并包裹双引号
        terms = query.strip().split()
        if not terms:
            return ""
        quoted = [f'"{t}"' for t in terms]
        return " OR ".join(quoted)

    # ------------------------------------------------------------------
    #  批量写入
    # ------------------------------------------------------------------

    def batch_set(self, items: Dict[str, Any]) -> int:
        """批量写入键值对（单事务提交）。

        Args:
            items: 键值对字典。

        Returns:
            写入数量。
        """
        count = 0
        now = _iso_timestamp()
        with self._write_lock:
            conn = self._get_conn()
            for key, value in items.items():
                serialized = json.dumps(value, ensure_ascii=False)
                text = _extract_search_text(value)

                existing = conn.execute(
                    f"SELECT created_at FROM {self.table_name} WHERE key = ?",
                    (key,),
                ).fetchone()
                created_at = existing["created_at"] if existing else now

                conn.execute(
                    f"""INSERT OR REPLACE INTO {self.table_name}
                        (key, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?)""",
                    (key, serialized, created_at, now),
                )
                self._update_fts(conn, key, text)
                count += 1
            self._maybe_commit()
        return count

    # ------------------------------------------------------------------
    #  事务
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文管理器。

        在 ``with`` 块内执行的所有写操作要么全部提交，要么全部回滚。
        支持嵌套：嵌套事务使用SAVEPOINT实现。

        Usage::

            with backend.transaction() as conn:
                conn.execute("...")
                conn.execute("...")
            # 提交在退出时自动执行
        """
        conn = self._get_conn()
        self._write_lock.acquire()

        # 追踪嵌套深度（线程本地）
        depth = getattr(self._local, "_tx_depth", 0)

        if depth == 0:
            # 外层事务：使用BEGIN/COMMIT/ROLLBACK
            try:
                conn.execute("BEGIN")
                self._local._tx_depth = depth + 1
                yield conn
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass  # 事务可能已被回滚
                raise
            finally:
                self._local._tx_depth = depth
                self._write_lock.release()
        else:
            # 嵌套事务：使用SAVEPOINT
            sp_name = f"sp_{depth}"
            try:
                conn.execute(f"SAVEPOINT {sp_name}")
                self._local._tx_depth = depth + 1
                yield conn
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            except Exception:
                try:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                except sqlite3.OperationalError:
                    pass
                raise
            finally:
                self._local._tx_depth = depth

    # ------------------------------------------------------------------
    #  统计与清空
    # ------------------------------------------------------------------

    def count(self) -> int:
        """返回键的总数。"""
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM {self.table_name}",
        ).fetchone()
        return row["cnt"]

    def clear(self) -> int:
        """清空所有数据（主表 + FTS索引）。

        Returns:
            被清除的键数量。
        """
        with self._write_lock:
            conn = self._get_conn()
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM {self.table_name}",
            ).fetchone()
            count = row["cnt"]
            conn.execute(f"DELETE FROM {self.table_name}")
            conn.execute(f"DELETE FROM {self.fts_table}")
            self._maybe_commit()
            return count

    # ------------------------------------------------------------------
    #  FTS索引维护
    # ------------------------------------------------------------------

    def _update_fts(
        self,
        conn: sqlite3.Connection,
        key: str,
        text: str,
    ) -> None:
        """更新FTS索引：删除旧记录并插入新记录。"""
        conn.execute(
            f"DELETE FROM {self.fts_table} WHERE key = ?",
            (key,),
        )
        conn.execute(
            f"INSERT INTO {self.fts_table} (content, key) VALUES (?, ?)",
            (text, key),
        )

    # ------------------------------------------------------------------
    #  Phase 13: Memory Quality & Evolution Log
    # ------------------------------------------------------------------

    def upsert_memory_quality(
        self,
        memory_id: str,
        source: str = "C",
        result: str = "SPECULATIVE",
        confidence: float = 0.5,
        evidence_count: int = 0,
        contradiction_count: int = 0,
        memory_weight: float = 0.5,
        decay_tau_days: Optional[float] = None,
        is_anti_pattern: bool = False,
        reinforcement_count: int = 0,
        contradiction_total: int = 0,
        reference_count: int = 0,
        last_reinforced: Optional[str] = None,
        is_user_pinned: bool = False,
    ) -> None:
        """Insert or update a memory quality record.

        Args:
            memory_id:           The memory's unique ID.
            source:              Source quality grade letter (S/A/B/C/D).
            result:              Result quality name (VERIFIED/TRUSTED/
                                 SPECULATIVE/FAILED).
            confidence:          Confidence in [0, 1].
            evidence_count:      Supporting evidence count.
            contradiction_count: Contradicting evidence count.
            memory_weight:       Computed memory weight [0, 1].
            decay_tau_days:      Decay time-constant in days (None = inf).
            is_anti_pattern:     Whether this is an anti-pattern memory.
            reinforcement_count: Times the memory was reinforced.
            contradiction_total: Total contradictions encountered.
            reference_count:     Times the memory was referenced.
            last_reinforced:     ISO timestamp of last reinforcement.
            is_user_pinned:      Whether the user pinned this memory.
        """
        now = _iso_timestamp()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO memory_quality
                   (memory_id, source, result, confidence, evidence_count,
                    contradiction_count, memory_weight, decay_tau_days,
                    is_anti_pattern, reinforcement_count, contradiction_total,
                    reference_count, last_reinforced, is_user_pinned,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory_id, source, result, confidence,
                    evidence_count, contradiction_count, memory_weight,
                    decay_tau_days, int(is_anti_pattern),
                    reinforcement_count, contradiction_total,
                    reference_count, last_reinforced, int(is_user_pinned),
                    now, now,
                ),
            )
            self._maybe_commit()

    def get_memory_quality(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the quality record for a memory.

        Args:
            memory_id: The memory's unique ID.

        Returns:
            A dict with quality fields, or ``None`` if not found.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM memory_quality WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_memory_quality(self, memory_id: str) -> bool:
        """Delete a memory quality record.

        Args:
            memory_id: The memory's unique ID.

        Returns:
            ``True`` if a record was deleted.
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM memory_quality WHERE memory_id = ?",
                (memory_id,),
            )
            self._maybe_commit()
            return cursor.rowcount > 0

    def query_memory_quality(
        self,
        source: Optional[str] = None,
        result: Optional[str] = None,
        is_anti_pattern: Optional[bool] = None,
        min_weight: Optional[float] = None,
        max_weight: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query memory quality records with optional filters.

        Args:
            source:           Filter by source grade (S/A/B/C/D).
            result:           Filter by result quality name.
            is_anti_pattern:  Filter by anti-pattern flag.
            min_weight:       Minimum memory weight.
            max_weight:       Maximum memory weight.
            limit:            Maximum number of results.

        Returns:
            List of quality record dicts.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if result is not None:
            clauses.append("result = ?")
            params.append(result)
        if is_anti_pattern is not None:
            clauses.append("is_anti_pattern = ?")
            params.append(int(is_anti_pattern))
        if min_weight is not None:
            clauses.append("memory_weight >= ?")
            params.append(min_weight)
        if max_weight is not None:
            clauses.append("memory_weight <= ?")
            params.append(max_weight)

        where_clause = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)

        conn = self._get_conn()
        rows = conn.execute(
            f"""SELECT * FROM memory_quality
                WHERE {where_clause}
                ORDER BY memory_weight DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def log_evolution_event(
        self,
        event_type: str,
        memory_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[str] = None,
    ) -> int:
        """Record an evolution event in the evolution_log table.

        Args:
            event_type: Type of event (e.g. 'quality_update',
                        'forget', 'compress', 'anti_pattern_register').
            memory_id:  ID of the affected memory.
            action:     Action taken (e.g. 'DEGRADE', 'PURGE').
            details:    JSON string with additional context.

        Returns:
            The row ID of the inserted log entry.
        """
        now = _iso_timestamp()
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """INSERT INTO evolution_log
                   (event_type, memory_id, action, details, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, memory_id, action, details, now),
            )
            self._maybe_commit()
            return cursor.lastrowid

    def query_evolution_log(
        self,
        event_type: Optional[str] = None,
        memory_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query the evolution log with optional filters.

        Args:
            event_type: Filter by event type.
            memory_id:  Filter by memory ID.
            limit:      Maximum number of results.

        Returns:
            List of log entry dicts, newest first.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if memory_id is not None:
            clauses.append("memory_id = ?")
            params.append(memory_id)

        where_clause = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)

        conn = self._get_conn()
        rows = conn.execute(
            f"""SELECT * FROM evolution_log
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def query_anti_patterns(
        self,
        include_resolved: bool = False,
        min_severity: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query anti-pattern memory records.

        Anti-patterns are stored as memory_quality records with
        ``is_anti_pattern = 1`` and ``result = 'FAILED'``.

        Args:
            include_resolved: Whether to include resolved patterns.
            min_severity:     Minimum severity threshold.
            limit:            Maximum number of results.

        Returns:
            List of anti-pattern record dicts.
        """
        clauses: List[str] = ["is_anti_pattern = 1"]
        params: List[Any] = []
        if not include_resolved:
            # Resolved patterns have is_user_pinned = 0 and
            # confidence > 0.5 (lowered severity). We approximate
            # "unresolved" as confidence <= 0.5.
            clauses.append("confidence <= 0.5")
        if min_severity is not None:
            # Severity is inversely related to confidence for anti-patterns
            clauses.append("(1.0 - confidence) >= ?")
            params.append(min_severity)

        where_clause = " AND ".join(clauses)
        params.append(limit)

        conn = self._get_conn()
        rows = conn.execute(
            f"""SELECT * FROM memory_quality
                WHERE {where_clause}
                ORDER BY confidence ASC, memory_weight DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    #  Phase 14: Loop Template Storage
    # ------------------------------------------------------------------

    def save_loop_template(self, template_data: Dict[str, Any]) -> None:
        """Insert or update a loop template record.

        Expects a dict with at least ``id``, ``task_signature``,
        and ``task_description`` keys.  List fields (``phases``,
        ``tools``, ``tool_order``, ``reflection_points``,
        ``termination_conditions``) should already be JSON-serialised
        or will be serialised by this method.

        Args:
            template_data: Dict containing all template fields.
        """
        now = _iso_timestamp()
        tid = template_data["id"]

        # Serialise list fields if not already strings
        def _ensure_json(value: Any, key: str) -> str:
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)

        phases_json = _ensure_json(
            template_data.get("phases_json") or template_data.get("phases", []),
            "phases",
        )
        tools_json = _ensure_json(
            template_data.get("tools_json") or template_data.get("tools", []),
            "tools",
        )
        tool_order_json = _ensure_json(
            template_data.get("tool_order_json") or template_data.get("tool_order", []),
            "tool_order",
        )
        reflection_points_json = _ensure_json(
            template_data.get("reflection_points_json")
            or template_data.get("reflection_points", []),
            "reflection_points",
        )
        termination_conditions_json = _ensure_json(
            template_data.get("termination_conditions_json")
            or template_data.get("termination_conditions", []),
            "termination_conditions",
        )

        # Quality fields
        quality = template_data.get("quality")
        source_quality = template_data.get("source_quality")
        result_quality = template_data.get("result_quality")
        confidence = template_data.get("confidence", 0.5)
        evidence_count = template_data.get("evidence_count", 0)
        contradiction_count = template_data.get("contradiction_count", 0)

        if quality and isinstance(quality, dict):
            # The 'quality' dict takes priority over flattened fields
            q_source = quality.get("source")
            q_result = quality.get("result")
            source_quality = q_source if q_source else (source_quality or "C")
            result_quality = q_result if q_result else (result_quality or "SPECULATIVE")
            confidence = quality.get("confidence", confidence)
            evidence_count = quality.get("evidence_count", evidence_count)
            contradiction_count = quality.get(
                "contradiction_count", contradiction_count,
            )

        with self._write_lock:
            conn = self._get_conn()

            # Preserve created_at if updating existing record
            existing = conn.execute(
                "SELECT created_at FROM loop_templates WHERE id = ?",
                (tid,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            last_used = template_data.get("last_used", now)

            conn.execute(
                """INSERT OR REPLACE INTO loop_templates
                   (id, task_signature, task_description,
                    phases_json, tools_json, tool_order_json,
                    reflection_points_json, max_iterations,
                    termination_conditions_json,
                    success_count, failure_count, success_rate,
                    avg_iterations, avg_cost,
                    source_quality, result_quality,
                    confidence, evidence_count, contradiction_count,
                    created_at, last_used, use_count,
                    parent_id, mutations_json, variants_json, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tid,
                    template_data.get("task_signature", ""),
                    template_data.get("task_description", ""),
                    phases_json,
                    tools_json,
                    tool_order_json,
                    reflection_points_json,
                    template_data.get("max_iterations", 10),
                    termination_conditions_json,
                    template_data.get("success_count", 0),
                    template_data.get("failure_count", 0),
                    template_data.get("success_rate", 0.0),
                    template_data.get("avg_iterations", 0.0),
                    template_data.get("avg_cost", 0.0),
                    source_quality,
                    result_quality,
                    confidence,
                    evidence_count,
                    contradiction_count,
                    created_at,
                    last_used,
                    template_data.get("use_count", 0),
                    template_data.get("parent_id"),
                    _ensure_json(
                        template_data.get("mutations_json")
                        or template_data.get("mutations", []),
                        "mutations",
                    ),
                    _ensure_json(
                        template_data.get("variants_json")
                        or template_data.get("variants", []),
                        "variants",
                    ),
                    int(template_data.get("is_active", True)),
                ),
            )

            # Update FTS index for loop templates
            conn.execute(
                "DELETE FROM loop_templates_fts WHERE template_id = ?",
                (tid,),
            )
            conn.execute(
                """INSERT INTO loop_templates_fts
                   (task_signature, task_description, template_id)
                   VALUES (?, ?, ?)""",
                (
                    template_data.get("task_signature", ""),
                    template_data.get("task_description", ""),
                    tid,
                ),
            )
            self._maybe_commit()

    def get_loop_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a loop template by ID.

        Args:
            template_id: The template's unique ID.

        Returns:
            A dict with all template fields (JSON fields deserialised),
            or ``None`` if not found.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM loop_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_loop_template(row)

    def search_loop_templates(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Full-text search for loop templates.

        Searches across ``task_signature`` and ``task_description``
        using FTS5 (or LIKE fallback).  Only active templates are
        returned.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of template dicts, best matches first.
        """
        if not query or not query.strip():
            return []

        conn = self._get_conn()
        results: List[Dict[str, Any]] = []

        if self._loop_fts_available:
            safe_query = self._escape_fts_query(query)
            if safe_query:
                try:
                    rows = conn.execute(
                        """SELECT lt.*,
                                  bm25(loop_templates_fts) AS score
                           FROM loop_templates_fts f
                           JOIN loop_templates lt ON lt.id = f.template_id
                           WHERE loop_templates_fts MATCH ?
                             AND lt.is_active = 1
                           ORDER BY score ASC
                           LIMIT ?""",
                        (safe_query, limit),
                    ).fetchall()
                    for row in rows:
                        tpl = self._row_to_loop_template(row)
                        tpl["search_score"] = -row["score"] if row["score"] < 0 else row["score"]
                        results.append(tpl)
                except sqlite3.OperationalError:
                    results = []  # fall through to LIKE

        if not results:
            # LIKE fallback (also used when FTS5 is unavailable)
            like_pattern = f"%{query}%"
            rows = conn.execute(
                """SELECT * FROM loop_templates
                   WHERE (task_signature LIKE ? OR task_description LIKE ?)
                     AND is_active = 1
                   LIMIT ?""",
                (like_pattern, like_pattern, limit),
            ).fetchall()
            for row in rows:
                results.append(self._row_to_loop_template(row))

        return results

    def update_loop_template_stats(
        self,
        template_id: str,
        success: bool,
        iterations: int,
        cost: float,
    ) -> None:
        """Update usage statistics for a loop template.

        Increments success/failure count, updates success_rate,
        avg_iterations, avg_cost, use_count, and last_used timestamp.

        Args:
            template_id: The template's unique ID.
            success:     Whether the template usage was successful.
            iterations:  Number of iterations used.
            cost:        Cost incurred.
        """
        now = _iso_timestamp()
        with self._write_lock:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT success_count, failure_count, avg_iterations,
                          avg_cost, use_count
                   FROM loop_templates WHERE id = ?""",
                (template_id,),
            ).fetchone()
            if row is None:
                return

            old_success = row["success_count"]
            old_failure = row["failure_count"]
            old_avg_iter = row["avg_iterations"]
            old_avg_cost = row["avg_cost"]
            old_use = row["use_count"]

            new_success = old_success + (1 if success else 0)
            new_failure = old_failure + (0 if success else 1)
            total = new_success + new_failure
            new_rate = new_success / total if total > 0 else 0.0

            new_use = old_use + 1
            # Running average: (old_avg * old_n + new_value) / new_n
            new_avg_iter = (old_avg_iter * old_use + iterations) / new_use
            new_avg_cost = (old_avg_cost * old_use + cost) / new_use

            conn.execute(
                """UPDATE loop_templates
                   SET success_count = ?, failure_count = ?,
                       success_rate = ?, avg_iterations = ?,
                       avg_cost = ?, use_count = ?, last_used = ?
                   WHERE id = ?""",
                (
                    new_success, new_failure, new_rate,
                    new_avg_iter, new_avg_cost, new_use, now,
                    template_id,
                ),
            )
            self._maybe_commit()

    def list_loop_templates(
        self,
        task_signature: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List loop templates, optionally filtered by task signature.

        Only active templates are returned by default.  Results are
        ordered by success_rate descending, then use_count descending.

        Args:
            task_signature: Optional filter — if provided, only
                templates with an exact match are returned.

        Returns:
            List of template dicts.
        """
        conn = self._get_conn()
        if task_signature is not None:
            rows = conn.execute(
                """SELECT * FROM loop_templates
                   WHERE task_signature = ? AND is_active = 1
                   ORDER BY success_rate DESC, use_count DESC""",
                (task_signature,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM loop_templates
                   WHERE is_active = 1
                   ORDER BY success_rate DESC, use_count DESC""",
            ).fetchall()
        return [self._row_to_loop_template(r) for r in rows]

    def deactivate_loop_template(self, template_id: str) -> bool:
        """Deactivate a loop template (soft delete).

        Args:
            template_id: The template's unique ID.

        Returns:
            ``True`` if the template was found and deactivated.
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE loop_templates SET is_active = 0 WHERE id = ?",
                (template_id,),
            )
            self._maybe_commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_loop_template(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a deserialised template dict."""
        result = dict(row)
        # Deserialise JSON fields
        for json_field in (
            "phases_json",
            "tools_json",
            "tool_order_json",
            "reflection_points_json",
            "termination_conditions_json",
            "mutations_json",
            "variants_json",
        ):
            raw = result.get(json_field)
            if raw is None:
                result[json_field] = []
            elif isinstance(raw, str):
                try:
                    result[json_field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    result[json_field] = []
            else:
                result[json_field] = raw
        # Convert is_active from int to bool
        result["is_active"] = bool(result.get("is_active", 1))
        return result

    # ------------------------------------------------------------------
    #  生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        """关闭当前线程的数据库连接。"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def __repr__(self) -> str:
        try:
            cnt = self.count()
        except Exception:
            cnt = -1
        return (
            f"SQLiteBackend(db={self.db_path!r}, "
            f"table={self.table_name!r}, "
            f"count={cnt})"
        )
