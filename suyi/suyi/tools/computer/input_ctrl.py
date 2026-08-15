"""输入控制模块 — 鼠标、键盘和应用启动.

封装 pyautogui 的鼠标和键盘操作，以及跨平台应用启动.

依赖策略：
- ``pyautogui`` 是可选依赖，未安装时所有函数返回明确的错误信息.
- 所有函数包裹在 try/except 中，不会因底层异常导致崩溃.
- 应用启动使用标准库 ``subprocess`` 和 ``sys.platform`` 分派.
"""

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from . import safety


# ═══════════════════════════════════════════════════════════════
#  可选依赖检测
# ═══════════════════════════════════════════════════════════════

try:
    import pyautogui  # type: ignore
    # 设置 pyautogui 安全特性：故障保护（鼠标移到左上角会触发异常）
    pyautogui.FAILSAFE = True
    # 默认操作间隔（秒），避免操作过快
    pyautogui.PAUSE = 0.05
    _HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None  # type: ignore
    _HAS_PYAUTOGUI = False


# pyautogui 未安装时的统一错误消息
_PYAUTOGUI_MISSING_MSG = (
    "pyautogui 未安装，无法执行鼠标/键盘操作。"
    "请安装: pip install pyautogui"
)


# ═══════════════════════════════════════════════════════════════
#  内部辅助
# ═══════════════════════════════════════════════════════════════


def _check_pyautogui() -> Optional[str]:
    """检查 pyautogui 是否可用.

    Returns:
        不可用时返回错误消息字符串，可用时返回 None.
    """
    if not _HAS_PYAUTOGUI:
        return _PYAUTOGUI_MISSING_MSG
    return None


# ═══════════════════════════════════════════════════════════════
#  鼠标操作
# ═══════════════════════════════════════════════════════════════


