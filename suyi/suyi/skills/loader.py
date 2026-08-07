"""技能加载器 — 渐进式披露三阶段实现.

设计原则：
- **渐进式披露**：三阶段按需加载，避免一次性加载所有技能全文.
  1. Menu 阶段：只加载 name + description（约 100 token/技能）.
  2. Load 阶段：LLM 选中后加载该技能的 SKILL.md 全文.
  3. Execute 阶段：解析 SKILL.md 指令，执行技能定义的流程.
- **YAML front matter 解析**：用正则解析 SKILL.md 的元数据头部 + Markdown 正文.
- **关键词匹配**：match_skills 基于简单关键词匹配，
  不依赖嵌入模型，保持纯 numpy/标准库依赖.

SKILL.md 格式::

    ---
    name: skill-name
    description: 一句话描述这个技能做什么
    ---
    # 技能正文（Markdown）
    ## 使用步骤
    ## 注意事项
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple


# ── SKILL.md 解析正则 ──────────────────────────────────────

# YAML front matter 块：--- 包裹的头部
_FRONT_MATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n?(.*)$",
    re.DOTALL,
)

# YAML 单行键值对：key: value
_YAML_KV_RE = re.compile(r"^(\w[\w\-]*)\s*:\s*(.*?)\s*$", re.MULTILINE)


class SkillMeta:
    """技能元数据（Menu 阶段加载）.

    仅包含 name + description，约 100 token/技能，
    用于生成技能菜单供 LLM 选择.

    Attributes:
        name: 技能唯一标识符（目录名）.
        description: 一句话描述技能功能.
        skill_dir: 技能目录的绝对路径.
    """

    def __init__(self, name: str, description: str, skill_dir: str):
        self.name = name
        self.description = description
        self.skill_dir = skill_dir

    def to_dict(self) -> dict:
        """转换为字典表示."""
        return {
            "name": self.name,
            "description": self.description,
            "skill_dir": self.skill_dir,
        }

    def __repr__(self) -> str:
        return f"SkillMeta(name={self.name!r}, description={self.description!r})"


class SkillContent:
    """技能完整内容（Load 阶段加载）.

    包含 SKILL.md 的全文及解析后的结构化字段.

    Attributes:
        name: 技能名称.
        description: 技能描述.
        raw: SKILL.md 原始全文.
        front_matter: YAML front matter 解析后的字典.
        body: Markdown 正文（front matter 之后的内容）.
        skill_dir: 技能目录路径.
    """

    def __init__(
        self,
        name: str,
        description: str,
        raw: str,
        front_matter: Dict[str, str],
        body: str,
        skill_dir: str,
    ):
        self.name = name
        self.description = description
        self.raw = raw
        self.front_matter = front_matter
        self.body = body
        self.skill_dir = skill_dir

    def to_dict(self) -> dict:
        """转换为字典表示."""
        return {
            "name": self.name,
            "description": self.description,
            "front_matter": self.front_matter,
            "body": self.body,
            "skill_dir": self.skill_dir,
        }

    def __repr__(self) -> str:
        return (
            f"SkillContent(name={self.name!r}, "
            f"description={self.description!r}, "
            f"body_length={len(self.body)})"
        )


class SkillLoader:
    """技能加载器.

    实现渐进式披露三阶段：
    1. :meth:`discover` + :meth:`get_menu`：扫描目录，生成技能菜单（~100 token/技能）.
    2. :meth:`load_skill`：加载指定技能的 SKILL.md 全文.
    3. :meth:`get_skill_resources`：获取技能的 scripts/ 和 references/ 附件路径.

    Attributes:
        skills_dir: 技能库根目录路径.
        _cache: 已发现的技能元数据缓存（name → SkillMeta）.
    """

    def __init__(self, skills_dir: str):
        """
        Args:
            skills_dir: 技能库根目录路径.
        """
        self.skills_dir = skills_dir
        self._cache: Optional[Dict[str, SkillMeta]] = None

    # ── 阶段 1：发现 + 菜单 ──────────────────────────────

    def discover(self) -> Dict[str, SkillMeta]:
        """扫描技能目录，发现所有含 SKILL.md 的子目录.

        遍历 ``skills_dir`` 下的一级子目录，
        检查每个子目录是否包含 ``SKILL.md`` 文件.
        解析 SKILL.md 的 YAML front matter 获取 name + description.

        结果会被缓存，后续调用直接返回缓存.

        Returns:
            技能名 → SkillMeta 的映射字典.
        """
        if self._cache is not None:
            return self._cache

        cache: Dict[str, SkillMeta] = {}

        if not os.path.isdir(self.skills_dir):
            self._cache = cache
            return cache

        for entry in sorted(os.listdir(self.skills_dir)):
            entry_path = os.path.join(self.skills_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            skill_md_path = os.path.join(entry_path, "SKILL.md")
            if not os.path.isfile(skill_md_path):
                continue

            try:
                meta = self._parse_front_matter(skill_md_path, entry_path)
                if meta is not None:
                    cache[meta.name] = meta
            except Exception:
                # 解析失败的技能跳过，不中断整体发现流程
                continue

        self._cache = cache
        return cache

    def get_menu(self) -> List[SkillMeta]:
        """返回所有技能的 name + description 列表（渐进式披露阶段 1）.

        Returns:
            SkillMeta 列表，按技能名排序.
        """
        skills = self.discover()
        return sorted(skills.values(), key=lambda m: m.name)

    def match_skills(self, query: str, top_k: int = 3) -> List[SkillMeta]:
        """根据 query 语义匹配最相关的技能.

        基于简单关键词匹配：将 query 分词后，
        统计每个技能的 name + description 中命中的关键词数量，
        按命中数降序排列.

        Args:
            query: 用户查询文本.
            top_k: 返回的最多技能数量.

        Returns:
            匹配度从高到低的 SkillMeta 列表.
        """
        skills = self.get_menu()
        if not skills:
            return []

        # 简单分词：按非字母数字字符分割，转小写
        query_words = set(
            w.lower() for w in re.split(r"[^\w]+", query) if len(w) >= 2
        )

        if not query_words:
            return skills[:top_k]

        scored: List[Tuple[int, SkillMeta]] = []
        for meta in skills:
            # 技能文本（name + description）
            skill_text = (meta.name + " " + meta.description).lower()
            skill_words = set(
                w.lower() for w in re.split(r"[^\w]+", skill_text) if len(w) >= 2
            )
            hits = len(query_words & skill_words)
            scored.append((hits, meta))

        # 按命中数降序，命中数为 0 的不返回
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [meta for score, meta in scored if score > 0]
        if not result:
            # 没有命中任何关键词，返回全部（按名称排序）
            return skills[:top_k]
        return result[:top_k]

    # ── 阶段 2：加载技能正文 ─────────────────────────────

    def load_skill(self, skill_name: str) -> Optional[SkillContent]:
        """读取指定技能的 SKILL.md 全文（渐进式披露阶段 2）.

        Args:
            skill_name: 技能名称.

        Returns:
            SkillContent 实例；技能不存在时返回 ``None``.
        """
        skills = self.discover()
        if skill_name not in skills:
            return None

        meta = skills[skill_name]
        skill_md_path = os.path.join(meta.skill_dir, "SKILL.md")

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return None

        front_matter, body = self._split_front_matter(raw)

        return SkillContent(
            name=meta.name,
            description=meta.description,
            raw=raw,
            front_matter=front_matter,
            body=body,
            skill_dir=meta.skill_dir,
        )

    # ── 阶段 3：获取附件资源 ─────────────────────────────

    def get_skill_resources(self, skill_name: str) -> List[Dict[str, str]]:
        """返回技能的 scripts/ 和 references/ 附件路径列表.

        扫描技能目录下的 ``scripts/`` 和 ``references/`` 子目录，
        返回所有文件的相对路径和类型.

        Args:
            skill_name: 技能名称.

        Returns:
            附件信息列表，每项包含：
            - ``path``：相对于技能目录的文件路径.
            - ``type``：``'scripts'`` 或 ``'references'``.
            技能不存在时返回空列表.
        """
        skills = self.discover()
        if skill_name not in skills:
            return []

        skill_dir = skills[skill_name].skill_dir
        attachments: List[Dict[str, str]] = []

        for subdir in ("scripts", "references"):
            subdir_path = os.path.join(skill_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue

            for root, _dirs, files in os.walk(subdir_path):
                for filename in sorted(files):
                    abs_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(abs_path, skill_dir)
                    attachments.append({
                        "path": rel_path,
                        "type": subdir,
                        "abs_path": abs_path,
                    })

        return attachments

    # ── 内部解析方法 ─────────────────────────────────────

    @staticmethod
    def _split_front_matter(raw: str) -> Tuple[Dict[str, str], str]:
        """将 SKILL.md 原文拆分为 front matter 字典和 Markdown 正文.

        Args:
            raw: SKILL.md 文件原始内容.

        Returns:
            (front_matter_dict, body_str) 元组.
            如果没有 front matter，返回 ``({}, raw)``.
        """
        match = _FRONT_MATTER_RE.match(raw)
        if not match:
            return {}, raw

        yaml_block = match.group(1)
        body = match.group(2)

        # 解析 YAML 键值对
        front_matter: Dict[str, str] = {}
        for kv_match in _YAML_KV_RE.finditer(yaml_block):
            key = kv_match.group(1)
            value = kv_match.group(2).strip()
            # 去除可能的首尾引号
            if value and value[0] in ("'", '"') and value[-1] == value[0]:
                value = value[1:-1]
            front_matter[key] = value

        return front_matter, body

    @classmethod
    def _parse_front_matter(
        cls, skill_md_path: str, skill_dir: str
    ) -> Optional[SkillMeta]:
        """解析 SKILL.md 的 front matter，返回 SkillMeta.

        Args:
            skill_md_path: SKILL.md 文件路径.
            skill_dir: 技能目录路径.

        Returns:
            SkillMeta 实例；解析失败时返回 ``None``.
        """
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return None

        front_matter, _body = cls._split_front_matter(raw)

        name = front_matter.get("name", "")
        description = front_matter.get("description", "")

        # 如果 front matter 中没有 name，用目录名兜底
        if not name:
            name = os.path.basename(skill_dir)

        if not description:
            description = "(无描述)"

        return SkillMeta(
            name=name,
            description=description,
            skill_dir=skill_dir,
        )

    # ── 工具方法 ─────────────────────────────────────────

    def list_skill_names(self) -> List[str]:
        """返回所有已发现技能的名称列表.

        Returns:
            技能名称列表，按字母排序.
        """
        return sorted(self.discover().keys())

    def has_skill(self, skill_name: str) -> bool:
        """检查是否存在指定名称的技能.

        Args:
            skill_name: 技能名称.

        Returns:
            是否存在.
        """
        return skill_name in self.discover()
