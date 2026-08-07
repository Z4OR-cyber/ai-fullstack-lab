"""Suyi 技能系统测试.

验证三个核心组件的功能：
1. SkillLoader — 技能加载和发现
2. SkillMenu — 菜单生成和选择
3. SkillScanner — 安全扫描
"""

import os
import pytest
from pathlib import Path

# 获取测试夹具路径
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "skills"


class TestSkillLoader:
    """技能加载器测试."""

    def test_discover_skills(self):
        """测试发现技能."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        skills = loader.discover()
        assert len(skills) == 3
        assert "code-reviewer" in skills
        assert "git-helper" in skills
        assert "dangerous-skill" in skills

    def test_get_menu(self):
        """测试生成技能菜单."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = loader.get_menu()
        assert len(menu) == 3
        assert all(hasattr(m, "name") and hasattr(m, "description") for m in menu)

    def test_load_skill_content(self):
        """测试加载技能内容."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        skill = loader.load_skill("code-reviewer")
        assert skill is not None
        assert skill.name == "code-reviewer"
        assert "审查" in skill.description
        assert "使用步骤" in skill.body

    def test_match_skills(self):
        """测试技能匹配."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        matches = loader.match_skills("Python 代码审查")
        assert len(matches) > 0
        assert matches[0].name == "code-reviewer"

    def test_get_skill_resources(self):
        """测试获取技能资源."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        resources = loader.get_skill_resources("code-reviewer")
        assert len(resources) >= 2
        paths = [r["path"] for r in resources]
        assert any("scan_patterns.py" in p for p in paths)
        assert any("security_checklist.md" in p for p in paths)

    def test_list_skill_names(self):
        """测试列出技能名称."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        names = loader.list_skill_names()
        assert names == ["code-reviewer", "dangerous-skill", "git-helper"]

    def test_has_skill(self):
        """测试检查技能是否存在."""
        from suyi.skills import SkillLoader
        loader = SkillLoader(str(FIXTURES_DIR))
        assert loader.has_skill("code-reviewer") is True
        assert loader.has_skill("nonexistent-skill") is False


class TestSkillMenu:
    """技能菜单生成器测试."""

    def test_generate_menu(self):
        """测试生成菜单文本."""
        from suyi.skills import SkillLoader, SkillMenu
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = SkillMenu()
        menu_text = menu.generate(loader)
        assert "code-reviewer" in menu_text
        assert "git-helper" in menu_text
        assert "dangerous-skill" in menu_text

    def test_format_compact(self):
        """测试紧凑格式."""
        from suyi.skills import SkillLoader, SkillMenu
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = SkillMenu()
        menu.generate(loader)
        compact = menu.format_compact(menu.get_skills())
        assert "\n" in compact
        assert len(compact.split("\n")) == 3

    def test_format_detailed(self):
        """测试详细格式."""
        from suyi.skills import SkillLoader, SkillMenu
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = SkillMenu()
        menu.generate(loader)
        detailed = menu.format_detailed(menu.get_skills())
        assert "## code-reviewer" in detailed
        assert "描述:" in detailed

    def test_to_xml_tag(self):
        """测试 XML 标签包裹."""
        from suyi.skills import SkillLoader, SkillMenu
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = SkillMenu()
        menu_text = menu.generate(loader)
        xml = menu.to_xml_tag(menu_text)
        assert "<available_skills>" in xml
        assert "</available_skills>" in xml
        assert "code-reviewer" in xml

    def test_select_skill(self):
        """测试技能选择."""
        from suyi.skills import SkillLoader, SkillMenu
        loader = SkillLoader(str(FIXTURES_DIR))
        menu = SkillMenu()
        menu_text = menu.generate(loader)
        selected = menu.select(menu_text, "Python 代码")
        assert len(selected) > 0
        assert "code-reviewer" in selected


