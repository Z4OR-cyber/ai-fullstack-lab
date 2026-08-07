"""
Tests for Suyi Human-in-the-loop — manager, policy, middleware.

Covers:
    - ConfirmationRequest: creation, status, expiry
    - HITLManager: create/approve/reject/expire/batch/callbacks/stats
    - HITLPolicy: tool name, parameter content, risk score, learning mode
    - HITLMiddleware: before_tool_call, block, confirm, integration
"""

import time

import pytest

from suyi.hitl import (
    HITLManager,
    ConfirmationRequest,
    ConfirmationStatus,
    HITLPolicy,
    RiskScore,
    HITLMiddleware,
)
from suyi.hitl.manager import RiskLevel
from suyi.hitl.policy import PolicyDecision, LearningRecord
from suyi.core.loop import LoopState


# ═══════════════════════════════════════════════════════════════
#  ConfirmationRequest
# ═══════════════════════════════════════════════════════════════


class TestConfirmationRequest:
    """Test the ConfirmationRequest dataclass."""

    def test_defaults(self):
        req = ConfirmationRequest(
            operation="bash:ls",
            arguments={"command": "ls"},
        )
        assert req.id  # auto-generated
        assert req.operation == "bash:ls"
        assert req.arguments == {"command": "ls"}
        assert req.risk_level == RiskLevel.MEDIUM
        assert req.status == ConfirmationStatus.PENDING
        assert req.timeout == 300.0
        assert req.created_at > 0

    def test_custom_fields(self):
        req = ConfirmationRequest(
            id="custom-id",
            operation="bash:rm",
            arguments={"command": "rm -rf /tmp"},
            risk_level=RiskLevel.HIGH,
            description="Delete temp directory",
            timeout=60.0,
        )
        assert req.id == "custom-id"
        assert req.risk_level == RiskLevel.HIGH
        assert req.description == "Delete temp directory"
        assert req.timeout == 60.0

    def test_is_pending(self):
        req = ConfirmationRequest(operation="test")
        assert req.is_pending is True
        req.status = ConfirmationStatus.APPROVED
        assert req.is_pending is False

    def test_is_expired_not_pending(self):
        req = ConfirmationRequest(operation="test")
        req.status = ConfirmationStatus.APPROVED
        assert req.is_expired is False

    def test_is_expired_pending_timeout(self):
        req = ConfirmationRequest(
            operation="test",
            timeout=1.0,
            created_at=time.time() - 10,
        )
        assert req.is_expired is True

    def test_is_expired_pending_within_timeout(self):
        req = ConfirmationRequest(
            operation="test",
            timeout=300.0,
            created_at=time.time(),
        )
        assert req.is_expired is False

    def test_to_dict(self):
        req = ConfirmationRequest(
            operation="bash:ls",
            arguments={"command": "ls"},
            risk_level=RiskLevel.LOW,
        )
        d = req.to_dict()
        assert d["operation"] == "bash:ls"
        assert d["arguments"] == {"command": "ls"}
        assert d["risk_level"] == RiskLevel.LOW
        assert d["status"] == ConfirmationStatus.PENDING


# ═══════════════════════════════════════════════════════════════
#  HITLManager
# ═══════════════════════════════════════════════════════════════


