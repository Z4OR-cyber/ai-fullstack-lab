"""技能安全扫描器 — 检测 SKILL.md 中的安全风险.

设计原则：
- **模式匹配优先**：使用正则模式匹配已知风险模式，
  不依赖外部 LLM，保持纯标准库依赖.
- **三档风险级别**：safe / warning / dangerous.
  - safe: 无安全风险.
  - warning: 存在潜在风险，建议人工审查.
  - dangerous: 存在明确危险，应阻止执行.
- **发现列表**：get_findings() 返回所有扫描发现，
  每项包含类型、严重程度、匹配内容、行号.

检测项：
1. 危险命令模式：``rm -rf``, ``sudo``, ``curl | bash`` 等.
2. 敏感信息泄露：API key 格式、密码模式.
3. 网络请求到非白名单域名.
4. 文件系统越权访问：``../`` 路径遍历.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ── 风险级别常量 ──────────────────────────────────────────

RISK_SAFE = "safe"
RISK_WARNING = "warning"
RISK_DANGEROUS = "dangerous"

# 风险级别 → 严重程度权重
_RISK_WEIGHT = {
    RISK_SAFE: 0,
    RISK_WARNING: 1,
    RISK_DANGEROUS: 2,
}


@dataclass
class ScanFinding:
    """单个扫描发现.

    Attributes:
        category: 发现类别（如 ``'dangerous_command'``, ``'sensitive_info'``）.
        severity: 严重程度（``'warning'`` 或 ``'dangerous'``）.
        pattern: 匹配到的模式描述.
        matched: 匹配到的实际文本.
        line_number: 行号（1-based，0 表示无法确定）.
    """

    category: str
    severity: str
    pattern: str
    matched: str
    line_number: int = 0

    def to_dict(self) -> dict:
        """转换为字典表示."""
        return {
            "category": self.category,
            "severity": self.severity,
            "pattern": self.pattern,
            "matched": self.matched,
            "line_number": self.line_number,
        }

    def __repr__(self) -> str:
        return (
            f"ScanFinding(category={self.category!r}, "
            f"severity={self.severity!r}, "
            f"matched={self.matched!r})"
        )


class SkillScanner:
    """技能安全扫描器.

    扫描 SKILL.md 内容，检测四类安全风险：
    1. 危险命令模式.
    2. 敏感信息泄露.
    3. 网络请求到非白名单域名.
    4. 文件系统越权访问.

    使用方法::

        scanner = SkillScanner()
        risk = scanner.get_risk_level(skill_content)
        if risk == 'dangerous':
            print("拒绝加载此技能")
        findings = scanner.get_findings()

    Attributes:
        DOMAIN_WHITELIST: 允许的网络请求域名白名单.
        _findings: 最近一次扫描的发现列表.
    """

    # 网络请求域名白名单
    DOMAIN_WHITELIST: List[str] = [
        "github.com",
        "raw.githubusercontent.com",
        "pypi.org",
        "docs.python.org",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    ]

    # ── 危险命令模式 ──────────────────────────────────────
    # (pattern, severity, description)

    _DANGEROUS_COMMAND_PATTERNS: List[tuple] = [
        # 破坏性删除
        (r"rm\s+-rf?\s+", RISK_DANGEROUS, "递归强制删除"),
        (r"rm\s+-[a-z]*r[a-z]*\s+", RISK_DANGEROUS, "递归删除"),
        (r"rm\s+-[a-z]*f[a-z]*\s+", RISK_DANGEROUS, "强制删除"),
        # 提权
        (r"\bsudo\s+", RISK_WARNING, "提权执行"),
        (r"\bsu\s+", RISK_WARNING, "切换用户"),
        # 管道执行远程脚本
        (r"curl\s+[^|]+\|\s*(bash|sh|zsh)", RISK_DANGEROUS, "管道执行远程脚本"),
        (r"wget\s+[^|]+\|\s*(bash|sh|zsh)", RISK_DANGEROUS, "管道执行远程脚本"),
        (r"curl\s+[^|]+\s*\|\s*python", RISK_DANGEROUS, "管道执行远程 Python 脚本"),
        # 格式化 / 磁盘操作
        (r"\bmkfs\b", RISK_DANGEROUS, "格式化文件系统"),
        (r"\bdd\s+if=", RISK_DANGEROUS, "磁盘镜像写入"),
        (r">\s*/dev/sd[a-z]", RISK_DANGEROUS, "写入块设备"),
        # 权限变更
        (r"\bchmod\s+777\b", RISK_WARNING, "设置全权限"),
        (r"\bchmod\s+[-+]?[rwx]{3}", RISK_WARNING, "修改文件权限"),
        # 系统控制
        (r"\bshutdown\b", RISK_DANGEROUS, "关机"),
        (r"\breboot\b", RISK_DANGEROUS, "重启"),
        (r"\bhalt\b", RISK_DANGEROUS, "停机"),
        (r"\bkill\s+-9\b", RISK_DANGEROUS, "强制杀死进程"),
        # fork bomb
        (r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", RISK_DANGEROUS, "Fork 炸弹"),
    ]

    # ── 敏感信息泄露模式 ────────────────────────────────

    _SENSITIVE_INFO_PATTERNS: List[tuple] = [
        # API Key 格式（通用，支持 sk- 等前缀和连字符）
        (r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?[a-zA-Z0-9_\-]{20,}['\"]?", RISK_DANGEROUS, "API Key 泄露"),
        # AWS Access Key
        (r"AKIA[0-9A-Z]{16}", RISK_DANGEROUS, "AWS Access Key 泄露"),
        # Secret Key
        (r"(?:secret[_-]?key|secretkey)\s*[=:]\s*['\"]?[^\s'\"]{8,}['\"]?", RISK_DANGEROUS, "Secret Key 泄露"),
        # 密码赋值
        (r"(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{3,}['\"]", RISK_WARNING, "密码明文"),
        # 私钥标记
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", RISK_DANGEROUS, "私钥泄露"),
        # Token 格式
        (r"(?:access[_-]?token|auth[_-]?token)\s*[=:]\s*['\"]?[a-zA-Z0-9]{20,}['\"]?", RISK_DANGEROUS, "Token 泄露"),
        # 数据库连接字符串含密码
        (r"(?:mongodb?|postgres|mysql|redis)://[^:\s]+:[^@\s]+@", RISK_DANGEROUS, "数据库连接串含密码"),
    ]

    # ── 网络请求模式 ────────────────────────────────────

    _NETWORK_REQUEST_RE = re.compile(
        r"(?:https?://)([a-zA-Z0-9][a-zA-Z0-9\-._]*\.[a-zA-Z]{2,})",
        re.IGNORECASE,
    )

    # ── 路径遍历模式 ────────────────────────────────────

    _PATH_TRAVERSAL_PATTERNS: List[tuple] = [
        (r"\.\./\.\./", RISK_DANGEROUS, "路径遍历（多层上级目录）"),
        (r"\.\./", RISK_WARNING, "路径遍历（上级目录）"),
        (r"\.\.\\", RISK_WARNING, "路径遍历（Windows 风格）"),
    ]

    def __init__(self):
        """初始化扫描器."""
        self._findings: List[ScanFinding] = []
        self._last_risk_level: str = RISK_SAFE

    # ── 核心扫描方法 ──────────────────────────────────────

    def scan(self, skill_content: str) -> str:
        """扫描 SKILL.md 内容，检测安全风险.

        执行全部四类检测，结果存储在内部状态中.
        后续可通过 :meth:`get_findings` 获取详细发现列表，
        通过 :meth:`get_risk_level` 获取最终风险级别.

        Args:
            skill_content: SKILL.md 文件内容.

        Returns:
            风险级别：``'safe'`` / ``'warning'`` / ``'dangerous'``.
        """
        # 重置状态
        self._findings = []
        self._last_risk_level = RISK_SAFE

        if not skill_content:
            return RISK_SAFE

        lines = skill_content.split("\n")

        # 1. 危险命令检测
        self._scan_dangerous_commands(skill_content, lines)

        # 2. 敏感信息泄露检测
        self._scan_sensitive_info(skill_content, lines)

        # 3. 网络请求域名检测
        self._scan_network_requests(skill_content, lines)

        # 4. 路径遍历检测
        self._scan_path_traversal(skill_content, lines)

        # 计算最终风险级别
        self._last_risk_level = self._compute_risk_level()
        return self._last_risk_level

    # ── 风险级别查询 ──────────────────────────────────────

    def get_risk_level(self, content: Optional[str] = None) -> str:
        """返回扫描的风险级别.

        如果传入 ``content``，会先执行扫描.
        否则返回最近一次 :meth:`scan` 的结果.

        Args:
            content: 可选，传入会先执行扫描.

        Returns:
            风险级别：``'safe'`` / ``'warning'`` / ``'dangerous'``.
        """
        if content is not None:
            return self.scan(content)
        return self._last_risk_level

    def get_findings(self) -> List[ScanFinding]:
        """返回扫描发现列表.

        返回最近一次 :meth:`scan` 的所有发现.
        每项是一个 :class:`ScanFinding` 实例.

        Returns:
            扫描发现列表.
        """
        return self._findings

    def get_findings_dict(self) -> List[dict]:
        """返回扫描发现的字典表示列表.

        Returns:
            扫描发现字典列表.
        """
        return [f.to_dict() for f in self._findings]

    # ── 便捷检查方法 ──────────────────────────────────────

    def is_safe(self, content: str) -> bool:
        """快速判断内容是否安全.

        Args:
            content: SKILL.md 内容.

        Returns:
            风险级别为 ``'safe'`` 时返回 ``True``.
        """
        return self.scan(content) == RISK_SAFE

    def is_dangerous(self, content: str) -> bool:
        """快速判断内容是否有危险.

        Args:
            content: SKILL.md 内容.

        Returns:
            风险级别为 ``'dangerous'`` 时返回 ``True``.
        """
        return self.scan(content) == RISK_DANGEROUS

    # ── 内部扫描方法 ──────────────────────────────────────

    def _scan_dangerous_commands(self, content: str, lines: List[str]) -> None:
        """扫描危险命令模式.

        Args:
            content: SKILL.md 全文.
            lines: 按行分割的文本列表.
        """
        for pattern, severity, desc in self._DANGEROUS_COMMAND_PATTERNS:
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(content):
                # 查找行号
                line_num = self._find_line_number(content, match.start())
                self._add_finding(
                    category="dangerous_command",
                    severity=severity,
                    pattern=desc,
                    matched=match.group(0),
                    line_number=line_num,
                )

    def _scan_sensitive_info(self, content: str, lines: List[str]) -> None:
        """扫描敏感信息泄露.

        Args:
            content: SKILL.md 全文.
            lines: 按行分割的文本列表.
        """
        for pattern, severity, desc in self._SENSITIVE_INFO_PATTERNS:
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(content):
                line_num = self._find_line_number(content, match.start())
                self._add_finding(
                    category="sensitive_info",
                    severity=severity,
                    pattern=desc,
                    matched=match.group(0),
                    line_number=line_num,
                )

    def _scan_network_requests(self, content: str, lines: List[str]) -> None:
        """扫描网络请求到非白名单域名.

        提取所有 http/https URL，检查域名是否在白名单中.

        Args:
            content: SKILL.md 全文.
            lines: 按行分割的文本列表.
        """
        for match in self._NETWORK_REQUEST_RE.finditer(content):
            domain = match.group(1).lower()

            # 检查是否在白名单中（支持子域名匹配）
            is_whitelisted = any(
                domain == w or domain.endswith("." + w)
                for w in self.DOMAIN_WHITELIST
            )

            if not is_whitelisted:
                line_num = self._find_line_number(content, match.start())
                self._add_finding(
                    category="network_request",
                    severity=RISK_WARNING,
                    pattern=f"非白名单域名请求: {domain}",
                    matched=match.group(0),
                    line_number=line_num,
                )

    def _scan_path_traversal(self, content: str, lines: List[str]) -> None:
        """扫描文件系统越权访问（路径遍历）.

        Args:
            content: SKILL.md 全文.
            lines: 按行分割的文本列表.
        """
        for pattern, severity, desc in self._PATH_TRAVERSAL_PATTERNS:
            regex = re.compile(pattern)
            for match in regex.finditer(content):
                line_num = self._find_line_number(content, match.start())
                self._add_finding(
                    category="path_traversal",
                    severity=severity,
                    pattern=desc,
                    matched=match.group(0),
                    line_number=line_num,
                )

    # ── 内部工具方法 ──────────────────────────────────────

    def _add_finding(
        self,
        category: str,
        severity: str,
        pattern: str,
        matched: str,
        line_number: int,
    ) -> None:
        """添加一个扫描发现.

        Args:
            category: 发现类别.
            severity: 严重程度.
            pattern: 模式描述.
            matched: 匹配到的文本.
            line_number: 行号.
        """
        # 截断过长的匹配文本
        if len(matched) > 100:
            matched = matched[:97] + "..."

        self._findings.append(ScanFinding(
            category=category,
            severity=severity,
            pattern=pattern,
            matched=matched,
            line_number=line_number,
        ))

    def _compute_risk_level(self) -> str:
        """根据发现列表计算最终风险级别.

        取所有发现中的最高风险级别.

        Returns:
            ``'safe'`` / ``'warning'`` / ``'dangerous'``.
        """
        if not self._findings:
            return RISK_SAFE

        max_weight = 0
        for finding in self._findings:
            weight = _RISK_WEIGHT.get(finding.severity, 0)
            if weight > max_weight:
                max_weight = weight

        for risk, weight in _RISK_WEIGHT.items():
            if weight == max_weight:
                return risk

        return RISK_SAFE

    @staticmethod
    def _find_line_number(content: str, pos: int) -> int:
        """根据字符偏移计算行号.

        Args:
            content: 全文内容.
            pos: 字符偏移位置.

        Returns:
            行号（1-based）.
        """
        return content.count("\n", 0, pos) + 1
