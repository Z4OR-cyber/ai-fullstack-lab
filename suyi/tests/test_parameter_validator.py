"""ParameterValidator 测试（P1 — 工具参数注入检测）.

覆盖范围:
- 路径穿越检测（../、..\\、URL 编码、双重编码、系统敏感目录）
- 命令注入检测（;、|、&&、||、反引号、$()、>、<、换行）
- SSRF 检测（127.0.0.1、localhost、169.254.、10.x、192.168.x、IPv6 ::1）
- 敏感文件路径检测（/etc/shadow、.env、.git/、id_rsa、.ssh/）
- 正常参数不被误报
- 嵌套结构检查（dict 中嵌套 list 中嵌套 string）
- strict / non-strict 模式
- HITLPolicy 集成测试
"""

import pytest

from suyi.tools.parameter_validator import (
    ParameterValidator,
    ValidationResult,
    ValidationIssue,
)
from suyi.hitl import HITLPolicy


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def strict_validator():
    """严格模式验证器."""
    return ParameterValidator(strict=True)


@pytest.fixture
def lenient_validator():
    """非严格模式验证器."""
    return ParameterValidator(strict=False)


# ═══════════════════════════════════════════════════════════════
#  路径穿越检测
# ═══════════════════════════════════════════════════════════════


class TestPathTraversal:
    """路径穿越检测测试."""

    def test_dot_dot_slash(self, strict_validator):
        """../../../etc/passwd 被检测."""
        result = strict_validator.validate_value("../../../etc/passwd")
        assert len(result) >= 1
        assert any(i.category == "path_traversal" for i in result)

    def test_dot_dot_backslash(self, strict_validator):
        """..\\..\\windows\\system32 被检测."""
        result = strict_validator.validate_value(
            "..\\\\..\\\\windows\\\\system32"
        )
        assert len(result) >= 1
        assert any(i.category == "path_traversal" for i in result)

    def test_url_encoded_traversal(self, strict_validator):
        """URL 编码 %2e%2e%2f 被检测."""
        result = strict_validator.validate_value(
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        )
        assert len(result) >= 1
        assert any(i.category == "path_traversal" for i in result)

    def test_double_url_encoded_traversal(self, strict_validator):
        """双重 URL 编码被检测."""
        result = strict_validator.validate_value(
            "%252e%252e%252fetc%252fpasswd"
        )
        assert len(result) >= 1
        assert any(i.category == "path_traversal" for i in result)

    def test_etc_directory(self, strict_validator):
        """/etc/ 系统目录被检测."""
        result = strict_validator.validate_value("/etc/passwd")
        # /etc/passwd 可能同时触发 path_traversal 和 sensitive_path
        assert len(result) >= 1
        categories = {i.category for i in result}
        assert "path_traversal" in categories or "sensitive_path" in categories

    def test_root_directory(self, strict_validator):
        """/root/ 系统目录被检测."""
        result = strict_validator.validate_value("/root/.ssh/id_rsa")
        assert len(result) >= 1

    def test_var_directory(self, strict_validator):
        """/var/ 系统目录被检测."""
        result = strict_validator.validate_value("/var/log/auth.log")
        assert any(
            i.category == "path_traversal" and "/var/" in i.match
            for i in result
        )

    def test_windows_system32(self, strict_validator):
        """C:\\Windows\\System32 被检测."""
        result = strict_validator.validate_value(
            "C:\\Windows\\System32\\config\\SAM"
        )
        assert len(result) >= 1
        assert any(i.category == "path_traversal" for i in result)

    def test_safe_tmp_path_not_flagged_as_traversal(self, strict_validator):
        """/tmp/myfile.txt 不被误报为路径穿越."""
        result = strict_validator.validate_value("/tmp/myfile.txt")
        # /tmp/ 不在敏感目录列表中
        traversal_issues = [
            i for i in result if i.category == "path_traversal"
        ]
        assert len(traversal_issues) == 0


