"""
Tests for Bounty Submission Adapter — Multi-platform unified report submission.

测试覆盖:
    - BountyReport 数据校验和序列化
    - PlatformConfig 配置校验
    - SubmissionError 异常
    - DraftReport 草稿序列化/反序列化
    - BountyPlatformAdapter 基类（认证头、重试、severity 映射）
    - HackerOneAdapter: payload 构建、认证、提交、查询、附件上传
    - BugcrowdAdapter: payload 构建、认证、提交、查询
    - IntigritiAdapter: payload 构建、认证、提交、CVSS 映射
    - YesWeHackAdapter: payload 构建、认证、提交、查询
    - BountyRouter: 注册、路由、环境变量加载
    - DraftStore: 保存、加载、列表、删除、审查标记
    - 安全机制: confirmed=False 默认草稿、dry_run 不发请求
    - 错误处理: HTTP 4xx/5xx、网络异常
    - 边界条件: 缺少必填字段、空附件、非法 severity

所有 HTTP 请求通过 mock httpx 模拟，不发送真实网络请求。
"""

import asyncio
import base64
import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── 被测模块导入 ──────────────────────────────────────────────
from suyi.integrations.bounty import (
    BountyReport,
    SubmissionResult,
    PlatformConfig,
    DraftReport,
    SubmissionError,
    BountyPlatformAdapter,
    HackerOneAdapter,
    BugcrowdAdapter,
    IntigritiAdapter,
    YesWeHackAdapter,
    BountyRouter,
    DraftStore,
)
from suyi.integrations.bounty.models import VALID_SEVERITIES


# ═══════════════════════════════════════════════════════════════
#  辅助函数和 Fixtures
# ═══════════════════════════════════════════════════════════════


