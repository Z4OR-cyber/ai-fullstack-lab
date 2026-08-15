"""屏幕感知模块 — 截屏、分辨率获取、窗口管理.

提供屏幕截图和窗口枚举的跨平台实现.

依赖策略：
- 优先使用 ``mss`` 进行高性能截图.
- 降级到 ``PIL.ImageGrab``（如果 Pillow 已安装）.
- 两者都不可用时返回明确的错误信息，不崩溃.

窗口管理：
- Windows 平台通过 ``ctypes`` 调用 ``user32.dll`` 枚举窗口.
- macOS / Linux 暂返回空列表或提示不支持（后续可扩展）.
"""

import ctypes
import sys
from ctypes import wintypes
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
#  可选依赖检测
# ═══════════════════════════════════════════════════════════════

try:
    import mss  # type: ignore
    _HAS_MSS = True
except ImportError:
    mss = None  # type: ignore
    _HAS_MSS = False

try:
    from PIL import ImageGrab  # type: ignore
    _HAS_PIL = True
except ImportError:
    ImageGrab = None  # type: ignore
    _HAS_PIL = False


# ═══════════════════════════════════════════════════════════════
#  截屏
# ═══════════════════════════════════════════════════════════════


def capture_screen(
    region: Optional[Dict[str, int]] = None,
) -> bytes:
    """截屏并返回 PNG 字节数据.

    优先使用 mss（高性能），降级到 PIL.ImageGrab.
    两者都不可用时抛出 RuntimeError.

    Args:
        region: 截图区域，格式为
            ``{"x": int, "y": int, "width": int, "height": int}``.
            为 None 时截取全屏.

    Returns:
        PNG 格式的截图字节数据.

    Raises:
        RuntimeError: mss 和 PIL 都不可用时抛出.
    """
    monitor = None
    if region:
        monitor = {
            "left": region.get("x", 0),
            "top": region.get("y", 0),
            "width": region.get("width", 100),
            "height": region.get("height", 100),
        }

    # 优先 mss
    if _HAS_MSS:
        with mss.mss() as sct:
            if monitor:
                screenshot = sct.grab(monitor)
            else:
                # mss 的 monitors[1] 是主显示器（monitors[0] 是所有显示器的合并）
                screenshot = sct.grab(sct.monitors[1])

            # mss 返回的是 BGRA 数据，需要转换为 PNG
            # mss.tools.to_png 可用，但为避免额外依赖，手动构建 PNG
            # mss 内部提供 to_png 方法
            png_bytes = mss.tools.to_png(
                screenshot.rgb, screenshot.size
            )
            return png_bytes

    # 降级 PIL.ImageGrab
    if _HAS_PIL:
        bbox = None
        if region:
            bbox = (
                region["x"],
                region["y"],
                region["x"] + region["width"],
                region["y"] + region["height"],
            )
        image = ImageGrab.grab(bbox=bbox)
        import io
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    raise RuntimeError(
        "截图功能不可用：请安装 mss（pip install mss）或 "
        "Pillow（pip install Pillow）"
    )


def get_screen_size() -> Tuple[int, int]:
    """获取屏幕分辨率.

    优先通过 mss 获取，降级到 ctypes（Windows）或 tkinter.

    Returns:
        (width, height) 屏幕分辨率元组.

    Raises:
        RuntimeError: 无法获取屏幕分辨率时抛出.
    """
    # 通过 mss 获取
    if _HAS_MSS:
        try:
            with mss.mss() as sct:
                # monitors[1] 是主显示器
                monitor = sct.monitors[1]
                return (monitor["width"], monitor["height"])
        except Exception:
            pass

    # Windows ctypes
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            return (width, height)
        except Exception:
            pass

    # 尝试 tkinter（跨平台，但可能无显示）
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return (width, height)
    except Exception:
        pass

    raise RuntimeError(
        "无法获取屏幕分辨率：请安装 mss（pip install mss）"
    )


# ═══════════════════════════════════════════════════════════════
#  窗口管理（Windows 实现）
# ═══════════════════════════════════════════════════════════════

# Windows API 回调函数类型
if sys.platform == "win32":
    _WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )


def _enum_windows_callback(hwnd, lparam):
    """EnumWindows 回调函数，收集可见窗口信息.

    Args:
        hwnd: 窗口句柄.
        lparam: 用户参数（指向结果列表的指针，这里不使用）.

    Returns:
        始终返回 True 以继续枚举.
    """
    user32 = ctypes.windll.user32

    # 只收集可见窗口
    if not user32.IsWindowVisible(hwnd):
        return True

    # 获取窗口标题长度
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return True

    # 获取窗口标题
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value

    if not title.strip():
        return True

    # 获取窗口位置
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    # 获取进程 ID
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # 存储到 lparam 指向的列表
    windows_list = ctypes.cast(lparam, ctypes.py_object).value
    windows_list.append({
        "id": hwnd,
        "title": title,
        "process_id": pid.value,
        "x": rect.left,
        "y": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    })

    return True


def list_windows() -> List[Dict[str, Any]]:
    """列出所有可见窗口.

    Windows 平台通过 ctypes 调用 user32.dll 枚举窗口.
    macOS / Linux 暂返回空列表.

    Returns:
        窗口信息列表，每个窗口包含：
        - ``id``: 窗口句柄（Windows）或窗口 ID.
        - ``title``: 窗口标题.
        - ``process_id``: 进程 ID.
        - ``x``, ``y``: 窗口左上角坐标.
        - ``width``, ``height``: 窗口宽高.
    """
    if sys.platform != "win32":
        return []

    try:
        user32 = ctypes.windll.user32
        windows: List[Dict[str, Any]] = []

        # 使用 py_object 传递列表引用
        lparam = ctypes.py_object(windows)
        callback = _WNDENUMPROC(_enum_windows_callback)
        user32.EnumWindows(callback, lparam)

        return windows
    except Exception:
        return []


def find_window(title_substring: str) -> Optional[Dict[str, Any]]:
    """按标题模糊查找窗口.

    Args:
        title_substring: 窗口标题的子串（大小写不敏感）.

    Returns:
        找到的窗口信息字典，未找到返回 None.
    """
    if not title_substring:
        return None

    windows = list_windows()
    title_lower = title_substring.lower()

    for win in windows:
        if title_lower in win.get("title", "").lower():
            return win

    return None


def focus_window(window_id: int) -> bool:
    """聚焦指定窗口.

    Args:
        window_id: 窗口句柄（Windows HWND）.

    Returns:
        成功聚焦返回 True，失败返回 False.
    """
    if sys.platform != "win32":
        return False

    try:
        user32 = ctypes.windll.user32
        hwnd = int(window_id)

        # 如果窗口最小化，先恢复
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)

        # 前置窗口
        result = user32.SetForegroundWindow(hwnd)
        return bool(result)
    except Exception:
        return False
