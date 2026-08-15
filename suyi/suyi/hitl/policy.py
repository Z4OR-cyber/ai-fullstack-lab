"""确认策略 — 决定哪些操作需要人工确认.

策略维度:
    1. 工具名称策略: 指定工具（如 bash/write）需要确认
    2. 参数内容策略: 检测危险参数（如 rm -rf 直接拒绝）
    3. 风险评分策略: 基于 risk score 判断（score > threshold 需确认）
    4. 学习模式: 记录用户确认/拒绝历史，优化策略

策略决策流程:
    1. 检查参数内容策略（hard block 优先）
    2. 检查工具名称策略
    3. 计算风险评分
    4. 参考学习历史
    5. 综合决策
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from .manager import RiskLevel

if TYPE_CHECKING:
    from suyi.tools.parameter_validator import ParameterValidator


# ── 风险评分 ──────────────────────────────────────────────────


@dataclass
class RiskScore:
    """风险评分结果.

    Attributes:
        score:       风险分数（0.0–1.0）.
        level:       风险等级（low/medium/high/critical）.
        factors:     评分因素列表.
        needs_confirm: 是否需要确认.
    """

    score: float = 0.0
    level: str = RiskLevel.LOW
    factors: List[str] = field(default_factory=list)
    needs_confirm: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "score": round(self.score, 4),
            "level": self.level,
            "factors": self.factors,
            "needs_confirm": self.needs_confirm,
        }


# ── 默认策略配置 ──────────────────────────────────────────────

# 默认需要确认的工具
_DEFAULT_CONFIRM_TOOLS: Set[str] = {
    "bash", "write_file", "write", "execute", "shell",
    "subprocess", "system", "rm", "delete",
}

# 默认自动放行的工具
_DEFAULT_AUTO_TOOLS: Set[str] = {
    "read", "read_file", "search", "list", "get", "info",
    "help", "status",
}

# 危险参数模式（直接拒绝）
_HARD_BLOCK_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\brm\s+-rf?\s+/(?:\s|$)", re.I),        # rm -rf /
    re.compile(r"\brm\s+-rf?\s+~", re.I),                 # rm -rf ~
    re.compile(r"\bdd\s+if=/dev/(?:zero|random)", re.I), # dd overwrite
    re.compile(r"\bmkfs\.", re.I),                        # format disk
    re.compile(r">\s*/dev/sda", re.I),                   # overwrite disk
    re.compile(r"\bshutdown\b", re.I),                   # shutdown
    re.compile(r"\breboot\b", re.I),                     # reboot
    re.compile(r"\bhalt\b", re.I),                       # halt
    re.compile(r"\b:\(\)\{.*\};\s*:", re.I),             # fork bomb
]

# 需要确认的参数模式
_CONFIRM_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\brm\s+", re.I),                     # rm command
    re.compile(r"\bchmod\s+\d{3,4}\s+", re.I),       # chmod
    re.compile(r"\bchown\s+", re.I),                 # chown
    re.compile(r"\bsudo\s+", re.I),                  # sudo
    re.compile(r"\bgit\s+push\s+", re.I),             # git push
    re.compile(r"\bcurl\s+.*\|\s*(?:sh|bash)", re.I),# curl | sh
    re.compile(r"\bwget\s+.*\|\s*(?:sh|bash)", re.I),# wget | sh
    re.compile(r">\s*/etc/", re.I),                  # write to /etc
    re.compile(r"\bkill\s+-9\s+", re.I),             # kill -9
    re.compile(r"\bpkill\s+", re.I),                  # pkill
    re.compile(r"\beval\s*\(", re.I),                 # eval
    re.compile(r"\bexec\s*\(", re.I),                 # exec
    re.compile(r"\bos\.system\s*\(", re.I),           # os.system
    re.compile(r"\bsubprocess\.", re.I),              # subprocess
]


# ── 学习历史记录 ──────────────────────────────────────────────


@dataclass
class LearningRecord:
    """用户确认/拒绝历史记录.

    Attributes:
        tool_name:   工具名称.
        operation:   操作描述.
        approved:    是否被批准.
        timestamp:   时间戳.
    """

    tool_name: str = ""
    operation: str = ""
    approved: bool = False
    timestamp: float = 0.0


# ── 确认策略 ──────────────────────────────────────────────────


class HITLPolicy:
    """Human-in-the-loop 确认策略.

    基于四个维度判断操作是否需要人工确认:
        1. 工具名称: 指定工具需要确认
        2. 参数内容: 危险参数直接拒绝或需要确认
        3. 风险评分: 综合评分 > 阈值需要确认
        4. 学习模式: 基于用户历史行为优化

    Args:
        confirm_tools:    需要确认的工具名称集合.
        auto_tools:       自动放行的工具名称集合.
        confirm_threshold: 风险评分阈值（>=此值需要确认）.
        enable_learning:   是否启用学习模式.
        learning_window:   学习历史保留条数.

    使用示例::

        policy = HITLPolicy(confirm_threshold=0.6)

        # 检查是否需要确认
        decision = policy.check("bash", {"command": "rm -rf /tmp"})
        assert decision.action == "block"  # rm -rf / → 直接拒绝

        decision = policy.check("bash", {"command": "ls -la"})
        assert decision.action == "auto"   # ls → 自动放行

        # 学习模式：记录用户决策
        policy.record("bash", "git push", approved=True)
        policy.record("bash", "git push", approved=True)
        # 第三次同类操作自动放行
        decision = policy.check("bash", {"command": "git push"})
        assert decision.action == "auto"  # learned
    """

    def __init__(
        self,
        confirm_tools: Optional[Set[str]] = None,
        auto_tools: Optional[Set[str]] = None,
        confirm_threshold: float = 0.6,
        enable_learning: bool = True,
        learning_window: int = 100,
        parameter_validator: Optional["ParameterValidator"] = None,
    ) -> None:
        self.confirm_tools: Set[str] = (
            confirm_tools or set(_DEFAULT_CONFIRM_TOOLS)
        )
        self.auto_tools: Set[str] = (
            auto_tools or set(_DEFAULT_AUTO_TOOLS)
        )
        self.confirm_threshold: float = confirm_threshold
        self.enable_learning: bool = enable_learning
        self.learning_window: int = learning_window
        # P1 加固：可选的参数安全验证器（None 表示不启用，保持向后兼容）
        self.parameter_validator: Optional["ParameterValidator"] = parameter_validator

        # 学习历史
        self._learning_history: List[LearningRecord] = []
        # 操作签名 → 批准/拒绝统计
        self._approval_stats: Dict[str, Dict[str, int]] = {}

    # ── 策略检查 ──────────────────────────────────────────────

    def check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> "PolicyDecision":
        """检查操作是否需要确认.

        决策流程:
            1. 参数内容策略（hard block 优先）
            2. 工具名称策略
            3. 风险评分
            4. 学习历史

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.

        Returns:
            PolicyDecision.
        """
        # 提取参数中的命令字符串
        command: str = self._extract_command(arguments)

        # 1. 参数内容策略 — hard block
        if command:
            for pattern in _HARD_BLOCK_PATTERNS:
                if pattern.search(command):
                    return PolicyDecision(
                        action="block",
                        reason=f"Dangerous command pattern: {pattern.pattern}",
                        risk_score=RiskScore(
                            score=1.0,
                            level=RiskLevel.CRITICAL,
                            factors=["hard_block_pattern"],
                            needs_confirm=False,
                        ),
                    )

        # 1.5 P1 加固：参数安全验证（路径穿越 / 命令注入 / SSRF / 敏感文件）
        if self.parameter_validator is not None:
            validation = self.parameter_validator.validate(
                tool_name, arguments
            )
            if validation.action == "block":
                return PolicyDecision(
                    action="block",
                    reason=f"Parameter validation failed: {validation.reason}",
                    risk_score=RiskScore(
                        score=1.0,
                        level=RiskLevel.CRITICAL,
                        factors=[
                            f"param_validation:{issue.category}"
                            for issue in validation.issues
                        ],
                        needs_confirm=False,
                    ),
                )

        # 2. 工具名称策略
        tool_lower: str = tool_name.lower()

        # 自动放行
        if tool_lower in self.auto_tools and not command:
            return PolicyDecision(
                action="auto",
                reason=f"Tool '{tool_name}' is in auto-allow list",
                risk_score=RiskScore(
                    score=0.1,
                    level=RiskLevel.LOW,
                    factors=["auto_tool"],
                    needs_confirm=False,
                ),
            )

        # 3. 风险评分
        risk: RiskScore = self._assess_risk(tool_name, command, arguments)

        # 4. 学习历史
        if self.enable_learning:
            learned: Optional[str] = self._check_learning(
                tool_name, command
            )
            if learned == "auto":
                risk.factors.append("learned_auto")
                return PolicyDecision(
                    action="auto",
                    reason="Auto-approved based on user learning history",
                    risk_score=risk,
                )
            elif learned == "block":
                risk.factors.append("learned_block")
                return PolicyDecision(
                    action="block",
                    reason="Blocked based on user learning history",
                    risk_score=risk,
                )

        # 5. 综合决策
        if risk.needs_confirm or tool_lower in self.confirm_tools:
            return PolicyDecision(
                action="confirm",
                reason=(
                    f"Tool '{tool_name}' requires confirmation "
                    f"(risk: {risk.level})"
                ),
                risk_score=risk,
            )

        return PolicyDecision(
            action="auto",
            reason=f"Tool '{tool_name}' is safe to execute",
            risk_score=risk,
        )

    # ── 风险评分 ──────────────────────────────────────────────

    def _assess_risk(
        self,
        tool_name: str,
        command: str,
        arguments: Dict[str, Any],
    ) -> RiskScore:
        """评估操作风险.

        综合考虑工具类型、命令模式、参数内容.

        Args:
            tool_name: 工具名称.
            command: 提取的命令字符串.
            arguments: 原始参数.

        Returns:
            RiskScore.
        """
        score: float = 0.0
        factors: List[str] = []

        # 工具类型评分
        tool_lower: str = tool_name.lower()
        if tool_lower in self.confirm_tools:
            score += 0.3
            factors.append("confirm_tool")
        elif tool_lower in self.auto_tools:
            score += 0.05
            factors.append("auto_tool")
        else:
            score += 0.15
            factors.append("unknown_tool")

        # 命令模式评分
        if command:
            confirm_hits: int = sum(
                1 for p in _CONFIRM_PATTERNS if p.search(command)
            )
            if confirm_hits > 0:
                score += min(0.4 + confirm_hits * 0.1, 0.7)
                factors.append(f"confirm_pattern({confirm_hits})")

        # 参数内容评分
        args_str: str = str(arguments)
        # 检查是否包含敏感路径
        if re.search(r"/etc/|/root/|/var/", args_str):
            score += 0.2
            factors.append("sensitive_path")
        # 检查是否包含网络操作
        if re.search(r"https?://|curl|wget|fetch", args_str, re.I):
            score += 0.1
            factors.append("network_operation")

        # 限制分数范围
        score = min(score, 1.0)

        # 确定风险等级
        level: str = RiskLevel.LOW
        if score >= 0.8:
            level = RiskLevel.CRITICAL
        elif score >= 0.6:
            level = RiskLevel.HIGH
        elif score >= 0.3:
            level = RiskLevel.MEDIUM

        return RiskScore(
            score=score,
            level=level,
            factors=factors,
            needs_confirm=score >= self.confirm_threshold,
        )

    # ── 学习模式 ──────────────────────────────────────────────

    def record(
        self,
        tool_name: str,
        operation: str,
        approved: bool,
    ) -> None:
        """记录用户确认/拒绝决策.

        用于学习模式，优化后续策略.

        Args:
            tool_name: 工具名称.
            operation: 操作描述.
            approved: 是否被批准.
        """
        if not self.enable_learning:
            return

        import time
        record: LearningRecord = LearningRecord(
            tool_name=tool_name,
            operation=operation,
            approved=approved,
            timestamp=time.time(),
        )
        self._learning_history.append(record)

        # 限制历史窗口
        if len(self._learning_history) > self.learning_window:
            self._learning_history = self._learning_history[
                -self.learning_window:
            ]

        # 更新统计
        key: str = f"{tool_name}:{operation}"
        if key not in self._approval_stats:
            self._approval_stats[key] = {"approved": 0, "rejected": 0}
        if approved:
            self._approval_stats[key]["approved"] += 1
        else:
            self._approval_stats[key]["rejected"] += 1

    def _check_learning(
        self, tool_name: str, command: str
    ) -> Optional[str]:
        """检查学习历史，返回学习决策.

        如果同一操作连续被批准 >= 3 次，自动放行.
        如果连续被拒绝 >= 2 次，自动拒绝.

        Args:
            tool_name: 工具名称.
            command: 命令字符串.

        Returns:
            "auto" / "block" / None（无学习结论）.
        """
        key: str = f"{tool_name}:{command}"
        stats: Optional[Dict[str, int]] = self._approval_stats.get(key)
        if stats is None:
            return None

        approved: int = stats.get("approved", 0)
        rejected: int = stats.get("rejected", 0)
        total: int = approved + rejected

        if total < 2:
            return None

        # 连续批准 >= 3 次 → 自动放行
        if approved >= 3 and rejected == 0:
            return "auto"

        # 连续拒绝 >= 2 次 → 自动拒绝
        if rejected >= 2 and approved == 0:
            return "block"

        return None

    # ── 工具管理 ──────────────────────────────────────────────

    def add_confirm_tool(self, tool_name: str) -> None:
        """添加需要确认的工具.

        Args:
            tool_name: 工具名称.
        """
        self.confirm_tools.add(tool_name)
        self.auto_tools.discard(tool_name)

    def add_auto_tool(self, tool_name: str) -> None:
        """添加自动放行的工具.

        Args:
            tool_name: 工具名称.
        """
        self.auto_tools.add(tool_name)
        self.confirm_tools.discard(tool_name)

    # ── 查询 ──────────────────────────────────────────────────

    def get_learning_stats(self) -> Dict[str, Dict[str, int]]:
        """获取学习统计.

        Returns:
            操作签名 → 批准/拒绝统计的映射.
        """
        return dict(self._approval_stats)

    def get_history(self) -> List[LearningRecord]:
        """获取学习历史.

        Returns:
            学习历史记录列表.
        """
        return list(self._learning_history)

    def clear_learning(self) -> None:
        """清除学习历史."""
        self._learning_history.clear()
        self._approval_stats.clear()

    # ── 辅助方法 ──────────────────────────────────────────────

    def _extract_command(self, arguments: Dict[str, Any]) -> str:
        """从工具参数中提取命令字符串.

        尝试从常见键中提取:
            command, cmd, script, code, input, query

        Args:
            arguments: 工具参数.

        Returns:
            命令字符串（无则空字符串）.
        """
        for key in ("command", "cmd", "script", "code", "input", "query"):
            value: Any = arguments.get(key)
            if isinstance(value, str):
                return value
        return ""


# ── 策略决策 ──────────────────────────────────────────────────


@dataclass
class PolicyDecision:
    """策略决策结果.

    Attributes:
        action:     决策动作（auto/confirm/block）.
        reason:     决策原因.
        risk_score: 风险评分.
    """

    action: str = "auto"
    reason: str = ""
    risk_score: RiskScore = field(default_factory=RiskScore)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "action": self.action,
            "reason": self.reason,
            "risk_score": self.risk_score.to_dict(),
        }
