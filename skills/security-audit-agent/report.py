"""
审计报告生成器
支持终端彩色输出、Markdown报告、JSON格式
"""

import json
import os
from datetime import datetime
from scanner import Vulnerability
from rules import SEVERITY_COLOR, SEVERITY_WEIGHT


class ReportGenerator:
    """安全审计报告生成器"""

    def __init__(self, findings, stats):
        self.findings = findings
        self.stats = stats
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def terminal_output(self):
        """终端彩色输出"""
        lines = []
        lines.append("=" * 70)
        lines.append("  🔒 安全审计报告")
        lines.append(f"  扫描时间: {self.timestamp}")
        lines.append("=" * 70)
        lines.append("")

        # 统计摘要
        lines.append("📊 扫描统计:")
        lines.append(f"  扫描文件: {self.stats['files_scanned']}")
        lines.append(f"  扫描行数: {self.stats['lines_scanned']:,}")
        lines.append(f"  发现问题: {self.stats['total_findings']}")
        lines.append(f"  风险评分: {self.stats['risk_score']}")
        lines.append("")

        # 风险分布
        lines.append("⚠️  风险分布:")
        for level, label in [("CRITICAL", "严重"), ("HIGH", "高危"),
                              ("MEDIUM", "中危"), ("LOW", "低危")]:
            count = self.stats[level.lower()]
            color = SEVERITY_COLOR.get(level, "")
            reset = "\033[0m" if color else ""
            bar = "█" * min(count, 30)
            lines.append(f"  {color}{label:4s} [{count:3d}] {bar}{reset}")
        lines.append("")

        if not self.findings:
            lines.append("✅ 未发现安全问题。代码看起来很健康！")
            lines.append("")
            lines.append("=" * 70)
            return "\n".join(lines)

        # 按严重程度排序
        sorted_findings = sorted(
            self.findings,
            key=lambda f: SEVERITY_WEIGHT.get(f.severity, 0),
            reverse=True
        )

        # 详细发现
        lines.append("🔍 详细发现:")
        lines.append("-" * 70)

        current_severity = None
        for i, vuln in enumerate(sorted_findings, 1):
            if vuln.severity != current_severity:
                current_severity = vuln.severity
                color = SEVERITY_COLOR.get(vuln.severity, "")
                reset = "\033[0m" if color else ""
                lines.append(f"\n{color}{'─' * 35} {vuln.severity} {'─' * 35}{reset}")

            color = SEVERITY_COLOR.get(vuln.severity, "")
            reset = "\033[0m" if color else ""

            lines.append(f"\n{color}[{i:03d}] {vuln.name} ({vuln.rule_id}){reset}")
            lines.append(f"     文件: {vuln.file_path}:{vuln.line_num}")
            lines.append(f"     类别: {vuln.category}")
            lines.append(f"     攻击: {vuln.attack_type}")
            lines.append(f"     描述: {vuln.description}")
            if vuln.code_snippet:
                lines.append(f"     代码: {vuln.code_snippet.strip()}")
            lines.append(f"     {color}修复: {vuln.defense}{reset}")

        lines.append("")
        lines.append("=" * 70)

        # 防御建议总览
        lines.append("\n🛡️  防御建议总览:")
        categories = {}
        for vuln in self.findings:
            if vuln.category not in categories:
                categories[vuln.category] = []
            if vuln.defense not in categories[vuln.category]:
                categories[vuln.category].append(vuln.defense)

        for cat, defenses in categories.items():
            lines.append(f"\n  [{cat}]")
            for d in defenses:
                lines.append(f"  • {d}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def markdown_report(self):
        """Markdown格式报告"""
        lines = []
        lines.append("# 🔒 安全审计报告")
        lines.append(f"\n> 生成时间: {self.timestamp}")
        lines.append("")

        # 统计摘要
        lines.append("## 📊 扫描统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 扫描文件数 | {self.stats['files_scanned']} |")
        lines.append(f"| 扫描代码行数 | {self.stats['lines_scanned']:,} |")
        lines.append(f"| 发现问题总数 | {self.stats['total_findings']} |")
        lines.append(f"| 严重(CRITICAL) | {self.stats['critical']} |")
        lines.append(f"| 高危(HIGH) | {self.stats['high']} |")
        lines.append(f"| 中危(MEDIUM) | {self.stats['medium']} |")
        lines.append(f"| 低危(LOW) | {self.stats['low']} |")
        lines.append(f"| 风险评分 | {self.stats['risk_score']} |")
        lines.append("")

        # 风险等级说明
        lines.append("### 风险等级说明")
        lines.append("")
        lines.append("| 等级 | 说明 |")
        lines.append("|------|------|")
        lines.append("| 🔴 CRITICAL | 可直接导致远程代码执行、数据泄露等严重后果 |")
        lines.append("| 🟡 HIGH | 可导致权限提升、信息泄露等 |")
        lines.append("| 🔵 MEDIUM | 可能被利用，需结合其他条件 |")
        lines.append("| ⚪ LOW | 最佳实践违反，风险较低 |")
        lines.append("")

        if not self.findings:
            lines.append("## ✅ 审计结果")
            lines.append("")
            lines.append("未发现安全问题。代码安全状况良好。")
            lines.append("")
            lines.append("---")
            lines.append("*本报告由安全审计Agent自动生成*")
            return "\n".join(lines)

        # 详细发现
        sorted_findings = sorted(
            self.findings,
            key=lambda f: SEVERITY_WEIGHT.get(f.severity, 0),
            reverse=True
        )

        lines.append("## 🔍 详细发现")
        lines.append("")

        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟡",
            "MEDIUM": "🔵",
            "LOW": "⚪",
        }

        current_severity = None
        for i, vuln in enumerate(sorted_findings, 1):
            if vuln.severity != current_severity:
                current_severity = vuln.severity
                lines.append(f"\n### {severity_emoji.get(vuln.severity, '')} {vuln.severity}\n")

            lines.append(f"#### [{i}] {vuln.name} `{vuln.rule_id}`")
            lines.append("")
            lines.append(f"| 属性 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 文件 | `{vuln.file_path}:{vuln.line_num}` |")
            lines.append(f"| 类别 | {vuln.category} |")
            lines.append(f"| 攻击类型 | {vuln.attack_type} |")
            lines.append(f"| 风险等级 | {vuln.severity} |")
            lines.append("")
            lines.append(f"**描述:** {vuln.description}")
            lines.append("")
            if vuln.code_snippet:
                lines.append(f"```")
                lines.append(vuln.code_snippet.strip())
                lines.append(f"```")
                lines.append("")
            lines.append(f"**🔧 修复建议:** {vuln.defense}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # 防御体系建议
        lines.append("\n## 🛡️ 防御体系建议")
        lines.append("")
        lines.append("基于本次审计发现，建议从以下维度构建纵深防御体系：")
        lines.append("")

        categories = {}
        for vuln in self.findings:
            if vuln.category not in categories:
                categories[vuln.category] = []
            if vuln.defense not in categories[vuln.category]:
                categories[vuln.category].append(vuln.defense)

        for cat, defenses in categories.items():
            lines.append(f"### {cat}")
            lines.append("")
            for d in defenses:
                lines.append(f"- {d}")
            lines.append("")

        lines.append("---")
        lines.append("*本报告由安全审计Agent自动生成 · 基于15类攻击共性检测 + 10层防御联动体系*")

        return "\n".join(lines)

    def json_report(self):
        """JSON格式报告"""
        return json.dumps({
            "timestamp": self.timestamp,
            "stats": self.stats,
            "findings": [f.to_dict() for f in self.findings],
        }, ensure_ascii=False, indent=2)

    def save_report(self, output_dir, fmt="markdown"):
        """保存报告到文件"""
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if fmt == "markdown":
            path = os.path.join(output_dir, f"security_audit_{ts}.md")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.markdown_report())
        elif fmt == "json":
            path = os.path.join(output_dir, f"security_audit_{ts}.json")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.json_report())
        else:
            return None

        return path
