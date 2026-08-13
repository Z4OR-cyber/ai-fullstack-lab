"""
PromptSanitizer 测试 — 覆盖所有检测类型、配置选项和边界场景。

测试组织：
    TestAPIKeySanitization      — 7 种 API Key 模式
    TestFilePathSanitization    — 4 种文件路径模式
    TestEmailSanitization        — 邮箱地址
    TestIPSanitization           — IP 地址 + localhost 排除
    TestPasswordSanitization     — 3 种密码模式
    TestDBConnSanitization       — 3 种数据库连接串
    TestMixedAndComplexScenarios — 混合敏感信息 / 中文 / 代码块 / JSON
    TestMessageSanitization      — messages 列表处理 + 不修改原始
    TestConfigurationOptions     — dry_run / redact_str / enabled_patterns
    TestLogAndReport             — get_redaction_log / reset_log / sanitize_with_report
    TestEdgeCases                — 空字符串 / 空列表 / 无敏感信息
    TestOmniRouteIntegration      — OmniRouteAdapter 集成
"""

import copy
import pytest

from suyi.llm.prompt_sanitizer import (
    PromptSanitizer,
    RedactionRecord,
    PatternType,
    ALL_PATTERN_TYPES,
)
from suyi.llm import PromptSanitizer as ExportedPromptSanitizer
from suyi.llm import OmniRouteAdapter


# ═══════════════════════════════════════════════════════════════
#  API Key 脱敏测试（7 种）
# ═══════════════════════════════════════════════════════════════


class TestAPIKeySanitization:
    """测试每种 API Key 模式的检测和脱敏。"""

    def test_openai_sk_key(self):
        """OpenAI/DeepSeek/SiliconFlow sk- 前缀。"""
        s = PromptSanitizer()
        text = "My API key is sk-abcdefghijklmnopqrstuvwxyz123456"
        result = s.sanitize(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED]" in result

    def test_github_pat(self):
        """GitHub Personal Access Token ghp_ 前缀。"""
        s = PromptSanitizer()
        text = "token: ghp_abcdefghijklmnopqrstuvwxyz1234567890AB"
        result = s.sanitize(text)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_kimi_ak(self):
        """Kimi/Moonshot ak- 前缀。"""
        s = PromptSanitizer()
        text = "Use ak-abcdefghijklmnopqrstuvwxyz1234 to authenticate"
        result = s.sanitize(text)
        assert "ak-abcdefghijklmnopqrstuvwxyz1234" not in result
        assert "[REDACTED]" in result

    def test_google_api_key(self):
        """Google API Key AIza 前缀。"""
        s = PromptSanitizer()
        key = "AIzaSyA1234567890abcdefghijklmnopqrstuvwxyz"
        text = f"Google key: {key}"
        result = s.sanitize(text)
        assert key not in result
        assert "[REDACTED]" in result

    def test_google_oauth(self):
        """Google OAuth AQ. 前缀。"""
        s = PromptSanitizer()
        token = "AQ.ABCdef1234567890abcdefghijklmnopqrstuvwxyz"
        text = f"OAuth token is {token}"
        result = s.sanitize(text)
        assert token not in result
        assert "[REDACTED]" in result

    def test_bearer_token(self):
        """Bearer token 模式。"""
        s = PromptSanitizer()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        result = s.sanitize(text)
        assert "Bearer " not in result
        assert "[REDACTED]" in result

    def test_anthropic_key(self):
        """Anthropic sk-ant- 前缀。"""
        s = PromptSanitizer()
        key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456"
        text = f"Anthropic key: {key}"
        result = s.sanitize(text)
        assert key not in result
        assert "[REDACTED]" in result

    def test_short_sk_not_matched(self):
        """太短的 sk- 前缀不应被匹配（少于 20 字符）。"""
        s = PromptSanitizer()
        text = "short key sk-abc123"
        result = s.sanitize(text)
        # "sk-abc123" 只有 6 个字符，不满足 {20,} 要求
        assert result == "short key sk-abc123"


# ═══════════════════════════════════════════════════════════════
#  文件路径脱敏测试（4 种）
# ═══════════════════════════════════════════════════════════════


