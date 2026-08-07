"""权限管理器 — 三档权限 + 命令级签名 + 两阶段安全分类器.

设计原则：
- **三档权限**：auto（只读/无副作用）/ confirm（有副作用）/ block（硬限制）.
- **权限决策链**：assessRisk() → block 硬限制 → 白名单 → defaultPermission.
- **命令级签名**：``bash:git status`` 而非 ``bash``，防止"始终允许"变成全量授权.
- **结构性安全约束**：分类器输入刻意不传入 modelReasoning / toolOutput /
  conversationHistory，是物理层面字段不构造，而非提示词约束.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from .base import AgentTool, ToolContext


# ── 权限级别常量 ──────────────────────────────────────────────

PERMISSION_AUTO = "auto"        # 只读 / 无副作用，自动执行
PERMISSION_CONFIRM = "confirm"  # 有副作用，需用户确认
PERMISSION_BLOCK = "block"      # 硬限制，禁止执行

VALID_PERMISSIONS = {PERMISSION_AUTO, PERMISSION_CONFIRM, PERMISSION_BLOCK}


# ── 两阶段安全分类器 ──────────────────────────────────────────


@dataclass
class ClassifierInput:
    """安全分类器输入.

    **结构性安全约束**：本数据类刻意 **不包含** 以下字段：
    - ``modelReasoning``：模型推理过程（可能包含越狱提示）.
    - ``toolOutput``：工具输出（可能包含注入内容）.
    - ``conversationHistory``：对话历史（可能包含社会工程攻击）.

    这是物理层面的约束（字段不存在于数据类定义中），
    而非提示词层面的"请不要使用这些信息"式的软约束.

    Attributes:
        tool_name: 工具名称.
        input_data: 工具输入参数.
        tool_description: 工具描述.
        tool_default_permission: 工具默认权限.
    """

    tool_name: str
    input_data: Dict[str, Any]
    tool_description: str = ""
    tool_default_permission: str = PERMISSION_CONFIRM


@dataclass
class ClassifierResult:
    """安全分类器结果.

    Attributes:
        level: 权限级别（``'auto'`` / ``'confirm'`` / ``'block'`` / ``None``）.
        reason: 判断理由.
        confidence: 置信度（0.0 - 1.0）.
    """

    level: Optional[str] = None
    reason: str = ""
    confidence: float = 0.0


class SecurityClassifier:
    """两阶段安全分类器接口.

    设计为可插拔接口，具体实现可后补.

    **两阶段设计**：
    - 第一阶段（快速判断 <100ms）：基于模式匹配、关键词检测，
      处理大部分明显安全/危险的请求.
    - 第二阶段（深度推理 500-2000ms）：基于语义分析，
      处理第一阶段无法判断的灰色地带.

    **结构性安全约束**：分类器只接收 :class:`ClassifierInput`，
    该输入物理上不包含 modelReasoning / toolOutput / conversationHistory.
    """

    def classify_fast(self, classifier_input: ClassifierInput) -> ClassifierResult:
        """第一阶段：快速分类（<100ms）.

        基于模式匹配和关键词检测，处理明显安全/危险的请求.

        Args:
            classifier_input: 分类器输入（受结构性安全约束）.

        Returns:
            分类结果。``level=None`` 表示无法判断，需进入第二阶段.
        """
        return ClassifierResult(level=None, reason="fast classifier not implemented")

    def classify_deep(self, classifier_input: ClassifierInput) -> ClassifierResult:
        """第二阶段：深度分类（500-2000ms）.

        基于语义分析，处理第一阶段无法判断的灰色地带.

        Args:
            classifier_input: 分类器输入（受结构性安全约束）.

        Returns:
            分类结果。
        """
        return ClassifierResult(level=None, reason="deep classifier not implemented")


# ── 权限管理器 ────────────────────────────────────────────────


class PermissionManager:
    """权限管理器.

    管理工具执行的权限决策，包含白名单管理和安全分类器集成.

    **权限决策链**（按优先级）::

        1. tool.assess_risk() → 'block'  → 硬限制，不可覆盖
        2. tool.assess_risk() → 'auto'   → 安全，直接放行
        3. 签名在白名单中                → 放行（用户已授权）
        4. tool.assess_risk() → 'confirm'→ 需确认
        5. 回退到 tool.default_permission

    **命令级签名**：使用 ``build_signature(tool_name, signature_key)`` 构建
    形如 ``bash:git status`` 的签名，确保白名单授权粒度到命令级别，
    而非整个工具.

    Attributes:
        always_allow: 持久白名单（跨会话生效）.
        session_allow: 会话级白名单（会话结束后清除）.
        classifier: 可选的安全分类器.
    """

    def __init__(self, classifier: Optional[SecurityClassifier] = None):
        self.always_allow: Set[str] = set()
        self.session_allow: Set[str] = set()
        self.classifier = classifier

    @staticmethod
    def build_signature(tool_name: str, signature_key: str) -> str:
        """构建命令级签名.

        签名格式：``tool_name:signature_key``
        当 signature_key 为空时，签名仅为 ``tool_name``.

        Args:
            tool_name: 工具名称.
            signature_key: 命令键（由工具的 ``get_signature_key`` 提供）.

        Returns:
            签名字符串，如 ``'bash:git status'``.

        Examples:
            >>> PermissionManager.build_signature("bash", "git status")
            'bash:git status'
            >>> PermissionManager.build_signature("read_file", "")
            'read_file'
        """
        if signature_key:
            return f"{tool_name}:{signature_key}"
        return tool_name

    def check(
        self,
        tool: AgentTool,
        input_data: dict,
        context: Optional[ToolContext] = None,
    ) -> str:
        """权限决策：检查工具调用是否被允许.

        执行完整的权限决策链：

        1. **工具自评估**（``assess_risk``）：
           - 返回 ``'block'`` → 硬限制，直接返回 ``'block'``（不可被白名单覆盖）.
           - 返回 ``'auto'`` → 安全，直接返回 ``'auto'``.
        2. **安全分类器**（如果配置）：
           - 快速阶段 → 深度阶段.
        3. **白名单检查**：
           - 签名在 ``always_allow`` 或 ``session_allow`` 中 → ``'auto'``.
        4. **工具自评估**返回 ``'confirm'`` → ``'confirm'``.
        5. **回退**到 ``tool.default_permission``.

        Args:
            tool: 工具实例.
            input_data: 工具输入参数.
            context: 执行上下文（可选）.

        Returns:
            权限级别：``'auto'`` / ``'confirm'`` / ``'block'``.
        """
        ctx = context or ToolContext()

        # ── 1. 工具自评估 ──
        risk = tool.assess_risk(input_data, ctx)

        # block 是硬限制，不可被白名单覆盖
        if risk == PERMISSION_BLOCK:
            return PERMISSION_BLOCK

        # auto 直接放行，无需检查白名单
        if risk == PERMISSION_AUTO:
            return PERMISSION_AUTO

        # ── 2. 安全分类器（如果配置）──
        if self.classifier is not None:
            classifier_input = ClassifierInput(
                tool_name=tool.name,
                input_data=input_data,
                tool_description=tool.description,
                tool_default_permission=tool.default_permission,
            )
            # 第一阶段：快速判断
            fast_result = self.classifier.classify_fast(classifier_input)
            if fast_result.level == PERMISSION_BLOCK:
                return PERMISSION_BLOCK
            if fast_result.level == PERMISSION_AUTO:
                return PERMISSION_AUTO

            # 第二阶段：深度推理
            deep_result = self.classifier.classify_deep(classifier_input)
            if deep_result.level == PERMISSION_BLOCK:
                return PERMISSION_BLOCK
            if deep_result.level == PERMISSION_AUTO:
                return PERMISSION_AUTO
            if deep_result.level == PERMISSION_CONFIRM:
                risk = PERMISSION_CONFIRM

        # ── 3. 白名单检查 ──
        signature_key = tool.get_signature_key(input_data)
        signature = self.build_signature(tool.name, signature_key)

        if signature in self.always_allow or signature in self.session_allow:
            return PERMISSION_AUTO

        # ── 4. 工具自评估建议 confirm ──
        if risk == PERMISSION_CONFIRM:
            return PERMISSION_CONFIRM

        # ── 5. 回退到默认权限 ──
        return tool.default_permission

    # ── 白名单管理 ──

    def add_always_allow(
        self, tool_name: str, input_data: dict, tool: Optional[AgentTool] = None
    ) -> str:
        """添加到持久白名单.

        Args:
            tool_name: 工具名称.
            input_data: 工具输入参数（用于提取命令键）.
            tool: 工具实例（可选，用于提取命令键）.

        Returns:
            被添加的签名字符串.
        """
        signature_key = tool.get_signature_key(input_data) if tool else ""
        signature = self.build_signature(tool_name, signature_key)
        self.always_allow.add(signature)
        return signature

    def add_session_allow(
        self, tool_name: str, input_data: dict, tool: Optional[AgentTool] = None
    ) -> str:
        """添加到会话级白名单.

        会话结束后应调用 :meth:`clear_session_allow` 清除.

        Args:
            tool_name: 工具名称.
            input_data: 工具输入参数.
            tool: 工具实例（可选）.

        Returns:
            被添加的签名字符串.
        """
        signature_key = tool.get_signature_key(input_data) if tool else ""
        signature = self.build_signature(tool_name, signature_key)
        self.session_allow.add(signature)
        return signature

    def remove_always_allow(self, signature: str) -> bool:
        """从持久白名单移除签名.

        Args:
            signature: 要移除的签名.

        Returns:
            是否成功移除.
        """
        if signature in self.always_allow:
            self.always_allow.discard(signature)
            return True
        return False

    def clear_session_allow(self) -> None:
        """清除会话级白名单."""
        self.session_allow.clear()

    def is_allowed(self, signature: str) -> bool:
        """检查签名是否在白名单中.

        Args:
            signature: 签名字符串.

        Returns:
            是否在白名单中.
        """
        return signature in self.always_allow or signature in self.session_allow
