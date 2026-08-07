"""Suyi 技能系统模块.

导出技能加载器、菜单生成器、安全扫描器.

渐进式披露三阶段：
1. **Menu 阶段**：只加载 name + description（约 100 token/技能）.
2. **Load 阶段**：加载技能的 SKILL.md 完整内容.
3. **Execute 阶段**：解析 SKILL.md 指令，执行技能流程.

快速使用::

    from suyi.skills import SkillLoader, SkillMenu, SkillScanner

    loader = SkillLoader('skills/')
    menu = SkillMenu()
    menu_text = menu.generate(loader)
    print(menu_text)

    # 安全扫描
    scanner = SkillScanner()
    risk = scanner.scan(skill_md_content)
    if risk == 'dangerous':
        print("拒绝加载此技能")
"""

from .loader import (
    SkillLoader,
    SkillMeta,
    SkillContent,
)
from .menu import SkillMenu
from .scanner import (
    SkillScanner,
    ScanFinding,
    RISK_SAFE,
    RISK_WARNING,
    RISK_DANGEROUS,
)

__all__ = [
    # 加载器
    "SkillLoader",
    "SkillMeta",
    "SkillContent",
    # 菜单
    "SkillMenu",
    # 扫描器
    "SkillScanner",
    "ScanFinding",
    "RISK_SAFE",
    "RISK_WARNING",
    "RISK_DANGEROUS",
]
