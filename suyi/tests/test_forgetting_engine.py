"""
Tests for the Forgetting Engine (Phase 13).

Covers:
    - ForgettingCurve: retention, time_until_threshold, reinforce, contradict,
      apply_high_reference, from_quality, serialisation
    - ForgettingAction enum
    - MemoryRecord: properties, serialisation
    - ForgettingEngine: evaluate, execute (dry-run and live), update_quality,
      compress, forgetting_report, batch operations
    - Exception handling: anti-patterns, user-pinned, high-ref memories
"""

import math
import time
import unittest

from suyi.quality.grader import (
    QualityScore,
    QualityAssessor,
    ResultQuality,
    SourceQuality,
)
from suyi.quality.forgetting import (
    ForgettingCurve,
    ForgettingAction,
    ForgettingEngine,
    MemoryRecord,
    THRESHOLD_KEEP,
    THRESHOLD_DEGRADE,
    THRESHOLD_COMPRESS,
    THRESHOLD_PURGE,
)


class TestForgettingCurve(unittest.TestCase):
    """ForgettingCurve tests."""

    def test_retention_at_zero(self):
        """At t=0, retention equals Q0."""
        curve = ForgettingCurve(q0=0.8, tau=86400.0)
        self.assertAlmostEqual(curve.retention(0), 0.8)

    def test_retention_decays(self):
        """Retention decreases over time."""
        curve = ForgettingCurve(q0=1.0, tau=86400.0)
        r1 = curve.retention(3600)    # 1 hour
        r2 = curve.retention(86400)   # 1 day
        r3 = curve.retention(86400 * 7)  # 7 days
        self.assertGreater(r1, r2)
        self.assertGreater(r2, r3)

    def test_retention_infinite_tau(self):
        """With tau=inf, retention never decays."""
        curve = ForgettingCurve(q0=0.7, tau=math.inf)
        self.assertAlmostEqual(curve.retention(999999999), 0.7)

    def test_retention_at_days(self):
        curve = ForgettingCurve(q0=1.0, tau=30 * 86400)
        r_days = curve.retention_at_days(30)
        r_seconds = curve.retention(30 * 86400)
        self.assertAlmostEqual(r_days, r_seconds, places=5)

    def test_retention_exponential_formula(self):
        """Q(t) = Q0 * e^(-t/tau)."""
        curve = ForgettingCurve(q0=0.9, tau=100.0)
        expected = 0.9 * math.exp(-50.0 / 100.0)
        self.assertAlmostEqual(curve.retention(50.0), expected, places=5)

    def test_retention_never_negative(self):
        curve = ForgettingCurve(q0=0.5, tau=1.0)
        self.assertGreaterEqual(curve.retention(10000), 0.0)

    def test_time_until_threshold(self):
        curve = ForgettingCurve(q0=1.0, tau=86400.0)
        # At tau, retention = Q0 * e^(-1) ≈ 0.368
        t = curve.time_until_threshold(0.368)
        self.assertAlmostEqual(t, 86400.0, delta=100)

    def test_time_until_threshold_above_q0(self):
        """Threshold above Q0 → 0."""
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        self.assertEqual(curve.time_until_threshold(0.6), 0.0)

    def test_time_until_threshold_infinite_tau(self):
        curve = ForgettingCurve(q0=0.5, tau=math.inf)
        self.assertEqual(curve.time_until_threshold(0.1), math.inf)

    def test_reinforce_boosts_q0(self):
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        reinforced = curve.reinforce(1)
        self.assertGreater(reinforced.q0, curve.q0)

    def test_reinforce_extends_tau(self):
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        reinforced = curve.reinforce(1)
        self.assertGreater(reinforced.tau, curve.tau)

    def test_reinforce_capped_at_max(self):
        curve = ForgettingCurve(q0=0.95, tau=100.0)
        reinforced = curve.reinforce(10)
        self.assertLessEqual(reinforced.q0, ForgettingCurve.MAX_Q0)

    def test_reinforce_immutable(self):
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        reinforced = curve.reinforce(1)
        self.assertAlmostEqual(curve.q0, 0.5)  # original unchanged
        self.assertNotEqual(id(curve), id(reinforced))

    def test_contradict_reduces_q0(self):
        curve = ForgettingCurve(q0=0.8, tau=100.0)
        contradicted = curve.contradict(1)
        self.assertLess(contradicted.q0, curve.q0)

    def test_contradict_shrinks_tau(self):
        curve = ForgettingCurve(q0=0.8, tau=100.0)
        contradicted = curve.contradict(1)
        self.assertLess(contradicted.tau, curve.tau)

    def test_contradict_floored_at_min(self):
        curve = ForgettingCurve(q0=0.1, tau=100.0)
        contradicted = curve.contradict(10)
        self.assertGreaterEqual(contradicted.q0, ForgettingCurve.MIN_Q0)

    def test_apply_high_reference_extends_tau(self):
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        extended = curve.apply_high_reference(15)
        self.assertGreater(extended.tau, curve.tau)

    def test_apply_high_reference_no_change_below_threshold(self):
        curve = ForgettingCurve(q0=0.5, tau=100.0)
        extended = curve.apply_high_reference(5)
        self.assertAlmostEqual(extended.tau, curve.tau)

    def test_apply_high_reference_infinite_tau_unchanged(self):
        curve = ForgettingCurve(q0=0.5, tau=math.inf)
        extended = curve.apply_high_reference(20)
        self.assertEqual(extended.tau, math.inf)

    def test_from_quality(self):
        qs = QualityScore(source=SourceQuality.B, result=ResultQuality.TRUSTED)
        curve = ForgettingCurve.from_quality(qs)
        self.assertAlmostEqual(curve.q0, qs.memory_weight)
        self.assertAlmostEqual(curve.tau, qs.decay_tau)

    def test_from_quality_with_reinforcement(self):
        qs = QualityScore(source=SourceQuality.B, result=ResultQuality.TRUSTED)
        curve = ForgettingCurve.from_quality(qs, reinforcement_count=2)
        base_curve = ForgettingCurve.from_quality(qs)
        self.assertGreater(curve.q0, base_curve.q0)

    def test_from_quality_with_contradiction(self):
        qs = QualityScore(source=SourceQuality.B, result=ResultQuality.TRUSTED)
        curve = ForgettingCurve.from_quality(qs, contradiction_count=2)
        base_curve = ForgettingCurve.from_quality(qs)
        self.assertLess(curve.q0, base_curve.q0)

    def test_to_dict_and_from_dict(self):
        curve = ForgettingCurve(q0=0.7, tau=5000.0)
        d = curve.to_dict()
        curve2 = ForgettingCurve.from_dict(d)
        self.assertAlmostEqual(curve.q0, curve2.q0)
        self.assertAlmostEqual(curve.tau, curve2.tau)

    def test_to_dict_infinite_tau(self):
        curve = ForgettingCurve(q0=0.7, tau=math.inf)
        d = curve.to_dict()
        self.assertIsNone(d["tau"])
        curve2 = ForgettingCurve.from_dict(d)
        self.assertEqual(curve2.tau, math.inf)

    def test_invalid_q0_raises(self):
        with self.assertRaises(ValueError):
            ForgettingCurve(q0=-0.1, tau=100.0)
        with self.assertRaises(ValueError):
            ForgettingCurve(q0=1.5, tau=100.0)

    def test_invalid_tau_raises(self):
        with self.assertRaises(ValueError):
            ForgettingCurve(q0=0.5, tau=-1.0)


