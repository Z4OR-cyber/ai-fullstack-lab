"""ComputerUseTool — OS 级桌面控制工具包.

提供截图、鼠标、键盘、窗口管理和应用启动能力.
这是 Agent 接通软件的第 5 层能力.

子模块：
- ``screen``: 屏幕感知（截屏、分辨率、窗口枚举）.
- ``input_ctrl``: 输入控制（鼠标、键盘、应用启动）.
- ``safety``: 安全护栏（危险组合键、风险评估、坐标检查）.
- ``computer_tool``: 主工具类 ``ComputerUseTool``.
"""

from .computer_tool import ComputerUseTool

__all__ = ["ComputerUseTool"]
