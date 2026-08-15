"""工具参数安全验证器 — 对 LLM 返回的工具调用参数做安全检查.

在工具执行前对参数值进行安全检测，防止以下攻击:

1. **路径穿越（Path Traversal）**:
   - 检测 ``../``、``..\\``、URL 编码（``%2e%2e%2f``）及双重编码
   - 检测指向系统敏感目录的绝对路径

2. **命令注入（Command Injection）**:
   - 检测 shell 元字符: ``;``、``|``、``&&``、``||``、反引号、
     ``$()``、``>``、``<``、换行符

3. **SSRF（服务端请求伪造）**:
   - 检测 URL 指向内网地址（127.0.0.1、localhost、169.254.、
     10.x、172.16-31.x、192.168.x、IPv6 ::1）
   - 使用 ``ipaddress`` 模块准确判断内网 IP
   - URL 参数会 parse 后检查 hostname

4. **敏感文件路径**:
   - 检测 ``/etc/passwd``、``/etc/shadow``、``.env``、
     ``.git/``、``id_rsa``、``.ssh/`` 等

设计要点:
- 纯标准库实现（re, ipaddress, dataclasses, typing, urllib.parse）
- 递归检查嵌套 dict/list 中的字符串值
- ``strict=True`` 时可疑参数直接 block，``False`` 时 warn
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse


# ═══════════════════════════════════════════════════════════════
#  数据类型
# ═══════════════════════════════════════════════════════════════


@dataclass
class ValidationIssue:
    """单个验证问题.

    Attributes:
        category:    问题类别（path_traversal / command_injection / ssrf / sensitive_path）.
        severity:    严重程度（low / medium / high / critical）.
        param_name:  参数名称（嵌套路径用点号表示，如 ``config.file``）.
        match:       匹配到的危险片段.
        description: 问题描述.
    """

    category: str
    severity: str
    param_name: str
    match: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "category": self.category,
            "severity": self.severity,
            "param_name": self.param_name,
            "match": self.match,
            "description": self.description,
        }


@dataclass
class ValidationResult:
    """参数验证结果.

    Attributes:
        passed:  是否通过（True 表示无问题或仅 warn）.
        action:  动作（allow / warn / block）.
        issues:  检测到的问题列表.
        reason:  综合原因说明.
    """

    passed: bool = True
    action: str = "allow"
    issues: List[ValidationIssue] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "passed": self.passed,
            "action": self.action,
            "issues": [i.to_dict() for i in self.issues],
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════════
#  检测正则与常量
# ═══════════════════════════════════════════════════════════════

# 路径穿越: ../ 或 ..\（可能含 URL 编码）
_PATH_TRAVERSAL_RE = re.compile(
    r"(?:\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f|%2e%2e%5c|\.\.%5c)",
    re.IGNORECASE,
)

# 双重 URL 编码的路径穿越
_PATH_TRAVERSAL_DOUBLE_ENCODED_RE = re.compile(
    r"%252e%252e%252f|%252e%252e/",
    re.IGNORECASE,
)

# 系统敏感目录绝对路径
_SENSITIVE_DIRS = (
    "/etc/",
    "/root/",
    "/var/",
    "/proc/",
    "/sys/",
    "/dev/",
    "/boot/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "/lib/",
    "/lib64/",
    "/srv/",
    "/opt/",
)

# Windows 系统目录
_SENSITIVE_WIN_DIRS_RE = re.compile(
    r"(?:[a-zA-Z]:\\(?:windows|winnt|system32|program files|users)\\?)",
    re.IGNORECASE,
)

# 命令注入 shell 元字符
_COMMAND_INJECTION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r";"), "分号（命令分隔）"),
    (re.compile(r"\|(?!\|)"), "管道符"),
    (re.compile(r"&&"), "AND 逻辑运算符"),
    (re.compile(r"\|\|"), "OR 逻辑运算符"),
    (re.compile(r"`"), "反引号（命令替换）"),
    (re.compile(r"\$\("), "$() 命令替换"),
    (re.compile(r">(?!>)"), "输出重定向"),
    (re.compile(r"<(?!<)"), "输入重定向"),
    (re.compile(r"\n"), "换行符（命令分隔）"),
]

# 敏感文件路径模式
_SENSITIVE_FILE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"/etc/passwd", re.IGNORECASE),
    re.compile(r"/etc/shadow", re.IGNORECASE),
    re.compile(r"/etc/sudoers", re.IGNORECASE),
    re.compile(r"\.env(?:\b|[.\s/\\])", re.IGNORECASE),
    re.compile(r"\.git/", re.IGNORECASE),
    re.compile(r"\.git\\", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"id_dsa", re.IGNORECASE),
    re.compile(r"\.ssh/", re.IGNORECASE),
    re.compile(r"\.ssh\\", re.IGNORECASE),
    re.compile(r"authorized_keys", re.IGNORECASE),
    re.compile(r"known_hosts", re.IGNORECASE),
    re.compile(r"\.aws/credentials", re.IGNORECASE),
    re.compile(r"\.docker/config", re.IGNORECASE),
    re.compile(r"htpasswd", re.IGNORECASE),
    re.compile(r"\.pgpass", re.IGNORECASE),
    re.compile(r"\.my.cnf", re.IGNORECASE),
]

# URL 正则（用于检测参数中的 URL）
_URL_RE = re.compile(
    r"https?://[^\s'\"<>]+",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
#  验证器
# ═══════════════════════════════════════════════════════════════


class ParameterValidator:
    """工具参数安全验证器.

    对 LLM 返回的工具调用参数在执行前做安全检查，检测路径穿越、
    命令注入、SSRF 和敏感文件路径.

    Args:
        strict: 严格模式（默认 True）.
                - True: 检测到任何问题直接 block.
                - False: 高严重度问题 block，低/中严重度问题 warn.

    使用示例::

        validator = ParameterValidator(strict=True)
        result = validator.validate("bash", {"command": "ls; rm -rf /"})
        assert result.action == "block"

        result = validator.validate("read_file", {"path": "../../etc/passwd"})
        assert result.action == "block"

        result = validator.validate("http_get", {"url": "http://127.0.0.1/admin"})
        assert result.action == "block"
    """

    def __init__(self, strict: bool = True) -> None:
        """初始化验证器.

        Args:
            strict: 是否启用严格模式.
        """
        self.strict: bool = strict

    # ── 公开接口 ──────────────────────────────────────────────

    def validate(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ValidationResult:
        """验证工具调用的所有参数.

        递归检查参数中所有字符串值（包括嵌套 dict/list 中的字符串）.

        Args:
            tool_name:  工具名称（用于日志和上下文）.
            arguments: 工具参数字典.

        Returns:
            ValidationResult.
        """
        all_issues: List[ValidationIssue] = []

        # 递归收集所有字符串参数
        self._collect_issues(arguments, "", all_issues)

        if not all_issues:
            return ValidationResult(
                passed=True,
                action="allow",
                issues=[],
                reason="所有参数通过安全检查",
            )

        # 根据 strict 模式和最高严重度决定动作
        max_severity: str = self._max_severity(all_issues)
        action: str = self._decide_action(max_severity)

        if action == "block":
            passed = False
            reason = f"参数安全检查未通过（工具: {tool_name}，最高风险: {max_severity}）"
        elif action == "warn":
            passed = True
            reason = f"参数存在潜在风险（工具: {tool_name}，最高风险: {max_severity}），已放行"
        else:
            passed = True
            reason = "参数通过安全检查"

        return ValidationResult(
            passed=passed,
            action=action,
            issues=all_issues,
            reason=reason,
        )

    def validate_value(
        self, value: str, param_name: str = ""
    ) -> List[ValidationIssue]:
        """检查单个字符串值.

        Args:
            value:      待检查的字符串值.
            param_name: 参数名称（用于报告）.

        Returns:
            检测到的问题列表（空列表表示无问题）.
        """
        issues: List[ValidationIssue] = []
        if not isinstance(value, str):
            return issues

        self._check_path_traversal(value, param_name, issues)
        self._check_command_injection(value, param_name, issues)
        self._check_ssrf(value, param_name, issues)
        self._check_sensitive_path(value, param_name, issues)

        return issues

    # ── 递归收集 ──────────────────────────────────────────────

    def _collect_issues(
        self,
        obj: Any,
        prefix: str,
        issues: List[ValidationIssue],
    ) -> None:
        """递归遍历参数对象，收集所有字符串值的安全问题.

        Args:
            obj:    当前遍历的对象（dict/list/str/其他）.
            prefix: 当前参数路径前缀（如 ``config.files[0]``）.
            issues: 收集问题的列表.
        """
        if isinstance(obj, dict):
            for key, val in obj.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                self._collect_issues(val, child_prefix, issues)
        elif isinstance(obj, (list, tuple)):
            for idx, item in enumerate(obj):
                child_prefix = f"{prefix}[{idx}]"
                self._collect_issues(item, child_prefix, issues)
        elif isinstance(obj, str):
            found = self.validate_value(obj, prefix)
            issues.extend(found)
        # 其他类型（int/float/bool/None）不检查

    # ── 路径穿越检测 ──────────────────────────────────────────

    def _check_path_traversal(
        self,
        value: str,
        param_name: str,
        issues: List[ValidationIssue],
    ) -> None:
        """检测路径穿越.

        检查:
        - ``../``、``..\\`` 直接穿越
        - URL 编码 ``%2e%2e%2f``
        - 双重编码 ``%252e%252e%252f``
        - 解码后再次检查
        - 指向系统敏感目录的绝对路径

        Args:
            value:      待检查的字符串.
            param_name: 参数名称.
            issues:     问题收集列表.
        """
        # 直接匹配路径穿越
        match = _PATH_TRAVERSAL_RE.search(value)
        if match:
            issues.append(ValidationIssue(
                category="path_traversal",
                severity="high",
                param_name=param_name,
                match=match.group(0),
                description="检测到路径穿越序列（../ 或 URL 编码变体）",
            ))
            return

        # 双重编码检查
        match = _PATH_TRAVERSAL_DOUBLE_ENCODED_RE.search(value)
        if match:
            issues.append(ValidationIssue(
                category="path_traversal",
                severity="high",
                param_name=param_name,
                match=match.group(0),
                description="检测到双重 URL 编码的路径穿越",
            ))
            return

        # URL 解码后再检查（处理编码绕过）
        try:
            decoded = unquote(value)
            if decoded != value:
                decoded_match = _PATH_TRAVERSAL_RE.search(decoded)
                if decoded_match:
                    issues.append(ValidationIssue(
                        category="path_traversal",
                        severity="high",
                        param_name=param_name,
                        match=decoded_match.group(0),
                        description="检测到 URL 编码后的路径穿越",
                    ))
                    return
                # 二次解码（双重编码）
                double_decoded = unquote(decoded)
                if double_decoded != decoded:
                    dd_match = _PATH_TRAVERSAL_RE.search(double_decoded)
                    if dd_match:
                        issues.append(ValidationIssue(
                            category="path_traversal",
                            severity="high",
                            param_name=param_name,
                            match=dd_match.group(0),
                            description="检测到双重 URL 编码后的路径穿越",
                        ))
                        return
        except Exception:
            # 解码失败忽略，继续后续检查
            pass

        # 检查指向系统敏感目录的绝对路径
        # 对 Unix 路径
        for sensitive_dir in _SENSITIVE_DIRS:
            if sensitive_dir in value:
                # 排除正常的非系统路径使用（如 /tmp/ 模仿 /etc/ 的情况）
                # 只有当值以 / 开头或是明确的绝对路径时才报告
                if value.startswith(sensitive_dir) or sensitive_dir in value:
                    issues.append(ValidationIssue(
                        category="path_traversal",
                        severity="medium",
                        param_name=param_name,
                        match=sensitive_dir,
                        description=f"检测到指向系统敏感目录的路径: {sensitive_dir}",
                    ))
                    return

        # Windows 系统目录
        win_match = _SENSITIVE_WIN_DIRS_RE.search(value)
        if win_match:
            issues.append(ValidationIssue(
                category="path_traversal",
                severity="medium",
                param_name=param_name,
                match=win_match.group(0),
                description="检测到 Windows 系统目录路径",
            ))

    # ── 命令注入检测 ──────────────────────────────────────────

    def _check_command_injection(
        self,
        value: str,
        param_name: str,
        issues: List[ValidationIssue],
    ) -> None:
        """检测命令注入.

        检查 shell 元字符: ; | && || 反引号 $() > < 换行符.

        Args:
            value:      待检查的字符串.
            param_name: 参数名称.
            issues:     问题收集列表.
        """
        for pattern, desc in _COMMAND_INJECTION_PATTERNS:
            match = pattern.search(value)
            if match:
                matched_str = match.group(0)
                # 避免误报：URL 中的 :// 后的 // 不被当作命令注入
                # 但 || 本身在 URL 中不常见，仍需报告
                # 对于 > 符号，在 JSON/XML 等格式中可能出现，
                # 但在命令参数上下文中是危险的
                issues.append(ValidationIssue(
                    category="command_injection",
                    severity="critical",
                    param_name=param_name,
                    match=matched_str,
                    description=f"检测到命令注入元字符: {desc}（'{matched_str}'）",
                ))
                # 只报告第一个匹配，避免重复
                return

    # ── SSRF 检测 ─────────────────────────────────────────────

    def _check_ssrf(
        self,
        value: str,
        param_name: str,
        issues: List[ValidationIssue],
    ) -> None:
        """检测 SSRF（服务端请求伪造）.

        检查 URL 是否指向内网/链路本地地址.
        使用 ``ipaddress`` 模块准确判断，不仅依赖正则.

        Args:
            value:      待检查的字符串.
            param_name: 参数名称.
            issues:     问题收集列表.
        """
        # 查找所有 URL
        urls = _URL_RE.findall(value)
        if not urls:
            return

        for url_str in urls:
            try:
                parsed = urlparse(url_str)
                hostname = parsed.hostname
                if not hostname:
                    continue

                # 检查 localhost
                if hostname.lower() == "localhost":
                    issues.append(ValidationIssue(
                        category="ssrf",
                        severity="critical",
                        param_name=param_name,
                        match=url_str,
                        description="URL 指向 localhost（内网地址）",
                    ))
                    continue

                # 尝试解析为 IP 地址
                ip_obj: Optional[Any] = None
                try:
                    ip_obj = ipaddress.ip_address(hostname)
                except ValueError:
                    # 不是 IP 地址，是域名
                    # 检查常见内网域名
                    if hostname.lower().endswith(".internal") or \
                       hostname.lower().endswith(".local"):
                        issues.append(ValidationIssue(
                            category="ssrf",
                            severity="high",
                            param_name=param_name,
                            match=url_str,
                            description=f"URL 指向内部域名: {hostname}",
                        ))
                    continue

                    # 非内网域名不报告（如 api.example.com）
                    continue

                # 使用 ipaddress 模块判断是否为内网/保留地址
                if ip_obj.is_private or ip_obj.is_loopback or \
                   ip_obj.is_link_local or ip_obj.is_reserved or \
                   ip_obj.is_multicast or ip_obj.is_unspecified:
                    issues.append(ValidationIssue(
                        category="ssrf",
                        severity="critical",
                        param_name=param_name,
                        match=url_str,
                        description=(
                            f"URL 指向内网/保留地址: {hostname} "
                            f"（类型: {self._ip_type(ip_obj)}）"
                        ),
                    ))
            except Exception:
                # URL 解析失败，忽略
                continue

    def _ip_type(self, ip_obj: Any) -> str:
        """返回 IP 地址类型描述.

        Args:
            ip_obj: ipaddress.IPv4Address 或 IPv6Address.

        Returns:
            类型描述字符串.
        """
        if ip_obj.is_loopback:
            return "loopback"
        if ip_obj.is_private:
            return "private"
        if ip_obj.is_link_local:
            return "link-local"
        if ip_obj.is_reserved:
            return "reserved"
        if ip_obj.is_multicast:
            return "multicast"
        if ip_obj.is_unspecified:
            return "unspecified"
        return "unknown"

    # ── 敏感文件路径检测 ──────────────────────────────────────

    def _check_sensitive_path(
        self,
        value: str,
        param_name: str,
        issues: List[ValidationIssue],
    ) -> None:
        """检测敏感文件路径.

        检查 ``/etc/passwd``、``.env``、``.git/``、``id_rsa`` 等.

        Args:
            value:      待检查的字符串.
            param_name: 参数名称.
            issues:     问题收集列表.
        """
        for pattern in _SENSITIVE_FILE_PATTERNS:
            match = pattern.search(value)
            if match:
                matched = match.group(0)
                # 避免对已经被 path_traversal 报告的 /etc/ 重复报告
                # 但敏感文件更具体，仍然报告
                issues.append(ValidationIssue(
                    category="sensitive_path",
                    severity="high",
                    param_name=param_name,
                    match=matched,
                    description=f"检测到敏感文件路径: {matched}",
                ))
                return  # 每个值只报告第一个敏感文件匹配

    # ── 辅助方法 ──────────────────────────────────────────────

    @staticmethod
    def _severity_rank(severity: str) -> int:
        """返回严重程度的数值排名（越大越严重）.

        Args:
            severity: 严重程度字符串.

        Returns:
            排名整数.
        """
        ranks = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return ranks.get(severity, 0)

    def _max_severity(self, issues: List[ValidationIssue]) -> str:
        """获取问题列表中的最高严重程度.

        Args:
            issues: 问题列表.

        Returns:
            最高严重程度字符串.
        """
        if not issues:
            return "low"
        return max(
            issues,
            key=lambda i: self._severity_rank(i.severity)
        ).severity

    def _decide_action(self, max_severity: str) -> str:
        """根据 strict 模式和最高严重程度决定动作.

        Args:
            max_severity: 最高严重程度.

        Returns:
            "block" / "warn" / "allow".
        """
        if self.strict:
            # 严格模式：任何问题都 block
            return "block"
        else:
            # 非严格模式：high/critical block，其余 warn
            if max_severity in ("high", "critical"):
                return "block"
            return "warn"