class TestFilePathSanitization:
    """测试每种文件路径模式的检测和脱敏。"""

    def test_windows_path(self):
        """Windows 绝对路径。"""
        s = PromptSanitizer()
        text = r"Config at C:\Users\admin\secrets\config.json"
        result = s.sanitize(text)
        assert "C:\\Users" not in result
        assert "[REDACTED]" in result

    def test_unix_home_path(self):
        """Unix home 路径。"""
        s = PromptSanitizer()
        text = "Check /home/user/.ssh/id_rsa for the key"
        result = s.sanitize(text)
        assert "/home/user/.ssh/id_rsa" not in result
        assert "[REDACTED]" in result

    def test_app_data_path(self):
        """App data 路径。"""
        s = PromptSanitizer()
        text = "Data stored at /app/data/secrets/credentials.json"
        result = s.sanitize(text)
        assert "/app/data/secrets/credentials.json" not in result
        assert "[REDACTED]" in result

    def test_coze_drive_path(self):
        """Coze Drive 路径。"""
        s = PromptSanitizer()
        text = "Project at /Coze/Drive/workspace/project/file.txt"
        result = s.sanitize(text)
        assert "/Coze/Drive/workspace/project/file.txt" not in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  邮箱地址脱敏测试
# ═══════════════════════════════════════════════════════════════


class TestEmailSanitization:
    """测试邮箱地址脱敏。"""

    def test_standard_email(self):
        """标准邮箱地址。"""
        s = PromptSanitizer()
        text = "Contact me at user@example.com for details"
        result = s.sanitize(text)
        assert "user@example.com" not in result
        assert "[REDACTED]" in result

    def test_complex_email(self):
        """复杂邮箱地址（带 + 和子域名）。"""
        s = PromptSanitizer()
        text = "Email: john.doe+test@mail.subdomain.example.co.uk"
        result = s.sanitize(text)
        assert "john.doe+test@mail.subdomain.example.co.uk" not in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  IP 地址脱敏测试
# ═══════════════════════════════════════════════════════════════


class TestIPSanitization:
    """测试 IP 地址脱敏。"""

    def test_ipv4_redacted(self):
        """普通 IPv4 地址应被脱敏。"""
        s = PromptSanitizer()
        text = "Connect to 192.168.1.100 on port 8080"
        result = s.sanitize(text)
        assert "192.168.1.100" not in result
        assert "[REDACTED]" in result

    def test_ipv4_excludes_localhost(self):
        """127.0.0.1 不应被脱敏。"""
        s = PromptSanitizer()
        text = "Server at 127.0.0.1:3000"
        result = s.sanitize(text)
        assert "127.0.0.1" in result  # 保留原样

    def test_ipv4_excludes_zero_zero(self):
        """0.0.0.0 不应被脱敏。"""
        s = PromptSanitizer()
        text = "Binding to 0.0.0.0:80"
        result = s.sanitize(text)
        assert "0.0.0.0" in result  # 保留原样

    def test_ipv4_public_redacted(self):
        """公网 IP 应被脱敏。"""
        s = PromptSanitizer()
        text = "External IP is 8.8.8.8 for DNS"
        result = s.sanitize(text)
        assert "8.8.8.8" not in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  密码模式脱敏测试
# ═══════════════════════════════════════════════════════════════


class TestPasswordSanitization:
    """测试密码 / 密钥模式脱敏。"""

    def test_password_kv(self):
        """password=value 模式，只脱敏值。"""
        s = PromptSanitizer()
        text = "config password=mySecretPassword123"
        result = s.sanitize(text)
        assert "mySecretPassword123" not in result
        assert "password" in result  # key 保留
        assert "[REDACTED]" in result

    def test_secret_kv(self):
        """secret=value 模式，只脱敏值。"""
        s = PromptSanitizer()
        text = "secret=superSecretValue456"
        result = s.sanitize(text)
        assert "superSecretValue456" not in result
        assert "secret" in result
        assert "[REDACTED]" in result

    def test_token_kv(self):
        """token=value 模式，只脱敏值。"""
        s = PromptSanitizer()
        text = "token: abcTokenXYZ789"
        result = s.sanitize(text)
        assert "abcTokenXYZ789" not in result
        assert "token" in result
        assert "[REDACTED]" in result

    def test_password_with_spaces(self):
        """password = value（含空格）模式。"""
        s = PromptSanitizer()
        text = "password = mypassword123"
        result = s.sanitize(text)
        assert "mypassword123" not in result
        assert "password" in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  数据库连接串脱敏测试
# ═══════════════════════════════════════════════════════════════


