"""安全护栏模块 — ComputerUseTool 的安全策略.

定义危险组合键、危险应用程序、坐标安全检查和动作风险评估.

设计原则：
- **纵深防御**：在工具执行前进行安全检查，危险操作直接拦截.
- **风险分级**：只读操作 auto、有副作用操作 confirm、危险操作 block.
- **可扩展**：危险集合和评估规则集中管理，便于后续扩展.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════
#  危险集合定义
# ═══════════════════════════════════════════════════════════════

#: 禁止的组合键（统一小写，键之间用 + 连接）.
#: 这些组合键会导致关闭窗口、锁屏、打开任务管理器等不可恢复的系统操作.
DANGEROUS_KEY_COMBINATIONS: Set[str] = {
    "alt+f4",            # 关闭当前窗口
    "ctrl+alt+del",      # 安全注意（锁屏/任务管理器/改密码）
    "win+l",             # 锁屏（Windows）
    "cmd+q",             # 退出应用（macOS）
    "ctrl+shift+esc",    # 直接打开任务管理器（Windows）
    "ctrl+alt+f1",       # 切换 TTY（Linux）
    "ctrl+alt+f2",       # 切换 TTY（Linux）
    "ctrl+alt+f3",       # 切换 TTY（Linux）
    "ctrl+alt+backspace",# 重启 X Server（Linux）
    "cmd+option+esc",    # 强制退出（macOS）
    "cmd+ctrl+q",        # 锁屏（macOS）
    "alt+sysrq",         # Magic SysRq key（Linux）
}

#: 禁止启动的应用程序/命令关键词.
#: 使用小写子串匹配，涵盖各平台的高风险命令.
DANGEROUS_APPLICATIONS: Set[str] = {
    "rm",            # 删除文件（Unix）
    "format",        # 格式化磁盘
    "shutdown",      # 关机
    "reboot",        # 重启
    "halt",          # 停机
    "reg",           # 注册表操作（Windows）
    "regedit",       # 注册表编辑器
    "cmd /c del",    # 命令行删除（Windows）
    "diskpart",      # 磁盘分区工具
    "dd",            # 磁盘写入（Unix）
    "mkfs",          # 创建文件系统（格式化）
    "fdisk",         # 磁盘分区
    "del /f",        # 强制删除（Windows）
    "rd /s",         # 删除目录树（Windows）
    "rmdir /s",      # 删除目录树（Windows）
    "taskkill",      # 强制终止进程
    "killall",       # 终止进程
    "poweroff",      # 关机
    "init 0",        # 关机（System V）
    "init 6",        # 重启（System V）
    ":(){:|:&};:",  # Fork bomb
    "chmod 777",     # 危险权限设置
    "chown",         # 修改文件所有者
}

#: 键盘输入中疑似 shell 元字符的模式.
#: 这些字符本身不构成拦截理由（打字是正常的），但会触发 warning.
_SHELL_METACHAR_PATTERN = re.compile(r"[;&|`$><]{2,}|`[^`]+`|\$\([^)]+\)")

#: 动作风险级别映射表.
#: key 为 action 名称，value 为默认风险级别.
_ACTION_RISK_MAP: Dict[str, str] = {
    # 只读动作 — auto
    "screenshot": "auto",
    "get_screen_size": "auto",
    "list_windows": "auto",
    "find_window": "auto",
    # 低风险动作 — auto（仅移动光标/按普通键，无实际副作用）
    "move": "auto",
    "focus_window": "auto",
    # 有副作用动作 — confirm
    "click": "confirm",
    "double_click": "confirm",
    "right_click": "confirm",
    "drag": "confirm",
    "scroll": "confirm",
    "type_text": "confirm",
    "press_key": "auto",  # 普通单键默认 auto，危险键在 assess 中升级
    "launch_app": "confirm",
    "hotkey": "confirm",  # 普通组合键 confirm，危险组合键在 assess 中升级
}


# ═══════════════════════════════════════════════════════════════
#  坐标安全检查
# ═══════════════════════════════════════════════════════════════


def is_coordinate_safe(
    x: int, y: int, screen_size: Tuple[int, int]
) -> bool:
    """检查坐标是否在屏幕范围内.

    Args:
        x: 横坐标.
        y: 纵坐标.
        screen_size: 屏幕分辨率 (width, height).

    Returns:
        坐标在屏幕范围内返回 True，否则返回 False.
    """
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False
    width, height = screen_size
    if width <= 0 or height <= 0:
        return False
    return 0 <= x < width and 0 <= y < height


# ═══════════════════════════════════════════════════════════════
#  组合键规范化与检查
# ═══════════════════════════════════════════════════════════════


def normalize_hotkey(keys: List[str]) -> str:
    """将组合键列表规范化为小写字符串.

    例如 ``["Ctrl", "Alt", "Del"]`` → ``"ctrl+alt+del"``.

    Args:
        keys: 按键名称列表.

    Returns:
        规范化后的组合键字符串，键之间用 ``+`` 连接.
    """
    return "+".join(k.strip().lower() for k in keys if k and k.strip())


def is_dangerous_hotkey(keys: List[str]) -> bool:
    """检查组合键是否在危险集合中.

    Args:
        keys: 按键名称列表.

    Returns:
        危险组合键返回 True，否则返回 False.
    """
    normalized = normalize_hotkey(keys)
    return normalized in DANGEROUS_KEY_COMBINATIONS


# ═══════════════════════════════════════════════════════════════
#  应用程序安全检查
# ═══════════════════════════════════════════════════════════════


def is_dangerous_application(path_or_command: str) -> Tuple[bool, str]:
    """检查应用程序启动命令是否包含危险程序名.

    使用小写子串匹配，对命令进行简单的危险关键词检测.

    Args:
        path_or_command: 应用程序路径或启动命令.

    Returns:
        (is_dangerous, matched_keyword): 如果危险返回 (True, 匹配的关键词);
        否则返回 (False, "").
    """
    if not path_or_command or not isinstance(path_or_command, str):
        return False, ""

    command_lower = path_or_command.lower().strip()

    for keyword in DANGEROUS_APPLICATIONS:
        if keyword in command_lower:
            return True, keyword

    return False, ""


# ═══════════════════════════════════════════════════════════════
#  键盘输入可疑模式检测
# ═══════════════════════════════════════════════════════════════


def detect_suspicious_typing(text: str) -> Optional[str]:
    """检测键盘输入中是否包含疑似 shell 注入的元字符序列.

    键盘输入本身是打字行为，无法判定意图，因此不拦截，
    但如果检测到可疑的 shell 元字符模式，返回 warning 信息.

    Args:
        text: 待检测的文本.

    Returns:
        检测到可疑模式时返回 warning 描述字符串，否则返回 None.
    """
    if not text or not isinstance(text, str):
        return None

    match = _SHELL_METACHAR_PATTERN.search(text)
    if match:
        return (
            f"输入文本包含疑似 shell 元字符序列: '{match.group()}'，"
            f"已记录但不拦截（键盘输入无法判定意图）"
        )
    return None


# ═══════════════════════════════════════════════════════════════
#  动作风险评估
# ═══════════════════════════════════════════════════════════════


def assess_action_risk(action: str, params: Dict[str, Any]) -> str:
    """评估动作的风险级别.

    风险级别：
    - ``"auto"``：只读或低风险，可自动执行.
    - ``"confirm"``：有副作用，需用户确认.
    - ``"block"``：危险操作，硬限制禁止执行.

    评估逻辑：
    1. 先查 ``_ACTION_RISK_MAP`` 获取基础风险级别.
    2. 对 ``hotkey`` 动作检查是否为危险组合键 → 升级为 block.
    3. 对 ``launch_app`` 动作检查是否为危险应用 → 升级为 block.
    4. 对 ``press_key`` 动作检查是否为危险单键 → 升级为 block.
    5. 对 ``click`` / ``drag`` 等坐标动作检查坐标越界 → 升级为 block.

    Args:
        action: 动作名称.
        params: 动作参数字典.

    Returns:
        风险级别字符串：``"auto"`` / ``"confirm"`` / ``"block"``.
    """
    base_risk = _ACTION_RISK_MAP.get(action, "confirm")

    # hotkey 危险组合键检查
    if action == "hotkey":
        keys = params.get("keys", [])
        if isinstance(keys, (list, tuple)) and is_dangerous_hotkey(list(keys)):
            return "block"

    # launch_app 危险应用检查
    if action == "launch_app":
        app_path = params.get("app_path", "")
        is_dangerous, _ = is_dangerous_application(app_path)
        if is_dangerous:
            return "block"

    # press_key 危险单键检查（某些键单独按也有风险）
    if action == "press_key":
        key = params.get("key", "")
        if isinstance(key, str) and key.strip().lower() in {
            "power", "sleep", "wake"
        }:
            return "block"

    # 坐标越界检查
    if action in ("click", "double_click", "right_click", "move", "drag", "scroll"):
        x = params.get("x")
        y = params.get("y")
        screen_size = params.get("_screen_size")
        if x is not None and y is not None and screen_size is not None:
            if not is_coordinate_safe(x, y, screen_size):
                return "block"

    return base_risk


# ═══════════════════════════════════════════════════════════════
#  敏感区域打码（预留接口）
# ═══════════════════════════════════════════════════════════════


def redact_sensitive_regions(
    image_bytes: bytes, regions: List[Dict[str, int]]
) -> bytes:
    """对截图中的敏感区域进行打码处理.

    TODO: 后续实现对密码框、API Key 显示区域等的自动打码.
    当前为预留接口，直接返回原始图片数据.

    Args:
        image_bytes: 原始截图的 PNG 字节数据.
        regions: 敏感区域列表，每个区域为
            ``{"x": int, "y": int, "width": int, "height": int}``.

    Returns:
        打码后的图片字节数据。当前直接返回原图.
    """
    # TODO: 实现敏感区域自动打码
    # 1. 识别密码输入框（可能需要 OCR 或 UI 自动化）
    # 2. 在指定区域绘制黑色矩形
    # 3. 返回处理后的 PNG bytes
    return image_bytes
