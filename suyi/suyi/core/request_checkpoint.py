"""
请求可重建自检（Request Reconstructable Self-Check）.

借鉴 Harness 文章的核心思路：每次发给 LLM 的请求（messages + tools +
system_prompt）必须可从持久化状态完整重建。崩溃/中断后能精确重放。

本模块提供：
    - :class:`RequestCheckpoint`：请求快照（含 sha256 checksum），支持 JSON 往返
    - :class:`RequestReconstructionValidator`：发送前做一次 "序列化 → 反序列化 →
      比对" 校验，不一致抛 :class:`RequestNotReconstructableError`
    - :class:`RequestNotReconstructableError`：校验失败异常

纯标准库实现（json / hashlib / uuid / datetime / copy），不引入外部依赖.

设计原则：
    - **保守可序列化**：只接受 json.dumps 能处理的对象（dict/list/str/int/
      float/bool/None）。bytes、set、自定义对象等会直接失败，这是故意的——
      不可 JSON 序列化的请求天然不可重建.
    - **checksum 即内容指纹**：用 sort_keys=True + 紧凑分隔符规范化后 sha256，
      保证相同逻辑内容产生相同 checksum，不受 dict 插入顺序影响.
    - **深拷贝隔离**：checkpoint 内部对 messages/tools 做深拷贝，避免外部
      后续修改污染快照.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  异常
# ═══════════════════════════════════════════════════════════════


class RequestNotReconstructableError(Exception):
    """请求无法从持久化状态完整重建.

    触发场景：
        - messages / tools / system_prompt 中包含不可 JSON 序列化的对象
        - 序列化→反序列化后 checksum 不一致（理论上不应发生，除非有
          不稳定的 __repr__ 或循环引用）

    Attributes:
        reason: 人类可读的失败原因.
        field_path: 出错的字段路径（如 ``"messages[2].content"``），
            若无法定位则为 None.
    """

    def __init__(
        self,
        reason: str,
        field_path: Optional[str] = None,
    ):
        self.reason = reason
        self.field_path = field_path
        detail = reason
        if field_path:
            detail = f"{reason} (field: {field_path})"
        super().__init__(detail)


# ═══════════════════════════════════════════════════════════════
#  请求快照
# ═══════════════════════════════════════════════════════════════


def _utc_now_iso() -> str:
    """返回 UTC ISO 8601 时间戳（带 Z 后缀，便于跨时区持久化）."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_json(obj: Any) -> str:
    """生成规范化 JSON 字符串（sort_keys + 紧凑分隔符）.

    这是 checksum 的基础，保证相同逻辑内容产生相同字节序列.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _compute_checksum(
    messages: list[dict],
    tools: list[dict],
    system_prompt: str,
    model_hint: Optional[str],
) -> str:
    """根据请求四元组计算 sha256 checksum."""
    payload = {
        "messages": messages,
        "tools": tools,
        "system_prompt": system_prompt,
        "model_hint": model_hint,
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class RequestCheckpoint:
    """LLM 请求的可重建快照.

    Attributes:
        request_id:      唯一请求 ID（uuid4 hex）.
        timestamp:       创建时的单调时间戳（time.time()，用于审计排序）.
        messages:        发给 LLM 的消息列表（深拷贝）.
        tools:           发给 LLM 的工具定义列表（深拷贝）.
        system_prompt:   系统提示词.
        model_hint:      模型标识（可选，不影响 checksum 语义但参与序列化）.
        tool_call_ids:   本次请求关联的 tool_call ID 列表（若有）.
        created_at_iso:  UTC ISO 8601 创建时间.
        checksum:        对规范化 JSON 的 sha256，作为内容指纹.
    """

    request_id: str
    timestamp: float
    messages: list[dict]
    tools: list[dict]
    system_prompt: str
    model_hint: Optional[str] = None
    tool_call_ids: list[str] = field(default_factory=list)
    created_at_iso: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        """dataclass 初始化后：深拷贝 messages/tools，补齐 checksum/时间戳.

        深拷贝保证 checkpoint 持有独立副本，外部后续修改原 messages/tools
        不会污染快照（崩溃恢复的前提：快照必须不可变）.
        """
        # 深拷贝隔离：dataclass 字段默认是引用赋值，这里强制复制
        self.messages = copy.deepcopy(self.messages)
        self.tools = copy.deepcopy(self.tools)
        if not self.created_at_iso:
            self.created_at_iso = _utc_now_iso()
        if not self.checksum:
            self.checksum = _compute_checksum(
                self.messages,
                self.tools,
                self.system_prompt,
                self.model_hint,
            )

    # ── JSON 往返 ────────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化为纯 JSON 兼容字典.

        深拷贝 messages/tools 防止外部修改影响快照.
        """
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "messages": copy.deepcopy(self.messages),
            "tools": copy.deepcopy(self.tools),
            "system_prompt": self.system_prompt,
            "model_hint": self.model_hint,
            "tool_call_ids": list(self.tool_call_ids),
            "created_at_iso": self.created_at_iso,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RequestCheckpoint":
        """从纯字典反序列化.

        重新计算 checksum 并与持久化的 checksum 比对；若不一致，说明
        持久化数据已损坏或被篡改，仍然构造对象但 checksum 以重算结果为准，
        调用方可通过 ``matches()`` 检测异常.
        """
        messages = copy.deepcopy(d.get("messages", []))
        tools = copy.deepcopy(d.get("tools", []))
        system_prompt = d.get("system_prompt", "")
        model_hint = d.get("model_hint")
        recomputed = _compute_checksum(
            messages, tools, system_prompt, model_hint
        )
        return cls(
            request_id=d.get("request_id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", 0.0),
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            model_hint=model_hint,
            tool_call_ids=list(d.get("tool_call_ids", [])),
            created_at_iso=d.get("created_at_iso", _utc_now_iso()),
            checksum=recomputed,
        )

    def reconstruct(self) -> "RequestCheckpoint":
        """模拟崩溃恢复：to_dict → from_dict，返回重建后的新对象.

        用于发送前自检——如果重建后的 checksum 与原对象一致，说明请求
        可被完整、无损地持久化和重放.
        """
        return self.__class__.from_dict(self.to_dict())

    def matches(self, other: "RequestCheckpoint") -> bool:
        """两个 checkpoint 是否逻辑一致（checksum 相等即可）.

        checksum 已经覆盖 messages + tools + system_prompt + model_hint，
        是内容一致性的充分必要条件。request_id / timestamp / created_at_iso
        属于元数据，不参与一致性判断（每次重建都会重新生成这些字段）.
        """
        if not isinstance(other, RequestCheckpoint):
            return False
        return self.checksum == other.checksum