class TestDBConnSanitization:
    """测试数据库连接串中的密码脱敏。"""

    def test_postgres_conn_string(self):
        """PostgreSQL 连接串密码脱敏。"""
        s = PromptSanitizer()
        text = "DATABASE_URL=postgres://admin:secretPass123@localhost:5432/mydb"
        result = s.sanitize(text)
        assert "secretPass123" not in result
        assert "postgres://admin:" in result  # protocol + user 保留
        assert "[REDACTED]" in result
        assert "@localhost:5432/mydb" in result  # host 保留

    def test_mysql_conn_string(self):
        """MySQL 连接串密码脱敏。"""
        s = PromptSanitizer()
        text = "mysql://root:password123@db.example.com:3306/shop"
        result = s.sanitize(text)
        assert "password123" not in result
        assert "mysql://root:" in result
        assert "[REDACTED]" in result

    def test_mongodb_conn_string(self):
        """MongoDB 连接串密码脱敏。"""
        s = PromptSanitizer()
        text = "mongodb://user:mongopass@cluster.mongodb.net:27017"
        result = s.sanitize(text)
        assert "mongopass" not in result
        assert "mongodb://user:" in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  混合 / 复杂场景测试
# ═══════════════════════════════════════════════════════════════


class TestMixedAndComplexScenarios:
    """测试多种敏感信息混合的场景。"""

    def test_mixed_sensitive_info(self):
        """一段文本中混合多种敏感信息。"""
        s = PromptSanitizer()
        text = (
            "Deploy config: API key sk-abcdefghijklmnopqrstuvwxyz1234, "
            "db at postgres://admin:dbpass@10.0.0.5:5432/app, "
            "email admin@company.com, "
            "secret file at /home/deploy/secrets/env"
        )
        result = s.sanitize(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result
        assert "dbpass" not in result
        assert "admin@company.com" not in result
        assert "/home/deploy/secrets/env" not in result
        assert "10.0.0.5" not in result
        assert result.count("[REDACTED]") >= 5

    def test_chinese_text_sensitive(self):
        """中文文本中的敏感信息检测。"""
        s = PromptSanitizer()
        text = "请把文件放在 C:\\Users\\张三\\桌面\\机密.txt，API密钥是 sk-abcdefghijklmnopqrstuvwxyz1234"
        result = s.sanitize(text)
        assert "C:\\Users" not in result
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result
        assert "[REDACTED]" in result

    def test_code_block_sensitive(self):
        """代码块中的敏感信息检测。"""
        s = PromptSanitizer()
        text = (
            "```python\n"
            "import os\n"
            "API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz12345678'\n"
            "DB_URL = 'postgres://user:mypassword@192.168.1.10:5432/db'\n"
            "```\n"
            "Please check the above config."
        )
        result = s.sanitize(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz12345678" not in result
        assert "mypassword" not in result
        assert "192.168.1.10" not in result
        assert "[REDACTED]" in result

    def test_json_text_sensitive(self):
        """JSON 格式文本中的敏感信息检测。"""
        s = PromptSanitizer()
        text = (
            '{"api_key": "sk-abcdefghijklmnopqrstuvwxyz1234", '
            '"email": "test@example.com", '
            '"server_ip": "10.20.30.40"}'
        )
        result = s.sanitize(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result
        assert "test@example.com" not in result
        assert "10.20.30.40" not in result
        assert "[REDACTED]" in result


# ═══════════════════════════════════════════════════════════════
#  Messages 列表处理测试
# ═══════════════════════════════════════════════════════════════


class TestMessageSanitization:
    """测试 sanitize_messages 对 messages 列表的处理。"""

    def test_sanitize_messages_basic(self):
        """基本 messages 列表处理。"""
        s = PromptSanitizer()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "My key is sk-abcdefghijklmnopqrstuvwxyz1234"},
            {"role": "assistant", "content": "I see."},
        ]
        result = s.sanitize_messages(messages)
        assert len(result) == 3
        assert result[0]["content"] == "You are helpful."
        assert "sk-" not in result[1]["content"]
        assert "[REDACTED]" in result[1]["content"]
        assert result[2]["content"] == "I see."

    def test_sanitize_messages_no_mutation(self):
        """不修改原始 messages（深拷贝验证）。"""
        s = PromptSanitizer()
        original = [
            {"role": "user", "content": "key sk-abcdefghijklmnopqrstuvwxyz1234"},
        ]
        original_deep = copy.deepcopy(original)
        _ = s.sanitize_messages(original)
        # 原始列表和字典不应被修改
        assert original == original_deep
        assert original[0]["content"] == "key sk-abcdefghijklmnopqrstuvwxyz1234"

    def test_sanitize_messages_none_content(self):
        """content 为 None 的消息应被跳过。"""
        s = PromptSanitizer()
        messages = [
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "user", "content": "sk-abcdefghijklmnopqrstuvwxyz1234"},
        ]
        result = s.sanitize_messages(messages)
        assert result[0]["content"] is None
        assert "[REDACTED]" in result[1]["content"]

    def test_sanitize_messages_non_string_content(self):
        """content 为非字符串（如 list）时应被跳过。"""
        s = PromptSanitizer()
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ]
        result = s.sanitize_messages(messages)
        # 非字符串 content 原样保留
        assert result[0]["content"] == [{"type": "text", "text": "hello"}]