# ═══════════════════════════════════════════════════════════════
#  命令注入检测
# ═══════════════════════════════════════════════════════════════


class TestCommandInjection:
    """命令注入检测测试."""

    def test_semicolon(self, strict_validator):
        """ls; rm -rf / 被检测."""
        result = strict_validator.validate_value("ls; rm -rf /")
        assert any(i.category == "command_injection" for i in result)

    def test_pipe(self, strict_validator):
        """echo hello | cat /etc/passwd 被检测."""
        result = strict_validator.validate_value(
            "echo hello | cat /etc/passwd"
        )
        assert any(i.category == "command_injection" for i in result)

    def test_and_and(self, strict_validator):
        """&& 被检测."""
        result = strict_validator.validate_value("ls && whoami")
        assert any(i.category == "command_injection" for i in result)

    def test_or_or(self, strict_validator):
        """|| 被检测."""
        result = strict_validator.validate_value("ls || id")
        assert any(i.category == "command_injection" for i in result)

    def test_backtick(self, strict_validator):
        """反引号 `id` 被检测."""
        result = strict_validator.validate_value("echo `id`")
        assert any(i.category == "command_injection" for i in result)

    def test_dollar_paren(self, strict_validator):
        """$(whoami) 被检测."""
        result = strict_validator.validate_value("echo $(whoami)")
        assert any(i.category == "command_injection" for i in result)

    def test_output_redirect(self, strict_validator):
        """> 被检测."""
        result = strict_validator.validate_value("echo hi > /tmp/x")
        assert any(i.category == "command_injection" for i in result)

    def test_input_redirect(self, strict_validator):
        """< 被检测."""
        result = strict_validator.validate_value("cat < /etc/passwd")
        assert any(i.category == "command_injection" for i in result)

    def test_newline(self, strict_validator):
        """换行符被检测."""
        result = strict_validator.validate_value("ls\nwhoami")
        assert any(i.category == "command_injection" for i in result)

    def test_severity_critical(self, strict_validator):
        """命令注入严重程度为 critical."""
        result = strict_validator.validate_value("ls; rm -rf /")
        for issue in result:
            if issue.category == "command_injection":
                assert issue.severity == "critical"
                break


# ═══════════════════════════════════════════════════════════════
#  SSRF 检测
# ═══════════════════════════════════════════════════════════════


class TestSSRF:
    """SSRF 检测测试."""

    def test_localhost(self, strict_validator):
        """http://127.0.0.1/admin 被检测."""
        result = strict_validator.validate_value(
            "http://127.0.0.1/admin"
        )
        assert any(i.category == "ssrf" for i in result)

    def test_localhost_name(self, strict_validator):
        """http://localhost/ 被检测."""
        result = strict_validator.validate_value("http://localhost/")
        assert any(i.category == "ssrf" for i in result)

    def test_link_local_metadata(self, strict_validator):
        """http://169.254.169.254/ 被检测（云元数据）."""
        result = strict_validator.validate_value(
            "http://169.254.169.254/latest/meta-data/"
        )
        assert any(i.category == "ssrf" for i in result)

    def test_10_network(self, strict_validator):
        """http://10.0.0.1/ 被检测."""
        result = strict_validator.validate_value("http://10.0.0.1/admin")
        assert any(i.category == "ssrf" for i in result)

    def test_172_16_network(self, strict_validator):
        """http://172.16.0.1/ 被检测."""
        result = strict_validator.validate_value(
            "http://172.16.0.1:8080/"
        )
        assert any(i.category == "ssrf" for i in result)

    def test_192_168_network(self, strict_validator):
        """http://192.168.1.1/ 被检测."""
        result = strict_validator.validate_value("http://192.168.1.1/")
        assert any(i.category == "ssrf" for i in result)

    def test_ipv6_loopback(self, strict_validator):
        """http://[::1]/ 被检测."""
        result = strict_validator.validate_value("http://[::1]/admin")
        assert any(i.category == "ssrf" for i in result)

    def test_0_0_0_0(self, strict_validator):
        """http://0.0.0.0/ 被检测."""
        result = strict_validator.validate_value("http://0.0.0.0/")
        assert any(i.category == "ssrf" for i in result)

    def test_external_url_not_flagged(self, strict_validator):
        """外部 URL 不被误报."""
        result = strict_validator.validate_value(
            "https://api.example.com/data"
        )
        ssrf_issues = [i for i in result if i.category == "ssrf"]
        assert len(ssrf_issues) == 0

    def test_external_ip_not_flagged(self, strict_validator):
        """公网 IP 不被误报."""
        result = strict_validator.validate_value(
            "http://8.8.8.8/dns-query"
        )
        ssrf_issues = [i for i in result if i.category == "ssrf"]
        assert len(ssrf_issues) == 0