class TestHITLManager:
    """Test the HITLManager class."""

    def test_defaults(self):
        mgr = HITLManager()
        assert mgr.default_timeout == 300.0
        assert mgr.auto_expire is True
        assert mgr.batch_threshold == RiskLevel.LOW

    def test_create_request(self):
        mgr = HITLManager()
        req = mgr.create_request(
            operation="bash:ls",
            arguments={"command": "ls"},
            risk_level=RiskLevel.LOW,
            description="List directory",
        )
        assert req.id
        assert req.is_pending
        assert req.operation == "bash:ls"

    def test_create_request_default_timeout(self):
        mgr = HITLManager(default_timeout=120.0)
        req = mgr.create_request(operation="test")
        assert req.timeout == 120.0

    def test_create_request_custom_timeout(self):
        mgr = HITLManager(default_timeout=120.0)
        req = mgr.create_request(operation="test", timeout=60.0)
        assert req.timeout == 60.0

    def test_approve(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        assert mgr.approve(req.id) is True
        assert req.status == ConfirmationStatus.APPROVED
        assert req.resolved_by == "user"
        assert req.resolved_at is not None

    def test_reject(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        assert mgr.reject(req.id) is True
        assert req.status == ConfirmationStatus.REJECTED

    def test_approve_nonexistent(self):
        mgr = HITLManager()
        assert mgr.approve("nonexistent") is False

    def test_approve_already_resolved(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        mgr.approve(req.id)
        # Cannot approve again
        assert mgr.approve(req.id) is False

    def test_get_request(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        assert mgr.get_request(req.id) is req
        assert mgr.get_request("nonexistent") is None

    def test_get_pending(self):
        mgr = HITLManager()
        r1 = mgr.create_request(operation="test1")
        r2 = mgr.create_request(operation="test2")
        pending = mgr.get_pending()
        assert len(pending) == 2

    def test_get_pending_after_resolve(self):
        mgr = HITLManager()
        r1 = mgr.create_request(operation="test1")
        r2 = mgr.create_request(operation="test2")
        mgr.approve(r1.id)
        pending = mgr.get_pending()
        assert len(pending) == 1
        assert pending[0].id == r2.id

    def test_get_by_status(self):
        mgr = HITLManager()
        r1 = mgr.create_request(operation="test1")
        r2 = mgr.create_request(operation="test2")
        mgr.approve(r1.id)
        mgr.reject(r2.id)
        approved = mgr.get_by_status(ConfirmationStatus.APPROVED)
        rejected = mgr.get_by_status(ConfirmationStatus.REJECTED)
        assert len(approved) == 1
        assert len(rejected) == 1

    def test_is_approved(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        mgr.approve(req.id)
        assert mgr.is_approved(req.id) is True
        assert mgr.is_rejected(req.id) is False

    def test_is_rejected(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")
        mgr.reject(req.id)
        assert mgr.is_rejected(req.id) is True
        assert mgr.is_approved(req.id) is False

    def test_is_rejected_expired(self):
        mgr = HITLManager()
        req = mgr.create_request(
            operation="test", timeout=0.01
        )
        # Force expiry
        req.created_at = time.time() - 10
        mgr.expire_pending()
        assert mgr.is_rejected(req.id) is True

    def test_expire_pending(self):
        mgr = HITLManager(auto_expire=False)
        r1 = mgr.create_request(operation="test1", timeout=0.01)
        r2 = mgr.create_request(operation="test2", timeout=300)
        # Make r1 expired
        r1.created_at = time.time() - 10
        expired = mgr.expire_pending()
        assert r1.id in expired
        assert r2.id not in expired
        assert r1.status == ConfirmationStatus.EXPIRED
        assert r2.status == ConfirmationStatus.PENDING

    def test_batch_approve_low_risk(self):
        mgr = HITLManager(batch_threshold=RiskLevel.LOW)
        r1 = mgr.create_request(operation="test1", risk_level=RiskLevel.LOW)
        r2 = mgr.create_request(operation="test2", risk_level=RiskLevel.LOW)
        results = mgr.batch_approve([r1.id, r2.id])
        assert results[r1.id] is True
        assert results[r2.id] is True
        assert r1.status == ConfirmationStatus.APPROVED
        assert r2.status == ConfirmationStatus.APPROVED

    def test_batch_approve_high_risk_blocked(self):
        mgr = HITLManager(batch_threshold=RiskLevel.LOW)
        r1 = mgr.create_request(operation="test1", risk_level=RiskLevel.LOW)
        r2 = mgr.create_request(operation="test2", risk_level=RiskLevel.HIGH)
        results = mgr.batch_approve([r1.id, r2.id])
        assert results[r1.id] is True
        assert results[r2.id] is False
        assert r2.status == ConfirmationStatus.PENDING

    def test_register_callback(self):
        mgr = HITLManager()
        req = mgr.create_request(operation="test")

        async def callback(op_id: str, approved: bool):
            pass

        mgr.register_callback(req.id, callback)
        assert mgr.get_callback(req.id) is callback

    def test_get_callback_nonexistent(self):
        mgr = HITLManager()
        assert mgr.get_callback("nonexistent") is None

    def test_clear(self):
        mgr = HITLManager()
        mgr.create_request(operation="test")
        mgr.clear()
        assert len(mgr._requests) == 0
        assert len(mgr._pending_order) == 0

    def test_clear_resolved(self):
        mgr = HITLManager()
        r1 = mgr.create_request(operation="test1")
        r2 = mgr.create_request(operation="test2")
        mgr.approve(r1.id)
        mgr.clear_resolved()
        # r1 removed, r2 kept
        assert mgr.get_request(r1.id) is None
        assert mgr.get_request(r2.id) is not None

    def test_stats(self):
        mgr = HITLManager()
        r1 = mgr.create_request(operation="test1")
        r2 = mgr.create_request(operation="test2")
        r3 = mgr.create_request(operation="test3")
        mgr.approve(r1.id)
        mgr.reject(r2.id)
        stats = mgr.stats()
        assert stats["pending"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["total"] == 3

    def test_risk_at_or_below(self):
        assert HITLManager._risk_at_or_below(RiskLevel.LOW, RiskLevel.LOW) is True
        assert HITLManager._risk_at_or_below(RiskLevel.LOW, RiskLevel.MEDIUM) is True
        assert HITLManager._risk_at_or_below(RiskLevel.HIGH, RiskLevel.LOW) is False
        assert HITLManager._risk_at_or_below(RiskLevel.CRITICAL, RiskLevel.HIGH) is False


# ═══════════════════════════════════════════════════════════════
#  RiskScore
# ═══════════════════════════════════════════════════════════════


class TestRiskScore:
    """Test the RiskScore dataclass."""

    def test_defaults(self):
        rs = RiskScore()
        assert rs.score == 0.0
        assert rs.level == RiskLevel.LOW
        assert rs.factors == []
        assert rs.needs_confirm is False

    def test_to_dict(self):
        rs = RiskScore(
            score=0.75,
            level=RiskLevel.HIGH,
            factors=["dangerous_command"],
            needs_confirm=True,
        )
        d = rs.to_dict()
        assert d["score"] == 0.75
        assert d["level"] == RiskLevel.HIGH
        assert "dangerous_command" in d["factors"]
        assert d["needs_confirm"] is True


# ═══════════════════════════════════════════════════════════════
#  HITLPolicy — Tool name strategy
# ═══════════════════════════════════════════════════════════════


class TestPolicyToolName:
    """Test tool name-based policy."""

    @pytest.fixture
    def p(self):
        return HITLPolicy()

    def test_confirm_tool(self, p):
        decision = p.check("bash", {"command": "echo hello"})
        assert decision.action == "confirm"
        assert "confirm" in decision.reason.lower()

    def test_auto_tool(self, p):
        decision = p.check("read_file", {})
        assert decision.action == "auto"

    def test_unknown_tool(self, p):
        decision = p.check("custom_tool", {})
        # Unknown tool without dangerous params → auto (low risk)
        assert decision.action in ("auto", "confirm")

    def test_add_confirm_tool(self, p):
        p.add_confirm_tool("custom_tool")
        decision = p.check("custom_tool", {})
        assert decision.action == "confirm"

    def test_add_auto_tool(self, p):
        p.add_auto_tool("bash")
        # bash is now auto, but only if no dangerous command
        decision = p.check("bash", {})
        assert decision.action == "auto"


# ═══════════════════════════════════════════════════════════════
#  HITLPolicy — Parameter content strategy
# ═══════════════════════════════════════════════════════════════


class TestPolicyParameterContent:
    """Test parameter content-based policy."""

    @pytest.fixture
    def p(self):
        return HITLPolicy()

    def test_hard_block_rm_rf_root(self, p):
        decision = p.check("bash", {"command": "rm -rf /"})
        assert decision.action == "block"
        assert decision.risk_score.level == RiskLevel.CRITICAL

    def test_hard_block_rm_rf_home(self, p):
        decision = p.check("bash", {"command": "rm -rf ~"})
        assert decision.action == "block"

    def test_hard_block_mkfs(self, p):
        decision = p.check("bash", {"command": "mkfs.ext4 /dev/sda"})
        assert decision.action == "block"

    def test_hard_block_shutdown(self, p):
        decision = p.check("bash", {"command": "shutdown now"})
        assert decision.action == "block"

    def test_confirm_rm(self, p):
        decision = p.check("bash", {"command": "rm somefile"})
        assert decision.action == "confirm"

    def test_confirm_sudo(self, p):
        decision = p.check("bash", {"command": "sudo apt install"})
        assert decision.action == "confirm"

    def test_confirm_git_push(self, p):
        decision = p.check("bash", {"command": "git push origin main"})
        assert decision.action == "confirm"

    def test_confirm_eval(self, p):
        decision = p.check("bash", {"command": "eval('test')"})
        assert decision.action == "confirm"

    def test_safe_ls(self, p):
        decision = p.check("read_file", {})
        assert decision.action == "auto"

    def test_sensitive_path_increases_risk(self, p):
        decision = p.check("write_file", {"path": "/etc/passwd", "content": "test"})
        # Writing to /etc should increase risk
        assert decision.risk_score.score > 0

    def test_network_operation_increases_risk(self, p):
        decision = p.check("bash", {"command": "curl https://example.com"})
        assert "network_operation" in decision.risk_score.factors


# ═══════════════════════════════════════════════════════════════
#  HITLPolicy — Risk scoring
# ═══════════════════════════════════════════════════════════════


class TestPolicyRiskScoring:
    """Test risk scoring."""

    def test_low_risk(self):
        p = HITLPolicy(confirm_threshold=0.6)
        decision = p.check("read_file", {})
        assert decision.risk_score.level == RiskLevel.LOW
        assert decision.risk_score.score < 0.3

    def test_medium_risk(self):
        p = HITLPolicy(confirm_threshold=0.6)
        # confirm tool without dangerous command
        decision = p.check("bash", {"command": "echo test"})
        assert decision.risk_score.level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_high_risk(self):
        p = HITLPolicy(confirm_threshold=0.6)
        decision = p.check("bash", {"command": "rm -rf /tmp/somedir"})
        # rm -rf is a confirm pattern, not a hard block (only / and ~ are hard blocks)
        assert decision.action in ("confirm", "block")

    def test_custom_threshold(self):
        p = HITLPolicy(confirm_threshold=0.1)
        # Even low-risk operations need confirmation
        decision = p.check("read_file", {})
        # read_file is in auto list, so it's auto regardless of threshold
        assert decision.action == "auto"

    def test_extract_command_from_various_keys(self):
        p = HITLPolicy()
        # command key
        d1 = p.check("bash", {"command": "ls"})
        # cmd key
        d2 = p.check("bash", {"cmd": "ls"})
        # script key
        d3 = p.check("bash", {"script": "ls"})
        # All should have the same risk
        assert d1.risk_score.score == d2.risk_score.score == d3.risk_score.score


# ═══════════════════════════════════════════════════════════════
#  HITLPolicy — Learning mode
# ═══════════════════════════════════════════════════════════════


class TestPolicyLearning:
    """Test learning mode."""

    def test_enable_learning_default(self):
        p = HITLPolicy()
        assert p.enable_learning is True

    def test_disable_learning(self):
        p = HITLPolicy(enable_learning=False)
        assert p.enable_learning is False

    def test_record_approved(self):
        p = HITLPolicy()
        p.record("bash", "git push", approved=True)
        stats = p.get_learning_stats()
        key = "bash:git push"
        assert key in stats
        assert stats[key]["approved"] == 1

    def test_record_rejected(self):
        p = HITLPolicy()
        p.record("bash", "rm file", approved=False)
        stats = p.get_learning_stats()
        key = "bash:rm file"
        assert key in stats
        assert stats[key]["rejected"] == 1

    def test_learning_auto_approve(self):
        """After 3 approvals, same operation auto-approves."""
        p = HITLPolicy()
        for _ in range(3):
            p.record("bash", "git status", approved=True)
        decision = p.check("bash", {"command": "git status"})
        assert decision.action == "auto"
        assert "learned_auto" in decision.risk_score.factors

    def test_learning_auto_block(self):
        """After 2 rejections, same operation auto-blocks."""
        p = HITLPolicy()
        for _ in range(2):
            p.record("bash", "rm file", approved=False)
        decision = p.check("bash", {"command": "rm file"})
        assert decision.action == "block"
        assert "learned_block" in decision.risk_score.factors

    def test_learning_no_conclusion(self):
        """Mixed history does not trigger auto-decision."""
        p = HITLPolicy()
        p.record("bash", "git push", approved=True)
        p.record("bash", "git push", approved=False)
        decision = p.check("bash", {"command": "git push"})
        # Should not be auto-approved or auto-blocked
        assert "learned_auto" not in decision.risk_score.factors
        assert "learned_block" not in decision.risk_score.factors

    def test_learning_disabled(self):
        """Learning disabled → no learning effect."""
        p = HITLPolicy(enable_learning=False)
        p.record("bash", "git push", approved=True)
        # record does nothing when disabled
        assert len(p.get_learning_stats()) == 0

    def test_get_history(self):
        p = HITLPolicy()
        p.record("bash", "git push", approved=True)
        p.record("bash", "rm file", approved=False)
        history = p.get_history()
        assert len(history) == 2

    def test_clear_learning(self):
        p = HITLPolicy()
        p.record("bash", "git push", approved=True)
        p.clear_learning()
        assert len(p.get_learning_stats()) == 0
        assert len(p.get_history()) == 0

    def test_learning_window(self):
        p = HITLPolicy(learning_window=5)
        for i in range(10):
            p.record("bash", f"cmd_{i}", approved=True)
        assert len(p.get_history()) <= 5

    def test_hard_block_overrides_learning(self):
        """Hard block patterns override learning."""
        p = HITLPolicy()
        # Even if we "learn" rm -rf /, it should still block
        p.record("bash", "rm -rf /", approved=True)
        p.record("bash", "rm -rf /", approved=True)
        p.record("bash", "rm -rf /", approved=True)
        decision = p.check("bash", {"command": "rm -rf /"})
        assert decision.action == "block"


# ═══════════════════════════════════════════════════════════════
#  PolicyDecision
# ═══════════════════════════════════════════════════════════════


class TestPolicyDecision:
    """Test PolicyDecision dataclass."""

    def test_defaults(self):
        d = PolicyDecision()
        assert d.action == "auto"
        assert d.reason == ""
        assert d.risk_score.score == 0.0

    def test_to_dict(self):
        d = PolicyDecision(
            action="confirm",
            reason="Need confirmation",
            risk_score=RiskScore(score=0.7, level=RiskLevel.HIGH),
        )
        d_dict = d.to_dict()
        assert d_dict["action"] == "confirm"
        assert d_dict["reason"] == "Need confirmation"
        assert d_dict["risk_score"]["level"] == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════
#  HITLMiddleware
# ═══════════════════════════════════════════════════════════════


class TestHITLMiddleware:
    """Test the HITLMiddleware class."""

    @pytest.fixture
    def state(self):
        return LoopState(
            history=[{"role": "user", "content": "test"}],
            turn=0,
        )

    def test_priority(self):
        mw = HITLMiddleware()
        assert mw.priority == 35

    def test_name(self):
        mw = HITLMiddleware()
        assert mw.name == "HITLMiddleware"

    def test_default_components(self):
        mw = HITLMiddleware()
        assert mw.manager is not None
        assert mw.policy is not None

    @pytest.mark.asyncio
    async def test_before_tool_call_auto(self, state):
        """Auto-approved tool passes through."""
        mw = HITLMiddleware()
        tool_name, args = await mw.before_tool_call(
            "read_file", {}, state
        )
        assert tool_name == "read_file"
        assert "hitl" in state.metadata

    @pytest.mark.asyncio
    async def test_before_tool_call_confirm(self, state):
        """Confirm-required tool creates a confirmation request."""
        mw = HITLMiddleware()
        tool_name, args = await mw.before_tool_call(
            "bash", {"command": "echo hello"}, state
        )
        assert tool_name == "bash"  # not blocked
        assert state.metadata.get("hitl_needs_confirmation") is True
        assert "hitl_pending_request" in state.metadata

    @pytest.mark.asyncio
    async def test_before_tool_call_block(self, state):
        """Hard-blocked tool returns empty tool_name."""
        mw = HITLMiddleware()
        tool_name, args = await mw.before_tool_call(
            "bash", {"command": "rm -rf /"}, state
        )
        assert tool_name == ""  # blocked
        assert state.metadata.get("hitl_blocked") is True

    @pytest.mark.asyncio
    async def test_before_tool_call_records_metadata(self, state):
        """before_tool_call records decision in metadata."""
        mw = HITLMiddleware()
        await mw.before_tool_call("bash", {"command": "ls"}, state)
        hitl_logs = state.metadata.get("hitl", [])
        assert len(hitl_logs) == 1
        assert hitl_logs[0]["tool"] == "bash"

    @pytest.mark.asyncio
    async def test_before_tool_call_auto_no_request(self, state):
        """Auto-approved tool does not create a confirmation request."""
        mw = HITLMiddleware()
        await mw.before_tool_call("read_file", {}, state)
        assert "hitl_pending_request" not in state.metadata
        assert state.metadata.get("hitl_needs_confirmation") is not True

    def test_create_confirmation(self):
        """create_confirmation creates a request."""
        mw = HITLMiddleware()
        req = mw.create_confirmation(
            "bash", {"command": "ls"}, RiskLevel.LOW, "List directory"
        )
        assert req.is_pending
        assert req.risk_level == RiskLevel.LOW

    def test_check_and_confirm_auto(self):
        """check_and_confirm returns approved request for auto operations."""
        mw = HITLMiddleware()
        req = mw.check_and_confirm("read_file", {})
        assert req.status == ConfirmationStatus.APPROVED

    def test_check_and_confirm_needs_confirmation(self):
        """check_and_confirm returns pending request for confirm operations."""
        mw = HITLMiddleware()
        req = mw.check_and_confirm("bash", {"command": "echo hello"})
        assert req.is_pending

    def test_resolve_and_learn_approved(self):
        """resolve_and_learn approves and records to learning."""
        mw = HITLMiddleware()
        req = mw.create_confirmation(
            "bash", {"command": "git push"}, RiskLevel.MEDIUM
        )
        result = mw.resolve_and_learn(req.id, approved=True)
        assert result is True
        assert mw.manager.is_approved(req.id)
        # Learning history should have the record
        stats = mw.policy.get_learning_stats()
        assert len(stats) > 0

    def test_resolve_and_learn_rejected(self):
        """resolve_and_learn rejects and records to learning."""
        mw = HITLMiddleware()
        req = mw.create_confirmation(
            "bash", {"command": "git push"}, RiskLevel.MEDIUM
        )
        result = mw.resolve_and_learn(req.id, approved=False)
        assert result is True
        assert mw.manager.is_rejected(req.id)

    def test_resolve_and_learn_nonexistent(self):
        """resolve_and_learn returns False for nonexistent request."""
        mw = HITLMiddleware()
        result = mw.resolve_and_learn("nonexistent", approved=True)
        assert result is False

    def test_get_pending_confirmations(self):
        """get_pending_confirmations returns pending requests."""
        mw = HITLMiddleware()
        mw.create_confirmation("bash", {"command": "ls"}, RiskLevel.LOW)
        mw.create_confirmation("bash", {"command": "pwd"}, RiskLevel.LOW)
        pending = mw.get_pending_confirmations()
        assert len(pending) == 2

    def test_is_tool_allowed_auto(self):
        """is_tool_allowed returns True for auto tools."""
        mw = HITLMiddleware()
        assert mw.is_tool_allowed("read_file", {}) is True

    def test_is_tool_allowed_confirm(self):
        """is_tool_allowed returns False for confirm tools."""
        mw = HITLMiddleware()
        assert mw.is_tool_allowed("bash", {"command": "echo hello"}) is False

    def test_full_lifecycle_with_learning(self):
        """Full lifecycle: confirm → approve → learn → auto next time."""
        mw = HITLMiddleware()
        # First time: needs confirmation
        req = mw.check_and_confirm("bash", {"command": "git status"})
        assert req.is_pending
        # Approve 3 times
        for _ in range(3):
            req = mw.check_and_confirm("bash", {"command": "git status"})
            if req.is_pending:
                mw.resolve_and_learn(req.id, approved=True)
        # Fourth time: should be auto-approved by learning
        decision = mw.policy.check("bash", {"command": "git status"})
        assert "learned_auto" in decision.risk_score.factors
