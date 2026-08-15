"""ComputerUseTool 测试 — OS 级桌面控制工具.

全部测试使用 dry_run 模式或 mock，不实际操作鼠标键盘，
可在无 GUI 环境（如云端沙箱）下运行.

覆盖场景：
1. 工具注册与 schema
2. 只读动作 dry_run
3. 鼠标动作 dry_run
4. 键盘动作 dry_run
5. launch_app dry_run
6. 安全拦截 — 危险组合键
7. 安全拦截 — 危险应用
8. 坐标越界保护
9. assess_risk 分级
10. get_signature_key 按动作区分
11. 禁用开关
12. 全局 dry_run_default
13. pyautogui 未安装降级
14. 审计日志
15. 截图保存到指定目录
16. 参数校验
17. 危险文本输入检测
18. 焦点窗口
"""

import os
import sys
import tempfile
from unittest import mock

import pytest

from suyi.tools import ComputerUseTool, ToolContext
from suyi.tools.computer import safety, screen, input_ctrl


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def ctx():
    """工具执行上下文."""
    return ToolContext()


@pytest.fixture
def tool():
    """默认 ComputerUseTool 实例（非 dry_run，但测试中用 dry_run=True 调用）."""
    return ComputerUseTool()


@pytest.fixture
def dry_tool():
    """默认 dry_run 的 ComputerUseTool 实例."""
    return ComputerUseTool(dry_run_default=True)


@pytest.fixture
def screenshot_dir():
    """临时截图目录."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ═══════════════════════════════════════════════════════════════
#  1. 工具注册与 schema
# ═══════════════════════════════════════════════════════════════


class TestToolRegistration:
    """工具注册与 schema 验证."""

    def test_name(self, tool):
        """工具名称为 computer_use."""
        assert tool.name == "computer_use"

    def test_description_contains_actions(self, tool):
        """描述中包含所有支持的 action."""
        desc = tool.description
        for action in [
            "screenshot", "get_screen_size", "list_windows",
            "find_window", "focus_window",
            "click", "double_click", "right_click",
            "move", "drag", "scroll",
            "type_text", "press_key", "hotkey", "launch_app",
        ]:
            assert action in desc, f"描述中缺少 action: {action}"

    def test_default_permission_is_block(self, tool):
        """默认权限为 block（最严格）."""
        assert tool.default_permission == "block"

    def test_to_schema_contains_all_actions(self, tool):
        """to_schema 包含 action 参数且枚举了所有动作."""
        schema = tool.to_schema()
        assert schema["name"] == "computer_use"
        assert "parameters" in schema
        props = schema["parameters"]["properties"]
        assert "action" in props
        # action 参数描述中列出了所有动作
        action_desc = props["action"]["description"]
        for action in ["screenshot", "click", "hotkey", "launch_app"]:
            assert action in action_desc

    def test_to_schema_required_fields(self, tool):
        """schema 中 action 为必填."""
        schema = tool.to_schema()
        required = schema["parameters"]["required"]
        assert "action" in required

    def test_to_schema_has_dry_run_param(self, tool):
        """schema 包含 dry_run 参数."""
        schema = tool.to_schema()
        props = schema["parameters"]["properties"]
        assert "dry_run" in props
        assert props["dry_run"]["type"] == "boolean"


# ═══════════════════════════════════════════════════════════════
#  2. 只读动作 dry_run
# ═══════════════════════════════════════════════════════════════


class TestReadOnlyActionsDryRun:
    """只读动作在 dry_run 下可执行."""

    def test_screenshot_dry_run(self, tool, ctx):
        """screenshot dry_run 返回 would_execute."""
        result = tool.execute(
            {"action": "screenshot", "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["dry_run"] is True
        assert result.output["would_execute"]["action"] == "screenshot"

    def test_get_screen_size_dry_run(self, tool, ctx):
        """get_screen_size dry_run 返回 would_execute."""
        result = tool.execute(
            {"action": "get_screen_size", "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["action"] == "get_screen_size"

    def test_list_windows_dry_run(self, tool, ctx):
        """list_windows dry_run 返回 would_execute."""
        result = tool.execute(
            {"action": "list_windows", "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["action"] == "list_windows"

    def test_find_window_dry_run(self, tool, ctx):
        """find_window dry_run 返回 would_execute."""
        result = tool.execute(
            {"action": "find_window", "window_title": "Notepad",
             "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["action"] == "find_window"
        assert result.output["would_execute"]["params"]["window_title"] == "Notepad"

    def test_focus_window_dry_run(self, tool, ctx):
        """focus_window dry_run 成功."""
        result = tool.execute(
            {"action": "focus_window", "window_id": 12345,
             "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["action"] == "focus_window"


# ═══════════════════════════════════════════════════════════════
#  3. 鼠标动作 dry_run
# ═══════════════════════════════════════════════════════════════


class TestMouseActionsDryRun:
    """鼠标动作 dry_run 测试."""

    def test_click_dry_run(self, tool, ctx):
        """click dry_run 记录参数."""
        result = tool.execute(
            {"action": "click", "x": 100, "y": 200, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["x"] == 100
        assert params["y"] == 200

    def test_double_click_dry_run(self, tool, ctx):
        """double_click dry_run 记录参数."""
        result = tool.execute(
            {"action": "double_click", "x": 300, "y": 400, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["x"] == 300
        assert params["y"] == 400

    def test_right_click_dry_run(self, tool, ctx):
        """right_click dry_run 记录参数."""
        result = tool.execute(
            {"action": "right_click", "x": 500, "y": 600, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["x"] == 500
        assert params["y"] == 600

    def test_move_dry_run(self, tool, ctx):
        """move dry_run 记录参数."""
        result = tool.execute(
            {"action": "move", "x": 700, "y": 800,
             "duration": 0.5, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["x"] == 700
        assert params["y"] == 800
        assert params["duration"] == 0.5

    def test_drag_dry_run(self, tool, ctx):
        """drag dry_run 记录参数."""
        result = tool.execute(
            {"action": "drag", "x": 10, "y": 20,
             "to_x": 300, "to_y": 400, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["x"] == 10
        assert params["to_x"] == 300

    def test_scroll_dry_run(self, tool, ctx):
        """scroll dry_run 记录参数."""
        result = tool.execute(
            {"action": "scroll", "x": 50, "y": 60,
             "direction": "down", "amount": 5, "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["direction"] == "down"
        assert params["amount"] == 5


# ═══════════════════════════════════════════════════════════════
#  4. 键盘动作 dry_run
# ═══════════════════════════════════════════════════════════════


class TestKeyboardActionsDryRun:
    """键盘动作 dry_run 测试."""

    def test_type_text_dry_run(self, tool, ctx):
        """type_text dry_run 记录文本."""
        result = tool.execute(
            {"action": "type_text", "text": "Hello World", "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["text"] == "Hello World"

    def test_press_key_dry_run(self, tool, ctx):
        """press_key dry_run 记录按键."""
        result = tool.execute(
            {"action": "press_key", "key": "enter", "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["key"] == "enter"

    def test_hotkey_dry_run(self, tool, ctx):
        """hotkey dry_run 记录组合键."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["ctrl", "c"], "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["keys"] == ["ctrl", "c"]


