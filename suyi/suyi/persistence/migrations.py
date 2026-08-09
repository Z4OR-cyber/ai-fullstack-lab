"""
JSON → SQLite 迁移脚本。

将现有JSON文件数据导入SQLite数据库，支持增量迁移和迁移日志。

迁移策略
--------
1. 扫描JSON源（目录或 ``JSONBackend`` 实例）
2. 逐条读取并写入SQLite目标
3. 增量模式：跳过目标中已存在的键
4. 全量模式：覆盖所有键
5. 记录迁移日志

Usage::

    from suyi.persistence import SQLiteBackend, migrate_json_to_sqlite

    target = SQLiteBackend("./data/suyi.db")
    report = migrate_json_to_sqlite(
        source="./data/sessions",
        target=target,
        incremental=True,
    )
    print(report)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Union

from .sqlite_backend import JSONBackend, SQLiteBackend


# ----------------------------------------------------------------------
#  迁移日志
# ----------------------------------------------------------------------

class MigrationLogger:
    """迁移日志记录器 — 收集迁移过程中的事件。"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.entries: List[Dict[str, Any]] = []

    def log(self, event: str, detail: str = "", key: str = "") -> None:
        """记录一条迁移事件。"""
        if not self.enabled:
            return
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "detail": detail,
            "key": key,
        }
        self.entries.append(entry)

    def summary(self) -> List[Dict[str, Any]]:
        """返回所有日志条目。"""
        return list(self.entries)


# ----------------------------------------------------------------------
#  迁移核心
# ----------------------------------------------------------------------

def migrate_json_to_sqlite(
    source: Union[str, JSONBackend],
    target: SQLiteBackend,
    incremental: bool = True,
    log: bool = True,
) -> Dict[str, Any]:
    """将JSON后端数据迁移到SQLite后端。

    Args:
        source:      JSON源 — 可以是目录路径或 ``JSONBackend`` 实例。
        target:      SQLite后端实例。
        incremental: 若 ``True``，只迁移目标中不存在的键。
        log:         是否记录迁移日志。

    Returns:
        迁移报告字典::

            {
                "total":       int,           # 源中键总数
                "migrated":    int,           # 成功迁移数
                "skipped":     int,           # 跳过数（增量模式）
                "failed":      int,           # 失败数
                "errors":      list[str],    # 错误信息列表
                "duration_s":  float,         # 耗时（秒）
                "log":         list[dict],   # 迁移日志
            }
    """
    logger = MigrationLogger(enabled=log)
    start_time = time.time()

    # 构建JSON后端实例
    if isinstance(source, str):
        # 从目录路径推断namespace（最后一级目录名）
        source_dir = os.path.dirname(source.rstrip("/"))
        namespace = os.path.basename(source.rstrip("/"))
        json_backend = JSONBackend(
            storage_dir=source_dir if source_dir else ".",
            namespace=namespace,
        )
        # 若source本身就是完整目录路径，直接用它
        if os.path.isdir(source):
            json_backend = JSONBackend(
                storage_dir=os.path.dirname(source.rstrip("/")) or ".",
                namespace=os.path.basename(source.rstrip("/")),
            )
    elif isinstance(source, JSONBackend):
        json_backend = source
    else:
        raise TypeError(
            f"source 必须是 str（目录路径）或 JSONBackend，"
            f"得到 {type(source).__name__}"
        )

    # 收集所有键
    all_keys = json_backend.list_keys()
    total = len(all_keys)
    migrated = 0
    skipped = 0
    failed = 0
    errors: List[str] = []

    logger.log("migration_start", f"source={json_backend._dir}, total={total}")

    # 批量准备数据
    batch: Dict[str, Any] = {}
    for key in all_keys:
        # 增量模式：跳过已存在的键
        if incremental and target.exists(key):
            skipped += 1
            logger.log("skip", "key already exists in target", key=key)
            continue

        try:
            value = json_backend.get(key)
            if value is not None:
                batch[key] = value
        except Exception as exc:
            failed += 1
            errors.append(f"Failed to read key '{key}': {exc}")
            logger.log("error", str(exc), key=key)

    # 批量写入
    if batch:
        try:
            migrated = target.batch_set(batch)
            for key in batch:
                logger.log("migrate", "success", key=key)
        except Exception as exc:
            # 批量失败，逐条重试
            for key, value in batch.items():
                try:
                    target.set(key, value)
                    migrated += 1
                    logger.log("migrate", "success (retry)", key=key)
                except Exception as exc2:
                    failed += 1
                    errors.append(f"Failed to write key '{key}': {exc2}")
                    logger.log("error", str(exc2), key=key)

    duration = round(time.time() - start_time, 4)

    logger.log(
        "migration_complete",
        f"migrated={migrated}, skipped={skipped}, failed={failed}",
    )

    return {
        "total": total,
        "migrated": migrated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "duration_s": duration,
        "log": logger.summary(),
    }


def migrate_json_dir_to_sqlite(
    json_dir: str,
    target: SQLiteBackend,
    incremental: bool = True,
    log: bool = True,
) -> Dict[str, Any]:
    """从JSON文件目录迁移到SQLite。

    扫描目录下所有 ``.json`` 文件，将每个文件作为一个键值对导入。

    Args:
        json_dir:    JSON文件所在目录。
        target:      SQLite后端实例。
        incremental: 若 ``True``，只导入目标中不存在的键。
        log:         是否记录迁移日志。

    Returns:
        与 :func:`migrate_json_to_sqlite` 相同的迁移报告。
    """
    logger = MigrationLogger(enabled=log)
    start_time = time.time()

    if not os.path.isdir(json_dir):
        raise FileNotFoundError(f"JSON目录不存在: {json_dir}")

    # 收集所有JSON文件
    json_files: List[str] = []
    for fname in os.listdir(json_dir):
        if fname.endswith(".json") and not fname.endswith("_export.json"):
            json_files.append(fname)

    total = len(json_files)
    migrated = 0
    skipped = 0
    failed = 0
    errors: List[str] = []

    logger.log("migration_start", f"dir={json_dir}, total={total}")

    batch: Dict[str, Any] = {}
    for fname in json_files:
        key = fname[:-5]  # 去掉.json后缀

        if incremental and target.exists(key):
            skipped += 1
            logger.log("skip", "key already exists in target", key=key)
            continue

        try:
            path = os.path.join(json_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                value = json.load(f)
            batch[key] = value
        except Exception as exc:
            failed += 1
            errors.append(f"Failed to read '{fname}': {exc}")
            logger.log("error", str(exc), key=key)

    if batch:
        try:
            migrated = target.batch_set(batch)
            for key in batch:
                logger.log("migrate", "success", key=key)
        except Exception as exc:
            for key, value in batch.items():
                try:
                    target.set(key, value)
                    migrated += 1
                    logger.log("migrate", "success (retry)", key=key)
                except Exception as exc2:
                    failed += 1
                    errors.append(f"Failed to write key '{key}': {exc2}")
                    logger.log("error", str(exc2), key=key)

    duration = round(time.time() - start_time, 4)
    logger.log(
        "migration_complete",
        f"migrated={migrated}, skipped={skipped}, failed={failed}",
    )

    return {
        "total": total,
        "migrated": migrated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "duration_s": duration,
        "log": logger.summary(),
    }