def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.1,
) -> Dict[str, Any]:
    """在指定坐标点击鼠标.

    Args:
        x: 横坐标.
        y: 纵坐标.
        button: 鼠标按键，``"left"`` / ``"right"`` / ``"middle"``.
        clicks: 点击次数.
        interval: 多次点击之间的间隔（秒）.

    Returns:
        结果字典，包含 ``success`` 和可选的 ``error`` / ``metadata``.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
        return {
            "success": True,
            "metadata": {"x": x, "y": y, "button": button, "clicks": clicks},
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标点击失败: {e}"}


def mouse_double_click(x: int, y: int) -> Dict[str, Any]:
    """在指定坐标双击鼠标左键.

    Args:
        x: 横坐标.
        y: 纵坐标.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.doubleClick(x=x, y=y)
        return {
            "success": True,
            "metadata": {"x": x, "y": y, "button": "left", "clicks": 2},
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标双击失败: {e}"}


def mouse_right_click(x: int, y: int) -> Dict[str, Any]:
    """在指定坐标点击鼠标右键.

    Args:
        x: 横坐标.
        y: 纵坐标.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.rightClick(x=x, y=y)
        return {
            "success": True,
            "metadata": {"x": x, "y": y, "button": "right", "clicks": 1},
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标右键点击失败: {e}"}


def mouse_move(x: int, y: int, duration: float = 0.2) -> Dict[str, Any]:
    """移动鼠标到指定坐标.

    Args:
        x: 目标横坐标.
        y: 目标纵坐标.
        duration: 移动持续时间（秒），0 为瞬间移动.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.moveTo(x=x, y=y, duration=duration)
        return {
            "success": True,
            "metadata": {"x": x, "y": y, "duration": duration},
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标移动失败: {e}"}


def mouse_drag(
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    duration: float = 0.3,
    button: str = "left",
) -> Dict[str, Any]:
    """从起点拖拽鼠标到终点.

    Args:
        from_x: 起点横坐标.
        from_y: 起点纵坐标.
        to_x: 终点横坐标.
        to_y: 终点纵坐标.
        duration: 拖拽持续时间（秒）.
        button: 拖拽时按住的鼠标按键.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        # 先移动到起点
        pyautogui.moveTo(x=from_x, y=from_y, duration=0)
        # 拖拽到终点
        pyautogui.dragTo(
            x=to_x, y=to_y, duration=duration, button=button
        )
        return {
            "success": True,
            "metadata": {
                "from_x": from_x,
                "from_y": from_y,
                "to_x": to_x,
                "to_y": to_y,
                "duration": duration,
                "button": button,
            },
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标拖拽失败: {e}"}


def mouse_scroll(
    x: int, y: int, direction: str = "up", amount: int = 3
) -> Dict[str, Any]:
    """在指定位置滚动鼠标滚轮.

    Args:
        x: 横坐标.
        y: 纵坐标.
        direction: 滚动方向，``"up"`` 或 ``"down"``.
        amount: 滚动量（正数向上/负数向下，取决于 pyautogui 约定）.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        # 先移动到目标位置
        pyautogui.moveTo(x=x, y=y, duration=0)

        # pyautogui.scroll 正数向上滚动，负数向下滚动
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount)

        return {
            "success": True,
            "metadata": {
                "x": x,
                "y": y,
                "direction": direction,
                "amount": amount,
            },
        }
    except Exception as e:
        return {"success": False, "error": f"鼠标滚动失败: {e}"}


# ═══════════════════════════════════════════════════════════════
#  键盘操作
# ═══════════════════════════════════════════════════════════════


def keyboard_type(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """模拟键盘输入文本.

    Args:
        text: 要输入的文本.
        interval: 每个按键之间的间隔（秒）.

    Returns:
        结果字典，metadata 中可能包含 warning.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.typewrite(text, interval=interval)

        result: Dict[str, Any] = {
            "success": True,
            "metadata": {"text_length": len(text)},
        }

        # 检测可疑输入模式
        warning = safety.detect_suspicious_typing(text)
        if warning:
            result["metadata"]["warning"] = warning

        return result
    except Exception as e:
        return {"success": False, "error": f"键盘输入失败: {e}"}


def keyboard_press(key: str) -> Dict[str, Any]:
    """按下并释放单个键.

    Args:
        key: 键名，如 ``"enter"``、``"esc"``、``"tab"``、``"up"`` 等.

    Returns:
        结果字典.
    """
    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.press(key)
        return {
            "success": True,
            "metadata": {"key": key},
        }
    except Exception as e:
        return {"success": False, "error": f"按键失败: {e}"}


def keyboard_hotkey(*keys: str) -> Dict[str, Any]:
    """按下组合键.

    例如 ``keyboard_hotkey("ctrl", "c")`` 发送 Ctrl+C.

    Args:
        *keys: 组成组合键的各键名.

    Returns:
        结果字典.
    """
    # 安全检查：危险组合键（优先于依赖检查，即使 pyautogui 未安装也要拦截）
    if safety.is_dangerous_hotkey(list(keys)):
        normalized = safety.normalize_hotkey(list(keys))
        return {
            "success": False,
            "error": f"操作被安全策略阻止: 危险组合键 '{normalized}' 已被禁止",
        }

    err = _check_pyautogui()
    if err:
        return {"success": False, "error": err}

    try:
        pyautogui.hotkey(*keys)
        return {
            "success": True,
            "metadata": {"keys": list(keys)},
        }
    except Exception as e:
        return {"success": False, "error": f"组合键执行失败: {e}"}


# ═══════════════════════════════════════════════════════════════
#  应用启动
# ═══════════════════════════════════════════════════════════════


def launch_application(path_or_command: str) -> Dict[str, Any]:
    """启动应用程序.

    跨平台实现：
    - Windows: 使用 ``os.startfile`` 或 ``subprocess.Popen``（detached）.
    - macOS: 使用 ``open`` 命令.
    - Linux: 使用 ``xdg-open`` 或直接执行.

    危险应用程序会被安全策略拦截.

    Args:
        path_or_command: 应用程序路径或启动命令.

    Returns:
        结果字典.
    """
    if not path_or_command or not isinstance(path_or_command, str):
        return {"success": False, "error": "未提供应用程序路径或命令"}

    # 安全检查：危险应用程序
    is_dangerous, keyword = safety.is_dangerous_application(path_or_command)
    if is_dangerous:
        return {
            "success": False,
            "error": (
                f"操作被安全策略阻止: 命令/程序 '{path_or_command}' "
                f"包含危险关键词 '{keyword}'"
            ),
        }

    try:
        if sys.platform == "win32":
            # Windows: 优先 os.startfile（适用于文档和可执行文件）
            try:
                os.startfile(path_or_command)  # type: ignore[attr-defined]
            except (OSError, AttributeError):
                # 降级到 subprocess.Popen
                subprocess.Popen(
                    path_or_command,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
                )
        elif sys.platform == "darwin":
            # macOS: 使用 open 命令
            subprocess.Popen(
                ["open", path_or_command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Linux/其他: 尝试 xdg-open，否则直接执行
            try:
                subprocess.Popen(
                    ["xdg-open", path_or_command],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                # 直接作为命令执行
                subprocess.Popen(
                    path_or_command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        return {
            "success": True,
            "metadata": {"launched": path_or_command},
        }
    except Exception as e:
        return {"success": False, "error": f"应用启动失败: {e}"}
