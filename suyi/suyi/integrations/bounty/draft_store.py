"""
Bounty draft store — 草稿持久化存储.

将 :class:`DraftReport` 保存为 JSON 文件到本地目录，支持提交前审查。
默认存储路径: ``~/.suyi/bounty_drafts/``

功能:
    - :meth:`save_draft` 保存草稿
    - :meth:`load_draft` 加载草稿
    - :meth:`list_drafts` 列出所有草稿
    - :meth:`delete_draft` 删除草稿
    - :meth:`mark_reviewed` 标记草稿为已审查
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import DraftReport

logger = logging.getLogger(__name__)

# 默认草稿存储目录
DEFAULT_DRAFT_DIR = os.path.join(
    os.path.expanduser("~"), ".suyi", "bounty_drafts"
)


class DraftStore:
    """草稿持久化存储.

    将草稿以 JSON 文件形式存储到本地文件系统。每个草稿一个文件，
    文件名为 ``{draft_id}.json``。

    Args:
        draft_dir: 草稿存储目录，默认为 ~/.suyi/bounty_drafts/
    """

    def __init__(self, draft_dir: Optional[str] = None):
        self.draft_dir = draft_dir or DEFAULT_DRAFT_DIR
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """确保存储目录存在."""
        os.makedirs(self.draft_dir, exist_ok=True)

    def _draft_path(self, draft_id: str) -> str:
        """获取草稿文件路径."""
        # 安全检查：防止路径穿越
        safe_id = os.path.basename(draft_id)
        if not safe_id or safe_id != draft_id:
            raise ValueError(f"非法的 draft_id: {draft_id!r}")
        return os.path.join(self.draft_dir, f"{safe_id}.json")

    # ------------------------------------------------------------------
    #  CRUD 操作
    # ------------------------------------------------------------------

    def save_draft(self, draft: DraftReport) -> str:
        """保存草稿到文件.

        Args:
            draft: 要保存的草稿

        Returns:
            草稿文件路径
        """
        path = self._draft_path(draft.draft_id)
        data = draft.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("草稿已保存: %s", path)
        return path

    def load_draft(self, draft_id: str) -> DraftReport:
        """从文件加载草稿.

        Args:
            draft_id: 草稿 ID

        Returns:
            DraftReport 实例

        Raises:
            FileNotFoundError: 草稿文件不存在
            ValueError: 文件内容格式错误
        """
        path = self._draft_path(draft_id)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"草稿不存在: {draft_id}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return DraftReport.from_dict(data)

    def list_drafts(
        self, platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出所有草稿的摘要信息.

        Args:
            platform: 可选，按平台名称过滤

        Returns:
            草稿摘要字典列表，每个包含 draft_id, target_platform,
            title, created_at, reviewed
        """
        drafts: List[Dict[str, Any]] = []
        if not os.path.isdir(self.draft_dir):
            return drafts

        for filename in sorted(os.listdir(self.draft_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.draft_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                target_platform = data.get("target_platform", "")
                if platform and target_platform != platform:
                    continue

                report = data.get("report", {})
                drafts.append({
                    "draft_id": data.get("draft_id", ""),
                    "target_platform": target_platform,
                    "title": report.get("title", ""),
                    "severity": report.get("severity", ""),
                    "created_at": data.get("created_at", 0),
                    "reviewed": data.get("reviewed", False),
                })
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning("跳过无法读取的草稿文件 %s: %s", filename, e)
                continue

        return drafts

    def delete_draft(self, draft_id: str) -> bool:
        """删除草稿.

        Args:
            draft_id: 草稿 ID

        Returns:
            是否成功删除（文件不存在时返回 False）
        """
        path = self._draft_path(draft_id)
        if os.path.isfile(path):
            os.remove(path)
            logger.info("草稿已删除: %s", path)
            return True
        return False

    # ------------------------------------------------------------------
    #  审查标记
    # ------------------------------------------------------------------

    def mark_reviewed(self, draft_id: str, reviewed: bool = True) -> None:
        """标记草稿为已审查/未审查.

        Args:
            draft_id: 草稿 ID
            reviewed: 是否已审查

        Raises:
            FileNotFoundError: 草稿不存在
        """
        path = self._draft_path(draft_id)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"草稿不存在: {draft_id}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["reviewed"] = reviewed

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            "草稿 %s 已标记为 %s",
            draft_id,
            "已审查" if reviewed else "未审查",
        )

    def count_drafts(self, platform: Optional[str] = None) -> int:
        """统计草稿数量.

        Args:
            platform: 可选，按平台过滤

        Returns:
            草稿数量
        """
        return len(self.list_drafts(platform=platform))
