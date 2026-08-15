"""弱信号积累器 — 积累零散负面信号，达到阈值才触发蒸馏.

旁路知识层的双循环思想：
    - **内循环（实时）**：单次交互的弱信号不直接改写策略，只记录积累。
    - **外循环（批式）**：同类弱信号累计到阈值后，才触发知识蒸馏，
      将"零散不满"转化为"可复用规则"。

这避免了单条噪声反馈导致策略抖动（recency bias / overreaction）。

隐私友好设计：
    - 不存储完整 prompt，只存前 200 字摘要。
    - 同类信号以 ``signal_type + category_hint`` 的 MD5 哈希作为 key，
      不保留可还原的用户输入。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# 弱信号类型常量
SIGNAL_REWRITE = "rewrite"
SIGNAL_THUMBS_DOWN = "thumbs_down"
SIGNAL_CORRECTION = "correction"
SIGNAL_RETRY = "retry"
SIGNAL_USER_COMMENT = "user_comment"

VALID_SIGNAL_TYPES = frozenset({
    SIGNAL_REWRITE,
    SIGNAL_THUMBS_DOWN,
    SIGNAL_CORRECTION,
    SIGNAL_RETRY,
    SIGNAL_USER_COMMENT,
})

# 摘要最大长度（不存完整 prompt）
MAX_CONTEXT_SUMMARY = 200


@dataclass
class WeakSignal:
    """一条累积中的弱信号.

    Attributes:
        id: 信号唯一标识符.
        signal_type: 信号类型（rewrite/thumbs_down/correction/retry/user_comment）.
        context_summary: 任务摘要（前 200 字，不存完整 prompt）.
        bureau: 业务域.
        category_hint: 可能的问题类别提示.
        count: 同类信号累计次数.
        first_seen: 首次出现时间戳.
        last_seen: 最近出现时间戳.
        key: 同类信号归并键（signal_type + category_hint 的 MD5）.
    """

    id: str = ""
    signal_type: str = ""
    context_summary: str = ""
    bureau: str = "default"
    category_hint: str = ""
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    key: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"ws_{uuid.uuid4().hex[:12]}"
        now = time.time()
        if self.first_seen == 0.0:
            self.first_seen = now
        if self.last_seen == 0.0:
            self.last_seen = now
        if not self.key:
            self.key = self.make_key(self.signal_type, self.category_hint, self.bureau)

    @staticmethod
    def make_key(signal_type: str, category_hint: str, bureau: str = "default") -> str:
        """生成同类信号归并键（MD5 哈希，不可逆）."""
        raw = f"{bureau}|{signal_type}|{category_hint}".encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WeakSignal":
        """从字典创建实例."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class WeakSignalCollector:
    """弱信号积累器.

    同类信号（同 bureau + signal_type + category_hint）累计计数，
    达到 ``threshold`` 后可通过 :meth:`get_pending_distillation`
    获取，触发外循环蒸馏。

    Usage::

        collector = WeakSignalCollector(threshold=5)
        collector.record("thumbs_down", "帮我读文件但失败了", category_hint="file_read")
        # ... 累计 5 次后
        pending = collector.get_pending_distillation()
    """

    def __init__(
        self,
        threshold: int = 5,
        storage_dir: Optional[str] = None,
    ) -> None:
        """
        Args:
            threshold: 触发蒸馏的累计次数阈值（默认 5）.
            storage_dir: 可选持久化目录，配置后自动 save/load.
        """
        self.threshold = threshold
        self.storage_dir = storage_dir
        # key → WeakSignal
        self._signals: Dict[str, WeakSignal] = {}
        self._storage_file = "weak_signals.json"

        if storage_dir is not None:
            os.makedirs(storage_dir, exist_ok=True)
            self.load()

    def record(
        self,
        signal_type: str,
        context_summary: str,
        bureau: str = "default",
        category_hint: str = "",
    ) -> WeakSignal:
        """记录一次弱信号，同类信号 count+1.

        Args:
            signal_type: 信号类型（见模块常量）.
            context_summary: 任务摘要（自动截断到 200 字）.
            bureau: 业务域.
            category_hint: 问题类别提示（用于归并同类信号）.

        Returns:
            更新后的 WeakSignal.
        """
        # 隐私：截断摘要，不保留完整 prompt
        summary = (context_summary or "")[:MAX_CONTEXT_SUMMARY]
        key = WeakSignal.make_key(signal_type, category_hint, bureau)

        if key in self._signals:
            signal = self._signals[key]
            signal.count += 1
            signal.last_seen = time.time()
            # 保留最新摘要（不累积原文）
            signal.context_summary = summary
        else:
            signal = WeakSignal(
                signal_type=signal_type,
                context_summary=summary,
                bureau=bureau,
                category_hint=category_hint,
                count=1,
                key=key,
            )
            self._signals[key] = signal

        self._maybe_save()
        return signal

    def get_pending_distillation(self) -> List[WeakSignal]:
        """返回累计达到阈值、应触发蒸馏的信号列表.

        Returns:
            count >= threshold 的 WeakSignal 列表（按 last_seen 降序）.
        """
        pending = [s for s in self._signals.values() if s.count >= self.threshold]
        pending.sort(key=lambda s: s.last_seen, reverse=True)
        return pending

    def mark_distilled(self, signal_id: str) -> bool:
        """标记某信号已蒸馏，将其从积累器中移除.

        Args:
            signal_id: WeakSignal.id.

        Returns:
            是否找到并移除.
        """
        for key, signal in list(self._signals.items()):
            if signal.id == signal_id:
                del self._signals[key]
                self._maybe_save()
                return True
        return False

    def get(self, signal_id: str) -> Optional[WeakSignal]:
        """按 ID 获取信号."""
        for signal in self._signals.values():
            if signal.id == signal_id:
                return signal
        return None

    def all_signals(self) -> List[WeakSignal]:
        """返回全部弱信号（按 last_seen 降序）."""
        return sorted(
            self._signals.values(), key=lambda s: s.last_seen, reverse=True
        )

    def count(self) -> int:
        """返回当前不同类信号的数量."""
        return len(self._signals)

    def clear(self) -> None:
        """清空所有信号（主要用于测试）."""
        self._signals.clear()
        self._maybe_save()

    # ── 持久化 ────────────────────────────────────────────

    @property
    def storage_path(self) -> Optional[str]:
        """持久化文件完整路径（未配置目录返回 None）."""
        if self.storage_dir is None:
            return None
        return os.path.join(self.storage_dir, self._storage_file)

    def save(self, path: Optional[str] = None) -> str:
        """保存弱信号到 JSON 文件."""
        if path is None:
            if self.storage_dir is None:
                raise ValueError("未配置 storage_dir，必须显式传入 path")
            path = os.path.join(self.storage_dir, self._storage_file)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {
            "threshold": self.threshold,
            "signals": [s.to_dict() for s in self._signals.values()],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load(self, path: Optional[str] = None) -> int:
        """从 JSON 文件加载弱信号（合并到当前，key 已存在则保留计数较大者）.

        Returns:
            新加载的信号数量.
        """
        if path is None:
            if self.storage_dir is None:
                return 0
            path = os.path.join(self.storage_dir, self._storage_file)

        if not os.path.isfile(path):
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0

        threshold = data.get("threshold")
        if isinstance(threshold, int):
            self.threshold = threshold

        loaded = 0
        for item in data.get("signals", []):
            try:
                signal = WeakSignal.from_dict(item)
            except (TypeError, ValueError):
                continue
            existing = self._signals.get(signal.key)
            if existing is None:
                self._signals[signal.key] = signal
                loaded += 1
            else:
                # 合并：取较大计数，更新最近时间
                if signal.count > existing.count:
                    existing.count = signal.count
                if signal.last_seen > existing.last_seen:
                    existing.last_seen = signal.last_seen
        return loaded

    def _maybe_save(self) -> None:
        """配置了持久化目录时自动保存."""
        if self.storage_dir is not None:
            try:
                self.save()
            except OSError:
                pass