# ═══════════════════════════════════════════════════════════════
#  重建校验器
# ═══════════════════════════════════════════════════════════════


def _find_unserializable_path(obj: Any, path: str = "") -> Optional[str]:
    """递归查找第一个不可 JSON 序列化的对象，返回其字段路径.

    用于在 :class:`RequestNotReconstructableError` 中给出精确的定位信息.
    只做"尽力而为"的探测，不保证 100% 覆盖（例如某些自定义 __getattr__
    可能导致误报），但对常见的 dict/list 嵌套结构足够可靠.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else str(k)
            found = _find_unserializable_path(v, sub)
            if found is not None:
                return found
        return None
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            sub = f"{path}[{i}]"
            found = _find_unserializable_path(v, sub)
            if found is not None:
                return found
        return None
    # tuple / set 等也可能可被 json 处理（tuple → list, set 不行）
    if isinstance(obj, tuple):
        for i, v in enumerate(obj):
            sub = f"{path}[{i}]"
            found = _find_unserializable_path(v, sub)
            if found is not None:
                return found
        return None
    # 其他类型直接标记为不可序列化
    return path or "<root>"


class RequestReconstructionValidator:
    """发送前的请求重建校验器.

    用法::

        validator = RequestReconstructionValidator()
        checkpoint = validator.validate(messages, tools, system_prompt)
        # checkpoint 可持久化，崩溃后用 from_dict 重建

    校验流程：
        1. 尝试 json.dumps 整个请求，检测不可序列化对象；
        2. 构造 :class:`RequestCheckpoint`；
        3. 调用 ``checkpoint.reconstruct()`` 做 to_dict → from_dict 往返；
        4. 用 ``matches()`` 比对 checksum；
        5. 任一步骤失败抛 :class:`RequestNotReconstructableError`.

    线程安全：本类无状态（除配置外），可在多个协程/线程间共享.
    """

    def validate(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        model_hint: Optional[str] = None,
        tool_call_ids: Optional[list[str]] = None,
    ) -> RequestCheckpoint:
        """校验请求可重建性，返回通过校验的 checkpoint.

        Args:
            messages:      发给 LLM 的消息列表.
            tools:         工具定义列表.
            system_prompt: 系统提示词.
            model_hint:    模型标识（可选）.
            tool_call_ids: 关联的 tool_call ID 列表（可选，仅审计用）.

        Returns:
            通过重建校验的 :class:`RequestCheckpoint`.

        Raises:
            RequestNotReconstructableError: 不可序列化或重建后 checksum 不一致.
        """
        # ── ① 预检查：尝试 json.dumps，精确定位不可序列化字段 ──
        probe_payload = {
            "messages": messages,
            "tools": tools,
            "system_prompt": system_prompt,
            "model_hint": model_hint,
        }
        try:
            _canonical_json(probe_payload)
        except (TypeError, ValueError) as e:
            # 尝试定位具体字段路径
            bad_path = _find_unserializable_path(probe_payload)
            raise RequestNotReconstructableError(
                reason=f"Request contains non-JSON-serializable object: {e}",
                field_path=bad_path,
            ) from e

        # ── ② 构造 checkpoint（深拷贝 + 计算 checksum）────────
        checkpoint = RequestCheckpoint(
            request_id=uuid.uuid4().hex,
            timestamp=_now_ts(),
            messages=copy.deepcopy(messages),
            tools=copy.deepcopy(tools),
            system_prompt=system_prompt,
            model_hint=model_hint,
            tool_call_ids=list(tool_call_ids or []),
        )

        # ── ③ 模拟崩溃重建：to_dict → from_dict ──────────────
        try:
            rebuilt = checkpoint.reconstruct()
        except Exception as e:
            raise RequestNotReconstructableError(
                reason=f"Checkpoint reconstruction failed: {e}",
                field_path=None,
            ) from e

        # ── ④ 比对 checksum ──────────────────────────────────
        if not checkpoint.matches(rebuilt):
            raise RequestNotReconstructableError(
                reason=(
                    "Checkpoint checksum mismatch after round-trip "
                    f"(original={checkpoint.checksum[:12]}..., "
                    f"rebuilt={rebuilt.checksum[:12]}...)"
                ),
                field_path=None,
            )

        return checkpoint


def _now_ts() -> float:
    """返回当前 Unix 时间戳（秒，浮点）.

    独立成函数便于测试 monkeypatch.
    """
    import time

    return time.time()


__all__ = [
    "RequestCheckpoint",
    "RequestReconstructionValidator",
    "RequestNotReconstructableError",
]
