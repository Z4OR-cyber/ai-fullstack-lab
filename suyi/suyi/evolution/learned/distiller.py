"""正样本蒸馏器 — 从高质量交互记录中提取可复用知识.

SuccessDistiller 从 :class:`~suyi.evolution.learner.InteractionRecord`
中提炼规则：

    - **正样本**（success=True, 0 tool failures, 正面反馈）→
      蒸馏出 ``success_pattern``：记录有效的工具调用序列。
    - **负样本**（success=False 或存在 tool failures）→
      提取 ``failure_lesson``：记录失败的工具与错误信息。
    - **低质量记录**（多次重试/高失败率）不产生成功模式。

默认使用**规则模板**提取，不调用 LLM。接口预留 ``llm_fn`` 注入点，
未来可用 LLM 生成更精炼的自然语言规则。蒸馏出的条目会经过
:class:`~suyi.evolution.learned.dedup.SemanticDeduplicator` 去重后入库，
避免知识库膨胀。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .dedup import DeduplicationResult, SemanticDeduplicator
from .store import KnowledgeEntry, LearnedKnowledgeStore

if TYPE_CHECKING:
    pass


# 任务类型推断关键词表（task 文本/tags → 任务类型标签）
_TASK_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "文件操作": ["file", "read", "write", "文件", "读取", "写入", "目录"],
    "代码执行": ["run", "exec", "code", "bash", "执行", "运行", "命令", "脚本"],
    "搜索检索": ["search", "find", "grep", "搜索", "查找", "检索"],
    "网络请求": ["http", "url", "web", "api", "请求", "网页", "下载"],
    "数据分析": ["data", "csv", "analyze", "分析", "统计", "数据"],
    "代码编写": ["implement", "create", "build", "编写", "实现", "开发", "函数"],
}


@dataclass
class DistillationResult:
    """一次（或批量）蒸馏的统计结果.

    Attributes:
        new_entries: 新增（APPEND）的知识条目列表.
        skipped: 因高度重复被 SKIP 的数量.
        merged: 因中等相似被 MERGE 的数量.
        appended: 追加的新条目数（== len(new_entries)）.
        weak_signals_accumulated: 蒸馏过程中触发的弱信号数（本蒸馏器不直接
            产生弱信号，此字段保留供上层编排统计，默认 0）.
    """

    new_entries: List[KnowledgeEntry] = field(default_factory=list)
    skipped: int = 0
    merged: int = 0
    appended: int = 0
    weak_signals_accumulated: int = 0

    @property
    def total_processed(self) -> int:
        """处理的记录总数（skipped + merged + appended）."""
        return self.skipped + self.merged + self.appended

    def merge(self, other: "DistillationResult") -> None:
        """合并另一个结果的统计（用于批量聚合）."""
        self.new_entries.extend(other.new_entries)
        self.skipped += other.skipped
        self.merged += other.merged
        self.appended += other.appended
        self.weak_signals_accumulated += other.weak_signals_accumulated


class SuccessDistiller:
    """从交互记录中蒸馏成功模式与失败教训.

    Usage::

        store = LearnedKnowledgeStore()
        dedup = SemanticDeduplicator(store)
        distiller = SuccessDistiller(store, dedup)
        result = distiller.distill_from_record(record)
    """

    def __init__(
        self,
        store: LearnedKnowledgeStore,
        deduplicator: SemanticDeduplicator,
        min_confidence: float = 0.3,
        llm_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
    ) -> None:
        """
        Args:
            store: 旁路知识存储.
            deduplicator: 语义去重器.
            min_confidence: 新蒸馏条目的初始置信度下限.
            llm_fn: 可选的 LLM 增强函数，签名
                ``(record_dict) -> refined_content``，用于把规则模板
                内容替换为更精炼的自然语言。默认 None（纯规则）.
        """
        self.store = store
        self.deduplicator = deduplicator
        self.min_confidence = min_confidence
        self.llm_fn = llm_fn

    # ── 单条蒸馏 ─────────────────────────────────────────

    def distill_from_record(self, record: Any) -> DistillationResult:
        """从单条交互记录蒸馏知识.

        判定逻辑：
            - 成功记录（success=True 且无 tool failures）→ success_pattern
            - 失败记录（success=False 或有 tool failures）→ failure_lesson
            - 其他情况返回空结果

        Args:
            record: InteractionRecord（鸭子类型，需有 id/task/tool_calls/
                success/tags/feedback 等字段）.

        Returns:
            :class:`DistillationResult`.
        """
        result = DistillationResult()

        if not self._is_high_quality_success(record):
            # 非高质量成功记录，尝试提取失败教训
            lesson = self.extract_failure_lesson(record)
            if lesson is not None:
                self._add_with_dedup(lesson, result)
            return result

        # 蒸馏成功模式
        entry = self._build_success_pattern(record)
        if entry is not None:
            self._add_with_dedup(entry, result)
        return result

    def extract_failure_lesson(self, record: Any) -> Optional[KnowledgeEntry]:
        """从失败记录提取教训.

        触发条件：success=False 或存在失败的工具调用。

        Args:
            record: 交互记录.

        Returns:
            failure_lesson 条目；记录非失败时返回 None.
        """
        failed_calls = [
            tc for tc in getattr(record, "tool_calls", [])
            if not tc.get("success", True)
        ]
        if getattr(record, "success", False) and not failed_calls:
            return None

        task = getattr(record, "task", "") or ""
        task_type = self._infer_task_type(task, getattr(record, "tags", []))
        bureau = self._extract_bureau(record)

        # 构造失败工具序列与错误信息
        failed_seq: List[str] = []
        error_details: List[str] = []
        for tc in failed_calls:
            name = tc.get("name", "unknown")
            failed_seq.append(name)
            output = tc.get("output_summary", "") or tc.get("error", "")
            if output:
                error_details.append(f"{name}: {output[:120]}")

        if failed_seq:
            tool_part = " -> ".join(failed_seq)
            content = (
                f"对于{task_type}类任务，以下工具调用序列曾导致失败：{tool_part}。"
            )
            if error_details:
                content += " 错误详情：" + "；".join(error_details[:3]) + "。"
            content += f" 应避免该失败路径。（来源 {record.id}）"
            title = f"失败教训：{task_type}任务"
            tags = list({*(getattr(record, "tags", []) or []), "failure", task_type})
        else:
            # success=False 但无明确失败工具：任务整体未完成
            content = (
                f"对于{task_type}类任务，该执行路径未成功完成任务。"
                f"任务描述摘要：{task[:120]}。建议重试或更换策略。（来源 {record.id}）"
            )
            title = f"失败教训：{task_type}任务（未完成）"
            tags = list({*(getattr(record, "tags", []) or []), "failure", task_type})

        # 失败教训置信度：有明确失败工具时更高
        confidence = max(self.min_confidence, 0.5 if failed_seq else 0.35)

        return KnowledgeEntry(
            bureau=bureau,
            category="failure_lesson",
            title=title,
            content=content,
            source_ids=[getattr(record, "id", "unknown")],
            confidence=confidence,
            tags=tags,
        )

    # ── 批量蒸馏 ─────────────────────────────────────────

    def distill_batch(self, records: List[Any]) -> DistillationResult:
        """批量蒸馏，聚合统计.

        Args:
            records: 交互记录列表.

        Returns:
            聚合后的 :class:`DistillationResult`.
        """
        aggregate = DistillationResult()
        for record in records:
            single = self.distill_from_record(record)
            aggregate.merge(single)
        return aggregate

    # ── 内部方法 ──────────────────────────────────────────

    def _is_high_quality_success(self, record: Any) -> bool:
        """判定是否为高质量成功记录.

        条件：success=True，无失败工具调用，且反馈非负面。
        """
        if not getattr(record, "success", False):
            return False

        tool_calls = getattr(record, "tool_calls", []) or []
        if any(not tc.get("success", True) for tc in tool_calls):
            return False

        # 负面反馈的记录不算高质量成功
        feedback = getattr(record, "feedback", None)
        if isinstance(feedback, dict):
            rating = feedback.get("rating")
            signal = feedback.get("signal", 0.0)
            if rating in ("thumbs_down", "down"):
                return False
            try:
                if float(signal) < -0.3:
                    return False
            except (TypeError, ValueError):
                pass

        return True

    def _build_success_pattern(self, record: Any) -> Optional[KnowledgeEntry]:
        """从成功记录构建 success_pattern 条目."""
        tool_calls = getattr(record, "tool_calls", []) or []
        successful_tools = [
            tc.get("name", "unknown")
            for tc in tool_calls
            if tc.get("success", True)
        ]
        if not successful_tools:
            return None

        task = getattr(record, "task", "") or ""
        task_type = self._infer_task_type(task, getattr(record, "tags", []))
        bureau = self._extract_bureau(record)

        tool_seq = " -> ".join(successful_tools)
        context = task[:200]

        if self.llm_fn is not None:
            try:
                content = self.llm_fn({
                    "id": getattr(record, "id", ""),
                    "task": task,
                    "task_type": task_type,
                    "tool_sequence": successful_tools,
                    "context": context,
                })
            except Exception:
                content = self._default_pattern_content(task_type, tool_seq, record.id, context)
        else:
            content = self._default_pattern_content(task_type, tool_seq, record.id, context)

        tags = list({
            *(getattr(record, "tags", []) or []),
            "success",
            task_type,
        })

        # 置信度：工具调用越多/来源越明确，置信度越高，钳制到 [min_conf, 0.9]
        confidence = min(0.9, self.min_confidence + 0.05 * len(successful_tools))

        return KnowledgeEntry(
            bureau=bureau,
            category="success_pattern",
            title=f"成功模式：{task_type}任务",
            content=content,
            source_ids=[getattr(record, "id", "unknown")],
            confidence=confidence,
            tags=tags,
        )

    @staticmethod
    def _default_pattern_content(
        task_type: str, tool_seq: str, record_id: str, context: str
    ) -> str:
        """默认规则模板生成的成功模式正文."""
        parts = [f"对于{task_type}类任务，有效的工具调用顺序为：{tool_seq}。"]
        if context:
            parts.append(f"任务上下文：{context}。")
        parts.append(f"该模式来自 {record_id}。")
        return " ".join(parts)

    @staticmethod
    def _infer_task_type(task: str, tags: Optional[List[str]]) -> str:
        """从 task 文本和 tags 推断任务类型.

        优先使用 tags 中的已知类型，否则按关键词匹配，最后回退到"通用".
        """
        tags = tags or []
        # tags 中若直接含已知类型关键词，优先采用
        for tag in tags:
            for known in _TASK_TYPE_KEYWORDS:
                if tag == known or (isinstance(tag, str) and known in tag):
                    return known

        text = (task or "").lower()
        for task_type, keywords in _TASK_TYPE_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                return task_type
        return "通用"

    @staticmethod
    def _extract_bureau(record: Any) -> str:
        """从记录中提取业务域（bureau），默认 default."""
        bureau = getattr(record, "bureau", None)
        if isinstance(bureau, str) and bureau:
            return bureau
        # 也可从 tags 中寻找 bureau: 前缀
        for tag in getattr(record, "tags", []) or []:
            if isinstance(tag, str) and tag.startswith("bureau:"):
                return tag.split(":", 1)[1]
        return "default"

    def _add_with_dedup(
        self, entry: KnowledgeEntry, result: DistillationResult
    ) -> None:
        """通过去重器将条目入库，并更新结果统计."""
        decision = self.deduplicator.decide(
            new_content=entry.content,
            bureau=entry.bureau,
            category=entry.category,
            new_title=entry.title,
        )
        target_id = self.deduplicator.apply(decision, entry)

        if decision.action == DeduplicationResult.SKIP:
            result.skipped += 1
        elif decision.action == DeduplicationResult.MERGE:
            result.merged += 1
        else:
            result.appended += 1
            stored = self.store.get(target_id) if target_id else None
            if stored is not None:
                result.new_entries.append(stored)
            else:
                result.new_entries.append(entry)