class TestForgettingAction(unittest.TestCase):
    """ForgettingAction enum tests."""

    def test_distinct_members(self):
        self.assertNotEqual(ForgettingAction.DEGRADE, ForgettingAction.COMPRESS)
        self.assertNotEqual(ForgettingAction.COMPRESS, ForgettingAction.PURGE)
        self.assertNotEqual(ForgettingAction.DEGRADE, ForgettingAction.PURGE)

    def test_three_actions(self):
        self.assertEqual(len(ForgettingAction), 3)


class TestMemoryRecord(unittest.TestCase):
    """MemoryRecord dataclass tests."""

    def test_default_values(self):
        rec = MemoryRecord(id="m1")
        self.assertEqual(rec.id, "m1")
        self.assertEqual(rec.quality.source, SourceQuality.C)
        self.assertFalse(rec.is_user_pinned)
        self.assertFalse(rec.is_episodic)

    def test_is_anti_pattern(self):
        rec = MemoryRecord(
            id="m1",
            quality=QualityScore(result=ResultQuality.FAILED),
        )
        self.assertTrue(rec.is_anti_pattern)

    def test_not_anti_pattern(self):
        rec = MemoryRecord(
            id="m1",
            quality=QualityScore(result=ResultQuality.TRUSTED),
        )
        self.assertFalse(rec.is_anti_pattern)

    def test_elapsed_seconds_non_negative(self):
        rec = MemoryRecord(id="m1", created_at=time.time() - 100)
        self.assertGreaterEqual(rec.elapsed_seconds, 0.0)

    def test_to_dict(self):
        rec = MemoryRecord(id="m1", content="hello", tags=["a", "b"])
        d = rec.to_dict()
        self.assertEqual(d["id"], "m1")
        self.assertEqual(d["content"], "hello")
        self.assertEqual(d["tags"], ["a", "b"])