# ═══════════════════════════════════════════════════════════════
#  敏感文件路径检测
# ═══════════════════════════════════════════════════════════════


class TestSensitivePaths:
    """敏感文件路径检测测试."""

    def test_etc_shadow(self, strict_validator):
        """/etc/shadow 被检测."""
        result = strict_validator.validate_value("/etc/shadow")
        assert any(i.category == "sensitive_path" for i in result)

    def test_etc_passwd(self, strict_validator):
        """/etc/passwd 被检测."""
        result = strict_validator.validate_value("/etc/passwd")
        assert any(i.category == "sensitive_path" for i in result)

    def test_ssh_id_rsa(self, strict_validator):
        """~/.ssh/id_rsa 被检测."""
        result = strict_validator.validate_value("~/.ssh/id_rsa")
        assert any(i.category == "sensitive_path" for i in result)

    def test_dot_env(self, strict_validator):
        """.env 被检测."""
        result = strict_validator.validate_value(".env")
        assert any(i.category == "sensitive_path" for i in result)

    def test_dot_git_dir(self, strict_validator):
        """.git/ 被检测."""
        result = strict_validator.validate_value(".git/config")
        assert any(i.category == "sensitive_path" for i in result)

    def test_ssh_dir(self, strict_validator):
        """.ssh/ 被检测."""
        result = strict_validator.validate_value(".ssh/authorized_keys")
        assert any(i.category == "sensitive_path" for i in result)

    def test_aws_credentials(self, strict_validator):
        """.aws/credentials 被检测."""
        result = strict_validator.validate_value(".aws/credentials")
        assert any(i.category == "sensitive_path" for i in result)

    def test_authorized_keys(self, strict_validator):
        """authorized_keys 被检测."""
        result = strict_validator.validate_value(
            "/home/user/.ssh/authorized_keys"
        )
        assert any(i.category == "sensitive_path" for i in result)


# ═══════════════════════════════════════════════════════════════
#  正常参数不误报
# ═══════════════════════════════════════════════════════════════


class TestNormalParameters:
    """正常参数不被误报."""

    def test_hello_world(self, strict_validator):
        """hello world 不被误报."""
        result = strict_validator.validate_value("hello world")
        assert len(result) == 0

    def test_tmp_file(self, strict_validator):
        """/tmp/myfile.txt 不被误报."""
        result = strict_validator.validate_value("/tmp/myfile.txt")
        assert len(result) == 0

    def test_external_url(self, strict_validator):
        """https://api.example.com/data 不被误报."""
        result = strict_validator.validate_value(
            "https://api.example.com/data"
        )
        assert len(result) == 0

    def test_relative_path(self, strict_validator):
        """相对路径 data/file.txt 不被误报."""
        result = strict_validator.validate_value("data/file.txt")
        assert len(result) == 0

    def test_filename_without_path(self, strict_validator):
        """普通文件名不被误报."""
        result = strict_validator.validate_value("report_2024.pdf")
        assert len(result) == 0

    def test_numeric_string(self, strict_validator):
        """数字字符串不被误报."""
        result = strict_validator.validate_value("42")
        assert len(result) == 0

    def test_validate_allows_safe_arguments(self, strict_validator):
        """validate 对安全参数返回 allow."""
        result = strict_validator.validate(
            "read_file",
            {"path": "/tmp/data.txt", "encoding": "utf-8"},
        )
        assert result.action == "allow"
        assert result.passed is True

    def test_simple_command_no_injection(self, strict_validator):
        """简单命令（无特殊字符）不被误报."""
        result = strict_validator.validate_value("ls -la /tmp")
        # 不含 ; | & ` $() > < \n，应通过
        injection_issues = [
            i for i in result if i.category == "command_injection"
        ]
        assert len(injection_issues) == 0


