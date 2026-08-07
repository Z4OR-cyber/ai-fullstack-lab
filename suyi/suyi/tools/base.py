"""工具基类 — AgentTool 抽象基类.

设计原则：
- **权限内聚**：工具自描述风险画像（default_permission + assess_risk），
  不依赖外部配置表。工具自己知道自己的风险等级。
- **递归性**：AgentTool 可包装子 Agent，子 Agent 即工具。
- **自然语言即接口契约**：description 是模型发现和选择工具的唯一依据.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ToolParameter:
    """工具参数描述符.

    用于声明工具接受的参数，生成工具 schema 供模型消费.

    Attributes:
        name: 参数名.
        type: 参数类型（如 ``"string"``, ``"integer"``）.
        description: 参数描述.
        required: 是否必填.
        default: 默认值.
    """

    def __init__(
        self,
        name: str,
        type: str,
        description: str,
        required: bool = True,
        default: Any = None,
    ):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default

    def to_dict(self) -> dict:
        """转换为字典表示."""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        return result


class ToolContext:
    """工具执行上下文.

    携带执行环境信息，传递给 ``execute`` 和 ``assess_risk``.

    结构性安全约束：本上下文 **不包含** modelReasoning / toolOutput /
    conversationHistory 字段。这是物理层面的约束（字段不存在），
    而非提示词层面的约束.

    Attributes:
        session_id: 会话 ID.
        user_id: 用户 ID.
        working_dir: 工作目录.
        metadata: 额外元数据.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.working_dir = working_dir
        self.metadata = metadata or {}


class ToolResult:
    """工具执行结果.

    Attributes:
        success: 是否成功.
        output: 输出内容（字符串或结构化数据）.
        error: 错误信息（失败时）.
        metadata: 额外元数据.
    """

    def __init__(
        self,
        success: bool = True,
        output: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        """转换为字典表示."""
        result = {"success": self.success, "output": self.output}
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def __repr__(self) -> str:
        if self.success:
            return f"ToolResult(success=True, output={self.output!r})"
        return f"ToolResult(success=False, error={self.error!r})"


class AgentTool(ABC):
    """Agent 工具抽象基类.

    所有工具继承此类，实现 ``execute`` 方法。
    工具通过 ``default_permission`` 和 ``assess_risk`` 自描述风险画像，
    权限管理器据此做决策.

    **权限内聚设计**：
    - ``default_permission``：工具声明自身默认权限级别.
    - ``assess_risk``：运行时根据具体输入动态评估风险，可覆盖默认权限.
    - 不依赖外部配置表，工具自身即为权限信息源.

    **递归性**：
    AgentTool 可包装子 Agent。子 Agent 作为工具被父 Agent 调用，
    形成递归的工具调用链。子 Agent 工具只需实现 ``execute`` 方法.

    Attributes:
        name: 工具唯一标识符.
        description: 人类可读描述，供模型选择工具.
        default_permission: 默认权限级别：``'auto'`` / ``'confirm'`` / ``'block'``.
        parameters: 参数描述符列表.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识符（如 ``'bash'``, ``'read_file'``）."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供模型理解和选择工具."""
        pass

    @property
    @abstractmethod
    def default_permission(self) -> str:
        """默认权限级别.

        - ``'auto'``：只读 / 无副作用，可自动执行.
        - ``'confirm'``：有副作用，需用户确认.
        - ``'block'``：硬限制，默认不执行.
        """
        pass

    @property
    def parameters(self) -> List[ToolParameter]:
        """参数描述符列表，默认为空."""
        return []

    @abstractmethod
    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """执行工具.

        Args:
            input_data: 输入参数字典.
            context: 执行上下文.

        Returns:
            工具执行结果.
        """
        pass

    def assess_risk(
        self, input_data: dict, context: ToolContext
    ) -> Optional[str]:
        """运行时风险评估.

        根据具体输入动态评估风险，可覆盖默认权限.

        Returns:
            - ``'auto'``：安全，可自动执行.
            - ``'confirm'``：需用户确认.
            - ``'block'``：硬限制，禁止执行.
            - ``None``：无法判断，回退到 ``default_permission``.

        默认实现返回 ``None``，子类可覆盖以实现命令级风险评估.

        Examples:
            BashTool 对 ``ls`` 返回 ``'auto'``，对 ``rm -rf`` 返回 ``'block'``.
        """
        return None

    def get_signature_key(self, input_data: dict) -> str:
        """获取用于权限签名的命令键.

        签名键用于构建命令级签名（如 ``bash:git status``），
        防止"始终允许"变成全量授权.

        默认返回空字符串（签名仅为工具名）.
        有命令子结构的工具（如 BashTool）应覆盖此方法.

        Args:
            input_data: 输入参数字典.

        Returns:
            命令键字符串，如 ``'git status'``.
        """
        return ""

    def to_schema(self) -> dict:
        """生成工具 schema，供模型消费.

        Returns:
            符合工具调用格式的 schema 字典.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    p.name: {"type": p.type, "description": p.description}
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required],
            },
        }