class TestForgettingEngine(unittest.TestCase):
    """ForgettingEngine tests."""

    def setUp(self):
        self.engine = ForgettingEngine()

    def _make_record(
        self,
        source=SourceQuality.B,
        result=ResultQuality.TRUSTED,
        age_seconds=0,
        reinforcement_count=0,
        contradiction_count=0,
        reference_count=0,
        is_user_pinned=False,
        is_episodic=False,
        content="test content",
        mem_id="test_mem",
    ):
        qs = QualityScore(source=source, result=result)
        now = time.time()
        return MemoryRecord(
            id=mem_id,
            quality=qs,
            created_at=now - age_seconds,
            last_reinforced=now - age_seconds if reinforcement_count > 0 else 0,
            reinforcement_count=reinforcement_count,
            contradiction_count=contradiction_count,
            reference_count=reference_count,
            is_user_pinned=is_user_pinned,
            is_episodic=is_episodic,
            content=content,
        )

    def test_evaluate_fresh_memory_degrade(self):
        """Fresh high-quality memory → DEGRADE (effectively keep)."""
        rec = self._make_record(
            source=SourceQuality.A, result=ResultQuality.VERIFIED,
            age_seconds=0,
        )
        action = self.engine.evaluate(rec)
        self.assertEqual(action, ForgettingAction.DEGRADE)

    def test_evaluate_old_low_quality_purge(self):
        """Very old, low-quality memory → PURGE."""
        rec = self._make_record(
            source=SourceQuality.D, result=ResultQuality.SPECULATIVE,
            age_seconds=86400 * 100,  # 100 days
        )
        action = self.engine.evaluate(rec)
        self.assertEqual(action, ForgettingAction.PURGE)

    def test_evaluate_medium_age_compress(self):
        """Moderate age, medium quality → COMPRESS."""
        rec = self._make_record(
            source=SourceQuality.C, result=ResultQuality.SPECULATIVE,
            age_seconds=86400 * 10,  # 10 days, tau=7 days
        )
        action = self.engine.evaluate(rec)
        # With C source (tau=7d) and 10 days, retention should be low
        self.assertIn(action, [ForgettingAction.COMPRESS, ForgettingAction.PURGE])

    def test_evaluate_user_pinned_never_forget(self):
        """User-pinned memory → always DEGRADE (never COMPRESS/PURGE)."""
        rec = self._make_record(
            source=SourceQuality.D, result=ResultQuality.SPECULATIVE,
            age_seconds=86400 * 365,  # 1 year
            is_user_pinned=True,
        )
        action = self.engine.evaluate(rec)
        self.assertEqual(action, ForgettingAction.DEGRADE)

    def test_evaluate_anti_pattern_never_purge(self):
        """Anti-pattern (FAILED) memory → never PURGE."""
        rec = self._make_record(
            source=SourceQuality.D, result=ResultQuality.FAILED,
            age_seconds=86400 * 365,
        )
        action = self.engine.evaluate(rec)
        self.assertNotEqual(action, ForgettingAction.PURGE)
        self.assertNotEqual(action, ForgettingAction.COMPRESS)

    def test_evaluate_s_source_never_decays(self):
        """S-grade source has infinite tau → never decays from age."""
        rec = self._make_record(
            source=SourceQuality.S, result=ResultQuality.VERIFIED,
            age_seconds=86400 * 3650,  # 10 years
        )
        retention = self.engine.retention(rec)
        self.assertGreater(retention, 0.5)

    def test_retention_computation(self):
        rec = self._make_record(
            source=SourceQuality.B, result=ResultQuality.TRUSTED,
            age_seconds=86400 * 15,  # 15 days, tau=30 days
        )
        retention = self.engine.retention(rec)
        self.assertGreater(retention, 0.0)
        self.assertLess(retention, 1.0)

    def test_evaluate_batch(self):
        records = [
            self._make_record(source=SourceQuality.A, age_seconds=0, content="m1"),
            self._make_record(source=SourceQuality.D, age_seconds=86400 * 100, content="m2"),
        ]
        results = self.engine.evaluate_batch(records)
        self.assertEqual(len(results), 2)
        for mem, action, retention in results:
            self.assertIsInstance(action, ForgettingAction)
            self.assertIsInstance(retention, float)

    def test_execute_dry_run(self):
        """In dry-run mode, callbacks are not invoked."""
        engine = ForgettingEngine(is_dry_run=True)
        rec = self._make_record(
            source=SourceQuality.D, age_seconds=86400 * 100,
        )
        called = []
        action = engine.execute(
            rec, on_purge=lambda mid: called.append(mid),
        )
        self.assertEqual(len(called), 0)  # callback not called in dry-run

    def test_execute_live_purge(self):
        """In live mode, PURGE calls on_purge."""
        engine = ForgettingEngine(is_dry_run=False)
        rec = self._make_record(
            source=SourceQuality.D, age_seconds=86400 * 100,
        )
        purged = []
        action = engine.execute(rec, on_purge=lambda mid: purged.append(mid))
        self.assertEqual(action, ForgettingAction.PURGE)
        self.assertEqual(len(purged), 1)

    def test_execute_live_compress(self):
        """In live mode, COMPRESS calls on_compress."""
        engine = ForgettingEngine(is_dry_run=False)
        rec = self._make_record(
            source=SourceQuality.C, age_seconds=86400 * 10,
            is_episodic=True, content="episodic content here",
        )
        compressed = []
        action = engine.execute(
            rec, on_compress=lambda m: compressed.append(m),
        )
        if action == ForgettingAction.COMPRESS:
            self.assertEqual(len(compressed), 1)

    def test_execute_anti_pattern_safety_net(self):
        """Even if evaluate returns PURGE, execute protects anti-patterns."""
        engine = ForgettingEngine(is_dry_run=False)
        rec = self._make_record(
            source=SourceQuality.D, result=ResultQuality.FAILED,
            age_seconds=86400 * 365,
        )
        purged = []
        action = engine.execute(
            rec,
            action=ForgettingAction.PURGE,  # force PURGE
            on_purge=lambda mid: purged.append(mid),
        )
        # Anti-pattern should be protected
        self.assertEqual(action, ForgettingAction.DEGRADE)
        self.assertEqual(len(purged), 0)

    def test_execute_user_pinned_safety_net(self):
        """User-pinned memories are protected from PURGE."""
        engine = ForgettingEngine(is_dry_run=False)
        rec = self._make_record(
            source=SourceQuality.D, age_seconds=86400 * 365,
            is_user_pinned=True,
        )
        purged = []
        action = engine.execute(
            rec,
            action=ForgettingAction.PURGE,
            on_purge=lambda mid: purged.append(mid),
        )
        self.assertEqual(action, ForgettingAction.DEGRADE)
        self.assertEqual(len(purged), 0)

    def test_execute_batch(self):
        engine = ForgettingEngine(is_dry_run=False)
        records = [
            self._make_record(source=SourceQuality.D, age_seconds=86400 * 100, content="m1"),
            self._make_record(source=SourceQuality.A, age_seconds=0, content="m2"),
        ]
        purged = []
        results = engine.execute_batch(records, on_purge=lambda mid: purged.append(mid))
        self.assertEqual(len(results), 2)
        self.assertGreater(len(purged), 0)  # at least one purged

    def test_update_quality_success(self):
        """update_quality upgrades result on success."""
        rec = self._make_record(
            source=SourceQuality.B, result=ResultQuality.SPECULATIVE,
        )
        updated = self.engine.update_quality(
            [rec], ResultQuality.TRUSTED, success=True, new_evidence=1,
        )
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].quality.result, ResultQuality.TRUSTED)
        self.assertEqual(updated[0].reinforcement_count, 1)

    def test_update_quality_failure(self):
        """update_quality downgrades on failure and increments contradiction."""
        rec = self._make_record(
            source=SourceQuality.A, result=ResultQuality.TRUSTED,
        )
        updated = self.engine.update_quality(
            [rec], ResultQuality.FAILED, contradiction=True, new_contradictions=1,
        )
        self.assertEqual(updated[0].quality.result, ResultQuality.FAILED)
        self.assertEqual(updated[0].contradiction_count, 1)

    def test_update_quality_preserves_id_and_content(self):
        rec = self._make_record(content="important content")
        updated = self.engine.update_quality([rec], ResultQuality.TRUSTED, success=True)
        self.assertEqual(updated[0].id, rec.id)
        self.assertEqual(updated[0].content, "important content")

    def test_update_quality_updates_timestamp(self):
        rec = self._make_record()
        old_accessed = rec.last_accessed
        time.sleep(0.01)
        updated = self.engine.update_quality([rec], ResultQuality.TRUSTED, success=True)
        self.assertGreater(updated[0].last_accessed, old_accessed)

    def test_compress_episodic(self):
        """compress produces a semantic memory dict."""
        rec = self._make_record(
            is_episodic=True,
            content="First sentence. Second sentence. Third sentence. Fourth.",
        )
        result = self.engine.compress(rec)
        self.assertIn("content", result)
        self.assertTrue(result["content"].startswith("[compressed]"))
        self.assertEqual(result["source"], "compressed")

    def test_compress_non_episodic_raises(self):
        rec = self._make_record(is_episodic=False)
        with self.assertRaises(ValueError):
            self.engine.compress(rec)

    def test_compress_short_content(self):
        """Short content is kept as-is (no truncation needed)."""
        rec = self._make_record(
            is_episodic=True, content="Short content.",
        )
        result = self.engine.compress(rec)
        self.assertIn("Short content", result["content"])

    def test_compress_batch(self):
        records = [
            self._make_record(is_episodic=True, content="episodic 1. More text.", mem_id="r1"),
            self._make_record(is_episodic=False, content="not episodic", mem_id="r2"),
            self._make_record(is_episodic=True, content="episodic 2. More text.", mem_id="r3"),
        ]
        results = self.engine.compress_batch(records)
        self.assertEqual(len(results), 2)  # only episodic ones

    def test_compress_batch_dry_run(self):
        engine = ForgettingEngine(is_dry_run=True)
        records = [
            self._make_record(is_episodic=True, content="episodic content"),
        ]
        results = engine.compress_batch(records)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "dry_run")

    def test_forgetting_report(self):
        records = [
            self._make_record(source=SourceQuality.A, age_seconds=0, content="m1"),
            self._make_record(source=SourceQuality.D, age_seconds=86400 * 100, content="m2"),
        ]
        report = self.engine.forgetting_report(records)
        self.assertEqual(report["total"], 2)
        self.assertIn("DEGRADE", report["actions"])
        self.assertIn("COMPRESS", report["actions"])
        self.assertIn("PURGE", report["actions"])
        self.assertEqual(len(report["details"]), 2)

    def test_forgetting_report_dry_run_flag(self):
        engine = ForgettingEngine(is_dry_run=True)
        report = engine.forgetting_report([])
        self.assertTrue(report["dry_run"])

    def test_high_reference_extends_tau(self):
        """Memories with >10 references get 3x tau extension."""
        rec = self._make_record(
            source=SourceQuality.C, result=ResultQuality.TRUSTED,
            age_seconds=86400 * 5,
            reference_count=15,
        )
        curve = self.engine.build_curve(rec)
        base_qs = QualityScore(source=SourceQuality.C, result=ResultQuality.TRUSTED)
        base_tau = base_qs.decay_tau
        self.assertGreater(curve.tau, base_tau)

    def test_repr_contains_mode(self):
        engine_live = ForgettingEngine(is_dry_run=False)
        engine_dry = ForgettingEngine(is_dry_run=True)
        self.assertIn("live", repr(engine_live))
        self.assertIn("dry-run", repr(engine_dry))


if __name__ == "__main__":
    unittest.main()