class TestSkillScanner:
    """技能安全扫描器测试."""

    def test_scan_safe_content(self):
        """测试扫描安全内容."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        safe_content = "# 安全技能\n\n## 使用步骤\n1. 读取文件\n2. 分析内容"
        risk = scanner.scan(safe_content)
        assert risk == "safe"

    def test_scan_dangerous_commands(self):
        """测试扫描危险命令."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        dangerous_content = "# 危险技能\n\n使用命令：`rm -rf /tmp/data`"
        risk = scanner.scan(dangerous_content)
        assert risk == "dangerous"
        findings = scanner.get_findings()
        assert len(findings) > 0
        assert any(f.category == "dangerous_command" for f in findings)

    def test_scan_sensitive_info(self):
        """测试扫描敏感信息."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        sensitive_content = "# 技能\n\nAPI Key: api_key=sk-1234567890abcdef1234567890abcdef"
        risk = scanner.scan(sensitive_content)
        assert risk == "dangerous"
        findings = scanner.get_findings()
        assert any(f.category == "sensitive_info" for f in findings)

    def test_scan_network_request(self):
        """测试扫描网络请求."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        network_content = "# 技能\n\n访问 https://evil.example.com/api"
        risk = scanner.scan(network_content)
        assert risk in ["warning", "dangerous"]
        findings = scanner.get_findings()
        assert any(f.category == "network_request" for f in findings)

    def test_scan_path_traversal(self):
        """测试扫描路径遍历."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        traversal_content = "# 技能\n\n读取文件 ../../etc/passwd"
        risk = scanner.scan(traversal_content)
        assert risk == "dangerous"  # ../../ 匹配多层路径遍历（dangerous）
        findings = scanner.get_findings()
        assert any(f.category == "path_traversal" for f in findings)

    def test_get_risk_level(self):
        """测试获取风险级别."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        content = "安全内容"
        risk = scanner.get_risk_level(content)
        assert risk == "safe"

    def test_is_safe_method(self):
        """测试便捷方法 is_safe."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        assert scanner.is_safe("安全内容") is True
        assert scanner.is_safe("危险命令: rm -rf /") is False

    def test_is_dangerous_method(self):
        """测试便捷方法 is_dangerous."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        assert scanner.is_dangerous("危险命令: rm -rf /") is True
        assert scanner.is_dangerous("安全内容") is False

    def test_scan_fixture_dangerous_skill(self):
        """测试扫描夹具中的危险技能."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        skill_path = FIXTURES_DIR / "dangerous-skill" / "SKILL.md"
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        risk = scanner.scan(content)
        assert risk == "dangerous"
        findings = scanner.get_findings()
        assert len(findings) >= 3  # 至少检测到危险命令、敏感信息、网络请求

    def test_scan_fixture_safe_skill(self):
        """测试扫描夹具中的安全技能."""
        from suyi.skills import SkillScanner
        scanner = SkillScanner()
        skill_path = FIXTURES_DIR / "git-helper" / "SKILL.md"
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        risk = scanner.scan(content)
        assert risk == "safe"


class TestIntegration:
    """集成测试."""

    def test_full_workflow(self):
        """测试完整工作流程."""
        from suyi.skills import SkillLoader, SkillMenu, SkillScanner

        # 1. 加载技能
        loader = SkillLoader(str(FIXTURES_DIR))
        skills = loader.discover()
        assert len(skills) == 3

        # 2. 生成菜单
        menu = SkillMenu()
        menu_text = menu.generate(loader)
        assert "code-reviewer" in menu_text

        # 3. 选择技能
        selected = menu.select(menu_text, "代码审查")
        assert len(selected) > 0

        # 4. 加载技能内容
        skill_name = selected[0]
        skill_content = loader.load_skill(skill_name)
        assert skill_content is not None

        # 5. 安全扫描
        scanner = SkillScanner()
        risk = scanner.scan(skill_content.raw)
        assert risk in ["safe", "warning", "dangerous"]

        # 6. 获取资源
        resources = loader.get_skill_resources(skill_name)
        assert isinstance(resources, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
