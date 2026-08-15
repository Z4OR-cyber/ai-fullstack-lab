"""OS 级桌面控制工具 — ComputerUseTool.

Agent 接通软件的第 5 层能力：截图、鼠标、键盘、窗口、应用启动等桌面操作.

设计原则：
- **最严格默认权限**：``default_permission = "block"``，因为 OS 控制风险最高.
- **HITL 确认**：有副作用的动作需用户确认，危险动作直接拦截.
- **可选依赖**：pyautogui / mss 未安装时工具仍可导入，给出友好错误.
- **dry_run 模式**：不实际执行动作，只记录"本应执行什么"，用于无 GUI 环境测试.
- **审计日志**：所有执行动作记录到 ``_action_log``，便于审计追溯.
"""

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base import AgentTool, ToolContext, ToolParameter, ToolResult
from . import input_ctrl, safety, screen


class ComputerUseTool(AgentTool):
    """OS 级桌面控制工具.

    支持以下 action：
    - **只读**：screenshot / get_screen_size / list_windows / find_window / focus_window
    - **鼠标**：click / double_click / right_click / move / drag / scroll
    - **键盘**：type_text / press_key / hotkey
    - **应用**：launch_app

    **安全策略**：
    - 危险组合键（Alt+F4 / Ctrl+Alt+Del / Win+L 等）直接 block.
    - 危险应用程序（shutdown / format / rm 等）直接 block.
    - 坐标越界保护.
    - 有副作用动作默认需 HITL 确认.

    **dry_run 模式**：
    不实际执行任何鼠标/键盘操作，只记录动作参数，返回 would_execute 信息.
    适用于无 GUI 环境（如云端沙箱）下的测试和开发.

    Attributes:
        dry_run_default: 全局默认 dry_run 模式.
        enabled: 工具是否启用.
        screenshot_dir: 截图保存目录（None 表示不保存到文件）.
    """

    #: 支持的所有动作集合
    _SUPPORTED_ACTIONS = {
        "screenshot", "get_screen_size", "list_windows",
        "find_window", "focus_window",
        "click", "double_click", "right_click",
        "move", "drag", "scroll",
        "type_text", "press_key", "hotkey", "launch_app",
    }

    def __init__(
        self,
        dry_run_default: bool = False,
        enabled: bool = True,
        screenshot_dir: Optional[str] = None,
    ):
        """初始化 ComputerUseTool.

        Args:
            dry_run_default: 全局默认 dry_run 模式。为 True 时所有动作
                不实际执行，只记录。单次调用可通过 input_data 中的
                dry_run 字段覆盖。
            enabled: 工具是否启用。为 False 时所有动作返回失败。
            screenshot_dir: 截图保存目录。设置后截图会保存为 PNG 文件
                并返回文件路径。
        """
        self.dry_run_default = dry_run_default
        self.enabled = enabled
        self.screenshot_dir = screenshot_dir
        self._action_log: List[Dict[str, Any]] = []
        self._last_screenshot_path: Optional[str] = None

    @property
    def name(self) -> str:
        return "computer_use"

    @property
    def description(self) -> str:
        return (
            "OS 级桌面控制工具（Computer Use）/ OS-level desktop control tool. "
            "支持截图、鼠标点击/移动/拖拽/滚动、键盘输入/按键/快捷键、窗口查找/聚焦、"
            "应用启动等桌面操作。\n"
            "Supported actions: "
            "screenshot, get_screen_size, list_windows, find_window, focus_window, "
            "click, double_click, right_click, move, drag, scroll, "
            "type_text, press_key, hotkey, launch_app.\n"
            "⚠️ 此工具具有最高风险等级，会触发 HITL（Human-in-the-Loop）确认。"
            "危险组合键和危险程序将被安全策略直接阻止。\n"
            "支持 dry_run 模式：设置 dry_run=true 只记录动作而不实际执行。"
        )

    @property
    def default_permission(self) -> str:
        return "block"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "要执行的动作: screenshot | get_screen_size | list_windows | "
                    "find_window | focus_window | click | double_click | "
                    "right_click | move | drag | scroll | type_text | "
                    "press_key | hotkey | launch_app"
                ),
                required=True,
            ),
            ToolParameter(
                name="x",
                type="integer",
                description="横坐标（鼠标操作）",
                required=False,
            ),
            ToolParameter(
                name="y",
                type="integer",
                description="纵坐标（鼠标操作）",
                required=False,
            ),
            ToolParameter(
                name="to_x",
                type="integer",
                description="拖拽终点横坐标",
                required=False,
            ),
            ToolParameter(
                name="to_y",
                type="integer",
                description="拖拽终点纵坐标",
                required=False,
            ),
            ToolParameter(
                name="text",
                type="string",
                description="要键入的文本（type_text 动作）",
                required=False,
            ),
            ToolParameter(
                name="key",
                type="string",
                description="单键名称（press_key 动作），如 enter / esc / tab",
                required=False,
            ),
            ToolParameter(
                name="keys",
                type="array",
                description="组合键列表（hotkey 动作），如 ['ctrl', 'c']",
                required=False,
            ),
            ToolParameter(
                name="direction",
                type="string",
                description="滚动方向: up / down（scroll 动作）",
                required=False,
                default="up",
            ),
            ToolParameter(
                name="amount",
                type="integer",
                description="滚动量（scroll 动作）",
                required=False,
                default=3,
            ),
            ToolParameter(
                name="window_title",
                type="string",
                description="窗口标题子串（find_window 动作）",
                required=False,
            ),
            ToolParameter(
                name="app_path",
                type="string",
                description="应用程序路径或启动命令（launch_app 动作）",
                required=False,
            ),
            ToolParameter(
                name="region",
                type="object",
                description=(
                    "截图区域: {x, y, width, height}（screenshot 动作），"
                    "不传则截取全屏"
                ),
                required=False,
            ),
            ToolParameter(
                name="dry_run",
                type="boolean",
                description="只记录动作不实际执行，默认 false",
                required=False,
                default=False,
            ),
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """执行桌面控制动作.

        Args:
            input_data: 动作参数字典，必须包含 ``action`` 字段.
            context: 执行上下文.

        Returns:
            工具执行结果.
        """
        # 1. 检查工具是否启用
        if not self.enabled:
            return ToolResult(
                success=False,
                error="ComputerUseTool 已被禁用",
            )

        action = input_data.get("action", "")
        if not action:
            return ToolResult(success=False, error="缺少必要参数: action")

        # 验证 action 是否为支持的动作
        if action not in self._SUPPORTED_ACTIONS:
            return ToolResult(
                success=False,
                error=f"未知动作: {action}，支持的动作: {', '.join(sorted(self._SUPPORTED_ACTIONS))}",
            )

        # 2. 判断 dry_run 模式
        dry_run = input_data.get("dry_run", self.dry_run_default)

        # 3. 参数校验
        validation_error = self._validate_params(action, input_data)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        # 4. 获取屏幕尺寸用于坐标安全检查（在非 dry_run 时）
        screen_size = None
        if not dry_run and action in (
            "click", "double_click", "right_click", "move",
            "drag", "scroll",
        ):
            try:
                screen_size = screen.get_screen_size()
            except Exception:
                pass  # 获取失败不阻塞，后续操作中 pyautogui 会自行处理

        # 5. 构建安全评估参数（注入屏幕尺寸）
        risk_params = dict(input_data)
        if screen_size:
            risk_params["_screen_size"] = screen_size

        # 6. 安全评估
        risk_level = safety.assess_action_risk(action, risk_params)
        if risk_level == "block":
            block_reason = self._get_block_reason(action, input_data)
            self._log_action(action, input_data, success=False, error=block_reason)
            return ToolResult(
                success=False,
                error=f"操作被安全策略阻止: {block_reason}",
            )

        # 7. dry_run 模式：只记录不执行
        if dry_run:
            would_execute = self._build_would_execute(action, input_data)
            self._log_action(
                action, input_data, success=True,
                result_summary="dry_run",
            )
            return ToolResult(
                success=True,
                output={"dry_run": True, "would_execute": would_execute},
            )

        # 8. 实际执行
        try:
            result = self._dispatch(action, input_data, screen_size)
        except Exception as e:
            self._log_action(action, input_data, success=False, error=str(e))
            return ToolResult(success=False, error=str(e))

        # 9. 记录审计日志
        self._log_action(
            action,
            input_data,
            success=result.get("success", False),
            result_summary=self._summarize_result(action, result),
            error=result.get("error"),
        )

        # 10. 转换为 ToolResult
        if result.get("success"):
            return ToolResult(
                success=True,
                output=result.get("output"),
                metadata=result.get("metadata", {}),
            )
        else:
            return ToolResult(
                success=False,
                error=result.get("error", "未知错误"),
                metadata=result.get("metadata", {}),
            )

    def assess_risk(
        self, input_data: dict, context: ToolContext
    ) -> Optional[str]:
        """运行时风险评估，委托给 safety.assess_action_risk.

        Args:
            input_data: 动作参数字典.
            context: 执行上下文.

        Returns:
            风险级别: "auto" / "confirm" / "block".
        """
        action = input_data.get("action", "")
        if not action:
            return None
        return safety.assess_action_risk(action, input_data)

    def get_signature_key(self, input_data: dict) -> str:
        """获取签名键，按动作类型区分.

        HITL 签名按 action 分别授权，避免"始终允许 click"变成全量授权.

        Args:
            input_data: 动作参数字典.

        Returns:
            动作名称字符串.
        """
        return input_data.get("action", "")

    # ── 额外公共方法 ──────────────────────────────────────────

    def get_action_log(self) -> List[Dict[str, Any]]:
        """返回审计日志.

        Returns:
            动作日志列表，每条包含时间戳、action、params、结果摘要.
        """
        return list(self._action_log)

    def last_screenshot_path(self) -> Optional[str]:
        """返回最近一次截图的文件路径.

        Returns:
            截图文件路径，如果未保存过截图返回 None.
        """
        return self._last_screenshot_path

    # ── 内部方法 ──────────────────────────────────────────────

    def _validate_params(self, action: str, input_data: dict) -> Optional[str]:
        """校验动作参数完整性.

        Args:
            action: 动作名称.
            input_data: 输入参数.

        Returns:
            校验失败时返回错误消息，通过返回 None.
        """
        # 需要坐标的动作
        coordinate_actions = {
            "click", "double_click", "right_click", "move", "scroll"
        }
        if action in coordinate_actions:
            if "x" not in input_data or "y" not in input_data:
                return f"动作 '{action}' 需要 x 和 y 参数"

        if action == "drag":
            if not all(k in input_data for k in ("x", "y", "to_x", "to_y")):
                return "动作 'drag' 需要 x, y, to_x, to_y 参数"

        if action == "type_text":
            if "text" not in input_data:
                return "动作 'type_text' 需要 text 参数"

        if action == "press_key":
            if "key" not in input_data:
                return "动作 'press_key' 需要 key 参数"

        if action == "hotkey":
            keys = input_data.get("keys", [])
            if not keys or not isinstance(keys, (list, tuple)):
                return "动作 'hotkey' 需要非空 keys 数组参数"

        if action == "launch_app":
            if "app_path" not in input_data or not input_data.get("app_path"):
                return "动作 'launch_app' 需要 app_path 参数"

        if action == "find_window":
            if "window_title" not in input_data:
                return "动作 'find_window' 需要 window_title 参数"

        if action == "focus_window":
            if "window_id" not in input_data:
                return "动作 'focus_window' 需要 window_id 参数"

        return None

    def _get_block_reason(self, action: str, input_data: dict) -> str:
        """获取安全拦截的具体原因.

        Args:
            action: 动作名称.
            input_data: 输入参数.

        Returns:
            拦截原因描述字符串.
        """
        if action == "hotkey":
            keys = input_data.get("keys", [])
            normalized = safety.normalize_hotkey(list(keys))
            return f"危险组合键 '{normalized}' 已被禁止"

        if action == "launch_app":
            app_path = input_data.get("app_path", "")
            is_dangerous, keyword = safety.is_dangerous_application(app_path)
            if is_dangerous:
                return f"程序 '{app_path}' 包含危险关键词 '{keyword}'"
            return "应用程序被安全策略阻止"

        if action in ("click", "double_click", "right_click", "move", "drag", "scroll"):
            x = input_data.get("x", 0)
            y = input_data.get("y", 0)
            return f"坐标 ({x}, {y}) 越界或不安全"

        return f"动作 '{action}' 被安全策略阻止"

    def _build_would_execute(
        self, action: str, input_data: dict
    ) -> Dict[str, Any]:
        """构建 dry_run 模式下的 would_execute 信息.

        Args:
            action: 动作名称.
            input_data: 输入参数.

        Returns:
            描述"本应执行什么"的字典.
        """
        # 提取与 action 相关的参数
        relevant_keys = self._get_relevant_keys(action)
        params = {
            k: v for k, v in input_data.items()
            if k in relevant_keys
        }
        return {"action": action, "params": params}

    def _get_relevant_keys(self, action: str) -> set:
        """获取动作相关的参数键名集合.

        Args:
            action: 动作名称.

        Returns:
            相关参数键名集合.
        """
        key_map = {
            "screenshot": {"region"},
            "get_screen_size": set(),
            "list_windows": set(),
            "find_window": {"window_title"},
            "focus_window": {"window_id"},
            "click": {"x", "y", "button", "clicks", "interval"},
            "double_click": {"x", "y"},
            "right_click": {"x", "y"},
            "move": {"x", "y", "duration"},
            "drag": {"x", "y", "to_x", "to_y", "duration", "button"},
            "scroll": {"x", "y", "direction", "amount"},
            "type_text": {"text", "interval"},
            "press_key": {"key"},
            "hotkey": {"keys"},
            "launch_app": {"app_path"},
        }
        return key_map.get(action, set())

    def _dispatch(
        self,
        action: str,
        input_data: dict,
        screen_size: Optional[tuple],
    ) -> Dict[str, Any]:
        """分派动作到具体实现模块.

        Args:
            action: 动作名称.
            input_data: 输入参数.
            screen_size: 屏幕分辨率.

        Returns:
            执行结果字典.
        """
        # ── 只读动作 ──
        if action == "screenshot":
            return self._do_screenshot(input_data)

        if action == "get_screen_size":
            return self._do_get_screen_size()

        if action == "list_windows":
            return self._do_list_windows()

        if action == "find_window":
            return self._do_find_window(input_data)

        if action == "focus_window":
            return self._do_focus_window(input_data)

        # ── 鼠标动作 ──
        if action == "click":
            return input_ctrl.mouse_click(
                x=input_data["x"],
                y=input_data["y"],
                button=input_data.get("button", "left"),
                clicks=input_data.get("clicks", 1),
                interval=input_data.get("interval", 0.1),
            )

        if action == "double_click":
            return input_ctrl.mouse_double_click(
                x=input_data["x"],
                y=input_data["y"],
            )

        if action == "right_click":
            return input_ctrl.mouse_right_click(
                x=input_data["x"],
                y=input_data["y"],
            )

        if action == "move":
            return input_ctrl.mouse_move(
                x=input_data["x"],
                y=input_data["y"],
                duration=input_data.get("duration", 0.2),
            )

        if action == "drag":
            return input_ctrl.mouse_drag(
                from_x=input_data["x"],
                from_y=input_data["y"],
                to_x=input_data["to_x"],
                to_y=input_data["to_y"],
                duration=input_data.get("duration", 0.3),
                button=input_data.get("button", "left"),
            )

        if action == "scroll":
            return input_ctrl.mouse_scroll(
                x=input_data["x"],
                y=input_data["y"],
                direction=input_data.get("direction", "up"),
                amount=input_data.get("amount", 3),
            )

        # ── 键盘动作 ──
        if action == "type_text":
            return input_ctrl.keyboard_type(
                text=input_data["text"],
                interval=input_data.get("interval", 0.02),
            )

        if action == "press_key":
            return input_ctrl.keyboard_press(
                key=input_data["key"],
            )

        if action == "hotkey":
            return input_ctrl.keyboard_hotkey(*input_data["keys"])

        # ── 应用启动 ──
        if action == "launch_app":
            return input_ctrl.launch_application(
                path_or_command=input_data["app_path"],
            )

        return {"success": False, "error": f"未知动作: {action}"}

    def _do_screenshot(self, input_data: dict) -> Dict[str, Any]:
        """执行截图动作.

        Args:
            input_data: 输入参数，可能包含 region.

        Returns:
            结果字典，metadata 包含 screen_size 和 image_size_bytes.
        """
        region = input_data.get("region")
        try:
            image_bytes = screen.capture_screen(region=region)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

        # 获取屏幕尺寸
        screen_size = None
        try:
            screen_size = screen.get_screen_size()
        except Exception:
            pass

        metadata: Dict[str, Any] = {
            "image_size_bytes": len(image_bytes),
        }
        if screen_size:
            metadata["screen_size"] = {
                "width": screen_size[0],
                "height": screen_size[1],
            }

        # 如果设置了截图目录，保存到文件
        output: Any = None
        if self.screenshot_dir:
            try:
                os.makedirs(self.screenshot_dir, exist_ok=True)
                timestamp = datetime.now(timezone.utc).strftime(
                    "%Y%m%d_%H%M%S_%f"
                )
                filename = f"screenshot_{timestamp}.png"
                filepath = os.path.join(self.screenshot_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
                self._last_screenshot_path = filepath
                output = {"screenshot_path": filepath}
                metadata["saved_to"] = filepath
            except Exception as e:
                metadata["save_error"] = str(e)

        return {
            "success": True,
            "output": output,
            "metadata": metadata,
        }

    def _do_get_screen_size(self) -> Dict[str, Any]:
        """执行获取屏幕分辨率动作.

        Returns:
            结果字典.
        """
        try:
            width, height = screen.get_screen_size()
            return {
                "success": True,
                "output": {"width": width, "height": height},
                "metadata": {"screen_size": {"width": width, "height": height}},
            }
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    def _do_list_windows(self) -> Dict[str, Any]:
        """执行列出窗口动作.

        Returns:
            结果字典.
        """
        windows = screen.list_windows()
        return {
            "success": True,
            "output": windows,
            "metadata": {"count": len(windows)},
        }

    def _do_find_window(self, input_data: dict) -> Dict[str, Any]:
        """执行查找窗口动作.

        Args:
            input_data: 包含 window_title.

        Returns:
            结果字典，找到时 output 为窗口信息，未找到为 None.
        """
        title = input_data.get("window_title", "")
        window = screen.find_window(title)
        return {
            "success": True,
            "output": window,  # 未找到时为 None
            "metadata": {"found": window is not None},
        }

    def _do_focus_window(self, input_data: dict) -> Dict[str, Any]:
        """执行聚焦窗口动作.

        Args:
            input_data: 包含 window_id.

        Returns:
            结果字典.
        """
        window_id = input_data.get("window_id")
        result = screen.focus_window(int(window_id))
        if result:
            return {
                "success": True,
                "output": {"focused": True, "window_id": window_id},
            }
        else:
            return {
                "success": False,
                "error": f"无法聚焦窗口 (id={window_id})",
            }

    def _log_action(
        self,
        action: str,
        params: dict,
        success: bool,
        result_summary: str = "",
        error: Optional[str] = None,
    ) -> None:
        """记录动作到审计日志.

        Args:
            action: 动作名称.
            params: 动作参数.
            success: 是否成功.
            result_summary: 结果摘要.
            error: 错误信息.
        """
        # 提取相关参数，避免记录过大的字段
        relevant_keys = self._get_relevant_keys(action)
        relevant_params = {
            k: v for k, v in params.items()
            if k in relevant_keys or k == "dry_run"
        }

        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "params": relevant_params,
            "success": success,
        }
        if result_summary:
            entry["result_summary"] = result_summary
        if error:
            entry["error"] = error

        self._action_log.append(entry)

    def _summarize_result(
        self, action: str, result: Dict[str, Any]
    ) -> str:
        """生成执行结果的简短摘要.

        Args:
            action: 动作名称.
            result: 执行结果字典.

        Returns:
            结果摘要字符串.
        """
        if not result.get("success"):
            return "failed"

        metadata = result.get("metadata", {})
        if action == "screenshot":
            size = metadata.get("image_size_bytes", 0)
            return f"screenshot ({size} bytes)"
        if action == "get_screen_size":
            ss = metadata.get("screen_size", {})
            return f"{ss.get('width', '?')}x{ss.get('height', '?')}"
        if action == "list_windows":
            return f"{metadata.get('count', 0)} windows"
        if action == "find_window":
            return "found" if metadata.get("found") else "not found"
        if action in ("click", "double_click", "right_click"):
            pos = metadata.get("x", "?"), metadata.get("y", "?")
            return f"{action} at {pos}"
        if action == "type_text":
            return f"typed {metadata.get('text_length', 0)} chars"
        if action == "hotkey":
            return "+".join(metadata.get("keys", []))
        if action == "launch_app":
            return f"launched {metadata.get('launched', '?')}"

        return "ok"