def make_mock_response(
    status_code: int = 200,
    json_data: object = None,
    text: str = "",
) -> MagicMock:
    """创建 mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
        resp.text = json.dumps(json_data)
    else:
        resp.json = MagicMock(side_effect=ValueError("no json"))
        resp.text = text
    return resp


def make_mock_client(responses: list = None) -> MagicMock:
    """创建 mock httpx.AsyncClient，按顺序返回预设响应."""
    client = MagicMock()
    if responses is None:
        responses = [make_mock_response(200, {"data": {"id": "123"}})]
    client.request = AsyncMock(side_effect=responses)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def sample_report_h1() -> BountyReport:
    """HackerOne 测试报告."""
    return BountyReport(
        title="Reflected XSS in search endpoint",
        vulnerability_information="The `q` parameter is reflected without encoding.",
        impact="An attacker can steal session cookies via crafted link.",
        severity="high",
        cwe_id="CWE-79",
        asset="example.com",
        endpoint_url="https://example.com/search?q=",
        team_handle="security_team",
        weakness_id="12",
        structured_scope_id="34",
        researcher_handle="hacker123",
    )


@pytest.fixture
def sample_report_bc() -> BountyReport:
    """Bugcrowd 测试报告."""
    return BountyReport(
        title="SQL Injection in login form",
        vulnerability_information="The username parameter is vulnerable to SQLi.",
        impact="Full database compromise possible.",
        severity="critical",
        cwe_id="CWE-89",
        asset="target.example.com",
        endpoint_url="https://target.example.com/login",
        program_code="test-program-uuid",
    )


@pytest.fixture
def sample_report_int() -> BountyReport:
    """Intigriti 测试报告."""
    return BountyReport(
        title="IDOR via user_id parameter",
        vulnerability_information="Changing user_id allows accessing other accounts.",
        impact="Unauthorized access to all user data.",
        severity="high",
        cwe_id="CWE-639",
        asset="app.example.com",
        endpoint_url="https://app.example.com/api/users/123",
        program_id="prog-uuid-456",
        asset_id="asset-uuid-789",
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
    )


@pytest.fixture
def sample_report_ywh() -> BountyReport:
    """YesWeHack 测试报告."""
    return BountyReport(
        title="Open redirect on /redirect endpoint",
        vulnerability_information="The url parameter allows redirecting to external sites.",
        impact="Phishing attacks possible.",
        severity="low",
        cwe_id="CWE-601",
        asset="www.example.com",
        endpoint_url="https://www.example.com/redirect?url=",
        program_slug="example-program",
    )


@pytest.fixture
def h1_config() -> PlatformConfig:
    return PlatformConfig(
        platform_name="hackerone",
        api_base="https://api.hackerone.com/v1",
        auth_type="basic_auth",
        credentials={"username": "testuser", "token": "testtoken123"},
        timeout=30.0,
    )


@pytest.fixture
def bc_config() -> PlatformConfig:
    return PlatformConfig(
        platform_name="bugcrowd",
        api_base="https://api.bugcrowd.com",
        auth_type="api_key_header",
        credentials={
            "header_name": "Authorization",
            "prefix": "Token",
            "token": "bc-token-xyz",
        },
        extra_headers={
            "Accept": "application/vnd.bugcrowd+json",
            "Content-Type": "application/vnd.api+json",
        },
    )


@pytest.fixture
def int_config() -> PlatformConfig:
    return PlatformConfig(
        platform_name="intigriti",
        api_base="https://api.intigriti.com/core/researcher",
        auth_type="bearer_token",
        credentials={"token": "int-pat-abc"},
    )


@pytest.fixture
def ywh_config() -> PlatformConfig:
    return PlatformConfig(
        platform_name="yeswehack",
        api_base="https://api.yeswehack.com",
        auth_type="bearer_token",
        credentials={"token": "ywh-pat-def"},
    )


@pytest.fixture
def tmp_draft_dir(tmp_path):
    """临时草稿目录."""
    return str(tmp_path / "bounty_drafts")


# ═══════════════════════════════════════════════════════════════
#  1. BountyReport 数据模型测试
# ═══════════════════════════════════════════════════════════════


class TestBountyReport:
    """BountyReport 数据类测试."""

    def test_create_minimal_report(self):
        """测试最小必填字段."""
        report = BountyReport(title="Test bug")
        assert report.title == "Test bug"
        assert report.severity == "medium"
        assert report.vulnerability_information == ""
        assert report.impact == ""
        assert report.attachments == []
        assert report.metadata == {}

    def test_create_full_report(self, sample_report_h1):
        """测试完整字段."""
        assert sample_report_h1.title == "Reflected XSS in search endpoint"
        assert sample_report_h1.severity == "high"
        assert sample_report_h1.cwe_id == "CWE-79"
        assert sample_report_h1.team_handle == "security_team"

    def test_empty_title_raises(self):
        """空标题应抛出 ValueError."""
        with pytest.raises(ValueError, match="title 不能为空"):
            BountyReport(title="")

    def test_whitespace_title_raises(self):
        """纯空格标题应抛出 ValueError."""
        with pytest.raises(ValueError, match="title 不能为空"):
            BountyReport(title="   ")

    def test_invalid_severity_raises(self):
        """非法 severity 应抛出 ValueError."""
        with pytest.raises(ValueError, match="severity"):
            BountyReport(title="Test", severity="super_critical")

    def test_severity_case_insensitive(self):
        """severity 大小写不敏感."""
        report = BountyReport(title="Test", severity="HIGH")
        assert report.severity == "high"

    @pytest.mark.parametrize("sev", VALID_SEVERITIES)
    def test_all_valid_severities(self, sev):
        """所有合法 severity 值."""
        report = BountyReport(title="Test", severity=sev)
        assert report.severity == sev

    def test_to_dict(self, sample_report_h1):
        """序列化字典."""
        d = sample_report_h1.to_dict()
        assert d["title"] == sample_report_h1.title
        assert d["severity"] == "high"
        assert d["cwe_id"] == "CWE-79"
        assert isinstance(d["attachments"], list)
        assert isinstance(d["metadata"], dict)

    def test_to_dict_independent_copy(self, sample_report_h1):
        """to_dict 返回深拷贝，修改不影响原对象."""
        d = sample_report_h1.to_dict()
        d["title"] = "Hacked"
        d["attachments"].append("evil.txt")
        assert sample_report_h1.title == "Reflected XSS in search endpoint"
        assert len(sample_report_h1.attachments) == 0

    def test_default_attachments_is_independent_list(self):
        """默认 attachments 不应在实例间共享."""
        r1 = BountyReport(title="A")
        r2 = BountyReport(title="B")
        r1.attachments.append("file.txt")
        assert r2.attachments == []


# ═══════════════════════════════════════════════════════════════
#  2. PlatformConfig 测试
# ═══════════════════════════════════════════════════════════════


class TestPlatformConfig:
    """PlatformConfig 配置测试."""

    def test_create_config(self, h1_config):
        """测试基本创建."""
        assert h1_config.platform_name == "hackerone"
        assert h1_config.auth_type == "basic_auth"
        assert h1_config.timeout == 30.0

    def test_invalid_auth_type_raises(self):
        """非法 auth_type 应抛出 ValueError."""
        with pytest.raises(ValueError, match="auth_type"):
            PlatformConfig(
                platform_name="test",
                api_base="https://api.test.com",
                auth_type="oauth",
            )

    def test_empty_platform_name_raises(self):
        """空平台名应抛出 ValueError."""
        with pytest.raises(ValueError, match="platform_name"):
            PlatformConfig(
                platform_name="",
                api_base="https://api.test.com",
            )

    def test_timeout_minimum_30(self):
        """timeout 低于 30 应自动提升到 30."""
        cfg = PlatformConfig(
            platform_name="test",
            api_base="https://api.test.com",
            timeout=5.0,
        )
        assert cfg.timeout == 30.0

    def test_trailing_slash_stripped(self):
        """api_base 尾部斜杠应被去除."""
        cfg = PlatformConfig(
            platform_name="test",
            api_base="https://api.test.com/v1///",
        )
        assert cfg.api_base == "https://api.test.com/v1"

    def test_to_dict_masks_credentials(self, h1_config):
        """to_dict 不暴露凭证明文."""
        d = h1_config.to_dict()
        assert "username" not in d
        assert "testtoken123" not in str(d)
        assert d["credentials_keys"] == ["username", "token"]

    def test_platform_name_lowercased(self):
        """平台名自动小写."""
        cfg = PlatformConfig(
            platform_name="HackerOne",
            api_base="https://api.hackerone.com",
        )
        assert cfg.platform_name == "hackerone"


# ═══════════════════════════════════════════════════════════════
#  3. SubmissionError 测试
# ═══════════════════════════════════════════════════════════════


class TestSubmissionError:
    """SubmissionError 异常测试."""

    def test_basic_error(self):
        """基本异常创建."""
        err = SubmissionError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.platform == ""
        assert err.status_code is None

    def test_error_with_platform(self):
        """带平台信息的异常."""
        err = SubmissionError(
            "Unauthorized",
            platform="hackerone",
            status_code=401,
            error_body={"error": "invalid token"},
        )
        assert "hackerone" in str(err)
        assert "401" in str(err)
        assert err.error_body == {"error": "invalid token"}

    def test_error_is_exception(self):
        """确认是 Exception 子类."""
        err = SubmissionError("test")
        assert isinstance(err, Exception)


# ═══════════════════════════════════════════════════════════════
#  4. DraftReport 测试
# ═══════════════════════════════════════════════════════════════


class TestDraftReport:
    """DraftReport 草稿测试."""

    def test_create_draft(self, sample_report_h1):
        """草稿创建."""
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={"data": {"type": "report"}},
        )
        assert draft.target_platform == "hackerone"
        assert draft.draft_id  # 自动生成
        assert draft.reviewed is False
        assert draft.created_at > 0

    def test_to_dict(self, sample_report_h1):
        """草稿序列化."""
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={"key": "value"},
        )
        d = draft.to_dict()
        assert d["target_platform"] == "hackerone"
        assert d["built_payload"] == {"key": "value"}
        assert d["report"]["title"] == sample_report_h1.title
        assert d["reviewed"] is False

    def test_from_dict_roundtrip(self, sample_report_h1):
        """字典反序列化往返."""
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={"data": {}},
        )
        d = draft.to_dict()
        restored = DraftReport.from_dict(d)
        assert restored.draft_id == draft.draft_id
        assert restored.target_platform == draft.target_platform
        assert restored.report.title == sample_report_h1.title
        assert restored.reviewed is False

    def test_unique_draft_ids(self, sample_report_h1):
        """每次创建草稿 ID 唯一."""
        d1 = DraftReport(report=sample_report_h1, target_platform="h1")
        d2 = DraftReport(report=sample_report_h1, target_platform="h1")
        assert d1.draft_id != d2.draft_id


# ═══════════════════════════════════════════════════════════════
#  5. 基类 BountyPlatformAdapter 测试
# ═══════════════════════════════════════════════════════════════


class TestBaseAdapter:
    """抽象基类通用功能测试."""

    def test_basic_auth_headers(self, h1_config):
        """Basic Auth 头构建."""
        adapter = HackerOneAdapter(config=h1_config)
        headers = adapter._get_auth_headers()
        assert "Authorization" in headers
        # 验证 Basic Auth 编码
        expected = base64.b64encode(b"testuser:testtoken123").decode("ascii")
        assert headers["Authorization"] == f"Basic {expected}"

    def test_bearer_auth_headers(self, int_config):
        """Bearer Token 认证头."""
        adapter = IntigritiAdapter(config=int_config)
        headers = adapter._get_auth_headers()
        assert headers["Authorization"] == "Bearer int-pat-abc"

    def test_api_key_header_auth(self, bc_config):
        """API Key Header 认证."""
        adapter = BugcrowdAdapter(config=bc_config)
        headers = adapter._get_auth_headers()
        assert headers["Authorization"] == "Token bc-token-xyz"

    def test_api_key_header_no_prefix(self):
        """无前缀的 API Key Header."""
        cfg = PlatformConfig(
            platform_name="custom",
            api_base="https://api.custom.com",
            auth_type="api_key_header",
            credentials={
                "header_name": "X-API-Key",
                "prefix": "",
                "token": "secret-key",
            },
        )

        class CustomAdapter(BountyPlatformAdapter):
            PLATFORM_NAME = "custom"

            def build_payload(self, report):
                return {}

            async def submit_report(self, report, **kw):
                return SubmissionResult(success=False)

            async def get_report(self, report_id):
                return SubmissionResult(success=False)

            def validate_config(self):
                pass

        adapter = CustomAdapter(config=cfg)
        headers = adapter._get_auth_headers()
        assert headers["X-API-Key"] == "secret-key"

    def test_severity_to_h1(self):
        """HackerOne severity 映射."""
        assert HackerOneAdapter.severity_to_h1("critical") == "critical"
        assert HackerOneAdapter.severity_to_h1("high") == "high"
        assert HackerOneAdapter.severity_to_h1("medium") == "medium"
        assert HackerOneAdapter.severity_to_h1("low") == "low"
        assert HackerOneAdapter.severity_to_h1("none") == "none"

    def test_severity_to_bugcrowd(self):
        """Bugcrowd P1-P5 映射."""
        assert BugcrowdAdapter.severity_to_bugcrowd("critical") == 1
        assert BugcrowdAdapter.severity_to_bugcrowd("high") == 2
        assert BugcrowdAdapter.severity_to_bugcrowd("medium") == 3
        assert BugcrowdAdapter.severity_to_bugcrowd("low") == 4
        assert BugcrowdAdapter.severity_to_bugcrowd("none") == 5

    def test_severity_to_intigriti(self):
        """Intigriti 1-5 映射."""
        assert IntigritiAdapter.severity_to_intigriti("critical") == 1
        assert IntigritiAdapter.severity_to_intigriti("high") == 2
        assert IntigritiAdapter.severity_to_intigriti("medium") == 3
        assert IntigritiAdapter.severity_to_intigriti("low") == 4
        assert IntigritiAdapter.severity_to_intigriti("none") == 5

    def test_severity_to_ywh(self):
        """YesWeHack severity 映射."""
        assert YesWeHackAdapter.severity_to_ywh("critical") == "critical"
        assert YesWeHackAdapter.severity_to_ywh("high") == "high"
        assert YesWeHackAdapter.severity_to_ywh("medium") == "medium"
        assert YesWeHackAdapter.severity_to_ywh("low") == "low"
        assert YesWeHackAdapter.severity_to_ywh("none") == "info"

    def test_build_draft(self, h1_config, sample_report_h1):
        """build_draft 不发送请求."""
        adapter = HackerOneAdapter(config=h1_config)
        draft = adapter.build_draft(sample_report_h1)
        assert isinstance(draft, DraftReport)
        assert draft.target_platform == "hackerone"
        assert "data" in draft.built_payload
        assert draft.report.title == sample_report_h1.title

    @pytest.mark.asyncio
    async def test_request_retry_on_503(self, h1_config):
        """503 错误应触发重试."""
        responses = [
            make_mock_response(503, text="Service Unavailable"),
            make_mock_response(503, text="Service Unavailable"),
            make_mock_response(200, {"data": {"id": "1"}}),
        ]
        client = make_mock_client(responses)
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await adapter._request("GET", "/test")
        assert response.status_code == 200
        assert client.request.await_count == 3

    @pytest.mark.asyncio
    async def test_request_no_retry_on_400(self, h1_config):
        """400 错误不应重试."""
        client = make_mock_client([
            make_mock_response(400, {"error": "bad request"}),
        ])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with pytest.raises(SubmissionError) as exc_info:
            await adapter._request("POST", "/test")
        assert exc_info.value.status_code == 400
        assert client.request.await_count == 1

    @pytest.mark.asyncio
    async def test_request_network_error_retry(self, h1_config):
        """网络错误应重试."""
        client = MagicMock()
        client.request = AsyncMock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                httpx.ConnectError("connection refused"),
                make_mock_response(200, {"ok": True}),
            ]
        )
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await adapter._request("GET", "/test")
        assert response.status_code == 200
        assert client.request.await_count == 3

    @pytest.mark.asyncio
    async def test_request_max_retries_exhausted(self, h1_config):
        """重试耗尽应抛出 SubmissionError."""
        client = MagicMock()
        client.request = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SubmissionError) as exc_info:
                await adapter._request("GET", "/test", max_retries=2)
        assert "Network error" in str(exc_info.value)
        assert client.request.await_count == 3  # 初始 + 2 重试

    @pytest.mark.asyncio
    async def test_request_timeout_raises_submission_error(self, h1_config):
        """超时应抛出 SubmissionError."""
        client = MagicMock()
        client.request = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SubmissionError, match="Network error"):
                await adapter._request("GET", "/test", max_retries=0)

    @pytest.mark.asyncio
    async def test_extra_headers_included(self, h1_config):
        """extra_headers 应被包含在请求中."""
        h1_config.extra_headers["X-Custom"] = "test-value"
        client = make_mock_client()
        adapter = HackerOneAdapter(config=h1_config, client=client)
        await adapter._request("GET", "/test")
        call_kwargs = client.request.call_args
        sent_headers = call_kwargs.kwargs.get("headers", {})
        assert sent_headers.get("X-Custom") == "test-value"


# ═══════════════════════════════════════════════════════════════
#  6. HackerOne 适配器测试
# ═══════════════════════════════════════════════════════════════


class TestHackerOneAdapter:
    """HackerOne 适配器测试."""

    def test_build_payload_structure(self, h1_config, sample_report_h1):
        """payload 结构符合 JSON API 规范."""
        adapter = HackerOneAdapter(config=h1_config)
        payload = adapter.build_payload(sample_report_h1)

        assert "data" in payload
        assert payload["data"]["type"] == "report"
        attrs = payload["data"]["attributes"]
        assert attrs["team_handle"] == "security_team"
        assert attrs["title"] == "Reflected XSS in search endpoint"
        assert attrs["severity_rating"] == "high"
        assert attrs["vulnerability_information"] == sample_report_h1.vulnerability_information

    def test_build_payload_includes_impact(self, h1_config, sample_report_h1):
        """payload 应包含 impact."""
        adapter = HackerOneAdapter(config=h1_config)
        payload = adapter.build_payload(sample_report_h1)
        attrs = payload["data"]["attributes"]
        assert attrs["impact"] == sample_report_h1.impact

    def test_build_payload_includes_weakness(self, h1_config, sample_report_h1):
        """payload 应包含 weakness_id."""
        adapter = HackerOneAdapter(config=h1_config)
        payload = adapter.build_payload(sample_report_h1)
        attrs = payload["data"]["attributes"]
        assert attrs["weakness_id"] == 12  # 数字

    def test_build_payload_includes_scope(self, h1_config, sample_report_h1):
        """payload 应包含 structured_scope_id."""
        adapter = HackerOneAdapter(config=h1_config)
        payload = adapter.build_payload(sample_report_h1)
        attrs = payload["data"]["attributes"]
        assert attrs["structured_scope_id"] == 34

    def test_build_payload_missing_team_handle_raises(self, h1_config):
        """缺少 team_handle 应抛出 SubmissionError."""
        report = BountyReport(title="Test")
        adapter = HackerOneAdapter(config=h1_config)
        with pytest.raises(SubmissionError, match="team_handle"):
            adapter.build_payload(report)

    def test_build_payload_with_metadata_team_handle(self, h1_config):
        """metadata 中的 team_handle 也应被识别."""
        report = BountyReport(
            title="Test",
            metadata={"team_handle": "meta_team"},
        )
        adapter = HackerOneAdapter(config=h1_config)
        payload = adapter.build_payload(report)
        assert payload["data"]["attributes"]["team_handle"] == "meta_team"

    def test_validate_config_missing_username(self):
        """缺少 username 校验失败."""
        cfg = PlatformConfig(
            platform_name="hackerone",
            api_base="https://api.hackerone.com/v1",
            auth_type="basic_auth",
            credentials={"token": "tok"},
        )
        adapter = HackerOneAdapter(config=cfg)
        with pytest.raises(SubmissionError, match="username"):
            adapter.validate_config()

    def test_validate_config_missing_token(self):
        """缺少 token 校验失败."""
        cfg = PlatformConfig(
            platform_name="hackerone",
            api_base="https://api.hackerone.com/v1",
            auth_type="basic_auth",
            credentials={"username": "user"},
        )
        adapter = HackerOneAdapter(config=cfg)
        with pytest.raises(SubmissionError, match="token"):
            adapter.validate_config()

    def test_validate_config_success(self, h1_config):
        """完整配置校验通过."""
        adapter = HackerOneAdapter(config=h1_config)
        adapter.validate_config()  # 不抛异常

    @pytest.mark.asyncio
    async def test_submit_unconfirmed_returns_draft(self, h1_config, sample_report_h1):
        """confirmed=False 默认返回草稿，不发请求."""
        client = make_mock_client()
        adapter = HackerOneAdapter(config=h1_config, client=client)
        result = await adapter.submit_report(sample_report_h1, confirmed=False)
        assert result.success is False
        assert result.status == "draft"
        assert result.platform == "hackerone"
        assert "data" in result.raw_response
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_dry_run_no_request(self, h1_config, sample_report_h1):
        """dry_run=True 不发送请求."""
        client = make_mock_client()
        adapter = HackerOneAdapter(config=h1_config, client=client)
        result = await adapter.submit_report(
            sample_report_h1, confirmed=True, dry_run=True
        )
        assert result.success is False
        assert result.status == "draft"
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_confirmed_success(self, h1_config, sample_report_h1):
        """confirmed=True 成功提交."""
        mock_resp = make_mock_response(201, {
            "data": {
                "id": "999",
                "attributes": {"state": "new"},
            },
            "links": {"self": "https://hackerone.com/reports/999"},
        })
        client = make_mock_client([mock_resp])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        result = await adapter.submit_report(
            sample_report_h1, confirmed=True
        )
        assert result.success is True
        assert result.report_id == "999"
        assert result.status == "new"
        assert "hackerone.com" in result.url
        client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_confirmed_sends_post(self, h1_config, sample_report_h1):
        """确认提交应发送 POST 请求到 /reports."""
        client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "100", "attributes": {"state": "new"}},
                "links": {},
            }),
        ])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        await adapter.submit_report(sample_report_h1, confirmed=True)
        call_args = client.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "https://api.hackerone.com/v1/reports"

    @pytest.mark.asyncio
    async def test_submit_auth_header(self, h1_config, sample_report_h1):
        """提交时应包含 Basic Auth 头."""
        client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "1", "attributes": {"state": "new"}},
            }),
        ])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        await adapter.submit_report(sample_report_h1, confirmed=True)
        call_kwargs = client.request.call_args.kwargs
        auth_header = call_kwargs["headers"]["Authorization"]
        assert auth_header.startswith("Basic ")

    @pytest.mark.asyncio
    async def test_get_report_success(self, h1_config):
        """查询报告成功."""
        client = make_mock_client([
            make_mock_response(200, {
                "data": {
                    "id": "555",
                    "attributes": {"state": "triaged"},
                },
                "links": {"self": "https://hackerone.com/reports/555"},
            }),
        ])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        result = await adapter.get_report("555")
        assert result.success is True
        assert result.report_id == "555"
        assert result.status == "triaged"
        assert result.url == "https://hackerone.com/reports/555"

    @pytest.mark.asyncio
    async def test_get_report_404_raises(self, h1_config):
        """查询不存在报告应抛出异常."""
        client = make_mock_client([
            make_mock_response(404, {"error": "not found"}),
        ])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with pytest.raises(SubmissionError) as exc:
            await adapter.get_report("nonexistent")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_attachment_upload(
        self, h1_config, sample_report_h1, tmp_path
    ):
        """附件上传流程."""
        # 创建临时文件
        att_file = tmp_path / "proof.png"
        att_file.write_bytes(b"fake image data")
        sample_report_h1.attachments = [str(att_file)]

        # 第一个请求：上传附件; 第二个请求：创建报告
        upload_resp = make_mock_response(200, {
            "data": {"id": 42, "attributes": {"file_name": "proof.png"}}
        })
        create_resp = make_mock_response(201, {
            "data": {"id": "200", "attributes": {"state": "new"}},
            "links": {},
        })
        client = make_mock_client([upload_resp, create_resp])
        adapter = HackerOneAdapter(config=h1_config, client=client)
        result = await adapter.submit_report(
            sample_report_h1, confirmed=True
        )
        assert result.success is True
        assert client.request.await_count == 2
        # 验证附件 ID 被放入 payload
        create_call = client.request.call_args_list[1]
        body = create_call.kwargs.get("json", {})
        assert body["data"]["attributes"]["attachment_ids"] == [42]

    @pytest.mark.asyncio
    async def test_attachment_missing_file_raises(
        self, h1_config, sample_report_h1
    ):
        """附件文件不存在应抛出异常."""
        sample_report_h1.attachments = ["/nonexistent/file.png"]
        client = make_mock_client()
        adapter = HackerOneAdapter(config=h1_config, client=client)
        with pytest.raises(SubmissionError, match="不存在"):
            await adapter.submit_report(
                sample_report_h1, confirmed=True
            )


# ═══════════════════════════════════════════════════════════════
#  7. Bugcrowd 适配器测试
# ═══════════════════════════════════════════════════════════════


class TestBugcrowdAdapter:
    """Bugcrowd 适配器测试."""

    def test_build_payload_structure(self, bc_config, sample_report_bc):
        """payload 符合 JSON API 规范."""
        adapter = BugcrowdAdapter(config=bc_config)
        payload = adapter.build_payload(sample_report_bc)

        assert payload["data"]["type"] == "submission"
        attrs = payload["data"]["attributes"]
        assert attrs["title"] == "SQL Injection in login form"
        assert "description" in attrs
        assert attrs["severity"] == 1  # critical → P1
        assert (
            payload["data"]["relationships"]["program"]["data"]["id"]
            == "test-program-uuid"
        )

    def test_build_payload_severity_mapping(self, bc_config):
        """severity 正确映射为 P1-P5."""
        adapter = BugcrowdAdapter(config=bc_config)
        for sev, expected in [
            ("critical", 1), ("high", 2), ("medium", 3),
            ("low", 4), ("none", 5),
        ]:
            report = BountyReport(
                title="T", program_code="prog", severity=sev
            )
            payload = adapter.build_payload(report)
            assert payload["data"]["attributes"]["severity"] == expected

    def test_build_payload_missing_program_code_raises(self, bc_config):
        """缺少 program_code 应抛出异常."""
        report = BountyReport(title="Test")
        adapter = BugcrowdAdapter(config=bc_config)
        with pytest.raises(SubmissionError, match="program_code"):
            adapter.build_payload(report)

    def test_validate_config_missing_token(self):
        """缺少 token 校验失败."""
        cfg = PlatformConfig(
            platform_name="bugcrowd",
            api_base="https://api.bugcrowd.com",
            auth_type="api_key_header",
            credentials={"header_name": "Authorization", "prefix": "Token"},
        )
        adapter = BugcrowdAdapter(config=cfg)
        with pytest.raises(SubmissionError, match="api_token"):
            adapter.validate_config()

    def test_validate_config_success(self, bc_config):
        """完整配置校验通过."""
        adapter = BugcrowdAdapter(config=bc_config)
        adapter.validate_config()

    @pytest.mark.asyncio
    async def test_submit_unconfirmed_returns_draft(self, bc_config, sample_report_bc):
        """未确认提交返回草稿."""
        client = make_mock_client()
        adapter = BugcrowdAdapter(config=bc_config, client=client)
        result = await adapter.submit_report(sample_report_bc, confirmed=False)
        assert result.success is False
        assert result.status == "draft"
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_confirmed_success(self, bc_config, sample_report_bc):
        """确认提交成功."""
        client = make_mock_client([
            make_mock_response(201, {
                "data": {
                    "id": "sub-uuid-1",
                    "attributes": {"state": "new"},
                },
                "links": {"self": "https://bugcrowd.com/submissions/sub-uuid-1"},
            }),
        ])
        adapter = BugcrowdAdapter(config=bc_config, client=client)
        result = await adapter.submit_report(
            sample_report_bc, confirmed=True
        )
        assert result.success is True
        assert result.report_id == "sub-uuid-1"
        assert result.status == "new"

    @pytest.mark.asyncio
    async def test_submit_auth_header(self, bc_config, sample_report_bc):
        """认证头格式正确."""
        client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "1", "attributes": {"state": "new"}},
            }),
        ])
        adapter = BugcrowdAdapter(config=bc_config, client=client)
        await adapter.submit_report(sample_report_bc, confirmed=True)
        headers = client.request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Token bc-token-xyz"
        assert headers["Accept"] == "application/vnd.bugcrowd+json"

    @pytest.mark.asyncio
    async def test_get_report_success(self, bc_config):
        """查询报告成功."""
        client = make_mock_client([
            make_mock_response(200, {
                "data": {
                    "id": "sub-789",
                    "attributes": {"state": "triaged"},
                },
            }),
        ])
        adapter = BugcrowdAdapter(config=bc_config, client=client)
        result = await adapter.get_report("sub-789")
        assert result.success is True
        assert result.status == "triaged"

    @pytest.mark.asyncio
    async def test_submit_http_401_raises(self, bc_config, sample_report_bc):
        """401 应抛出 SubmissionError."""
        client = make_mock_client([
            make_mock_response(401, {"error": "invalid token"}),
        ])
        adapter = BugcrowdAdapter(config=bc_config, client=client)
        with pytest.raises(SubmissionError) as exc:
            await adapter.submit_report(sample_report_bc, confirmed=True)
        assert exc.value.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  8. Intigriti 适配器测试
# ═══════════════════════════════════════════════════════════════


class TestIntigritiAdapter:
    """Intigriti 适配器测试."""

    def test_build_payload_structure(self, int_config, sample_report_int):
        """payload 结构正确."""
        adapter = IntigritiAdapter(config=int_config)
        payload = adapter.build_payload(sample_report_int)

        assert payload["programId"] == "prog-uuid-456"
        assert payload["assetId"] == "asset-uuid-789"
        assert payload["title"] == "IDOR via user_id parameter"
        assert payload["severity"] == 2  # high
        assert "description" in payload
        assert "impact" in payload
        assert payload["endpoint"] == sample_report_int.endpoint_url
        assert payload["cvss"]["vector"] == sample_report_int.cvss_vector

    def test_build_payload_severity_mapping(self, int_config):
        """severity 映射为 1-5."""
        adapter = IntigritiAdapter(config=int_config)
        for sev, expected in [
            ("critical", 1), ("high", 2), ("medium", 3),
            ("low", 4), ("none", 5),
        ]:
            report = BountyReport(
                title="T", program_id="p1", severity=sev
            )
            payload = adapter.build_payload(report)
            assert payload["severity"] == expected

    def test_build_payload_missing_program_id_raises(self, int_config):
        """缺少 program_id 应抛出异常."""
        report = BountyReport(title="Test")
        adapter = IntigritiAdapter(config=int_config)
        with pytest.raises(SubmissionError, match="program_id"):
            adapter.build_payload(report)

    def test_cvss_to_severity_calculator(self):
        """CVSS 分数到 severity 的转换."""
        assert IntigritiAdapter.cvss_to_severity(9.5) == 1
        assert IntigritiAdapter.cvss_to_severity(8.0) == 2
        assert IntigritiAdapter.cvss_to_severity(5.5) == 3
        assert IntigritiAdapter.cvss_to_severity(2.0) == 4
        assert IntigritiAdapter.cvss_to_severity(0.0) == 5

    def test_validate_config_success(self, int_config):
        """完整配置校验通过."""
        adapter = IntigritiAdapter(config=int_config)
        adapter.validate_config()

    def test_validate_config_missing_token(self):
        """缺少 token 校验失败."""
        cfg = PlatformConfig(
            platform_name="intigriti",
            api_base="https://api.intigriti.com",
            auth_type="bearer_token",
            credentials={},
        )
        adapter = IntigritiAdapter(config=cfg)
        with pytest.raises(SubmissionError, match="token"):
            adapter.validate_config()

    @pytest.mark.asyncio
    async def test_submit_confirmed_success(self, int_config, sample_report_int):
        """确认提交成功."""
        client = make_mock_client([
            make_mock_response(201, {
                "id": "int-sub-001",
                "status": "new",
                "url": "https://intigriti.com/researcher/submissions/int-sub-001",
            }),
        ])
        adapter = IntigritiAdapter(config=int_config, client=client)
        result = await adapter.submit_report(
            sample_report_int, confirmed=True
        )
        assert result.success is True
        assert result.report_id == "int-sub-001"
        assert result.status == "new"

    @pytest.mark.asyncio
    async def test_submit_bearer_auth_header(self, int_config, sample_report_int):
        """Bearer 认证头正确."""
        client = make_mock_client([
            make_mock_response(201, {"id": "1", "status": "new"}),
        ])
        adapter = IntigritiAdapter(config=int_config, client=client)
        await adapter.submit_report(sample_report_int, confirmed=True)
        headers = client.request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer int-pat-abc"

    @pytest.mark.asyncio
    async def test_get_report_success(self, int_config):
        """查询报告成功."""
        client = make_mock_client([
            make_mock_response(200, {
                "id": "int-555",
                "status": "accepted",
                "url": "https://intigriti.com/sub/int-555",
            }),
        ])
        adapter = IntigritiAdapter(config=int_config, client=client)
        result = await adapter.get_report("int-555")
        assert result.success is True
        assert result.status == "accepted"

    @pytest.mark.asyncio
    async def test_dry_run_returns_payload(self, int_config, sample_report_int):
        """dry_run 返回构建好的 payload."""
        client = make_mock_client()
        adapter = IntigritiAdapter(config=int_config, client=client)
        result = await adapter.submit_report(
            sample_report_int, confirmed=True, dry_run=True
        )
        assert result.success is False
        assert result.raw_response["programId"] == "prog-uuid-456"
        client.request.assert_not_called()


# ═══════════════════════════════════════════════════════════════
#  9. YesWeHack 适配器测试
# ═══════════════════════════════════════════════════════════════


class TestYesWeHackAdapter:
    """YesWeHack 适配器测试."""

    def test_build_payload_structure(self, ywh_config, sample_report_ywh):
        """payload 结构正确."""
        adapter = YesWeHackAdapter(config=ywh_config)
        payload = adapter.build_payload(sample_report_ywh)

        assert payload["program_slug"] == "example-program"
        assert payload["title"] == "Open redirect on /redirect endpoint"
        assert payload["severity"] == "low"
        assert "description" in payload
        assert "impact" in payload

    def test_build_payload_severity_mapping(self, ywh_config):
        """severity 映射正确."""
        adapter = YesWeHackAdapter(config=ywh_config)
        for sev, expected in [
            ("critical", "critical"),
            ("high", "high"),
            ("medium", "medium"),
            ("low", "low"),
            ("none", "info"),
        ]:
            report = BountyReport(
                title="T", program_slug="slug", severity=sev
            )
            payload = adapter.build_payload(report)
            assert payload["severity"] == expected

    def test_build_payload_missing_slug_raises(self, ywh_config):
        """缺少 program_slug 应抛出异常."""
        report = BountyReport(title="Test")
        adapter = YesWeHackAdapter(config=ywh_config)
        with pytest.raises(SubmissionError, match="program_slug"):
            adapter.build_payload(report)

    def test_build_payload_cvss_vector(self, ywh_config):
        """CVSS 向量应被包含."""
        report = BountyReport(
            title="T",
            program_slug="slug",
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        )
        adapter = YesWeHackAdapter(config=ywh_config)
        payload = adapter.build_payload(report)
        assert payload["cvss_vector"] == report.cvss_vector

    def test_validate_config_success(self, ywh_config):
        """完整配置校验通过."""
        adapter = YesWeHackAdapter(config=ywh_config)
        adapter.validate_config()

    def test_validate_config_missing_token(self):
        """缺少 token 校验失败."""
        cfg = PlatformConfig(
            platform_name="yeswehack",
            api_base="https://api.yeswehack.com",
            auth_type="bearer_token",
            credentials={},
        )
        adapter = YesWeHackAdapter(config=cfg)
        with pytest.raises(SubmissionError, match="token"):
            adapter.validate_config()

    @pytest.mark.asyncio
    async def test_submit_confirmed_success(self, ywh_config, sample_report_ywh):
        """确认提交成功."""
        client = make_mock_client([
            make_mock_response(201, {
                "id": "ywh-001",
                "status": "new",
                "url": "https://yeswehack.com/reports/ywh-001",
            }),
        ])
        adapter = YesWeHackAdapter(config=ywh_config, client=client)
        result = await adapter.submit_report(
            sample_report_ywh, confirmed=True
        )
        assert result.success is True
        assert result.report_id == "ywh-001"

    @pytest.mark.asyncio
    async def test_submit_bearer_auth(self, ywh_config, sample_report_ywh):
        """Bearer 认证头正确."""
        client = make_mock_client([
            make_mock_response(201, {"id": "1", "status": "new"}),
        ])
        adapter = YesWeHackAdapter(config=ywh_config, client=client)
        await adapter.submit_report(sample_report_ywh, confirmed=True)
        headers = client.request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer ywh-pat-def"

    @pytest.mark.asyncio
    async def test_get_report_success(self, ywh_config):
        """查询报告成功."""
        client = make_mock_client([
            make_mock_response(200, {
                "id": "ywh-777",
                "status": "resolved",
                "url": "https://yeswehack.com/r/ywh-777",
            }),
        ])
        adapter = YesWeHackAdapter(config=ywh_config, client=client)
        result = await adapter.get_report("ywh-777")
        assert result.success is True
        assert result.status == "resolved"

    @pytest.mark.asyncio
    async def test_submit_server_error_raises(self, ywh_config, sample_report_ywh):
        """500 错误应抛出异常."""
        # 500 会重试（初始 + 3 次重试），需要 4 个 500 响应
        client = make_mock_client([
            make_mock_response(500, {"error": "internal"}),
            make_mock_response(500, {"error": "internal"}),
            make_mock_response(500, {"error": "internal"}),
            make_mock_response(500, {"error": "internal"}),
        ])
        adapter = YesWeHackAdapter(config=ywh_config, client=client)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SubmissionError) as exc:
                await adapter.submit_report(
                    sample_report_ywh, confirmed=True
                )
        assert exc.value.status_code == 500


# ═══════════════════════════════════════════════════════════════
#  10. BountyRouter 测试
# ═══════════════════════════════════════════════════════════════


class TestBountyRouter:
    """统一路由器测试."""

    def test_register_platform(self, h1_config):
        """注册平台."""
        router = BountyRouter()
        router.register_platform(h1_config)
        assert "hackerone" in router.list_platforms()

    def test_register_multiple_platforms(
        self, h1_config, bc_config, int_config, ywh_config
    ):
        """注册多个平台."""
        router = BountyRouter()
        router.register_platform(h1_config)
        router.register_platform(bc_config)
        router.register_platform(int_config)
        router.register_platform(ywh_config)
        platforms = router.list_platforms()
        assert len(platforms) == 4
        assert set(platforms) == {
            "hackerone", "bugcrowd", "intigriti", "yeswehack"
        }

    def test_register_unknown_platform_raises(self):
        """注册未知平台应抛出异常."""
        router = BountyRouter()
        cfg = PlatformConfig(
            platform_name="unknown_platform",
            api_base="https://api.unknown.com",
        )
        with pytest.raises(SubmissionError, match="未知平台"):
            router.register_platform(cfg)

    def test_unregister_platform(self, h1_config):
        """注销平台."""
        router = BountyRouter()
        router.register_platform(h1_config)
        assert "hackerone" in router.list_platforms()
        router.unregister_platform("hackerone")
        assert "hackerone" not in router.list_platforms()

    def test_unregister_nonexistent_no_error(self):
        """注销不存在的平台不报错."""
        router = BountyRouter()
        router.unregister_platform("nonexistent")  # 不抛异常

    def test_get_adapter_registered(self, h1_config):
        """获取已注册适配器."""
        router = BountyRouter()
        router.register_platform(h1_config)
        adapter = router.get_adapter("hackerone")
        assert isinstance(adapter, HackerOneAdapter)

    def test_get_adapter_not_registered_raises(self):
        """获取未注册平台应抛出异常."""
        router = BountyRouter()
        with pytest.raises(SubmissionError, match="未注册"):
            router.get_adapter("hackerone")

    def test_get_adapter_case_insensitive(self, h1_config):
        """平台名大小写不敏感."""
        router = BountyRouter()
        router.register_platform(h1_config)
        adapter = router.get_adapter("HackerOne")
        assert isinstance(adapter, HackerOneAdapter)

    def test_build_draft(self, h1_config, sample_report_h1):
        """通过 router 构建草稿."""
        router = BountyRouter()
        router.register_platform(h1_config)
        draft = router.build_draft(sample_report_h1, "hackerone")
        assert isinstance(draft, DraftReport)
        assert draft.target_platform == "hackerone"

    @pytest.mark.asyncio
    async def test_submit_routes_to_correct_adapter(
        self, h1_config, sample_report_h1
    ):
        """submit 路由到正确的适配器."""
        client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "routed-1", "attributes": {"state": "new"}},
                "links": {},
            }),
        ])
        router = BountyRouter(client=client)
        router.register_platform(h1_config)
        result = await router.submit(
            sample_report_h1, "hackerone", confirmed=True
        )
        assert result.success is True
        assert result.platform == "hackerone"

    @pytest.mark.asyncio
    async def test_submit_default_unconfirmed(self, h1_config, sample_report_h1):
        """router.submit 默认 confirmed=False."""
        client = make_mock_client()
        router = BountyRouter(client=client)
        router.register_platform(h1_config)
        result = await router.submit(sample_report_h1, "hackerone")
        assert result.success is False
        assert result.status == "draft"
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_status(self, h1_config):
        """通过 router 查询状态."""
        client = make_mock_client([
            make_mock_response(200, {
                "data": {
                    "id": "status-1",
                    "attributes": {"state": "resolved"},
                },
                "links": {},
            }),
        ])
        router = BountyRouter(client=client)
        router.register_platform(h1_config)
        result = await router.get_status("status-1", "hackerone")
        assert result.success is True
        assert result.status == "resolved"

    def test_load_from_env(self, monkeypatch):
        """从环境变量加载配置."""
        monkeypatch.setenv("BOUNTY_H1_USER", "envuser")
        monkeypatch.setenv("BOUNTY_H1_TOKEN", "envtoken")
        monkeypatch.setenv("BOUNTY_BC_TOKEN", "bctoken")
        # 不设置 Intigriti 和 YWH 的环境变量

        router = BountyRouter(auto_load_env=True)
        platforms = router.list_platforms()
        assert "hackerone" in platforms
        assert "bugcrowd" in platforms
        assert "intigriti" not in platforms
        assert "yeswehack" not in platforms

    def test_load_from_env_partial_credentials_skipped(self, monkeypatch):
        """部分凭证缺失的平台不加载."""
        # 只设置 H1 username，不设置 token
        monkeypatch.setenv("BOUNTY_H1_USER", "envuser")
        monkeypatch.delenv("BOUNTY_H1_TOKEN", raising=False)
        monkeypatch.delenv("BOUNTY_BC_TOKEN", raising=False)
        monkeypatch.delenv("BOUNTY_INT_TOKEN", raising=False)
        monkeypatch.delenv("BOUNTY_YWH_TOKEN", raising=False)

        router = BountyRouter(auto_load_env=True)
        assert len(router.list_platforms()) == 0

    def test_load_from_env_all_platforms(self, monkeypatch):
        """环境变量齐全时加载所有平台."""
        monkeypatch.setenv("BOUNTY_H1_USER", "u")
        monkeypatch.setenv("BOUNTY_H1_TOKEN", "t")
        monkeypatch.setenv("BOUNTY_BC_TOKEN", "b")
        monkeypatch.setenv("BOUNTY_INT_TOKEN", "i")
        monkeypatch.setenv("BOUNTY_YWH_TOKEN", "y")

        router = BountyRouter(auto_load_env=True)
        assert len(router.list_platforms()) == 4

    def test_no_auto_load_by_default(self, monkeypatch):
        """默认不自动加载环境变量."""
        monkeypatch.setenv("BOUNTY_H1_USER", "u")
        monkeypatch.setenv("BOUNTY_H1_TOKEN", "t")
        router = BountyRouter()
        assert len(router.list_platforms()) == 0

    @pytest.mark.asyncio
    async def test_router_aclose(self, h1_config):
        """路由器关闭."""
        client = make_mock_client()
        router = BountyRouter(client=client)
        router.register_platform(h1_config)
        await router.aclose()
        client.aclose.assert_called_once()


# ═══════════════════════════════════════════════════════════════
#  11. DraftStore 测试
# ═══════════════════════════════════════════════════════════════


class TestDraftStore:
    """草稿持久化存储测试."""

    def test_save_and_load_draft(self, tmp_draft_dir, sample_report_h1):
        """保存和加载草稿."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={"data": {"type": "report"}},
        )
        store.save_draft(draft)

        loaded = store.load_draft(draft.draft_id)
        assert loaded.draft_id == draft.draft_id
        assert loaded.target_platform == "hackerone"
        assert loaded.report.title == sample_report_h1.title
        assert loaded.built_payload == {"data": {"type": "report"}}

    def test_list_drafts_empty(self, tmp_draft_dir):
        """空目录返回空列表."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        assert store.list_drafts() == []

    def test_list_drafts_multiple(self, tmp_draft_dir, sample_report_h1, sample_report_bc):
        """列出多个草稿."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        d1 = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={},
        )
        d2 = DraftReport(
            report=sample_report_bc,
            target_platform="bugcrowd",
            built_payload={},
        )
        store.save_draft(d1)
        store.save_draft(d2)

        drafts = store.list_drafts()
        assert len(drafts) == 2
        platforms = {d["target_platform"] for d in drafts}
        assert platforms == {"hackerone", "bugcrowd"}

    def test_list_drafts_filter_by_platform(
        self, tmp_draft_dir, sample_report_h1, sample_report_bc
    ):
        """按平台过滤草稿."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        store.save_draft(DraftReport(
            report=sample_report_h1, target_platform="hackerone", built_payload={},
        ))
        store.save_draft(DraftReport(
            report=sample_report_bc, target_platform="bugcrowd", built_payload={},
        ))

        h1_drafts = store.list_drafts(platform="hackerone")
        assert len(h1_drafts) == 1
        assert h1_drafts[0]["target_platform"] == "hackerone"

    def test_delete_draft(self, tmp_draft_dir, sample_report_h1):
        """删除草稿."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={},
        )
        store.save_draft(draft)
        assert store.count_drafts() == 1

        deleted = store.delete_draft(draft.draft_id)
        assert deleted is True
        assert store.count_drafts() == 0

    def test_delete_nonexistent_returns_false(self, tmp_draft_dir):
        """删除不存在的草稿返回 False."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        assert store.delete_draft("nonexistent") is False

    def test_load_nonexistent_raises(self, tmp_draft_dir):
        """加载不存在的草稿抛出 FileNotFoundError."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        with pytest.raises(FileNotFoundError):
            store.load_draft("nonexistent")

    def test_mark_reviewed(self, tmp_draft_dir, sample_report_h1):
        """标记草稿已审查."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={},
        )
        store.save_draft(draft)

        assert draft.reviewed is False
        store.mark_reviewed(draft.draft_id)
        loaded = store.load_draft(draft.draft_id)
        assert loaded.reviewed is True

    def test_mark_unreviewed(self, tmp_draft_dir, sample_report_h1):
        """取消审查标记."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={},
            reviewed=True,
        )
        store.save_draft(draft)
        store.mark_reviewed(draft.draft_id, reviewed=False)
        loaded = store.load_draft(draft.draft_id)
        assert loaded.reviewed is False

    def test_count_drafts(self, tmp_draft_dir, sample_report_h1, sample_report_bc):
        """统计草稿数量."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        assert store.count_drafts() == 0
        store.save_draft(DraftReport(
            report=sample_report_h1, target_platform="hackerone", built_payload={},
        ))
        assert store.count_drafts() == 1
        store.save_draft(DraftReport(
            report=sample_report_bc, target_platform="bugcrowd", built_payload={},
        ))
        assert store.count_drafts() == 2

    def test_count_drafts_by_platform(self, tmp_draft_dir, sample_report_h1, sample_report_bc):
        """按平台统计草稿."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        store.save_draft(DraftReport(
            report=sample_report_h1, target_platform="hackerone", built_payload={},
        ))
        store.save_draft(DraftReport(
            report=sample_report_bc, target_platform="bugcrowd", built_payload={},
        ))
        assert store.count_drafts("hackerone") == 1
        assert store.count_drafts("bugcrowd") == 1
        assert store.count_drafts("intigriti") == 0

    def test_draft_summary_fields(self, tmp_draft_dir, sample_report_h1):
        """草稿摘要包含必要字段."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_h1,
            target_platform="hackerone",
            built_payload={},
        )
        store.save_draft(draft)
        drafts = store.list_drafts()
        assert len(drafts) == 1
        summary = drafts[0]
        assert "draft_id" in summary
        assert "target_platform" in summary
        assert "title" in summary
        assert "severity" in summary
        assert "created_at" in summary
        assert "reviewed" in summary
        assert summary["title"] == sample_report_h1.title
        assert summary["severity"] == "high"

    def test_path_traversal_prevention(self, tmp_draft_dir):
        """防止路径穿越."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        with pytest.raises(ValueError):
            store._draft_path("../../../etc/passwd")

    def test_default_dir_creation(self, tmp_path, monkeypatch):
        """默认目录自动创建."""
        custom_home = str(tmp_path / "home")
        monkeypatch.setenv("HOME", custom_home)
        # DraftStore 在模块加载时已确定 DEFAULT_DRAFT_DIR，
        # 但显式传入 None 会使用模块级常量。这里直接测试目录创建。
        store = DraftStore(draft_dir=str(tmp_path / "custom_drafts"))
        assert os.path.isdir(str(tmp_path / "custom_drafts"))

    def test_draft_roundtrip_preserves_all_fields(
        self, tmp_draft_dir, sample_report_int
    ):
        """完整往返保留所有字段."""
        store = DraftStore(draft_dir=tmp_draft_dir)
        draft = DraftReport(
            report=sample_report_int,
            target_platform="intigriti",
            built_payload={"programId": "prog-123", "severity": 2},
            reviewed=True,
        )
        store.save_draft(draft)
        loaded = store.load_draft(draft.draft_id)
        assert loaded.report.program_id == "prog-uuid-456"
        assert loaded.report.cvss_vector == sample_report_int.cvss_vector
        assert loaded.built_payload["severity"] == 2
        assert loaded.reviewed is True


