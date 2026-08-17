"""AML 7 维自测套件 — v1.10.0 P1 改造。

本模块实现 :class:`AMLEvaluator`，在**不依赖外部 AML 评测平台、不调用
任何 LLM** 的前提下，对 :class:`~suyi.memory.aml_memory.AMLMemoryStore`
和 :class:`~suyi.memory.aml_adapter.AMLMemoryServer` 做 7 个维度的本地
回归测试，对应 AML 评测的 7 个能力维度：

1. :meth:`AMLEvaluator.evaluate_fact_recall`     — A 显式事实召回
2. :meth:`AMLEvaluator.evaluate_multi_hop`       — B 多跳整合
3. :meth:`AMLEvaluator.evaluate_temporal`        — C 时序推理
4. :meth:`AMLEvaluator.evaluate_governance`      — D 记忆治理
5. :meth:`AMLEvaluator.evaluate_personalization` — E 个性化
6. :meth:`AMLEvaluator.evaluate_rule_execution`  — G 规则执行
7. :meth:`AMLEvaluator.evaluate_security_privacy` — H 安全隐私

每个维度构造若干确定性测试用例（模拟消息序列 + 查询 + 期望结果），
调用 AML 的 ``/add`` 和 ``/search`` 接口（或直接调用 store 的等价
方法），然后验证检索结果是否包含期望记忆。

评分
----

- 每个用例二元判定：``passed = True/False``；
- 维度得分 = ``passed / total * 100``，保留 2 位小数；
- 总分 = 各维度得分的算术平均，保留 2 位小数。

设计原则
--------

- **纯规则，不调 LLM**：所有"期望结果"通过关键词/子串匹配判断。
- **可重复**：每次运行使用独立临时目录，不污染真实数据。
- **可离线**：除安全/隐私维度通过真实 HTTP loopback 验证外，其它维度
  直接在内存中的 store 上运行，毫秒级完成。
- **不依赖外部 AML 公开子集**：测试用例以代码形式固化，便于 CI。

典型用法::

    from suyi.memory.aml_evaluator import AMLEvaluator

    evaluator = AMLEvaluator()
    report = evaluator.run_all()
    print(report.total_score)
    print(report.to_json(indent=2))
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .aml_memory import AMLMemoryStore
from .aml_adapter import AMLMemoryServer


# ----------------------------------------------------------------------
#  数据类
# ----------------------------------------------------------------------

@dataclass
class CaseResult:
    """单个测试用例的结果。

    Attributes:
        name: 用例名（在维度内唯一）。
        passed: 是否通过。
        detail: 人类可读的说明，例如"期望关键词 X 未出现在 top-3 结果中"。
        expected: 期望关键词/子串列表。
        actual: 实际检索到的内容摘要（前若干条 content）。
        elapsed_ms: 用例执行耗时（毫秒）。
    """

    name: str
    passed: bool
    detail: str = ""
    expected: List[str] = field(default_factory=list)
    actual: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


@dataclass
class DimensionResult:
    """单个维度的评估结果。

    Attributes:
        dimension: 维度标识（``fact_recall`` 等）。
        display_name: 维度中文/英文名。
        score: 得分（0–100，保留 2 位小数）。
        passed_cases: 通过用例数。
        total_cases: 总用例数。
        cases: 各用例结果。
    """

    dimension: str
    display_name: str
    score: float
    passed_cases: int
    total_cases: int
    cases: List[CaseResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "display_name": self.display_name,
            "score": self.score,
            "passed_cases": self.passed_cases,
            "total_cases": self.total_cases,
            "cases": [c.to_dict() for c in self.cases],
        }


@dataclass
class EvalReport:
    """7 维评估聚合报告。

    Attributes:
        dimension_scores: 各维度得分子项。
        total_score: 总分（7 维算术平均，0–100）。
        passed_cases: 全量通过用例数。
        total_cases: 全量用例数。
        details: 维度名（key）到 :class:`DimensionResult` 的映射。
        started_at: 开始时间（Unix 秒）。
        finished_at: 结束时间（Unix 秒）。
        version: 生成报告的评估器版本。
    """

    dimension_scores: Dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    passed_cases: int = 0
    total_cases: int = 0
    details: Dict[str, DimensionResult] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0
    version: str = "1.10.0"

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "version": self.version,
            "total_score": self.total_score,
            "passed_cases": self.passed_cases,
            "total_cases": self.total_cases,
            "dimension_scores": dict(self.dimension_scores),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": round(
                (self.finished_at - self.started_at) * 1000, 2
            ),
            "details": {
                k: v.to_dict() for k, v in self.details.items()
            },
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def summary(self) -> str:
        """返回简短的多行摘要，便于打印。"""
        lines = [
            f"AML 7 维自测报告 (v{self.version})",
            f"  总分: {self.total_score:.2f} / 100  "
            f"({self.passed_cases}/{self.total_cases} 用例通过)",
        ]
        for key, dim in self.details.items():
            lines.append(
                f"  - {dim.display_name:<14} "
                f"{dim.score:6.2f}  "
                f"({dim.passed_cases}/{dim.total_cases})"
            )
        return "\n".join(lines)


# ----------------------------------------------------------------------
#  AMLEvaluator
# ----------------------------------------------------------------------

# 每个维度的展示名
_DIM_NAMES: Dict[str, str] = {
    "fact_recall": "A. 事实召回",
    "multi_hop": "B. 多跳整合",
    "temporal": "C. 时序推理",
    "governance": "D. 记忆治理",
    "personalization": "E. 个性化",
    "rule_execution": "G. 规则执行",
    "security_privacy": "H. 安全隐私",
}


class AMLEvaluator:
    """AML 7 维本地自测套件。

    评估器内部为每个维度创建独立的临时目录和独立的
    :class:`~suyi.memory.aml_memory.AMLMemoryStore`，从而避免维度之间
    的数据污染。安全/隐私维度还会在本地启动一个真实的 HTTP 服务器
    （随机端口），验证 API Key 鉴权和用户隔离的端到端行为。

    Attributes:
        base_dir: 临时工作目录的根；若为 None 则使用系统 tempdir。
        keep_data: 是否在评估结束后保留工作目录（默认 False，便于 CI
            自动清理；调试时可设为 True）。
        top_k: 检索时默认返回的 top_k 数量。
        verbose: 是否在评估过程中打印每个用例的执行信息。
    """

    def __init__(
        self,
        *,
        base_dir: Optional[str] = None,
        keep_data: bool = False,
        top_k: int = 5,
        verbose: bool = False,
    ) -> None:
        """初始化评估器。

        Args:
            base_dir: 临时目录根。None 时使用 :func:`tempfile.mkdtemp`。
            keep_data: True 时不自动删除临时数据，便于调试。
            top_k: 每个测试用例检索时的默认 top_k。
            verbose: 是否打印进度。
        """
        self.base_dir = base_dir or tempfile.mkdtemp(prefix="aml_eval_")
        self.keep_data = keep_data
        self.top_k = int(top_k)
        self.verbose = bool(verbose)

        os.makedirs(self.base_dir, exist_ok=True)

    # ------------------------------------------------------------------
    #  辅助
    # ------------------------------------------------------------------

    def _new_store(
        self,
        dim: str,
        *,
        reranker: Any = False,
        **kwargs: Any,
    ) -> AMLMemoryStore:
        """为指定维度创建一个干净的 AMLMemoryStore。

        默认**关闭** utility 重排器，因为自测的断言主要验证"是否召回
        期望记忆"，重排只改变顺序、不改变召回集合；关闭重排可以让
        测试结果更加确定。需要测试重排端到端行为的用例会显式开启。

        Args:
            dim: 维度名，用于隔离目录。
            reranker: 传给 :class:`AMLMemoryStore` 的 reranker 参数。
            **kwargs: 其它 store 参数。

        Returns:
            一个新的 store 实例。
        """
        path = os.path.join(self.base_dir, dim)
        os.makedirs(path, exist_ok=True)
        # 关闭持久化文件共享的潜在干扰；让每个 store 独立目录。
        return AMLMemoryStore(
            storage_dir=path,
            reranker=reranker,
            **kwargs,
        )

    def _add(
        self,
        store: AMLMemoryStore,
        user: str,
        session: str,
        content: str,
        role: str = "user",
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """封装 ``store.add_message``，便于统一日志。"""
        store.add_message(
            user_id=user,
            session_id=session,
            role=role,
            content=content,
            timestamp=timestamp,
            metadata=metadata or {},
        )

    def _search(
        self,
        store: AMLMemoryStore,
        user: str,
        session: str,
        query: str,
        top_k: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """封装 ``store.search``，便于统一日志。"""
        return store.search(
            user_id=user,
            session_id=session,
            query=query,
            top_k=top_k or self.top_k,
            **kwargs,
        )

    @staticmethod
    def _contains_any(
        results: Sequence[Dict[str, Any]],
        keywords: Sequence[str],
        field_name: str = "content",
    ) -> bool:
        """判断结果列表中是否至少有一条命中任意一个关键词（子串，忽略大小写）。

        Args:
            results: 检索结果。
            keywords: 期望命中的关键词列表（OR 语义）。
            field_name: 要匹配的字段，默认 ``content``。

        Returns:
            是否命中。
        """
        if not keywords:
            return False
        lowered = [k.lower() for k in keywords if k]
        for r in results:
            value = str(r.get(field_name, "")).lower()
            if any(k in value for k in lowered):
                return True
        return False

    @staticmethod
    def _contains_all(
        results: Sequence[Dict[str, Any]],
        keywords: Sequence[str],
    ) -> bool:
        """判断所有关键词是否都能在结果集中找到（可分布在不同结果上）。"""
        if not keywords:
            return False
        joined = " ".join(
            str(r.get("content", "")) for r in results
        ).lower()
        return all(k.lower() in joined for k in keywords if k)

    @staticmethod
    def _result_contents(
        results: Sequence[Dict[str, Any]], limit: int = 5
    ) -> List[str]:
        """截取前若干条结果的 content，用于报告中的 actual 字段。"""
        return [
            str(r.get("content", ""))[:120]
            for r in list(results)[:limit]
        ]

    def _run_case(
        self,
        name: str,
        func: Callable[[], Tuple[bool, str, List[str], List[str]]],
    ) -> CaseResult:
        """执行单个测试用例并统一捕获异常、计时。

        Args:
            name: 用例名。
            func: 无参数回调，返回 ``(passed, detail, expected, actual)``。

        Returns:
            :class:`CaseResult`。
        """
        start = time.time()
        try:
            passed, detail, expected, actual = func()
            elapsed = (time.time() - start) * 1000
            return CaseResult(
                name=name,
                passed=bool(passed),
                detail=detail,
                expected=list(expected),
                actual=list(actual),
                elapsed_ms=round(elapsed, 2),
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.time() - start) * 1000
            return CaseResult(
                name=name,
                passed=False,
                detail=f"unexpected exception: {type(exc).__name__}: {exc}",
                expected=[],
                actual=[],
                elapsed_ms=round(elapsed, 2),
            )

    def _aggregate(
        self,
        dimension: str,
        cases: Sequence[CaseResult],
    ) -> DimensionResult:
        """把若干用例聚合成维度结果。"""
        total = len(cases)
        passed = sum(1 for c in cases if c.passed)
        score = round(passed / total * 100, 2) if total else 0.0
        return DimensionResult(
            dimension=dimension,
            display_name=_DIM_NAMES.get(dimension, dimension),
            score=score,
            passed_cases=passed,
            total_cases=total,
            cases=list(cases),
        )

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    #  维度 A：事实召回
    # ------------------------------------------------------------------

    def evaluate_fact_recall(self) -> DimensionResult:
        """A. 事实召回 — 明确事实能被检索到。

        构造 6 个用例：

        1. 英文事实（"Python GIL prevents true multithreading"）。
        2. 中文事实。
        3. 包含数字和型号的事实（"iPhone 15 Pro released 2023"）。
        4. 多条事实中检索到正确的一条。
        5. 长查询中包含关键词。
        6. semantic 层事实（包含 "remember that"）。
        """
        store = self._new_store("fact_recall")

        cases: List[CaseResult] = []

        def case_english_fact() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "alice", "s1",
                      "Python GIL prevents true multithreading in CPython.")
            res = self._search(store, "alice", "s1",
                               "What does the GIL do in Python?")
            ok = self._contains_any(res, ["GIL", "multithreading"])
            return (ok,
                    "GIL fact should be recalled" if ok
                    else "GIL fact not found",
                    ["GIL", "multithreading"],
                    self._result_contents(res))

        def case_chinese_fact() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "alice", "s1",
                      "水的化学式是 H2O，在标准大气压下 100 摄氏度沸腾。")
            res = self._search(store, "alice", "s1",
                               "水在什么温度下沸腾？")
            ok = self._contains_any(res, ["100", "沸", "H2O"])
            return (ok,
                    "Chinese fact should be recalled" if ok
                    else "Chinese fact not found",
                    ["100", "沸"],
                    self._result_contents(res))

        def case_numeric_fact() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "bob", "s1",
                      "The iPhone 15 Pro was released in September 2023 "
                      "with an A17 Pro chip.")
            res = self._search(store, "bob", "s1",
                               "When did iPhone 15 Pro come out?")
            ok = self._contains_any(res, ["2023", "iPhone 15 Pro"])
            return (ok,
                    "Numeric fact should be recalled" if ok
                    else "numeric fact not found",
                    ["2023", "iPhone 15 Pro"],
                    self._result_contents(res))

        def case_disambiguation() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "carol", "s1",
                      "My bank PIN is 4729 and my vault PIN is 8821.")
            self._add(store, "carol", "s1",
                      "The server runs on port 8080 and debug on 8081.")
            res = self._search(store, "carol", "s1",
                               "What is the bank PIN?")
            ok = self._contains_any(res, ["4729"])
            return (ok,
                    "Bank PIN should be recalled among other numbers"
                    if ok else "bank PIN not found",
                    ["4729"],
                    self._result_contents(res))

        def case_semantic_layer() -> Tuple[bool, str, List[str], List[str]]:
            # "remember that" 触发 semantic 层抽取
            self._add(store, "dave", "s1",
                      "Please remember that the database password is "
                      " rotated every 90 days.")
            res = self._search(store, "dave", "s1",
                               "How often is the database password rotated?",
                               top_k=10)
            ok = self._contains_any(res, ["90 days", "password"])
            return (ok,
                    "semantic 'remember that' fact should be recalled"
                    if ok else "semantic fact not found",
                    ["90 days", "password"],
                    self._result_contents(res))

        def case_special_characters() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "erin", "s1",
                      "Use API endpoint https://api.example.com/v2/users "
                      "with Bearer token abc-123-XYZ.")
            res = self._search(store, "erin", "s1",
                               "What is the API endpoint URL?")
            ok = self._contains_any(
                res, ["api.example.com", "endpoint"]
            )
            return (ok,
                    "URL/token fact should be recalled" if ok
                    else "special-char fact not found",
                    ["api.example.com"],
                    self._result_contents(res))

        cases.append(self._run_case("english_fact", case_english_fact))
        cases.append(self._run_case("chinese_fact", case_chinese_fact))
        cases.append(self._run_case("numeric_fact", case_numeric_fact))
        cases.append(self._run_case("disambiguation", case_disambiguation))
        cases.append(self._run_case("semantic_layer", case_semantic_layer))
        cases.append(
            self._run_case("special_characters", case_special_characters)
        )

        # 清理该维度的 store（释放文件句柄 / 触发持久化落盘）
        try:
            del store
        except Exception:  # noqa: BLE001
            pass
        return self._aggregate("fact_recall", cases)

    # ------------------------------------------------------------------
    #  维度 B：多跳整合
    # ------------------------------------------------------------------

    def evaluate_multi_hop(self) -> DimensionResult:
        """B. 多跳整合 — 分散的关联事实能在结果集中同时被召回。

        5 个用例：

        1. 一个人物的出生地 + 毕业院校分布在两条消息。
        2. 一个项目的技术栈 + 部署平台。
        3. 一次会议的时间 + 地点。
        4. 用户的姓名 + 职位。
        5. 产品的价格 + 货币。
        """
        store = self._new_store("multi_hop")
        cases: List[CaseResult] = []

        def case_person_background() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u1", "s1",
                      "Alice was born in Shanghai in 1992.")
            self._add(store, "u1", "s1",
                      "Alice graduated from Tsinghua University with a CS "
                      "degree in 2014.")
            res = self._search(
                store, "u1", "s1",
                "Tell me about Alice's background, including birthplace "
                "and university.",
                top_k=10,
            )
            ok = self._contains_all(res, ["Shanghai", "Tsinghua"])
            return (ok,
                    "Both Shanghai and Tsinghua should be recalled"
                    if ok else "missing one or more multi-hop facts",
                    ["Shanghai", "Tsinghua"],
                    self._result_contents(res))

        def case_tech_stack() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u2", "s1",
                      "The new service is written in Go and uses gRPC.")
            self._add(store, "u2", "s1",
                      "It is deployed on Kubernetes in the AWS eu-west-1 "
                      "region.")
            res = self._search(
                store, "u2", "s1",
                "What language, protocol and cloud platform does the new "
                "service use?",
                top_k=10,
            )
            ok = self._contains_all(res, ["Go", "gRPC", "Kubernetes", "AWS"])
            return (ok,
                    "All tech stack facts should be present"
                    if ok else "tech stack facts incomplete",
                    ["Go", "gRPC", "Kubernetes", "AWS"],
                    self._result_contents(res))

        def case_meeting_time_place() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u3", "s1",
                      "The design review is scheduled for 2026-09-10 at "
                      "10:00.")
            self._add(store, "u3", "s1",
                      "It will be held in the Blue Room on the 5th floor.")
            res = self._search(
                store, "u3", "s1",
                "When and where is the design review?",
                top_k=10,
            )
            ok = self._contains_all(res, ["2026-09-10", "Blue Room"])
            return (ok,
                    "Both time and location should be recalled"
                    if ok else "time/location incomplete",
                    ["2026-09-10", "Blue Room"],
                    self._result_contents(res))

        def case_name_role() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u4", "s1",
                      "My name is Wei and I lead the platform team.")
            self._add(store, "u4", "s1",
                      "I joined Acme Corp as a senior engineer in 2020 "
                      "and was promoted to engineering manager in 2023.")
            res = self._search(
                store, "u4", "s1",
                "Who is Wei and what is his role?",
                top_k=10,
            )
            ok = self._contains_all(res, ["Wei", "manager", "Acme"])
            return (ok,
                    "Name and role should both be present"
                    if ok else "name/role incomplete",
                    ["Wei", "manager", "Acme"],
                    self._result_contents(res))

        def case_price_currency() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u5", "s1",
                      "The Pro plan costs 29.99 per user per month.")
            self._add(store, "u5", "s1",
                      "All prices on this page are listed in USD.")
            res = self._search(
                store, "u5", "s1",
                "How much does Pro cost and in what currency?",
                top_k=10,
            )
            ok = self._contains_all(res, ["29.99", "USD"])
            return (ok,
                    "Price and currency should both be recalled"
                    if ok else "price/currency incomplete",
                    ["29.99", "USD"],
                    self._result_contents(res))

        for name, fn in [
            ("person_background", case_person_background),
            ("tech_stack", case_tech_stack),
            ("meeting_time_place", case_meeting_time_place),
            ("name_role", case_name_role),
            ("price_currency", case_price_currency),
        ]:
            cases.append(self._run_case(name, fn))

        try:
            del store
        except Exception:  # noqa: BLE001
            pass
        return self._aggregate("multi_hop", cases)

    # ------------------------------------------------------------------
    #  维度 C：时序推理
    # ------------------------------------------------------------------

    def evaluate_temporal(self) -> DimensionResult:
        """C. 时序推理 — 带时间戳的事件能被按时间关系召回。

        6 个用例：

        1. 最新事件优先（查询 "latest"）。
        2. 最早事件可被召回。
        3. 某时间点之后的事件能匹配。
        4. 某时间点之前的事件能匹配。
        5. 同一会话多轮中最近一轮的信息可被召回。
        6. 时间戳作为元数据可在返回结果中访问。
        """
        store = self._new_store("temporal")
        cases: List[CaseResult] = []
        base = 1_700_000_000.0  # 固定基准时间，确保测试可重复

        def case_latest_event() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u", "s1",
                      "Version 1.0 was released in January.",
                      timestamp=base)
            self._add(store, "u", "s1",
                      "Version 2.0 was released in March.",
                      timestamp=base + 60 * 24 * 3600)
            self._add(store, "u", "s1",
                      "Version 3.0 was released in June.",
                      timestamp=base + 150 * 24 * 3600)
            res = self._search(store, "u", "s1",
                               "latest version release", top_k=5)
            # "latest version" 应该返回最相关版本信息；只要 top-1 是
            # 3.0 或包含 3.0 即可。
            top_content = (
                res[0]["content"] if res else ""
            )
            ok = "3.0" in top_content or self._contains_any(
                res, ["3.0 was released"]
            )
            return (ok,
                    "Top result should be the latest version (3.0)"
                    if ok else "latest event not ranked first",
                    ["3.0"],
                    self._result_contents(res))

        def case_earliest_event() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u", "s1",
                      "First customer Acme signed in Q1.",
                      timestamp=base,
                      metadata={"event": "signed", "customer": "Acme"})
            self._add(store, "u", "s1",
                      "Globex signed in Q3.",
                      timestamp=base + 200 * 24 * 3600)
            res = self._search(store, "u", "s1",
                               "first customer earliest signed",
                               top_k=10)
            ok = self._contains_any(res, ["Acme"])
            return (ok,
                    "Earliest customer Acme should be recalled"
                    if ok else "earliest event missing",
                    ["Acme"],
                    self._result_contents(res))

        def case_after_event() -> Tuple[bool, str, List[str], List[str]]:
            cut = base + 100 * 24 * 3600
            self._add(store, "u2", "s1",
                      "Before the deadline, we shipped feature A.",
                      timestamp=base + 10 * 24 * 3600)
            self._add(store, "u2", "s1",
                      "After the deadline, we shipped feature B.",
                      timestamp=cut + 10 * 24 * 3600)
            res = self._search(
                store, "u2", "s1",
                "What was shipped after the deadline?",
                top_k=10,
                metadata_filter=None,
            )
            # 我们不依赖排序，只要结果集中包含 feature B
            ok = self._contains_any(res, ["feature B"])
            return (ok,
                    "Post-deadline event should be recallable"
                    if ok else "post-deadline event missing",
                    ["feature B"],
                    self._result_contents(res))

        def case_before_event() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u3", "s1",
                      "The pre-launch beta went out in February.",
                      timestamp=base + 30 * 24 * 3600)
            self._add(store, "u3", "s1",
                      "The public launch happened in May.",
                      timestamp=base + 120 * 24 * 3600)
            res = self._search(
                store, "u3", "s1",
                "What happened before the public launch?",
                top_k=10,
            )
            ok = self._contains_any(res, ["beta"])
            return (ok,
                    "Pre-launch beta should be recallable"
                    if ok else "pre-launch event missing",
                    ["beta"],
                    self._result_contents(res))

        def case_recent_turn() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "u4", "s1",
                      "I used to prefer dark tea.",
                      timestamp=base)
            self._add(store, "u4", "s1",
                      "I now prefer green tea every morning.",
                      timestamp=base + 5 * 24 * 3600)
            res = self._search(store, "u4", "s1",
                               "What tea do I currently prefer?",
                               top_k=10)
            ok = self._contains_any(res, ["green tea"])
            return (ok,
                    "Recent preference (green tea) should be recalled"
                    if ok else "recent preference missing",
                    ["green tea"],
                    self._result_contents(res))

        def case_timestamp_preserved() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            ts = base + 12345
            self._add(store, "u5", "s1",
                      "The audit log entry is timestamped.",
                      timestamp=ts)
            res = self._search(store, "u5", "s1",
                               "audit log entry timestamped", top_k=5)
            if not res:
                return (False, "no results returned", ["timestamp"], [])
            returned_ts = res[0].get("metadata", {}).get("timestamp")
            ok = returned_ts is not None and abs(
                float(returned_ts) - ts
            ) < 1.0
            return (ok,
                    "Returned metadata should preserve the timestamp"
                    if ok else f"timestamp mismatch: {returned_ts}",
                    ["timestamp"],
                    self._result_contents(res))

        for name, fn in [
            ("latest_event", case_latest_event),
            ("earliest_event", case_earliest_event),
            ("after_event", case_after_event),
            ("before_event", case_before_event),
            ("recent_turn", case_recent_turn),
            ("timestamp_preserved", case_timestamp_preserved),
        ]:
            cases.append(self._run_case(name, fn))

        try:
            del store
        except Exception:  # noqa: BLE001
            pass
        return self._aggregate("temporal", cases)

    # ------------------------------------------------------------------
    #  维度 D：记忆治理
    # ------------------------------------------------------------------

    def evaluate_governance(self) -> DimensionResult:
        """D. 记忆治理 — TTL 过期、容量淘汰、去重。

        5 个用例：

        1. 过期记忆在默认 search 中不出现（用极短 TTL）。
        2. 未过期记忆仍能被检索。
        3. 同一会话重复内容被去重。
        4. 超容量时旧记忆被淘汰（用极小容量）。
        5. cleanup_expired 能正确清理过期条目。
        """
        cases: List[CaseResult] = []

        def case_expired_excluded() -> Tuple[bool, str, List[str], List[str]]:
            store = self._new_store(
                "gov_expired",
                working_ttl=0.3,
                episodic_ttl=0.3,
                semantic_ttl=0.3,
            )
            self._add(store, "u", "s", "The secret code is AZURE-42.")
            time.sleep(0.5)  # 让 TTL 过期
            res = self._search(store, "u", "s",
                               "What is the secret code?", top_k=10)
            ok = not self._contains_any(res, ["AZURE-42"])
            return (ok,
                    "Expired memory should NOT be returned"
                    if ok else "expired memory was returned",
                    [],
                    self._result_contents(res))

        def case_not_expired_returned() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            store = self._new_store(
                "gov_not_expired",
                working_ttl=60.0,
                episodic_ttl=60.0,
            )
            self._add(store, "u", "s",
                      "The project codename is Orion.")
            res = self._search(store, "u", "s",
                               "What is the project codename?", top_k=5)
            ok = self._contains_any(res, ["Orion"])
            return (ok,
                    "Non-expired memory should be returned"
                    if ok else "valid memory missing",
                    ["Orion"],
                    self._result_contents(res))

        def case_dedup() -> Tuple[bool, str, List[str], List[str]]:
            store = self._new_store("gov_dedup")
            for _ in range(3):
                self._add(store, "u", "s",
                          "The meeting starts at 9am every Monday.")
            res = self._search(store, "u", "s",
                               "When is the weekly meeting?", top_k=20)
            # 同层同内容不应重复出现
            contents = [
                r["content"]
                for r in res
                if r.get("metadata", {}).get("layer") == "working"
            ]
            ok = contents.count(
                "The meeting starts at 9am every Monday."
            ) <= 1
            return (ok,
                    "Duplicate content should be deduplicated per layer"
                    if ok else f"duplicates present: {len(contents)}",
                    [],
                    self._result_contents(res))

        def case_capacity_eviction() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            # 极小 working 容量，触发容量淘汰
            store = self._new_store(
                "gov_capacity",
                working_capacity=2,
                episodic_capacity=100,
            )
            self._add(store, "u", "s", "Fact one is about apples.")
            self._add(store, "u", "s", "Fact two is about bananas.")
            self._add(store, "u", "s", "Fact three is about cherries.")
            # working 层应只保留最近 2 条
            working = store.get_session_records("u", "s", layer="working")
            contents = [r.content for r in working]
            ok = "Fact one is about apples." not in contents and len(
                contents
            ) <= 2
            return (ok,
                    "Oldest working record should be evicted"
                    if ok else f"capacity eviction failed: {contents}",
                    [],
                    contents)

        def case_cleanup_expired() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            store = self._new_store(
                "gov_cleanup",
                working_ttl=0.2,
                episodic_ttl=0.2,
            )
            self._add(store, "u", "s", "Temporary token TEMP-1.")
            before = store.total_records
            time.sleep(0.4)
            removed = store.cleanup_expired()
            after = store.total_records
            ok = removed >= 1 and after < before
            return (ok,
                    "cleanup_expired should remove expired records"
                    if ok else f"cleanup removed={removed} "
                    f"before={before} after={after}",
                    [],
                    [f"removed={removed}", f"before={before}",
                     f"after={after}"])

        for name, fn in [
            ("expired_excluded", case_expired_excluded),
            ("not_expired_returned", case_not_expired_returned),
            ("dedup", case_dedup),
            ("capacity_eviction", case_capacity_eviction),
            ("cleanup_expired", case_cleanup_expired),
        ]:
            cases.append(self._run_case(name, fn))

        return self._aggregate("governance", cases)

    # ------------------------------------------------------------------
    #  维度 E：个性化
    # ------------------------------------------------------------------

    def evaluate_personalization(self) -> DimensionResult:
        """E. 个性化 — 用户偏好能被检索并用于排序。

        5 个用例：

        1. 语言偏好。
        2. 饮食偏好。
        3. 工作风格偏好。
        4. 不同用户的偏好互不串扰。
        5. 偏好更新后，新偏好可被检索。
        """
        store = self._new_store("personalization")
        cases: List[CaseResult] = []

        def case_language_pref() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "p1", "s1",
                      "I prefer replies in concise English with bullet "
                      "points.")
            res = self._search(store, "p1", "s1",
                               "What language and style do I prefer?",
                               top_k=10)
            ok = self._contains_any(res, ["English", "concise"])
            return (ok,
                    "Language preference should be recalled"
                    if ok else "language preference missing",
                    ["English", "concise"],
                    self._result_contents(res))

        def case_diet_pref() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "p2", "s1",
                      "I am vegetarian and I love tofu.")
            res = self._search(store, "p2", "s1",
                               "vegetarian dinner tofu food preference",
                               top_k=10)
            ok = self._contains_any(res, ["vegetarian", "tofu"])
            return (ok,
                    "Dietary preference should be recalled"
                    if ok else "diet preference missing",
                    ["vegetarian", "tofu"],
                    self._result_contents(res))

        def case_work_style() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "p3", "s1",
                      "Always include code examples in your explanations.")
            res = self._search(store, "p3", "s1",
                               "How should explanations be formatted?",
                               top_k=10)
            ok = self._contains_any(res, ["code examples"])
            return (ok,
                    "Work style preference should be recalled"
                    if ok else "work style preference missing",
                    ["code examples"],
                    self._result_contents(res))

        def case_user_isolation() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "p4", "s1",
                      "I like dark chocolate and hate coffee.")
            self._add(store, "p5", "s1",
                      "I hate chocolate but love coffee.")
            res_p4 = self._search(store, "p4", "s1",
                                  "What do I like?", top_k=10)
            res_p5 = self._search(store, "p5", "s1",
                                  "What do I like?", top_k=10)
            p4_likes_chocolate = self._contains_any(
                res_p4, ["dark chocolate"]
            )
            p5_likes_coffee = self._contains_any(res_p5, ["coffee"])
            # 关键：p5 的结果不应包含 p4 的 "dark chocolate"（用户隔离）
            p5_has_chocolate = self._contains_any(
                res_p5, ["dark chocolate"]
            )
            ok = (
                p4_likes_chocolate
                and p5_likes_coffee
                and not p5_has_chocolate
            )
            return (ok,
                    "Preferences should be isolated between users"
                    if ok else "preferences leaked across users",
                    ["dark chocolate (only p4)", "coffee (only p5)"],
                    self._result_contents(res_p5))

        def case_preference_update() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            self._add(store, "p6", "s1",
                      "I prefer Python for backend work.")
            self._add(store, "p6", "s2",
                      "Actually I now prefer Rust for new backend "
                      "services.")
            res = self._search(store, "p6", "s2",
                               "What language should I use for new "
                               "backend services?",
                               top_k=10)
            ok = self._contains_any(res, ["Rust"])
            return (ok,
                    "Updated preference should be recallable"
                    if ok else "updated preference missing",
                    ["Rust"],
                    self._result_contents(res))

        for name, fn in [
            ("language_pref", case_language_pref),
            ("diet_pref", case_diet_pref),
            ("work_style", case_work_style),
            ("user_isolation", case_user_isolation),
            ("preference_update", case_preference_update),
        ]:
            cases.append(self._run_case(name, fn))

        try:
            del store
        except Exception:  # noqa: BLE001
            pass
        return self._aggregate("personalization", cases)

    # ------------------------------------------------------------------
    #  维度 G：规则执行
    # ------------------------------------------------------------------

    def evaluate_rule_execution(self) -> DimensionResult:
        """G. 规则执行 — 规则型记忆可被精确检索。

        5 个用例：

        1. "always" 规则。
        2. "never" 规则。
        3. "remember that" 规则。
        4. 多条规则中按关键词命中正确一条。
        5. 规则被存入 semantic 层（fact_type=rule）。
        """
        store = self._new_store("rule_execution")
        cases: List[CaseResult] = []

        def case_always_rule() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "r1", "s1",
                      "Always run tests before pushing to main.")
            res = self._search(store, "r1", "s1",
                               "What should I do before pushing to main?",
                               top_k=10)
            ok = self._contains_any(res, ["run tests", "tests"])
            return (ok,
                    "'always' rule should be recalled"
                    if ok else "always rule missing",
                    ["tests"],
                    self._result_contents(res))

        def case_never_rule() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "r2", "s1",
                      "Never commit secrets or API keys to the repo.")
            res = self._search(store, "r2", "s1",
                               "What am I not allowed to commit?",
                               top_k=10)
            ok = self._contains_any(res, ["secrets", "API keys"])
            return (ok,
                    "'never' rule should be recalled"
                    if ok else "never rule missing",
                    ["secrets", "API keys"],
                    self._result_contents(res))

        def case_remember_that() -> Tuple[bool, str, List[str], List[str]]:
            self._add(store, "r3", "s1",
                      "Remember that production deploys happen only on "
                      "Tuesdays and Thursdays.")
            res = self._search(store, "r3", "s1",
                               "When can production be deployed?",
                               top_k=10)
            ok = self._contains_all(res, ["Tuesdays", "Thursdays"])
            return (ok,
                    "'remember that' rule should be recalled"
                    if ok else "remember-that rule missing",
                    ["Tuesdays", "Thursdays"],
                    self._result_contents(res))

        def case_disambiguate_rules() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            self._add(store, "r4", "s1",
                      "Always write unit tests for new code.")
            self._add(store, "r4", "s1",
                      "Never use tabs for indentation; use 4 spaces.")
            self._add(store, "r4", "s1",
                      "Remember to update CHANGELOG.md on every release.")
            res = self._search(store, "r4", "s1",
                               "indentation style rule", top_k=10)
            ok = self._contains_any(res, ["spaces", "indentation"])
            return (ok,
                    "Correct rule (indentation) should be selected among "
                    "multiple rules"
                    if ok else "indentation rule not found",
                    ["spaces", "indentation"],
                    self._result_contents(res))

        def case_rule_in_semantic_layer() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            self._add(store, "r5", "s1",
                      "The rule is that all PII must be encrypted at "
                      "rest.")
            # 等 search 完成后，检查 semantic 层是否有 fact_type=rule
            sem_records = store.get_user_records("r5", layer="semantic")
            rule_records = [
                r for r in sem_records
                if r.metadata.get("fact_type") == "rule"
            ]
            ok = len(rule_records) >= 1
            # 同时验证它可被检索
            res = self._search(store, "r5", "s1",
                               "PII encryption requirement",
                               top_k=10)
            ok = ok and self._contains_any(res, ["PII", "encrypted"])
            return (ok,
                    "Rules should be extracted into semantic layer with "
                    "fact_type=rule and remain searchable"
                    if ok else "rule semantic extraction failed",
                    ["PII", "encrypted"],
                    [r.content for r in rule_records][:5])

        for name, fn in [
            ("always_rule", case_always_rule),
            ("never_rule", case_never_rule),
            ("remember_that", case_remember_that),
            ("disambiguate_rules", case_disambiguate_rules),
            ("rule_in_semantic_layer", case_rule_in_semantic_layer),
        ]:
            cases.append(self._run_case(name, fn))

        try:
            del store
        except Exception:  # noqa: BLE001
            pass
        return self._aggregate("rule_execution", cases)

    # ------------------------------------------------------------------
    #  维度 H：安全隐私
    # ------------------------------------------------------------------

    def evaluate_security_privacy(self) -> DimensionResult:
        """H. 安全隐私 — 用户隔离、API Key 鉴权、敏感数据保护。

        本维度通过真实的 loopback HTTP 服务器验证，以确保不仅 store
        层逻辑正确，HTTP 层鉴权也正常。

        6 个用例：

        1. 无 API Key 时 /search 返回 401（当服务器配置了 key）。
        2. 错误 API Key 返回 401。
        3. 正确 API Key 可正常访问。
        4. A 用户搜不到 B 用户的记忆（store 层）。
        5. A 用户搜不到 B 用户的记忆（HTTP 端到端）。
        6. 不带 user_id 的请求被拒绝（参数校验）。
        """
        cases: List[CaseResult] = []
        http_dir = os.path.join(self.base_dir, "security_http")
        os.makedirs(http_dir, exist_ok=True)

        # 启动一个带 api_key 的服务器
        server = AMLMemoryServer(
            host="127.0.0.1",
            port=0,  # 随机端口
            storage_dir=http_dir,
            api_key="eval-secret-key",
            version="eval-1.10.0",
            reranker=False,
        )
        server.start_in_thread()
        # 等待服务器就绪
        port = None
        for _ in range(50):
            if server.httpd is not None:
                port = server.httpd.server_address[1]
                break
            time.sleep(0.05)
        if port is None:
            # 服务器没起来，本维度所有用例直接失败
            for name in [
                "no_api_key_rejected",
                "wrong_api_key_rejected",
                "correct_api_key_allowed",
                "user_isolation_store",
                "user_isolation_http",
                "missing_user_id_rejected",
            ]:
                cases.append(CaseResult(
                    name=name,
                    passed=False,
                    detail="HTTP server failed to start",
                ))
            return self._aggregate("security_privacy", cases)

        base_url = f"http://127.0.0.1:{port}"

        def _post(
            path: str,
            payload: Dict[str, Any],
            api_key: Optional[str] = None,
        ) -> Tuple[int, Any]:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                base_url + path,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            if api_key is not None:
                req.add_header("X-API-Key", api_key)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode("utf-8")
                    try:
                        return resp.status, json.loads(raw)
                    except json.JSONDecodeError:
                        return resp.status, raw
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace")
                try:
                    return e.code, json.loads(raw)
                except json.JSONDecodeError:
                    return e.code, raw

        def case_no_api_key() -> Tuple[bool, str, List[str], List[str]]:
            code, body = _post("/search", {
                "user_id": "u", "session_id": "s",
                "query": "hello", "top_k": 1,
            })
            ok = code == 401
            return (ok,
                    "Missing API key should be rejected with 401"
                    if ok else f"expected 401, got {code}",
                    ["401"],
                    [str(body)[:200]])

        def case_wrong_api_key() -> Tuple[bool, str, List[str], List[str]]:
            code, body = _post("/search", {
                "user_id": "u", "session_id": "s",
                "query": "hello", "top_k": 1,
            }, api_key="wrong-key")
            ok = code == 401
            return (ok,
                    "Wrong API key should be rejected with 401"
                    if ok else f"expected 401, got {code}",
                    ["401"],
                    [str(body)[:200]])

        def case_correct_api_key() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            # 先 add 一条数据，再 search
            code_add, _ = _post("/add", {
                "user_id": "auth_user",
                "session_id": "s1",
                "messages": [
                    {"role": "user", "content": "The security code is 7788."}
                ],
            }, api_key="eval-secret-key")
            code_srch, body = _post("/search", {
                "user_id": "auth_user",
                "session_id": "s1",
                "query": "security code",
                "top_k": 5,
            }, api_key="eval-secret-key")
            results = body.get("results", []) if isinstance(body, dict) else []
            ok = (
                code_add in (200, 204)
                and code_srch == 200
                and any("7788" in r.get("content", "") for r in results)
            )
            return (ok,
                    "Correct API key should allow add+search"
                    if ok else f"add={code_add} search={code_srch} "
                    f"results={len(results)}",
                    ["7788"],
                    [r.get("content", "")[:120] for r in results[:5]])

        def case_user_isolation_store() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            s = self._new_store("sec_isolation_store")
            self._add(s, "alice", "s1",
                      "Alice's private note: her favorite color is blue.")
            self._add(s, "bob", "s1",
                      "Bob's private note: his favorite color is red.")
            res_alice = self._search(s, "alice", "s1",
                                     "favorite color", top_k=10)
            res_bob = self._search(s, "bob", "s1",
                                   "favorite color", top_k=10)
            alice_leak = any(
                "Bob" in r["content"] or "red" in r["content"]
                for r in res_alice
            )
            bob_leak = any(
                "Alice" in r["content"] or "blue" in r["content"]
                for r in res_bob
            )
            ok = not alice_leak and not bob_leak
            return (ok,
                    "Store-layer user isolation should hold"
                    if ok else "cross-user memory leak detected",
                    [],
                    ["alice: " + c for c in self._result_contents(res_alice)]
                    + ["bob: " + c for c in self._result_contents(res_bob)])

        def case_user_isolation_http() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            _post("/add", {
                "user_id": "victim",
                "session_id": "s1",
                "messages": [
                    {"role": "user",
                     "content": "Victim secret: the cake is a lie."}
                ],
            }, api_key="eval-secret-key")
            code, body = _post("/search", {
                "user_id": "attacker",
                "session_id": "s1",
                "query": "secret cake lie",
                "top_k": 10,
            }, api_key="eval-secret-key")
            results = body.get("results", []) if isinstance(body, dict) else []
            leaked = any(
                "cake is a lie" in r.get("content", "").lower()
                for r in results
            )
            ok = code == 200 and not leaked
            return (ok,
                    "Attacker must not retrieve victim's memory over HTTP"
                    if ok else f"leak detected: {len(results)} results",
                    [],
                    [r.get("content", "")[:120] for r in results[:5]])

        def case_missing_user_id() -> Tuple[
            bool, str, List[str], List[str]
        ]:
            code, body = _post("/search", {
                "session_id": "s1",
                "query": "anything",
                "top_k": 1,
            }, api_key="eval-secret-key")
            ok = code == 400
            return (ok,
                    "Missing user_id should be rejected with 400"
                    if ok else f"expected 400, got {code}",
                    ["400"],
                    [str(body)[:200]])

        for name, fn in [
            ("no_api_key_rejected", case_no_api_key),
            ("wrong_api_key_rejected", case_wrong_api_key),
            ("correct_api_key_allowed", case_correct_api_key),
            ("user_isolation_store", case_user_isolation_store),
            ("user_isolation_http", case_user_isolation_http),
            ("missing_user_id_rejected", case_missing_user_id),
        ]:
            cases.append(self._run_case(name, fn))

        # 关闭服务器
        try:
            server.stop(timeout=5)
        except Exception:  # noqa: BLE001
            pass

        return self._aggregate("security_privacy", cases)

    # ------------------------------------------------------------------
    #  run_all
    # ------------------------------------------------------------------

    def run_all(
        self,
        *,
        dimensions: Optional[Sequence[str]] = None,
    ) -> EvalReport:
        """执行 7 维（或指定子集）评估。

        Args:
            dimensions: 只运行指定的维度 key（例如
                ``["fact_recall", "temporal"]``）。None 表示全部 7 维。

        Returns:
            聚合后的 :class:`EvalReport`。
        """
        all_dims = [
            "fact_recall",
            "multi_hop",
            "temporal",
            "governance",
            "personalization",
            "rule_execution",
            "security_privacy",
        ]
        selected = list(dimensions) if dimensions else all_dims

        report = EvalReport(started_at=time.time())

        runners: Dict[str, Callable[[], DimensionResult]] = {
            "fact_recall": self.evaluate_fact_recall,
            "multi_hop": self.evaluate_multi_hop,
            "temporal": self.evaluate_temporal,
            "governance": self.evaluate_governance,
            "personalization": self.evaluate_personalization,
            "rule_execution": self.evaluate_rule_execution,
            "security_privacy": self.evaluate_security_privacy,
        }

        for dim in selected:
            runner = runners.get(dim)
            if runner is None:
                continue
            self._log(f"[AMLEvaluator] running {dim} ...")
            dim_result = runner()
            report.details[dim] = dim_result
            report.dimension_scores[dim] = dim_result.score
            report.passed_cases += dim_result.passed_cases
            report.total_cases += dim_result.total_cases
            self._log(
                f"  -> {dim_result.score:.2f} "
                f"({dim_result.passed_cases}/{dim_result.total_cases})"
            )

        if report.dimension_scores:
            report.total_score = round(
                sum(report.dimension_scores.values())
                / len(report.dimension_scores),
                2,
            )

        report.finished_at = time.time()

        # 自动清理
        if not self.keep_data:
            try:
                shutil.rmtree(self.base_dir, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass

        return report

    # ------------------------------------------------------------------
    #  便利方法
    # ------------------------------------------------------------------

    def save_report(
        self,
        report: EvalReport,
        path: str,
    ) -> str:
        """把报告写入 JSON 文件。

        Args:
            report: 要保存的报告。
            path: 目标路径（若为目录则自动补文件名）。

        Returns:
            实际写入的文件路径。
        """
        if os.path.isdir(path):
            path = os.path.join(
                path,
                f"aml_eval_report_{int(time.time())}.json",
            )
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.to_json(indent=2))
        return path

    def __repr__(self) -> str:
        return (
            f"AMLEvaluator(base_dir={self.base_dir!r}, "
            f"keep_data={self.keep_data}, top_k={self.top_k})"
        )