# ═══════════════════════════════════════════════════════════════
#  5. launch_app dry_run
# ═══════════════════════════════════════════════════════════════


class TestLaunchAppDryRun:
    """应用启动 dry_run 测试."""

    def test_launch_notepad_dry_run(self, tool, ctx):
        """启动 notepad dry_run 被记录."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "notepad.exe",
             "dry_run": True}, ctx
        )
        assert result.success is True
        params = result.output["would_execute"]["params"]
        assert params["app_path"] == "notepad.exe"

    def test_launch_normal_command_dry_run(self, tool, ctx):
        """启动正常命令 dry_run 被记录."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "code .",
             "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["params"]["app_path"] == "code ."


# ═══════════════════════════════════════════════════════════════
#  6. 安全拦截 — 危险组合键
# ═══════════════════════════════════════════════════════════════


class TestDangerousHotkeysBlocked:
    """危险组合键拦截测试."""

    def test_ctrl_alt_del_blocked(self, tool, ctx):
        """Ctrl+Alt+Del 被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["ctrl", "alt", "del"],
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_alt_f4_blocked(self, tool, ctx):
        """Alt+F4 被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["alt", "f4"], "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_win_l_blocked(self, tool, ctx):
        """Win+L（锁屏）被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["win", "l"], "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_ctrl_shift_esc_blocked(self, tool, ctx):
        """Ctrl+Shift+Esc（任务管理器）被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["ctrl", "shift", "esc"],
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_cmd_q_blocked(self, tool, ctx):
        """Cmd+Q（macOS 退出）被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["cmd", "q"], "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_normal_hotkey_not_blocked(self, tool, ctx):
        """正常组合键（Ctrl+C）不被拦截."""
        result = tool.execute(
            {"action": "hotkey", "keys": ["ctrl", "c"], "dry_run": True}, ctx
        )
        assert result.success is True


# ═══════════════════════════════════════════════════════════════
#  7. 安全拦截 — 危险应用
# ═══════════════════════════════════════════════════════════════


class TestDangerousAppsBlocked:
    """危险应用程序拦截测试."""

    def test_shutdown_blocked(self, tool, ctx):
        """shutdown 命令被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "shutdown /s /t 0",
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_format_blocked(self, tool, ctx):
        """format 命令被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "format C:",
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_reg_delete_blocked(self, tool, ctx):
        """reg delete 命令被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "reg delete HKLM",
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_rm_rf_blocked(self, tool, ctx):
        """rm -rf 命令被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "rm -rf /",
             "dry_run": True}, ctx
        )
        assert result.success is False
        assert "安全策略" in result.error

    def test_reboot_blocked(self, tool, ctx):
        """reboot 命令被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "reboot", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_diskpart_blocked(self, tool, ctx):
        """diskpart 被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "diskpart",
             "dry_run": True}, ctx
        )
        assert result.success is False

    def test_normal_app_not_blocked(self, tool, ctx):
        """正常应用不被拦截."""
        result = tool.execute(
            {"action": "launch_app", "app_path": "notepad.exe",
             "dry_run": True}, ctx
        )
        assert result.success is True


# ═══════════════════════════════════════════════════════════════
#  8. 坐标越界保护
# ═══════════════════════════════════════════════════════════════


class TestCoordinateBounds:
    """坐标越界保护测试."""

    def test_click_out_of_bounds_blocked(self, tool, ctx):
        """点击越界坐标被拦截（非 dry_run，需要 mock 屏幕尺寸）."""
        with mock.patch.object(
            screen, "get_screen_size", return_value=(1920, 1080)
        ):
            result = tool.execute(
                {"action": "click", "x": 99999, "y": 99999,
                 "dry_run": False}, ctx
            )
        assert result.success is False
        assert "安全策略" in result.error

    def test_click_negative_coordinates_blocked(self, tool, ctx):
        """负坐标被拦截."""
        with mock.patch.object(
            screen, "get_screen_size", return_value=(1920, 1080)
        ):
            result = tool.execute(
                {"action": "click", "x": -1, "y": -1, "dry_run": False}, ctx
            )
        assert result.success is False

    def test_valid_coordinates_pass(self, tool, ctx):
        """合法坐标在 dry_run 下通过."""
        result = tool.execute(
            {"action": "click", "x": 100, "y": 100, "dry_run": True}, ctx
        )
        assert result.success is True

    def test_is_coordinate_safe_function(self):
        """直接测试 is_coordinate_safe 函数."""
        assert safety.is_coordinate_safe(0, 0, (1920, 1080)) is True
        assert safety.is_coordinate_safe(1919, 1079, (1920, 1080)) is True
        assert safety.is_coordinate_safe(1920, 1080, (1920, 1080)) is False
        assert safety.is_coordinate_safe(-1, 0, (1920, 1080)) is False
        assert safety.is_coordinate_safe(0, -1, (1920, 1080)) is False
        assert safety.is_coordinate_safe(99999, 500, (1920, 1080)) is False


# ═══════════════════════════════════════════════════════════════
#  9. assess_risk 分级
# ═══════════════════════════════════════════════════════════════


class TestAssessRisk:
    """风险评估分级测试."""

    def test_screenshot_is_auto(self, tool, ctx):
        """screenshot 风险级别为 auto."""
        risk = tool.assess_risk({"action": "screenshot"}, ctx)
        assert risk == "auto"

    def test_get_screen_size_is_auto(self, tool, ctx):
        """get_screen_size 风险级别为 auto."""
        risk = tool.assess_risk({"action": "get_screen_size"}, ctx)
        assert risk == "auto"

    def test_list_windows_is_auto(self, tool, ctx):
        """list_windows 风险级别为 auto."""
        risk = tool.assess_risk({"action": "list_windows"}, ctx)
        assert risk == "auto"

    def test_click_is_confirm(self, tool, ctx):
        """click 风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "click", "x": 100, "y": 100}, ctx
        )
        assert risk == "confirm"

    def test_type_text_is_confirm(self, tool, ctx):
        """type_text 风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "type_text", "text": "hello"}, ctx
        )
        assert risk == "confirm"

    def test_dangerous_hotkey_is_block(self, tool, ctx):
        """危险组合键风险级别为 block."""
        risk = tool.assess_risk(
            {"action": "hotkey", "keys": ["ctrl", "alt", "del"]}, ctx
        )
        assert risk == "block"

    def test_normal_hotkey_is_confirm(self, tool, ctx):
        """正常组合键风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "hotkey", "keys": ["ctrl", "c"]}, ctx
        )
        assert risk == "confirm"

    def test_dangerous_app_is_block(self, tool, ctx):
        """危险应用风险级别为 block."""
        risk = tool.assess_risk(
            {"action": "launch_app", "app_path": "shutdown -s"}, ctx
        )
        assert risk == "block"

    def test_normal_app_is_confirm(self, tool, ctx):
        """正常应用风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "launch_app", "app_path": "notepad"}, ctx
        )
        assert risk == "confirm"

    def test_move_is_auto(self, tool, ctx):
        """move（仅移动光标）风险级别为 auto."""
        risk = tool.assess_risk(
            {"action": "move", "x": 100, "y": 100}, ctx
        )
        assert risk == "auto"

    def test_right_click_is_confirm(self, tool, ctx):
        """right_click 风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "right_click", "x": 100, "y": 100}, ctx
        )
        assert risk == "confirm"

    def test_drag_is_confirm(self, tool, ctx):
        """drag 风险级别为 confirm."""
        risk = tool.assess_risk(
            {"action": "drag", "x": 0, "y": 0, "to_x": 100, "to_y": 100}, ctx
        )
        assert risk == "confirm"


