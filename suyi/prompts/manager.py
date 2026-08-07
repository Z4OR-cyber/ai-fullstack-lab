"""Prompt 管理器 — 模板注册、版本管理、热重载.

核心功能::

    ┌──────────────────────────────────────────────────────┐
    │  注册/获取模板    — register() / get()                 │
    │  版本管理         — 版本号 + 回滚                       │
    │  文件/目录加载    — load_from_file() / load_from_dir() │
    │  变量验证         — validate_template()                 │
    │  热重载           — reload() / watch()                  │
    │  导出/导入        — export() / import()                 │
    └──────────────────────────────────────────────────────┘

设计原则：
- **版本控制**：每次修改自动创建新版本，支持回滚到任意版本.
- **文件加载**：从 ``.txt`` / ``.md`` 文件加载模板内容.
- **热重载**：检测文件变更并自动重新加载（基于 mtime）.
- **JSON 持久化**：模板库可导出为 JSON 文件.

Usage::

    mgr = PromptManager()

    # 注册模板
    tpl = PromptTemplate("Hello, {name}!", name="greeting")
    mgr.register(tpl)

    # 获取并渲染
    rendered = mgr.render("greeting", name="World")

    # 版本管理
    mgr.update("greeting", PromptTemplate("Hi, {name}!", name="greeting"))
    mgr.rollback("greeting")  # 回滚到上一版本

    # 从文件加载
    mgr.load_from_dir("./prompts/")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .templates import PromptTemplate


# ═══════════════════════════════════════════════════════════════
#  Versioned Template
# ═══════════════════════════════════════════════════════════════


@dataclass
class TemplateVersion:
    """模板的版本记录.

    Attributes:
        version:     版本号（从 1 开始递增）.
        template:    该版本的模板实例.
        timestamp:   创建时间戳.
        description: 版本描述.
    """

    version: int
    template: PromptTemplate
    timestamp: float = 0.0
    description: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "template_str": self.template.template,
            "template_name": self.template.name,
            "description": self.template.description,
            "timestamp": self.timestamp,
            "version_description": self.description,
        }


# ═══════════════════════════════════════════════════════════════
#  Prompt Manager
# ═══════════════════════════════════════════════════════════════


class PromptManager:
    """Prompt 模板管理器.

    提供模板的注册、版本管理、文件加载和热重载功能.

    Args:
        storage_dir: 持久化存储目录（可选）.

    Usage::

        mgr = PromptManager(storage_dir="./prompt_data")

        # 注册
        mgr.register(PromptTemplate("Hello {name}!", name="greeting"))

        # 获取
        tpl = mgr.get("greeting")

        # 渲染
        text = mgr.render("greeting", name="World")

        # 更新（自动版本管理）
        mgr.update("greeting", PromptTemplate("Hi {name}!", name="greeting"))

        # 回滚
        mgr.rollback("greeting")

        # 从目录加载
        mgr.load_from_dir("./prompts/")
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir
        if storage_dir:
            os.makedirs(storage_dir, exist_ok=True)

        # name → List[TemplateVersion]
        self._templates: Dict[str, List[TemplateVersion]] = {}

        # 文件路径追踪（用于热重载）
        self._file_map: Dict[str, str] = {}  # template_name → file_path
        self._file_mtimes: Dict[str, float] = {}  # file_path → last mtime

    # ── 注册与获取 ────────────────────────────────────────

    def register(
        self,
        template: PromptTemplate,
        description: str = "",
    ) -> "PromptManager":
        """注册一个新模板.

        如果模板名已存在，将创建一个新版本.

        Args:
            template: 要注册的模板实例.
            description: 版本描述.

        Returns:
            self（支持链式调用）.
        """
        name = template.name

        if name in self._templates:
            # 已存在，创建新版本
            versions = self._templates[name]
            next_version = versions[-1].version + 1
            versions.append(TemplateVersion(
                version=next_version,
                template=template,
                description=description,
            ))
        else:
            # 新模板
            self._templates[name] = [
                TemplateVersion(
                    version=1,
                    template=template,
                    description=description,
                )
            ]

        return self

    def get(self, name: str, version: Optional[int] = None) -> PromptTemplate:
        """获取模板.

        Args:
            name: 模板名称.
            version: 版本号（None 表示最新版本）.

        Returns:
            模板实例.

        Raises:
            KeyError: 模板不存在.
            ValueError: 版本号不存在.
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found.")

        versions = self._templates[name]

        if version is None:
            return versions[-1].template

        for v in versions:
            if v.version == version:
                return v.template

        raise ValueError(
            f"Version {version} not found for template '{name}'. "
            f"Available versions: {[v.version for v in versions]}"
        )

    def render(self, template_name: str, version: Optional[int] = None, **kwargs: Any) -> str:
        """获取并渲染模板.

        Args:
            template_name: 模板名称.
            version: 版本号（可选）.
            **kwargs: 渲染变量.

        Returns:
            渲染后的字符串.
        """
        tpl = self.get(template_name, version=version)
        return tpl.render(**kwargs)

    def render_safe(self, template_name: str, version: Optional[int] = None, **kwargs: Any) -> str:
        """安全渲染（缺失变量用空字符串替代）."""
        tpl = self.get(template_name, version=version)
        return tpl.render_safe(**kwargs)

    # ── 更新与版本管理 ────────────────────────────────────

    def update(
        self,
        name: str,
        template: PromptTemplate,
        description: str = "",
    ) -> int:
        """更新模板（创建新版本）.

        Args:
            name: 要更新的模板名称.
            template: 新的模板实例.
            description: 版本描述.

        Returns:
            新版本号.

        Raises:
            KeyError: 模板不存在.
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found. Use register() first.")

        # 确保模板名称一致
        if template.name != name:
            template.name = name

        versions = self._templates[name]
        next_version = versions[-1].version + 1
        versions.append(TemplateVersion(
            version=next_version,
            template=template,
            description=description,
        ))
        return next_version

    def rollback(self, name: str, steps: int = 1) -> PromptTemplate:
        """回滚模板到之前的版本.

        Args:
            name: 模板名称.
            steps: 回滚步数（1 = 上一版本）.

        Returns:
            回滚后的模板实例.

        Raises:
            KeyError: 模板不存在.
            ValueError: 没有足够的版本可以回滚.
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found.")

        versions = self._templates[name]
        if len(versions) <= steps:
            raise ValueError(
                f"Cannot rollback {steps} steps for template '{name}'. "
                f"Only {len(versions)} version(s) exist."
            )

        # 移除最近的 steps 个版本
        for _ in range(steps):
            versions.pop()

        return versions[-1].template

    def get_versions(self, name: str) -> List[TemplateVersion]:
        """获取模板的所有版本记录."""
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found.")
        return list(self._templates[name])

    def get_version_count(self, name: str) -> int:
        """获取模板的版本数量."""
        if name not in self._templates:
            return 0
        return len(self._templates[name])

    # ── 列表与搜索 ────────────────────────────────────────

    def list_templates(self) -> List[str]:
        """列出所有已注册的模板名称."""
        return list(self._templates.keys())

    def has(self, name: str) -> bool:
        """检查模板是否存在."""
        return name in self._templates

    def remove(self, name: str) -> "PromptManager":
        """移除模板（包括所有版本）."""
        self._templates.pop(name, None)
        self._file_map.pop(name, None)
        return self

    # ── 变量验证 ──────────────────────────────────────────

    def validate_template(self, name: str, **kwargs: Any) -> List[str]:
        """验证模板的变量是否完整.

        Args:
            name: 模板名称.
            **kwargs: 提供的变量.

        Returns:
            缺失变量名列表（空列表表示验证通过）.
        """
        tpl = self.get(name)
        return tpl.validate(**kwargs)

    # ── 文件加载 ──────────────────────────────────────────

    def load_from_file(
        self,
        filepath: str,
        name: Optional[str] = None,
        description: str = "",
    ) -> PromptTemplate:
        """从文件加载模板.

        支持的文件格式：``.txt``, ``.md``, ``.prompt``.

        Args:
            filepath: 文件路径.
            name: 模板名称（默认使用文件名，不含扩展名）.
            description: 版本描述.

        Returns:
            加载的模板实例.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Template file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if name is None:
            name = os.path.splitext(os.path.basename(filepath))[0]

        tpl = PromptTemplate(
            template=content,
            name=name,
            description=description,
        )

        self.register(tpl, description=f"Loaded from {filepath}")
        self._file_map[name] = filepath
        self._file_mtimes[filepath] = os.path.getmtime(filepath)

        return tpl

    def load_from_dir(
        self,
        dirpath: str,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """从目录批量加载模板.

        扫描目录下所有指定扩展名的文件，注册为模板.

        Args:
            dirpath: 目录路径.
            extensions: 文件扩展名列表（默认 ['.txt', '.md', '.prompt']）.

        Returns:
            成功加载的模板名称列表.
        """
        if extensions is None:
            extensions = [".txt", ".md", ".prompt"]

        if not os.path.isdir(dirpath):
            raise FileNotFoundError(f"Directory not found: {dirpath}")

        loaded: List[str] = []

        for filename in sorted(os.listdir(dirpath)):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in extensions:
                continue

            filepath = os.path.join(dirpath, filename)
            if not os.path.isfile(filepath):
                continue

            try:
                tpl = self.load_from_file(filepath)
                loaded.append(tpl.name)
            except Exception:
                continue

        return loaded

    # ── 热重载 ────────────────────────────────────────────

    def reload(self, name: Optional[str] = None) -> List[str]:
        """重新加载模板（从文件）.

        检测文件是否被修改，如果修改则重新加载.

        Args:
            name: 指定模板名称（None 表示重载所有文件加载的模板）.

        Returns:
            被重新加载的模板名称列表.
        """
        reloaded: List[str] = []

        targets = [name] if name else list(self._file_map.keys())

        for tpl_name in targets:
            filepath = self._file_map.get(tpl_name)
            if not filepath or not os.path.exists(filepath):
                continue

            current_mtime = os.path.getmtime(filepath)
            last_mtime = self._file_mtimes.get(filepath, 0)

            if current_mtime > last_mtime:
                # 文件被修改，重新加载
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                tpl = PromptTemplate(
                    template=content,
                    name=tpl_name,
                )

                # 更新为新版本
                self.update(tpl_name, tpl, description=f"Hot-reloaded from {filepath}")
                self._file_mtimes[filepath] = current_mtime
                reloaded.append(tpl_name)

        return reloaded

    def check_changed(self) -> List[str]:
        """检查哪些模板文件被修改（不重新加载）.

        Returns:
            被修改的模板名称列表.
        """
        changed: List[str] = []

        for tpl_name, filepath in self._file_map.items():
            if not os.path.exists(filepath):
                continue

            current_mtime = os.path.getmtime(filepath)
            last_mtime = self._file_mtimes.get(filepath, 0)

            if current_mtime > last_mtime:
                changed.append(tpl_name)

        return changed

    # ── 导出与导入 ────────────────────────────────────────

    def export(self, filepath: Optional[str] = None) -> str:
        """导出模板库为 JSON.

        Args:
            filepath: 保存路径（可选，不提供则返回 JSON 字符串）.

        Returns:
            JSON 字符串.
        """
        data = {
            "templates": {},
            "exported_at": time.time(),
        }

        for name, versions in self._templates.items():
            data["templates"][name] = [v.to_dict() for v in versions]

        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        if filepath:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)

        return json_str

    def import_data(self, filepath_or_json: str) -> int:
        """从 JSON 导入模板库.

        Args:
            filepath_or_json: 文件路径或 JSON 字符串.

        Returns:
            导入的模板数量.
        """
        if os.path.exists(filepath_or_json):
            with open(filepath_or_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(filepath_or_json)

        count = 0
        for name, version_dicts in data.get("templates", {}).items():
            for vd in version_dicts:
                tpl = PromptTemplate(
                    template=vd["template_str"],
                    name=vd.get("template_name", name),
                    description=vd.get("description", ""),
                )
                self.register(tpl, description=vd.get("version_description", ""))
            count += 1

        return count

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """返回管理器统计信息."""
        total_versions = sum(len(v) for v in self._templates.values())
        return {
            "template_count": len(self._templates),
            "total_versions": total_versions,
            "file_loaded": len(self._file_map),
            "storage_dir": self.storage_dir,
        }

    def __repr__(self) -> str:
        return (
            f"PromptManager(templates={len(self._templates)}, "
            f"total_versions={sum(len(v) for v in self._templates.values())})"
        )

    def __len__(self) -> int:
        return len(self._templates)

    def __contains__(self, name: str) -> bool:
        return name in self._templates
