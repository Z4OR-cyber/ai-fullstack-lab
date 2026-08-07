"""技能自动生成器 — 从重复工具序列中生成可复用技能.

设计原则：
- **模式识别**：通过 n-gram 频率分析识别重复执行的工具序列，
  不依赖外部 LLM，保持纯标准库依赖.
- **SKILL.md 兼容**：生成的 SKILL.md 格式完全兼容 Phase 2 的
  SkillLoader，包含 YAML front matter + Markdown 正文.
- **安全验证**：生成后通过 SkillScanner 安全扫描，
  通过 SkillLoader 加载验证，两步验证后激活.
- **渐进式注册**：新技能先注册为 pending 状态，
  验证通过后标记为 active.

核心流程::

    重复工具序列 ──▶ 生成 SKILL.md ──▶ 安全扫描 ──▶ 加载验证 ──▶ 激活
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from .learner import InteractionRecord, Pattern


@dataclass
class ToolSequence:
    """一个可复用的工具序列模式.

    Attributes:
        tools: 工具名称列表（按执行顺序）.
        frequency: 出现频率.
        success_rate: 成功率.
        avg_duration: 平均耗时.
        example_arguments: 示例参数列表（每次调用的参数摘要）.
        context_tags: 上下文标签.
        source_interactions: 来源交互记录 ID 列表.
    """

    tools: List[str] = field(default_factory=list)
    frequency: int = 0
    success_rate: float = 0.0
    avg_duration: float = 0.0
    example_arguments: List[List[Dict[str, Any]]] = field(default_factory=list)
    context_tags: List[str] = field(default_factory=list)
    source_interactions: List[str] = field(default_factory=list)

    @property
    def is_reusable(self) -> bool:
        """是否可复用（频率 >= 3 且成功率 >= 0.6）."""
        return self.frequency >= 3 and self.success_rate >= 0.6

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)


@dataclass
class GeneratedSkill:
    """生成的技能信息.

    Attributes:
        name: 技能名称.
        description: 技能描述.
        content: SKILL.md 文件内容.
        skill_dir: 技能目录路径.
        status: 技能状态 — ``'pending'`` / ``'active'`` / ``'rejected'``.
        source_pattern: 来源 Pattern ID.
        validation_result: 验证结果.
        created_at: 创建时间戳.
    """

    name: str = ""
    description: str = ""
    content: str = ""
    skill_dir: str = ""
    status: str = "pending"
    source_pattern: str = ""
    validation_result: Optional[Dict[str, Any]] = None
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GeneratedSkill":
        """从字典创建实例."""
        return cls(**d)


class SkillGenerator:
    """技能自动生成器.

    从交互记录中识别重复的工具序列模式，
    自动生成 SKILL.md 格式文件，
    注册到技能目录并经过验证后激活.

    Usage::

        generator = SkillGenerator(
            skills_dir="skills/",
            storage_dir="data/evolution",
        )

        # 从模式生成技能
        skills = generator.generate_from_patterns(patterns)

        # 验证并激活
        for skill in skills:
            if generator.validate_skill(skill):
                generator.activate_skill(skill.name)
    """

    # 最小频率阈值
    MIN_FREQUENCY: int = 3

    # 最小成功率阈值
    MIN_SUCCESS_RATE: float = 0.6

    # 最小序列长度
    MIN_SEQUENCE_LENGTH: int = 2

    def __init__(
        self,
        skills_dir: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ):
        """
        Args:
            skills_dir: 技能库根目录（生成的技能存放位置）.
            storage_dir: 数据持久化目录.
        """
        if skills_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(pkg_root, "skills", "generated")

        if storage_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "evolution")

        self.skills_dir = skills_dir
        self.storage_dir = storage_dir
        os.makedirs(skills_dir, exist_ok=True)
        os.makedirs(storage_dir, exist_ok=True)

        self._generated: List[GeneratedSkill] = []
        self._load_registry()

    # ── 模式识别 ──────────────────────────────────────────

    def find_reusable_sequences(
        self,
        interactions: List[InteractionRecord],
        min_frequency: Optional[int] = None,
        min_success_rate: Optional[float] = None,
        min_length: Optional[int] = None,
    ) -> List[ToolSequence]:
        """从交互记录中识别可复用的工具序列.

        使用 n-gram 频率分析：
        1. 对每个交互的工具序列提取 n-gram（n=2,3,...）
        2. 统计每个 n-gram 的频率和成功率
        3. 筛选满足阈值的序列

        Args:
            interactions: 交互记录列表.
            min_frequency: 最小频率阈值.
            min_success_rate: 最小成功率阈值.
            min_length: 最小序列长度.

        Returns:
            ToolSequence 列表，按频率降序排列.
        """
        min_freq = min_frequency or self.MIN_FREQUENCY
        min_sr = min_success_rate or self.MIN_SUCCESS_RATE
        min_len = min_length or self.MIN_SEQUENCE_LENGTH

        # 收集所有 n-gram
        # key: tuple of tool names → list of interaction metadata
        ngram_data: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}

        for record in interactions:
            seq = record.tool_sequence
            # 提取不同长度的 n-gram
            for n in range(min_len, min(len(seq), 5) + 1):
                for i in range(len(seq) - n + 1):
                    ngram = tuple(seq[i:i + n])
                    if ngram not in ngram_data:
                        ngram_data[ngram] = []
                    # 收集参数
                    args = [
                        tc.get("arguments", {})
                        for tc in record.tool_calls[i:i + n]
                    ]
                    ngram_data[ngram].append({
                        "interaction_id": record.id,
                        "success": record.success,
                        "duration": record.duration,
                        "arguments": args,
                        "tags": record.tags,
                    })

        # 筛选可复用序列
        sequences: List[ToolSequence] = []
        for ngram, entries in ngram_data.items():
            freq = len(entries)
            if freq < min_freq:
                continue

            successes = sum(1 for e in entries if e["success"])
            sr = successes / freq
            if sr < min_sr:
                continue

            durations = [e["duration"] for e in entries]
            all_tags: List[str] = []
            for e in entries:
                all_tags.extend(e["tags"])

            # 收集示例参数（最多 3 组）
            example_args = [e["arguments"] for e in entries[:3]]
            source_ids = [e["interaction_id"] for e in entries]

            # 去重 tags
            from collections import Counter
            tag_counts = Counter(all_tags)
            top_tags = [t for t, _ in tag_counts.most_common(5)]

            sequences.append(ToolSequence(
                tools=list(ngram),
                frequency=freq,
                success_rate=round(sr, 4),
                avg_duration=round(sum(durations) / len(durations), 2),
                example_arguments=example_args,
                context_tags=top_tags,
                source_interactions=source_ids,
            ))

        # 按频率降序
        sequences.sort(key=lambda s: s.frequency, reverse=True)
        return sequences

    # ── SKILL.md 生成 ────────────────────────────────────

    def generate_skill_md(
        self,
        sequence: ToolSequence,
        skill_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """生成 SKILL.md 格式内容.

        生成的 SKILL.md 包含：
        - YAML front matter（name, description, generated, version）
        - 使用步骤（基于工具序列）
        - 工具参数示例
        - 注意事项

        Args:
            sequence: 工具序列模式.
            skill_name: 自定义技能名称. 默认从工具序列自动生成.

        Returns:
            (skill_name, skill_md_content) 元组.
        """
        if skill_name is None:
            skill_name = self._auto_name(sequence)

        description = self._generate_description(sequence)

        # 构建 YAML front matter
        front_matter = (
            "---\n"
            f"name: {skill_name}\n"
            f"description: {description}\n"
            f"generated: true\n"
            f"version: 1.0.0\n"
            f"success_rate: {sequence.success_rate}\n"
            f"frequency: {sequence.frequency}\n"
            "---\n\n"
        )

        # 构建正文
        body_lines: List[str] = []
        body_lines.append(f"# {self._title_case(skill_name)}\n")
        body_lines.append(
            f"> 自动生成技能 — 从 {sequence.frequency} 次成功交互中提取"
            f"（成功率: {sequence.success_rate:.0%}）.\n"
        )

        # 使用步骤
        body_lines.append("## 使用步骤\n")
        for i, tool in enumerate(sequence.tools, 1):
            body_lines.append(f"{i}. 使用 `{tool}` 工具")
            # 添加参数示例
            if sequence.example_arguments and i <= len(sequence.example_arguments[0]):
                example_arg = sequence.example_arguments[0][i - 1]
                if example_arg:
                    arg_str = ", ".join(
                        f"{k}={v!r}" for k, v in list(example_arg.items())[:3]
                    )
                    body_lines.append(f"   - 示例参数: `{arg_str}`")
            body_lines.append("")

        # 上下文标签
        if sequence.context_tags:
            body_lines.append("## 适用场景\n")
            body_lines.append(
                "此技能适用于以下场景：\n"
                + "\n".join(f"- {tag}" for tag in sequence.context_tags)
                + "\n"
            )

        # 注意事项
        body_lines.append("## 注意事项\n")
        body_lines.append(
            "- 此技能由自进化引擎自动生成，建议人工审查后使用.\n"
            f"- 统计基于 {sequence.frequency} 次交互，平均耗时 {sequence.avg_duration:.1f}s.\n"
            "- 如遇异常情况，请回退到手动操作.\n"
        )

        content = front_matter + "\n".join(body_lines)
        return skill_name, content

    # ── 技能注册与验证 ────────────────────────────────────

    def generate_from_patterns(
        self,
        patterns: List[Pattern],
        skills_dir: Optional[str] = None,
    ) -> List[GeneratedSkill]:
        """从 Pattern 列表批量生成技能.

        筛选高价值模式（高频 + 高成功率），
        为每个模式生成 SKILL.md 并注册到技能目录.

        Args:
            patterns: Pattern 列表.
            skills_dir: 技能目录（覆盖默认）.

        Returns:
            GeneratedSkill 列表.
        """
        target_dir = skills_dir or self.skills_dir
        os.makedirs(target_dir, exist_ok=True)

        results: List[GeneratedSkill] = []

        for pattern in patterns:
            if not pattern.is_high_value:
                continue

            # 构建 ToolSequence
            sequence = ToolSequence(
                tools=pattern.tool_sequence,
                frequency=pattern.frequency,
                success_rate=pattern.success_rate,
                avg_duration=pattern.avg_duration,
                context_tags=pattern.context_tags,
            )

            skill_name, content = self.generate_skill_md(sequence)
            skill_dir = os.path.join(target_dir, skill_name)

            # 创建目录并写入 SKILL.md
            os.makedirs(skill_dir, exist_ok=True)
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(content)

            generated = GeneratedSkill(
                name=skill_name,
                description=self._generate_description(sequence),
                content=content,
                skill_dir=skill_dir,
                status="pending",
                source_pattern=pattern.id,
            )
            results.append(generated)
            self._generated.append(generated)

        self._save_registry()
        return results

    def generate_from_sequences(
        self,
        sequences: List[ToolSequence],
        skills_dir: Optional[str] = None,
    ) -> List[GeneratedSkill]:
        """从 ToolSequence 列表批量生成技能.

        Args:
            sequences: ToolSequence 列表.
            skills_dir: 技能目录（覆盖默认）.

        Returns:
            GeneratedSkill 列表.
        """
        target_dir = skills_dir or self.skills_dir
        os.makedirs(target_dir, exist_ok=True)

        results: List[GeneratedSkill] = []

        for seq in sequences:
            if not seq.is_reusable:
                continue

            skill_name, content = self.generate_skill_md(seq)
            skill_dir = os.path.join(target_dir, skill_name)

            os.makedirs(skill_dir, exist_ok=True)
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(content)

            generated = GeneratedSkill(
                name=skill_name,
                description=self._generate_description(seq),
                content=content,
                skill_dir=skill_dir,
                status="pending",
            )
            results.append(generated)
            self._generated.append(generated)

        self._save_registry()
        return results

    def validate_skill(self, skill: GeneratedSkill) -> bool:
        """验证生成的技能是否可用.

        执行两步验证：
        1. **安全扫描**：使用 SkillScanner 检测安全风险.
        2. **加载验证**：使用 SkillLoader 尝试加载 SKILL.md.

        Args:
            skill: 待验证的 GeneratedSkill.

        Returns:
            验证是否通过.
        """
        validation: Dict[str, Any] = {
            "safe": True,
            "loadable": False,
            "findings": [],
            "errors": [],
        }

        # Step 1: 安全扫描
        try:
            from ..skills.scanner import SkillScanner
            scanner = SkillScanner()
            risk_level = scanner.scan(skill.content)
            validation["safe"] = risk_level != "dangerous"
            validation["risk_level"] = risk_level
            if scanner.get_findings():
                validation["findings"] = [
                    f.to_dict() for f in scanner.get_findings()
                ]
        except Exception as e:
            validation["errors"].append(f"Scanner error: {e}")
            validation["safe"] = False

        # Step 2: 加载验证
        try:
            from ..skills.loader import SkillLoader
            # 用技能目录的父目录作为 skills_dir
            parent_dir = os.path.dirname(skill.skill_dir)
            loader = SkillLoader(parent_dir)
            content = loader.load_skill(skill.name)
            if content is not None:
                validation["loadable"] = True
                validation["parsed_name"] = content.name
                validation["parsed_description"] = content.description
            else:
                validation["errors"].append("SkillLoader returned None")
        except Exception as e:
            validation["errors"].append(f"Loader error: {e}")

        skill.validation_result = validation

        passed = validation["safe"] and validation["loadable"]
        if passed:
            skill.status = "validated"
        else:
            skill.status = "rejected"

        self._save_registry()
        return passed

    def activate_skill(self, skill_name: str) -> bool:
        """将已验证的技能标记为活跃状态.

        Args:
            skill_name: 技能名称.

        Returns:
            是否成功激活.
        """
        for skill in self._generated:
            if skill.name == skill_name:
                if skill.status == "validated":
                    skill.status = "active"
                    self._save_registry()
                    return True
                return False
        return False

    def get_generated_skills(self) -> List[GeneratedSkill]:
        """返回所有已生成的技能."""
        return list(self._generated)

    def get_active_skills(self) -> List[GeneratedSkill]:
        """返回所有活跃状态的技能."""
        return [s for s in self._generated if s.status == "active"]

    # ── 持久化 ────────────────────────────────────────────

    def _save_registry(self) -> None:
        """保存技能注册表."""
        registry_path = os.path.join(self.storage_dir, "skill_registry.json")
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(
                [s.to_dict() for s in self._generated],
                f, ensure_ascii=False, indent=2,
            )

    def _load_registry(self) -> None:
        """加载技能注册表."""
        registry_path = os.path.join(self.storage_dir, "skill_registry.json")
        if os.path.isfile(registry_path):
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._generated = [GeneratedSkill.from_dict(d) for d in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    # ── 内部工具方法 ──────────────────────────────────────

    @staticmethod
    def _auto_name(sequence: ToolSequence) -> str:
        """从工具序列自动生成技能名称.

        规则：取工具名的前缀 + 序号，确保唯一性.

        Examples:
            ["search", "read_file"] → "search-read-file"
            ["bash", "write_file", "bash"] → "bash-write-bash"
        """
        parts = []
        for tool in sequence.tools:
            # 取工具名的最后一段（去掉模块前缀）
            name = tool.replace("_", "-").lower()
            parts.append(name)
        base = "-".join(parts)
        # 限制长度
        if len(base) > 50:
            base = base[:50]
        return f"auto-{base}"

    @staticmethod
    def _generate_description(sequence: ToolSequence) -> str:
        """生成技能描述."""
        tools_str = " → ".join(sequence.tools)
        return (
            f"自动生成：依次使用 {tools_str} 完成任务"
            f"（成功率 {sequence.success_rate:.0%}，{sequence.frequency} 次验证）"
        )

    @staticmethod
    def _title_case(name: str) -> str:
        """将技能名转为标题格式."""
        return " ".join(
            word.capitalize() for word in name.replace("-", " ").split()
        )