# ═══════════════════════════════════════════════════════════════
#  配置选项测试
# ═══════════════════════════════════════════════════════════════


class TestConfigurationOptions:
    """测试 dry_run、redact_str、enabled_patterns 等配置。"""

    def test_dry_run_mode(self):
        """dry_run=True 时只记录不替换。"""
        s = PromptSanitizer(dry_run=True)
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234"
        result = s.sanitize(text)
        assert result == text  # 原样返回
        # 但日志应有记录
        log = s.get_redaction_log()
        assert len(log) == 1
        assert log[0]["redacted"] is False

    def test_custom_redact_str(self):
        """自定义 redact_str。"""
        s = PromptSanitizer(redact_str="***HIDDEN***")
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234"
        result = s.sanitize(text)
        assert "***HIDDEN***" in result
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result

    def test_enabled_patterns_partial(self):
        """只启用部分检测类型。"""
        s = PromptSanitizer(enabled_patterns={"api_key", "email"})
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234 email test@example.com ip 10.0.0.1"
        result = s.sanitize(text)
        # api_key 被脱敏
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result
        # email 被脱敏
        assert "test@example.com" not in result
        # ip 未被脱敏（未启用）
        assert "10.0.0.1" in result

    def test_enabled_patterns_empty_set(self):
        """空集合禁用所有模式。"""
        s = PromptSanitizer(enabled_patterns=set())
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234 email test@example.com"
        result = s.sanitize(text)
        assert result == text  # 无任何脱敏

    def test_no_log_redactions(self):
        """log_redactions=False 时不记录日志。"""
        s = PromptSanitizer(log_redactions=False)
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234"
        result = s.sanitize(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result
        assert s.get_redaction_log() == []

    def test_exported_class_is_same(self):
        """从 suyi.llm 导出的 PromptSanitizer 应与模块中的一致。"""
        assert ExportedPromptSanitizer is PromptSanitizer


# ═══════════════════════════════════════════════════════════════
#  日志与报告测试
# ═══════════════════════════════════════════════════════════════


class TestLogAndReport:
    """测试 get_redaction_log / reset_log / sanitize_with_report。"""

    def test_get_redaction_log(self):
        """获取脱敏日志。"""
        s = PromptSanitizer()
        s.sanitize("key sk-abcdefghijklmnopqrstuvwxyz1234")
        log = s.get_redaction_log()
        assert len(log) == 1
        assert log[0]["type"] == "api_key"
        assert log[0]["original_pattern"] == "openai_sk"
        assert isinstance(log[0]["position"], int)
        assert isinstance(log[0]["context"], str)
        assert log[0]["redacted"] is True

    def test_reset_log(self):
        """清空脱敏日志。"""
        s = PromptSanitizer()
        s.sanitize("key sk-abcdefghijklmnopqrstuvwxyz1234")
        assert len(s.get_redaction_log()) == 1
        s.reset_log()
        assert s.get_redaction_log() == []

    def test_log_accumulates_across_calls(self):
        """多次 sanitize 调用日志累计。"""
        s = PromptSanitizer()
        s.sanitize("sk-abcdefghijklmnopqrstuvwxyz1234")
        s.sanitize("email test@example.com")
        log = s.get_redaction_log()
        assert len(log) == 2
        assert log[0]["type"] == "api_key"
        assert log[1]["type"] == "email"

    def test_sanitize_with_report(self):
        """sanitize_with_report 返回清洗后文本和报告。"""
        s = PromptSanitizer()
        text = "key sk-abcdefghijklmnopqrstuvwxyz1234 and email test@example.com"
        result, report = s.sanitize_with_report(text)
        assert "sk-" not in result
        assert "test@example.com" not in result
        assert "[REDACTED]" in result
        assert len(report) == 2
        types = {r["type"] for r in report}
        assert "api_key" in types
        assert "email" in types

    def test_sanitize_with_report_only_this_call(self):
        """sanitize_with_report 仅返回本次调用的记录。"""
        s = PromptSanitizer()
        s.sanitize("sk-abcdefghijklmnopqrstuvwxyz1234")
        _, report = s.sanitize_with_report("email test@example.com")
        # report 只包含第二次调用的记录
        assert len(report) == 1
        assert report[0]["type"] == "email"


# ═══════════════════════════════════════════════════════════════
#  边界场景测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """测试空字符串、空列表、无敏感信息等边界场景。"""

    def test_empty_string(self):
        """空字符串原样返回。"""
        s = PromptSanitizer()
        assert s.sanitize("") == ""
        assert s.get_redaction_log() == []

    def test_empty_messages_list(self):
        """空 messages 列表返回空列表。"""
        s = PromptSanitizer()
        assert s.sanitize_messages([]) == []

    def test_no_sensitive_info(self):
        """无敏感信息的文本原样返回。"""
        s = PromptSanitizer()
        text = "This is a normal message with no sensitive data at all."
        result = s.sanitize(text)
        assert result == text
        assert s.get_redaction_log() == []

    def test_only_sensitive_info(self):
        """文本完全由敏感信息组成。"""
        s = PromptSanitizer()
        text = "sk-abcdefghijklmnopqrstuvwxyz12345678901234"
        result = s.sanitize(text)
        assert result == "[REDACTED]"

    def test_multiple_same_type(self):
        """文本中包含多个同类型敏感信息。"""
        s = PromptSanitizer()
        text = "keys: sk-abcdefghijklmnopqrstuvwxyz1234 and sk-1234567890abcdefghijklmnop"
        result = s.sanitize(text)
        assert "sk-" not in result
        assert result.count("[REDACTED]") == 2


# ═══════════════════════════════════════════════════════════════
#  OmniRouteAdapter 集成测试
# ═══════════════════════════════════════════════════════════════


class TestOmniRouteIntegration:
    """测试 PromptSanitizer 与 OmniRouteAdapter 的集成。"""

    def test_adapter_accepts_sanitizer(self):
        """OmniRouteAdapter 构造函数应接受 sanitizer 参数。"""
        sanitizer = PromptSanitizer()
        adapter = OmniRouteAdapter(sanitizer=sanitizer)
        assert adapter.sanitizer is sanitizer

    def test_adapter_default_no_sanitizer(self):
        """默认 sanitizer 为 None。"""
        adapter = OmniRouteAdapter()
        assert adapter.sanitizer is None

    def test_factory_creates_with_sanitizer(self):
        """工厂函数应支持 sanitizer 参数透传。"""
        from suyi.llm import create_llm

        sanitizer = PromptSanitizer()
        adapter = create_llm("omniroute", sanitizer=sanitizer)
        assert isinstance(adapter, OmniRouteAdapter)
        assert adapter.sanitizer is sanitizer

    async def test_chat_sanitizes_messages(self):
        """chat() 应在发送前清洗 messages。"""
        from unittest.mock import AsyncMock, MagicMock, patch

        sanitizer = PromptSanitizer()
        adapter = OmniRouteAdapter(sanitizer=sanitizer)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        messages = [
            {"role": "user", "content": "My key is sk-abcdefghijklmnopqrstuvwxyz1234"},
        ]

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=messages,
                tools=[],
                system_prompt="",
            )

        # 验证响应正常
        assert response.content == "Hello!"
        # 验证发送的请求体中不包含敏感信息
        # system_prompt="" 时不会添加 system message，所以 user message 在 index 0
        sent_body = mock_client.post.call_args[1]["json"]
        sent_content = sent_body["messages"][0]["content"]
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in sent_content
        assert "[REDACTED]" in sent_content

    async def test_chat_without_sanitizer_unchanged(self):
        """无 sanitizer 时 messages 不被清洗。"""
        from unittest.mock import AsyncMock, MagicMock, patch

        adapter = OmniRouteAdapter()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        sensitive = "sk-abcdefghijklmnopqrstuvwxyz1234"
        messages = [{"role": "user", "content": f"My key is {sensitive}"}]

        with patch.object(adapter, "_get_client", return_value=mock_client):
            await adapter.chat(
                messages=messages,
                tools=[],
                system_prompt="",
            )

        # 无 sanitizer 时，敏感信息原样发送
        # system_prompt="" 时不会添加 system message，所以 user message 在 index 0
        sent_body = mock_client.post.call_args[1]["json"]
        assert sensitive in sent_body["messages"][0]["content"]

    async def test_chat_sanitizes_system_prompt(self):
        """chat() 应同时清洗 system_prompt。"""
        from unittest.mock import AsyncMock, MagicMock, patch

        sanitizer = PromptSanitizer()
        adapter = OmniRouteAdapter(sanitizer=sanitizer)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            await adapter.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                system_prompt="Config: sk-abcdefghijklmnopqrstuvwxyz1234",
            )

        sent_body = mock_client.post.call_args[1]["json"]
        system_content = sent_body["messages"][0]["content"]
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in system_content
        assert "[REDACTED]" in system_content