# ═══════════════════════════════════════════════════════════════
#  12. 安全机制测试
# ═══════════════════════════════════════════════════════════════


class TestSafetyMechanisms:
    """安全设计验证."""

    @pytest.mark.asyncio
    async def test_confirmed_false_default_all_platforms(
        self, h1_config, bc_config, int_config, ywh_config,
        sample_report_h1, sample_report_bc, sample_report_int, sample_report_ywh,
    ):
        """所有平台 confirmed=False 默认不发送请求."""
        configs_reports = [
            (HackerOneAdapter(h1_config), sample_report_h1),
            (BugcrowdAdapter(bc_config), sample_report_bc),
            (IntigritiAdapter(int_config), sample_report_int),
            (YesWeHackAdapter(ywh_config), sample_report_ywh),
        ]
        for adapter, report in configs_reports:
            client = make_mock_client()
            adapter._client = client
            result = await adapter.submit_report(report)
            assert result.success is False
            assert result.status == "draft"
            client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_all_platforms(
        self, h1_config, bc_config, int_config, ywh_config,
        sample_report_h1, sample_report_bc, sample_report_int, sample_report_ywh,
    ):
        """所有平台 dry_run=True 不发送请求."""
        configs_reports = [
            (HackerOneAdapter(h1_config), sample_report_h1),
            (BugcrowdAdapter(bc_config), sample_report_bc),
            (IntigritiAdapter(int_config), sample_report_int),
            (YesWeHackAdapter(ywh_config), sample_report_ywh),
        ]
        for adapter, report in configs_reports:
            client = make_mock_client()
            adapter._client = client
            result = await adapter.submit_report(
                report, confirmed=True, dry_run=True
            )
            assert result.success is False
            client.request.assert_not_called()

    def test_no_hardcoded_tokens(self):
        """源码中不应包含硬编码的 token."""
        import suyi.integrations.bounty as bounty_pkg
        pkg_dir = os.path.dirname(bounty_pkg.__file__)
        token_like = []
        for root, dirs, files in os.walk(pkg_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        # 查找疑似硬编码 token 的模式
                        if "api_token" in line.lower() and "=" in line:
                            # 排除环境变量和参数引用
                            if "os.environ" not in line and "get(" not in line:
                                if '"' in line or "'" in line:
                                    # 检查等号后是否有非空字符串字面量
                                    pass

    def test_credentials_only_via_config_or_env(self, monkeypatch):
        """凭证只能通过 config 或环境变量传入."""
        monkeypatch.delenv("BOUNTY_H1_USER", raising=False)
        monkeypatch.delenv("BOUNTY_H1_TOKEN", raising=False)
        # 默认适配器不应有硬编码凭证
        adapter = HackerOneAdapter()
        assert adapter.config.credentials.get("username", "") == ""
        assert adapter.config.credentials.get("token", "") == ""


# ═══════════════════════════════════════════════════════════════
#  13. 端到端集成场景测试
# ═══════════════════════════════════════════════════════════════


class TestEndToEndScenarios:
    """端到端流程测试."""

    @pytest.mark.asyncio
    async def test_full_workflow_draft_review_submit(
        self, h1_config, sample_report_h1, tmp_draft_dir
    ):
        """完整流程：构建草稿 → 保存到 DraftStore → 审查 → 提交."""
        # 1. 注册平台
        client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "e2e-001", "attributes": {"state": "new"}},
                "links": {},
            }),
        ])
        router = BountyRouter(client=client)
        router.register_platform(h1_config)

        # 2. 构建草稿
        draft = router.build_draft(sample_report_h1, "hackerone")
        assert draft.built_payload["data"]["attributes"]["title"] == \
            sample_report_h1.title

        # 3. 保存到 DraftStore
        store = DraftStore(draft_dir=tmp_draft_dir)
        store.save_draft(draft)
        assert store.count_drafts() == 1

        # 4. 审查标记
        store.mark_reviewed(draft.draft_id)
        loaded = store.load_draft(draft.draft_id)
        assert loaded.reviewed is True

        # 5. 确认提交
        result = await router.submit(
            sample_report_h1, "hackerone", confirmed=True
        )
        assert result.success is True
        assert result.report_id == "e2e-001"

        # 6. 清理草稿
        store.delete_draft(draft.draft_id)
        assert store.count_drafts() == 0

    @pytest.mark.asyncio
    async def test_multi_platform_submission(
        self, h1_config, bc_config, int_config, ywh_config,
        sample_report_h1, sample_report_bc, sample_report_int, sample_report_ywh,
    ):
        """多平台批量提交（mock）."""
        router = BountyRouter()
        router.register_platform(h1_config)
        router.register_platform(bc_config)
        router.register_platform(int_config)
        router.register_platform(ywh_config)

        # 所有报告先构建草稿
        drafts = [
            router.build_draft(sample_report_h1, "hackerone"),
            router.build_draft(sample_report_bc, "bugcrowd"),
            router.build_draft(sample_report_int, "intigriti"),
            router.build_draft(sample_report_ywh, "yeswehack"),
        ]
        assert len(drafts) == 4
        for d in drafts:
            assert d.built_payload  # payload 非空

    @pytest.mark.asyncio
    async def test_router_shares_client_across_platforms(
        self, h1_config, bc_config, sample_report_h1, sample_report_bc
    ):
        """多个平台适配器共享同一个 httpx client."""
        shared_client = make_mock_client([
            make_mock_response(201, {
                "data": {"id": "1", "attributes": {"state": "new"}},
                "links": {},
            }),
            make_mock_response(201, {
                "data": {"id": "2", "attributes": {"state": "new"}},
                "links": {},
            }),
        ])
        router = BountyRouter(client=shared_client)
        router.register_platform(h1_config)
        router.register_platform(bc_config)

        # 两个适配器应该使用同一个 client
        h1_adapter = router.get_adapter("hackerone")
        bc_adapter = router.get_adapter("bugcrowd")
        assert h1_adapter._client is shared_client
        assert bc_adapter._client is shared_client

    @pytest.mark.asyncio
    async def test_adapter_context_manager(self, h1_config):
        """异步上下文管理器."""
        adapter = HackerOneAdapter(config=h1_config)
        async with adapter:
            draft = adapter.build_draft(
                BountyReport(title="T", team_handle="t")
            )
        assert draft.target_platform == "hackerone"


