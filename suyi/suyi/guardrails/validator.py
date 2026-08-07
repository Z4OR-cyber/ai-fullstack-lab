"""输出验证 — 验证 LLM 输出的格式和安全性.

验证类别:
    1. JSON 格式验证: 从输出中提取 JSON 并验证结构
    2. 代码安全验证: 检测危险代码模式（eval/exec/os.system 等）
    3. URL 验证: 检测恶意 URL 模式

验证不通过时返回:
    - valid: False
    - issues: 问题列表
    - sanitized_output: 清理后的输出（移除危险部分）
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 危险代码模式 ──────────────────────────────────────────────

_DANGEROUS_CODE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\beval\s*\(", re.M),
    re.compile(r"\bexec\s*\(", re.M),
    re.compile(r"\bos\.system\s*\(", re.M),
    re.compile(r"\bsubprocess\.(?:call|run|Popen|check_output)\s*\(", re.M),
    re.compile(r"\b__import__\s*\(", re.M),
    re.compile(r"\bopen\s*\(\s*['\"](?:/etc/passwd|/etc/shadow)", re.M),
    re.compile(r"\b(?:rm|del)\s+-rf?\s+/", re.M),
    re.compile(r"\bchmod\s+\d{3,4}\s+/", re.M),
    re.compile(r"\b(?:curl|wget)\s+.*\|\s*(?:sh|bash)", re.M),
    re.compile(r"\bpickle\.loads?\s*\(", re.M),
    re.compile(r"\bshell\s*=\s*True", re.M),
]

# ── 恶意 URL 模式 ─────────────────────────────────────────────

_MALICIOUS_URL_PATTERNS: List[re.Pattern[str]] = [
    re.compile(
        r"https?://(?:"
        r"localhost"              # localhost
        r"|127\.0\.0\.1"          # loopback
        r"|0\.0\.0\.0"            # all interfaces
        r"|(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\."  # private ranges
        r")",
        re.I,
    ),
    re.compile(
        r"https?://(?:"
        r"(?:[a-z0-9-]+\.)*"
        r"(?:example\.com|test\.com|invalid)"  # test domains
        r")",
        re.I,
    ),
    # data: URI（潜在的 XSS 向量）
    re.compile(r"data:(?:text/html|application/javascript)", re.I),
    # javascript: URI
    re.compile(r"javascript:", re.I),
]

# ── 结果类型 ──────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """验证问题.

    Attributes:
        category: 问题类别（json / code / url）.
        severity: 严重程度（error / warning）.
        message: 问题描述.
        detail: 详细信息.
    """

    category: str = ""
    severity: str = "error"
    message: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class ValidationResult:
    """验证结果.

    Attributes:
        valid: 是否通过验证.
        issues: 问题列表.
        sanitized_output: 清理后的输出.
        extracted_json: 提取出的 JSON 对象（如适用）.
    """

    valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    sanitized_output: str = ""
    extracted_json: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "sanitized_output": self.sanitized_output,
            "extracted_json": self.extracted_json,
        }


# ── 输出验证器 ────────────────────────────────────────────────


class OutputValidator:
    """LLM 输出验证器.

    验证三方面:
        1. JSON 格式: 提取并验证 JSON 结构
        2. 代码安全: 检测危险代码模式
        3. URL 安全: 检测恶意 URL

    Args:
        enable_json_validation: 是否启用 JSON 验证（默认 True）.
        enable_code_validation: 是否启用代码安全验证（默认 True）.
        enable_url_validation:  是否启用 URL 验证（默认 True）.

    使用示例::

        v = OutputValidator()

        # JSON 验证
        result = v.validate('```json\\n{"name": "test"}\\n```')
        assert result.valid
        assert result.extracted_json == {"name": "test"}

        # 代码安全验证
        result = v.validate('eval("malicious code")')
        assert not result.valid
    """

    def __init__(
        self,
        enable_json_validation: bool = True,
        enable_code_validation: bool = True,
        enable_url_validation: bool = True,
    ) -> None:
        self.enable_json_validation: bool = enable_json_validation
        self.enable_code_validation: bool = enable_code_validation
        self.enable_url_validation: bool = enable_url_validation

    def validate(self, output: str) -> ValidationResult:
        """验证 LLM 输出.

        按顺序执行: JSON 提取验证 → 代码安全验证 → URL 验证.

        Args:
            output: LLM 输出字符串.

        Returns:
            ValidationResult.
        """
        issues: List[ValidationIssue] = []
        sanitized: str = output
        extracted_json: Optional[Any] = None

        # 1. JSON 格式验证
        if self.enable_json_validation:
            json_result: Optional[Any] = None
            json_error: Optional[str] = None

            # 尝试直接解析
            try:
                json_result = json.loads(output)
            except json.JSONDecodeError:
                # 尝试从 markdown 代码块中提取
                json_result, json_error = self._extract_json_from_markdown(output)

            if json_result is not None:
                extracted_json = json_result
            elif json_error:
                # 只有当输出看起来像 JSON 时才报错
                if self._looks_like_json(output):
                    issues.append(ValidationIssue(
                        category="json",
                        severity="warning",
                        message="JSON parsing failed",
                        detail=json_error,
                    ))

        # 2. 代码安全验证
        if self.enable_code_validation:
            code_issues: List[ValidationIssue] = self._check_code_safety(output)
            issues.extend(code_issues)
            if code_issues:
                sanitized = self._sanitize_code(sanitized)

        # 3. URL 验证
        if self.enable_url_validation:
            url_issues: List[ValidationIssue] = self._check_urls(output)
            issues.extend(url_issues)
            if url_issues:
                sanitized = self._sanitize_urls(sanitized)

        # 判断是否有效（有 error 级别的 issue 则无效）
        has_errors: bool = any(
            issue.severity == "error" for issue in issues
        )

        return ValidationResult(
            valid=not has_errors,
            issues=issues,
            sanitized_output=sanitized if issues else output,
            extracted_json=extracted_json,
        )

    # ── JSON 提取 ──────────────────────────────────────────────

    def _extract_json_from_markdown(
        self, text: str
    ) -> tuple[Optional[Any], Optional[str]]:
        """从 markdown 代码块中提取 JSON.

        支持格式:
            ```json ... ```
            ``` ... ```
            { ... }（裸 JSON）

        Args:
            text: 输入文本.

        Returns:
            (解析结果, 错误信息) — 解析结果为 None 表示未找到 JSON.
        """
        # ```json ... ```
        match: Optional[re.Match[str]] = re.search(
            r"```(?:json)?\s*\n(.*?)\n\s*```",
            text,
            re.DOTALL,
        )
        if match:
            json_str: str = match.group(1).strip()
            try:
                return json.loads(json_str), None
            except json.JSONDecodeError as e:
                return None, str(e)

        # 裸 JSON 对象/数组
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str), None
            except json.JSONDecodeError as e:
                return None, str(e)

        return None, None

    def _looks_like_json(self, text: str) -> bool:
        """判断文本是否看起来像 JSON.

        Args:
            text: 输入文本.

        Returns:
            True 如果文本包含 JSON 特征（花括号/方括号 + 冒号）.
        """
        stripped: str = text.strip()
        # 以 { 或 [ 开头
        if stripped.startswith(("{", "[")):
            return True
        # 包含 ```json
        if "```json" in text.lower():
            return True
        return False

    # ── 代码安全 ──────────────────────────────────────────────

    def _check_code_safety(self, text: str) -> List[ValidationIssue]:
        """检查代码安全.

        Args:
            text: 输出文本.

        Returns:
            问题列表.
        """
        issues: List[ValidationIssue] = []
        for pattern in _DANGEROUS_CODE_PATTERNS:
            matches: List[str] = pattern.findall(text)
            if matches:
                issues.append(ValidationIssue(
                    category="code",
                    severity="error",
                    message="Dangerous code pattern detected",
                    detail=f"Pattern: {pattern.pattern}, "
                           f"matches: {len(matches)}",
                ))
        return issues

    def _sanitize_code(self, text: str) -> str:
        """清理代码中的危险部分.

        将危险代码模式替换为注释提示.

        Args:
            text: 原始文本.

        Returns:
            清理后的文本.
        """
        result: str = text
        for pattern in _DANGEROUS_CODE_PATTERNS:
            result = pattern.sub("# [REMOVED: dangerous code]", result)
        return result

    # ── URL 安全 ──────────────────────────────────────────────

    def _check_urls(self, text: str) -> List[ValidationIssue]:
        """检查 URL 安全.

        Args:
            text: 输出文本.

        Returns:
            问题列表.
        """
        issues: List[ValidationIssue] = []
        for pattern in _MALICIOUS_URL_PATTERNS:
            matches: List[str] = pattern.findall(text)
            if matches:
                issues.append(ValidationIssue(
                    category="url",
                    severity="warning",
                    message="Potentially malicious URL detected",
                    detail=f"Pattern: {pattern.pattern}, "
                           f"matches: {len(matches)}",
                ))
        return issues

    def _sanitize_urls(self, text: str) -> str:
        """清理恶意 URL.

        Args:
            text: 原始文本.

        Returns:
            清理后的文本.
        """
        result: str = text
        for pattern in _MALICIOUS_URL_PATTERNS:
            result = pattern.sub("[REDACTED_URL]", result)
        return result
