"""技能菜单生成器 — 为 LLM 生成可消费的技能菜单.

设计原则：
- **紧凑优先**：默认紧凑格式（每技能一行），最小化 token 消耗.
- **XML 标签包裹**：支持用 ``<available_skills>`` 标签包裹菜单，
  便于在 prompt 中结构化嵌入.
- **关键词匹配选择**：select() 基于关键词匹配辅助 LLM 选择技能.

与 SkillLoader 的协作：
- :meth:`generate` 从 SkillLoader 获取技能列表，生成菜单文本.
- :meth:`select` 基于用户 query 匹配最相关技能.
"""

import re
from typing import List, Optional

from .loader import SkillLoader, SkillMeta


class SkillMenu:
    """技能菜单生成器.

    从 SkillLoader 获取技能元数据，生成不同格式的菜单文本.
    生成的菜单文本可直接嵌入 prompt 供 LLM 消费.

    Attributes:
        _last_menu_text: 最近一次生成的菜单文本缓存.
    """

    def __init__(self):
        self._last_menu_text: str = ""
        self._last_skills: List[SkillMeta] = []

    # ── 菜单生成 ─────────────────────────────────────────

    def generate(self, loader: SkillLoader) -> str:
        """从 SkillLoader 生成技能菜单文本（紧凑格式）.

        Args:
            loader: 技能加载器实例.

        Returns:
            紧凑格式的菜单文本.
        """
        skills = loader.get_menu()
        self._last_skills = skills
        self._last_menu_text = self.format_compact(skills)
        return self._last_menu_text

    @staticmethod
    def format_compact(skills: List[SkillMeta]) -> str:
        """生成紧凑格式菜单（每技能一行）.

        格式::

            skill-name: 一句话描述
            another-skill: 另一句描述

        Args:
            skills: 技能元数据列表.

        Returns:
            紧凑格式菜单文本.
        """
        if not skills:
            return "(无可用技能)"

        lines: List[str] = []
        for meta in skills:
            lines.append(f"{meta.name}: {meta.description}")
        return "\n".join(lines)

    @staticmethod
    def format_detailed(skills: List[SkillMeta]) -> str:
        """生成详细格式菜单（含技能名、描述、资源提示）.

        格式::

            ## skill-name
            描述: 一句话描述这个技能做什么
            附件: scripts/, references/

        Args:
            skills: 技能元数据列表.

        Returns:
            详细格式菜单文本.
        """
        if not skills:
            return "(无可用技能)"

        blocks: List[str] = []
        for meta in skills:
            block = (
                f"## {meta.name}\n"
                f"描述: {meta.description}\n"
                f"附件: scripts/, references/"
            )
            blocks.append(block)
        return "\n\n".join(blocks)

    @staticmethod
    def to_xml_tag(menu_text: str) -> str:
        """用 XML 标签包裹菜单文本.

        将菜单文本用 ``<available_skills>`` 标签包裹，
        便于在 prompt 中结构化嵌入.

        Args:
            menu_text: 菜单文本.

        Returns:
            XML 标签包裹的菜单文本.

        Examples:
            >>> text = "skill-a: 描述A"
            >>> print(SkillMenu.to_xml_tag(text))
            <available_skills>
            skill-a: 描述A
            </available_skills>
        """
        return f"<available_skills>\n{menu_text}\n</available_skills>"

    # ── 技能选择 ─────────────────────────────────────────

    @staticmethod
    def select(menu_text: str, query: str, top_k: int = 3) -> List[str]:
        """从菜单文本中基于关键词匹配选择最相关的技能.

        解析菜单文本中的技能名和描述，
        与 query 进行关键词匹配，返回最相关的技能名列表.

        Args:
            menu_text: 菜单文本（紧凑格式 ``name: description``）.
            query: 用户查询文本.
            top_k: 返回的最多技能数量.

        Returns:
            匹配度从高到低的技能名列表.
        """
        if not menu_text or menu_text == "(无可用技能)":
            return []

        # 解析菜单文本：每行 "name: description"
        skill_entries: List[tuple[str, str]] = []
        for line in menu_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("<"):
                continue
            # 查找第一个冒号分隔符
            colon_pos = line.find(":")
            if colon_pos < 0:
                continue
            name = line[:colon_pos].strip()
            description = line[colon_pos + 1:].strip()
            skill_entries.append((name, description))

        if not skill_entries:
            return []

        # 简单分词
        query_words = set(
            w.lower() for w in re.split(r"[^\w]+", query) if len(w) >= 2
        )

        if not query_words:
            return [name for name, _ in skill_entries][:top_k]

        # 统计命中数
        scored: List[tuple[int, str]] = []
        for name, description in skill_entries:
            skill_text = (name + " " + description).lower()
            skill_words = set(
                w.lower() for w in re.split(r"[^\w]+", skill_text) if len(w) >= 2
            )
            hits = len(query_words & skill_words)
            scored.append((hits, name))

        # 按命中数降序
        scored.sort(key=lambda x: x[0], reverse=True)

        # 只返回命中数 > 0 的技能
        result = [name for score, name in scored if score > 0]
        if not result:
            # 没有命中，返回全部
            return [name for name, _ in skill_entries][:top_k]
        return result[:top_k]

    # ── 便捷方法 ─────────────────────────────────────────

    def get_xml_menu(self, loader: SkillLoader) -> str:
        """一步生成 XML 标签包裹的菜单.

        等价于::

            menu = generate(loader)
            to_xml_tag(menu)

        Args:
            loader: 技能加载器实例.

        Returns:
            XML 标签包裹的菜单文本.
        """
        menu_text = self.generate(loader)
        return self.to_xml_tag(menu_text)

    def get_skills(self) -> List[SkillMeta]:
        """返回最近一次 generate() 获取的技能列表.

        Returns:
            SkillMeta 列表；若未调用过 generate()，返回空列表.
        """
        return self._last_skills