# ═══════════════════════════════════════════════════════════════
#  10. get_signature_key 按动作区分
# ═══════════════════════════════════════════════════════════════


class TestSignatureKey:
    """签名键按动作类型区分测试."""

    def test_click_signature(self, tool):
        """click 签名键为 click."""
        key = tool.get_signature_key({"action": "click", "x": 1, "y": 2})
        assert key == "click"

    def test_type_text_signature(self, tool):
        """type_text 签名键为 type_text."""
        key = tool.get_signature_key(
            {"action": "type_text", "text": "hello"}
        )
        assert key == "type_text"

    def test_different_actions_different_signatures(self, tool):
        """不同动作签名键不同."""
        key_click = tool.get_signature_key({"action": "click"})
        key_type = tool.get_signature_key({"action": "type_text"})
        assert key_click != key_type

    def test_same_action_same_signature(self, tool):
        """相同动作签名键相同（不区分参数）."""
        key1 = tool.get_signature_key({"action": "click", "x": 100, "y": 200})
        key2 = tool.get_signature_key({"action": "click", "x": 300, "y": 400})
        assert key1 == key2  # 都是 "click"


# ═══════════════════════════════════════════════════════════════
#  11. 禁用开关
# ═══════════════════════════════════════════════════════════════


class TestDisabledTool:
    """工具禁用开关测试."""

    def test_disabled_screenshot_fails(self, ctx):
        """禁用后 screenshot 返回失败."""
        tool = ComputerUseTool(enabled=False)
        result = tool.execute(
            {"action": "screenshot", "dry_run": True}, ctx
        )
        assert result.success is False
        assert "禁用" in result.error

    def test_disabled_click_fails(self, ctx):
        """禁用后 click 返回失败."""
        tool = ComputerUseTool(enabled=False)
        result = tool.execute(
            {"action": "click", "x": 100, "y": 100, "dry_run": True}, ctx
        )
        assert result.success is False

    def test_disabled_launch_app_fails(self, ctx):
        """禁用后 launch_app 返回失败."""
        tool = ComputerUseTool(enabled=False)
        result = tool.execute(
            {"action": "launch_app", "app_path": "notepad", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_enabled_by_default(self, tool):
        """默认启用."""
        assert tool.enabled is True


# ═══════════════════════════════════════════════════════════════
#  12. 全局 dry_run_default
# ═══════════════════════════════════════════════════════════════


class TestDryRunDefault:
    """全局 dry_run_default 测试."""

    def test_global_dry_run_blocks_pyautogui(self, dry_tool, ctx):
        """全局 dry_run=True 时 pyautogui 函数不被调用."""
        with mock.patch.object(
            input_ctrl, "pyautogui", create=True
        ) as mock_pg:
            result = dry_tool.execute(
                {"action": "click", "x": 100, "y": 100}, ctx
            )
            assert result.success is True
            assert result.output["dry_run"] is True
            # pyautogui.click 不应被调用
            if hasattr(mock_pg, "click"):
                mock_pg.click.assert_not_called()

    def test_global_dry_run_all_write_actions(self, dry_tool, ctx):
        """全局 dry_run 下所有写动作不实际执行."""
        actions = [
            {"action": "click", "x": 1, "y": 2},
            {"action": "type_text", "text": "hi"},
            {"action": "hotkey", "keys": ["ctrl", "v"]},
            {"action": "scroll", "x": 10, "y": 10, "direction": "up"},
        ]
        for action_input in actions:
            result = dry_tool.execute(action_input, ctx)
            assert result.success is True
            assert result.output["dry_run"] is True

    def test_per_call_dry_run_overrides(self, tool, ctx):
        """单次调用 dry_run=True 覆盖全局 False."""
        result = tool.execute(
            {"action": "click", "x": 100, "y": 100, "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["dry_run"] is True


# ═══════════════════════════════════════════════════════════════
#  13. pyautogui 未安装降级
# ═══════════════════════════════════════════════════════════════


class TestPyAutoGuiNotInstalled:
    """pyautogui 未安装时的优雅降级测试."""

    def test_click_returns_friendly_error(self, tool, ctx):
        """pyautogui 为 None 时 click 返回友好错误."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", False):
            with mock.patch.object(input_ctrl, "pyautogui", None):
                with mock.patch.object(
                    screen, "get_screen_size", return_value=(1920, 1080)
                ):
                    result = tool.execute(
                        {"action": "click", "x": 100, "y": 100,
                         "dry_run": False}, ctx
                    )
        assert result.success is False
        assert "pyautogui" in result.error
        assert "pip install" in result.error

    def test_type_text_returns_friendly_error(self, tool, ctx):
        """pyautogui 为 None 时 type_text 返回友好错误."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", False):
            with mock.patch.object(input_ctrl, "pyautogui", None):
                result = tool.execute(
                    {"action": "type_text", "text": "hello",
                     "dry_run": False}, ctx
                )
        assert result.success is False
        assert "pyautogui" in result.error

    def test_dry_run_works_without_pyautogui(self, tool, ctx):
        """dry_run 模式下即使 pyautogui 未安装也能正常工作."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", False):
            with mock.patch.object(input_ctrl, "pyautogui", None):
                result = tool.execute(
                    {"action": "click", "x": 100, "y": 100,
                     "dry_run": True}, ctx
                )
        assert result.success is True
        assert result.output["dry_run"] is True


# ═══════════════════════════════════════════════════════════════
#  14. 审计日志
# ═══════════════════════════════════════════════════════════════


class TestActionLog:
    """审计日志测试."""

    def test_log_contains_entries(self, tool, ctx):
        """执行动作后日志包含对应条目."""
        tool.execute(
            {"action": "screenshot", "dry_run": True}, ctx
        )
        tool.execute(
            {"action": "click", "x": 100, "y": 200, "dry_run": True}, ctx
        )
        log = tool.get_action_log()
        assert len(log) >= 2
        actions = [entry["action"] for entry in log]
        assert "screenshot" in actions
        assert "click" in actions

    def test_log_entries_have_timestamps(self, tool, ctx):
        """日志条目包含时间戳."""
        tool.execute(
            {"action": "move", "x": 50, "y": 50, "dry_run": True}, ctx
        )
        log = tool.get_action_log()
        assert len(log) >= 1
        assert "timestamp" in log[-1]
        # ISO 格式时间戳
        assert "T" in log[-1]["timestamp"]

    def test_log_records_success_and_failure(self, tool, ctx):
        """日志记录成功和失败."""
        tool.execute(
            {"action": "click", "x": 100, "y": 100, "dry_run": True}, ctx
        )
        tool.execute(
            {"action": "hotkey", "keys": ["ctrl", "alt", "del"],
             "dry_run": True}, ctx
        )
        log = tool.get_action_log()
        # 最后一条应该是失败的
        assert log[-1]["success"] is False
        assert "error" in log[-1]

    def test_log_returns_copy(self, tool, ctx):
        """get_action_log 返回副本，修改不影响内部日志."""
        tool.execute(
            {"action": "screenshot", "dry_run": True}, ctx
        )
        log1 = tool.get_action_log()
        log1.clear()
        log2 = tool.get_action_log()
        assert len(log2) >= 1

    def test_log_params_dont_include_sensitive_data(self, tool, ctx):
        """日志不记录 text 内容以外的大字段（截图数据等）."""
        tool.execute(
            {"action": "type_text", "text": "secret123", "dry_run": True}, ctx
        )
        log = tool.get_action_log()
        last = log[-1]
        assert "text" in last["params"]


# ═══════════════════════════════════════════════════════════════
#  15. 截图保存到指定目录
# ═══════════════════════════════════════════════════════════════


class TestScreenshotSave:
    """截图保存到指定目录测试."""

    def test_screenshot_saved_to_dir(self, ctx, screenshot_dir):
        """截图保存到指定目录并返回路径."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        tool = ComputerUseTool(screenshot_dir=screenshot_dir)

        with mock.patch.object(
            screen, "capture_screen", return_value=fake_png
        ):
            with mock.patch.object(
                screen, "get_screen_size", return_value=(1920, 1080)
            ):
                result = tool.execute(
                    {"action": "screenshot", "dry_run": False}, ctx
                )

        assert result.success is True
        assert result.metadata["saved_to"] is not None
        assert os.path.exists(result.metadata["saved_to"])
        assert tool.last_screenshot_path() is not None

    def test_screenshot_metadata_contains_size(self, ctx, screenshot_dir):
        """截图 metadata 包含 image_size_bytes."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        tool = ComputerUseTool(screenshot_dir=screenshot_dir)

        with mock.patch.object(
            screen, "capture_screen", return_value=fake_png
        ):
            with mock.patch.object(
                screen, "get_screen_size", return_value=(1920, 1080)
            ):
                result = tool.execute(
                    {"action": "screenshot", "dry_run": False}, ctx
                )

        assert result.success is True
        assert result.metadata["image_size_bytes"] == len(fake_png)
        assert result.metadata["screen_size"]["width"] == 1920

    def test_screenshot_dry_run_no_file_saved(self, ctx, screenshot_dir):
        """dry_run 模式下不保存文件."""
        tool = ComputerUseTool(screenshot_dir=screenshot_dir)
        result = tool.execute(
            {"action": "screenshot", "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["dry_run"] is True
        # 截图目录应该是空的
        files = os.listdir(screenshot_dir)
        assert len(files) == 0

    def test_last_screenshot_path_initially_none(self, tool):
        """初始状态下 last_screenshot_path 为 None."""
        assert tool.last_screenshot_path() is None

    def test_screenshot_with_region(self, ctx, screenshot_dir):
        """区域截图正常工作."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
        tool = ComputerUseTool(screenshot_dir=screenshot_dir)

        with mock.patch.object(
            screen, "capture_screen", return_value=fake_png
        ) as mock_capture:
            with mock.patch.object(
                screen, "get_screen_size", return_value=(1920, 1080)
            ):
                result = tool.execute(
                    {
                        "action": "screenshot",
                        "region": {"x": 0, "y": 0, "width": 100, "height": 100},
                        "dry_run": False,
                    },
                    ctx,
                )

        assert result.success is True
        mock_capture.assert_called_once_with(
            region={"x": 0, "y": 0, "width": 100, "height": 100}
        )


# ═══════════════════════════════════════════════════════════════
#  16. 参数校验
# ═══════════════════════════════════════════════════════════════


class TestParameterValidation:
    """参数校验测试."""

    def test_missing_action_fails(self, tool, ctx):
        """缺少 action 返回失败."""
        result = tool.execute({"dry_run": True}, ctx)
        assert result.success is False
        assert "action" in result.error

    def test_click_missing_xy_fails(self, tool, ctx):
        """click 缺少 x/y 返回失败."""
        result = tool.execute(
            {"action": "click", "dry_run": True}, ctx
        )
        assert result.success is False
        assert "x" in result.error and "y" in result.error

    def test_drag_missing_to_xy_fails(self, tool, ctx):
        """drag 缺少 to_x/to_y 返回失败."""
        result = tool.execute(
            {"action": "drag", "x": 0, "y": 0, "dry_run": True}, ctx
        )
        assert result.success is False
        assert "to_x" in result.error or "to_y" in result.error

    def test_type_text_missing_text_fails(self, tool, ctx):
        """type_text 缺少 text 返回失败."""
        result = tool.execute(
            {"action": "type_text", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_press_key_missing_key_fails(self, tool, ctx):
        """press_key 缺少 key 返回失败."""
        result = tool.execute(
            {"action": "press_key", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_hotkey_missing_keys_fails(self, tool, ctx):
        """hotkey 缺少 keys 返回失败."""
        result = tool.execute(
            {"action": "hotkey", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_launch_app_missing_path_fails(self, tool, ctx):
        """launch_app 缺少 app_path 返回失败."""
        result = tool.execute(
            {"action": "launch_app", "dry_run": True}, ctx
        )
        assert result.success is False

    def test_unknown_action_fails(self, tool, ctx):
        """未知 action 返回失败."""
        result = tool.execute(
            {"action": "nonexistent_action", "dry_run": True}, ctx
        )
        assert result.success is False


# ═══════════════════════════════════════════════════════════════
#  17. 危险文本输入检测
# ═══════════════════════════════════════════════════════════════


class TestSuspiciousTypingDetection:
    """可疑键盘输入检测测试."""

    def test_shell_metachars_not_blocked(self, tool, ctx):
        """包含 shell 元字符的输入不被拦截（打字无法判定意图）."""
        result = tool.execute(
            {
                "action": "type_text",
                "text": "ls -la; rm -rf / && echo pwned",
                "dry_run": True,
            },
            ctx,
        )
        # dry_run 下仍然成功
        assert result.success is True

    def test_detect_suspicious_typing_function(self):
        """直接测试 detect_suspicious_typing 函数."""
        # 包含命令替换
        warning = safety.detect_suspicious_typing("$(whoami)")
        assert warning is not None
        assert "shell" in warning.lower() or "元字符" in warning

        # 包含反引号
        warning = safety.detect_suspicious_typing("`id`")
        assert warning is not None

        # 普通文本不触发
        warning = safety.detect_suspicious_typing("hello world")
        assert warning is None

        # 空文本
        warning = safety.detect_suspicious_typing("")
        assert warning is None

    def test_keyboard_type_records_warning(self, ctx):
        """实际 keyboard_type 执行时检测到可疑输入记录 warning（非 dry_run）."""
        mock_pg = mock.MagicMock()
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", True):
            with mock.patch.object(input_ctrl, "pyautogui", mock_pg):
                result = input_ctrl.keyboard_type("$(whoami)")
        assert result["success"] is True
        assert "warning" in result["metadata"]


# ═══════════════════════════════════════════════════════════════
#  18. 焦点窗口
# ═══════════════════════════════════════════════════════════════


class TestWindowFocus:
    """窗口焦点测试."""

    def test_focus_window_dry_run_success(self, tool, ctx):
        """focus_window dry_run 成功."""
        result = tool.execute(
            {"action": "focus_window", "window_id": 12345,
             "dry_run": True}, ctx
        )
        assert result.success is True
        assert result.output["would_execute"]["action"] == "focus_window"

    def test_find_window_not_found_returns_none(self, tool, ctx):
        """find_window 未找到窗口返回 success=True, output=None."""
        with mock.patch.object(screen, "find_window", return_value=None):
            result = tool.execute(
                {"action": "find_window", "window_title": "NonExistentWindow",
                 "dry_run": False}, ctx
            )
        assert result.success is True
        assert result.output is None

    def test_find_window_found(self, tool, ctx):
        """find_window 找到窗口返回窗口信息."""
        fake_window = {
            "id": 12345,
            "title": "Notepad",
            "process_id": 5678,
            "x": 0, "y": 0, "width": 800, "height": 600,
        }
        with mock.patch.object(screen, "find_window", return_value=fake_window):
            result = tool.execute(
                {"action": "find_window", "window_title": "Notepad",
                 "dry_run": False}, ctx
            )
        assert result.success is True
        assert result.output["title"] == "Notepad"
        assert result.metadata["found"] is True

    def test_list_windows_returns_list(self, tool, ctx):
        """list_windows 返回列表."""
        with mock.patch.object(screen, "list_windows", return_value=[]):
            result = tool.execute(
                {"action": "list_windows", "dry_run": False}, ctx
            )
        assert result.success is True
        assert isinstance(result.output, list)
        assert result.metadata["count"] == 0


# ═══════════════════════════════════════════════════════════════
#  额外测试：safety 模块单元测试
# ═══════════════════════════════════════════════════════════════


class TestSafetyModule:
    """safety 模块独立单元测试."""

    def test_normalize_hotkey(self):
        """组合键规范化."""
        assert safety.normalize_hotkey(["Ctrl", "Alt", "Del"]) == "ctrl+alt+del"
        assert safety.normalize_hotkey(["ALT", "F4"]) == "alt+f4"
        assert safety.normalize_hotkey([]) == ""

    def test_is_dangerous_hotkey(self):
        """危险组合键检测."""
        assert safety.is_dangerous_hotkey(["ctrl", "alt", "del"]) is True
        assert safety.is_dangerous_hotkey(["alt", "f4"]) is True
        assert safety.is_dangerous_hotkey(["ctrl", "c"]) is False

    def test_is_dangerous_application(self):
        """危险应用检测."""
        is_danger, keyword = safety.is_dangerous_application("shutdown -s")
        assert is_danger is True
        assert keyword == "shutdown"

        is_danger, keyword = safety.is_dangerous_application("notepad.exe")
        assert is_danger is False

    def test_assess_action_risk_unknown_action(self):
        """未知动作默认 confirm."""
        assert safety.assess_action_risk("unknown_action", {}) == "confirm"

    def test_redact_sensitive_regions_returns_original(self):
        """redact_sensitive_regions 当前返回原图."""
        original = b"fake_image_data"
        result = safety.redact_sensitive_regions(original, [{"x": 0, "y": 0, "width": 10, "height": 10}])
        assert result == original


# ═══════════════════════════════════════════════════════════════
#  额外测试：screen 模块的降级行为
# ═══════════════════════════════════════════════════════════════


class TestScreenModule:
    """screen 模块降级行为测试."""

    def test_capture_screen_no_backend_raises(self):
        """mss 和 PIL 都不可用时 capture_screen 抛出 RuntimeError."""
        with mock.patch.object(screen, "_HAS_MSS", False):
            with mock.patch.object(screen, "_HAS_PIL", False):
                with pytest.raises(RuntimeError, match="mss|Pillow|截图"):
                    screen.capture_screen()

    def test_list_windows_non_windows_returns_empty(self):
        """非 Windows 平台 list_windows 返回空列表."""
        with mock.patch.object(screen.sys, "platform", "linux"):
            windows = screen.list_windows()
            assert isinstance(windows, list)

    def test_focus_window_non_windows_returns_false(self):
        """非 Windows 平台 focus_window 返回 False."""
        with mock.patch.object(screen.sys, "platform", "linux"):
            result = screen.focus_window(12345)
            assert result is False

    def test_capture_screen_with_mss(self):
        """mss 可用时正常截图."""
        fake_rgb = b"\x00" * 100
        fake_size = (10, 10)

        # 模拟 mss 上下文管理器
        mock_sct = mock.MagicMock()
        mock_sct.monitors = [None, {"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_screenshot = mock.MagicMock()
        mock_screenshot.rgb = fake_rgb
        mock_screenshot.size = fake_size
        mock_sct.grab.return_value = mock_screenshot

        mock_mss = mock.MagicMock()
        mock_mss.mss.return_value.__enter__ = mock.MagicMock(return_value=mock_sct)
        mock_mss.mss.return_value.__exit__ = mock.MagicMock(return_value=False)
        mock_mss.tools.to_png.return_value = b"\x89PNG fake"

        with mock.patch.object(screen, "_HAS_MSS", True):
            with mock.patch.object(screen, "mss", mock_mss):
                result = screen.capture_screen()

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_get_screen_size_no_backend_raises(self):
        """无可用后端时 get_screen_size 抛出 RuntimeError."""
        # 模拟 tkinter 导入失败
        mock_tkinter = mock.MagicMock()
        mock_tkinter.Tk.side_effect = Exception("no display")
        with mock.patch.object(screen, "_HAS_MSS", False):
            with mock.patch.object(screen.sys, "platform", "linux"):
                with mock.patch.dict(
                    sys.modules, {"tkinter": mock_tkinter}
                ):
                    with pytest.raises(RuntimeError):
                        screen.get_screen_size()


# ═══════════════════════════════════════════════════════════════
#  额外测试：input_ctrl 模块
# ═══════════════════════════════════════════════════════════════


class TestInputCtrlModule:
    """input_ctrl 模块单元测试."""

    def test_launch_application_dangerous_blocked(self):
        """input_ctrl.launch_application 直接拦截危险程序."""
        result = input_ctrl.launch_application("shutdown -s")
        assert result["success"] is False
        assert "安全策略" in result["error"]

    def test_launch_application_empty_command(self):
        """空命令返回错误."""
        result = input_ctrl.launch_application("")
        assert result["success"] is False

    def test_keyboard_hotkey_dangerous_blocked(self):
        """input_ctrl.keyboard_hotkey 直接拦截危险组合键."""
        result = input_ctrl.keyboard_hotkey("alt", "f4")
        assert result["success"] is False
        assert "安全策略" in result["error"]

    def test_mouse_click_no_pyautogui(self):
        """pyautogui 未安装时 mouse_click 返回错误."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", False):
            with mock.patch.object(input_ctrl, "pyautogui", None):
                result = input_ctrl.mouse_click(100, 100)
        assert result["success"] is False
        assert "pyautogui" in result["error"]

    def test_keyboard_type_no_pyautogui(self):
        """pyautogui 未安装时 keyboard_type 返回错误."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", False):
            with mock.patch.object(input_ctrl, "pyautogui", None):
                result = input_ctrl.keyboard_type("hello")
        assert result["success"] is False

    def test_mouse_move_with_pyautogui(self):
        """pyautogui 可用时 mouse_move 正常调用."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", True):
            mock_pg = mock.MagicMock()
            with mock.patch.object(input_ctrl, "pyautogui", mock_pg):
                result = input_ctrl.mouse_move(100, 200, duration=0.5)
        assert result["success"] is True
        mock_pg.moveTo.assert_called_once_with(x=100, y=200, duration=0.5)

    def test_keyboard_press_with_pyautogui(self):
        """pyautogui 可用时 keyboard_press 正常调用."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", True):
            mock_pg = mock.MagicMock()
            with mock.patch.object(input_ctrl, "pyautogui", mock_pg):
                result = input_ctrl.keyboard_press("enter")
        assert result["success"] is True
        mock_pg.press.assert_called_once_with("enter")

    def test_mouse_scroll_up(self):
        """向上滚动调用 pyautogui.scroll 正数."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", True):
            mock_pg = mock.MagicMock()
            with mock.patch.object(input_ctrl, "pyautogui", mock_pg):
                result = input_ctrl.mouse_scroll(100, 100, direction="up", amount=5)
        assert result["success"] is True
        mock_pg.scroll.assert_called_once_with(5)

    def test_mouse_scroll_down(self):
        """向下滚动调用 pyautogui.scroll 负数."""
        with mock.patch.object(input_ctrl, "_HAS_PYAUTOGUI", True):
            mock_pg = mock.MagicMock()
            with mock.patch.object(input_ctrl, "pyautogui", mock_pg):
                result = input_ctrl.mouse_scroll(100, 100, direction="down", amount=3)
        assert result["success"] is True
        mock_pg.scroll.assert_called_once_with(-3)