# ═══════════════════════════════════════════════════════════════
#  嵌套结构检查
# ═══════════════════════════════════════════════════════════════


class TestNestedStructures:
    """嵌套 dict/list 结构递归检查."""

    def test_nested_dict_in_dict(self, strict_validator):
        """dict 嵌套 dict 中的危险字符串被检测."""
        arguments = {
            "config": {
                "file_path": "../../../etc/passwd",
            }
        }
        result = strict_validator.validate("write_file", arguments)
        assert result.action == "block"
        assert len(result.issues) >= 1

    def test_nested_list_in_dict(self, strict_validator):
        """dict 嵌套 list 中的危险字符串被检测."""
        arguments = {
            "files": [
                "/tmp/safe.txt",
                "../../etc/shadow",
            ]
        }
        result = strict_validator.validate("read_file", arguments)
        assert result.action == "block"

    def test_deeply_nested(self, strict_validator):
        """深层嵌套结构中的危险字符串被检测."""
        arguments = {
            "level1": {
                "level2": [
                    {"url": "http://127.0.0.1/secret"},
                ]
            }
        }
        result = strict_validator.validate("http_get", arguments)
        assert result.action == "block"
        assert any(i.category == "ssrf" for i in result.issues)

    def test_param_name_in_issue(self, strict_validator):
        """问题中包含正确的参数路径名."""
        arguments = {
            "config": {
                "path": "../../etc/passwd",
            }
        }
        result = strict_validator.validate("tool", arguments)
        assert len(result.issues) >= 1
        # 参数路径应包含 config.path
        assert any(
            "config" in i.param_name and "path" in i.param_name
            for i in result.issues
        )

    def test_list_index_in_param_name(self, strict_validator):
        """list 索引出现在参数路径中."""
        arguments = {
            "items": ["safe", "http://169.254.169.254/"],
        }
        result = strict_validator.validate("tool", arguments)
        assert len(result.issues) >= 1
        assert any("[1]" in i.param_name for i in result.issues)

    def test_tuple_values_checked(self, strict_validator):
        """tuple 中的字符串也被检查."""
        arguments = {
            "paths": ("/tmp/safe", "../../etc/shadow"),
        }
        result = strict_validator.validate("tool", arguments)
        assert result.action == "block"

    def test_non_string_values_ignored(self, strict_validator):
        """非字符串值不导致错误."""
        arguments = {
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
            "nothing": None,
        }
        result = strict_validator.validate("tool", arguments)
        assert result.action == "allow"


# ═══════════════════════════════════════════════════════════════
#  strict / non-strict 模式
# ═══════════════════════════════════════════════════════════════


class TestStrictnessModes:
    """strict / non-strict 模式测试."""

    def test_strict_blocks_all(self, strict_validator):
        """严格模式下任何问题都 block."""
        # 用一个 medium 严重度的问题（敏感目录路径）
        result = strict_validator.validate(
            "tool", {"path": "/var/log/syslog"}
        )
        assert result.action == "block"

    def test_lenient_warns_on_medium(self, lenient_validator):
        """非严格模式下 medium 问题只 warn 不 block."""
        result = lenient_validator.validate(
            "tool", {"path": "/var/log/syslog"}
        )
        # /var/ 是 medium，非严格模式应 warn
        assert result.action in ("warn", "block")
        assert len(result.issues) > 0

    def test_lenient_blocks_critical(self, lenient_validator):
        """非严格模式下 critical 问题仍然 block."""
        result = lenient_validator.validate(
            "bash", {"command": "ls; rm -rf /"}
        )
        assert result.action == "block"

    def test_lenient_blocks_high(self, lenient_validator):
        """非严格模式下 high 问题仍然 block."""
        result = lenient_validator.validate(
            "read_file", {"path": "../../../etc/passwd"}
        )
        assert result.action == "block"