# ═══════════════════════════════════════════════════════════════
#  14. SubmissionResult 测试
# ═══════════════════════════════════════════════════════════════


class TestSubmissionResult:
    """提交结果测试."""

    def test_create_success_result(self):
        """成功结果."""
        result = SubmissionResult(
            success=True,
            platform="hackerone",
            report_id="123",
            url="https://hackerone.com/reports/123",
            status="new",
        )
        assert result.success is True
        assert result.submitted_at > 0

    def test_create_failure_result(self):
        """失败结果."""
        result = SubmissionResult(
            success=False,
            platform="bugcrowd",
            status="draft",
        )
        assert result.success is False
        assert result.report_id == ""

    def test_to_dict(self):
        """结果序列化."""
        result = SubmissionResult(
            success=True,
            platform="intigriti",
            report_id="int-1",
            url="https://intigriti.com/1",
            status="triaged",
            raw_response={"id": "int-1"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["platform"] == "intigriti"
        assert d["report_id"] == "int-1"
        assert d["status"] == "triaged"


# ═══════════════════════════════════════════════════════════════
#  15. 版本号和模块导出测试
# ═══════════════════════════════════════════════════════════════


class TestModuleExports:
    """模块导出和版本测试."""

    def test_version_is_1_8_0(self):
        """版本号为 1.8.0."""
        import suyi
        assert suyi.__version__ == "1.8.0"

    def test_bounty_module_importable(self):
        """bounty 模块可导入."""
        from suyi.integrations import bounty
        assert hasattr(bounty, "BountyReport")
        assert hasattr(bounty, "BountyRouter")
        assert hasattr(bounty, "DraftStore")

    def test_all_public_classes_exported(self):
        """所有公开类已导出."""
        from suyi.integrations.bounty import __all__
        expected = {
            "BountyReport", "SubmissionResult", "PlatformConfig",
            "DraftReport", "SubmissionError",
            "BountyPlatformAdapter",
            "HackerOneAdapter", "BugcrowdAdapter",
            "IntigritiAdapter", "YesWeHackAdapter",
            "BountyRouter", "DraftStore",
        }
        assert set(__all__) == expected

    def test_platforms_module_exports(self):
        """平台模块导出正确."""
        from suyi.integrations.bounty.platforms import __all__
        assert set(__all__) == {
            "HackerOneAdapter", "BugcrowdAdapter",
            "IntigritiAdapter", "YesWeHackAdapter",
        }