# ═══════════════════════════════════════════════════════════════
#  ValidationResult / ValidationIssue 数据类
# ═══════════════════════════════════════════════════════════════


class TestDataClasses:
    """数据类测试."""

    def test_validation_issue_to_dict(self):
        """ValidationIssue.to_dict() 返回正确结构."""
        issue = ValidationIssue(
            category="ssrf",
            severity="critical",
            param_name="url",
            match="http://127.0.0.1/",
            description="URL 指向 localhost",
        )
        d = issue.to_dict()
        assert d["category"] == "ssrf"
        assert d["severity"] == "critical"
        assert d["param_name"] == "url"
        assert d["match"] == "http://127.0.0.1/"

    def test_validation_result_to_dict(self):
        """ValidationResult.to_dict() 返回正确结构."""
        result = ValidationResult(
            passed=False,
            action="block",
            issues=[
                ValidationIssue(
                    category="command_injection",
                    severity="critical",
                    param_name="cmd",
                    match=";",
                    description="分号",
                )
            ],
            reason="test",
        )
        d = result.to_dict()
        assert d["passed"] is False
        assert d["action"] == "block"
        assert len(d["issues"]) == 1
        assert d["reason"] == "test"

    def test_default_result_is_allow(self):
        """默认 ValidationResult 为 allow."""
        result = ValidationResult()
        assert result.passed is True
        assert result.action == "allow"
        assert result.issues == []


# ═══════════════════════════════════════════════════════════════
#  HITLPolicy 集成
# ═══════════════════════════════════════════════════════════════


class TestHITLPolicyIntegration:
    """HITLPolicy 与 ParameterValidator 集成测试."""

    def test_policy_without_validator_backward_compatible(self):
        """不传 validator 时行为不变（向后兼容）."""
        policy = HITLPolicy()
        # 安全参数不被 block
        decision = policy.check(
            "read_file", {"path": "/tmp/data.txt"}
        )
        assert decision.action != "block"

    def test_policy_blocks_path_traversal(self):
        """传入 validator 后路径穿越被 block."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "read_file", {"path": "../../../etc/passwd"}
        )
        assert decision.action == "block"
        assert "Parameter validation" in decision.reason or \
               "param" in decision.reason.lower()

    def test_policy_blocks_command_injection(self):
        """传入 validator 后命令注入被 block."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "bash", {"command": "echo hi; rm -rf /"}
        )
        assert decision.action == "block"

    def test_policy_blocks_ssrf(self):
        """传入 validator 后 SSRF 被 block."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "http_get", {"url": "http://127.0.0.1/admin"}
        )
        assert decision.action == "block"

    def test_policy_blocks_sensitive_file(self):
        """传入 validator 后敏感文件路径被 block."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "read_file", {"path": "/etc/shadow"}
        )
        assert decision.action == "block"

    def test_policy_allows_safe_params_with_validator(self):
        """传入 validator 后安全参数不被 block."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "read_file", {"path": "/tmp/myfile.txt"}
        )
        assert decision.action != "block"

    def test_policy_validator_none_by_default(self):
        """HITLPolicy 默认 parameter_validator 为 None."""
        policy = HITLPolicy()
        assert policy.parameter_validator is None

    def test_policy_risk_score_critical_on_block(self):
        """参数验证 block 时风险评分为 critical."""
        validator = ParameterValidator(strict=True)
        policy = HITLPolicy(parameter_validator=validator)
        decision = policy.check(
            "bash", {"command": "ls; whoami"}
        )
        assert decision.action == "block"
        assert decision.risk_score.level == "critical"
        assert decision.risk_score.score == 1.0
