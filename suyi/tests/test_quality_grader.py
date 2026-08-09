"""
Tests for the Quality Grading System (Phase 13).

Covers:
    - SourceQuality enum: values, labels, from_label, grade_letter
    - ResultQuality enum: values, labels, from_label, is_failure
    - QualityScore: validation, memory_weight, decay_tau, serialisation
    - QualityAssessor: assess_source, assess_result, assess, update_after_task
    - Edge cases and invariant checks
"""

import math
import unittest

from suyi.quality.grader import (
    SourceQuality,
    ResultQuality,
    QualityScore,
    QualityAssessor,
)


class TestSourceQuality(unittest.TestCase):
    """SourceQuality enum tests."""

    def test_grade_ordering(self):
        """S > A > B > C > D by numeric value."""
        self.assertGreater(SourceQuality.S.value, SourceQuality.A.value)
        self.assertGreater(SourceQuality.A.value, SourceQuality.B.value)
        self.assertGreater(SourceQuality.B.value, SourceQuality.C.value)
        self.assertGreater(SourceQuality.C.value, SourceQuality.D.value)

    def test_from_label_verified(self):
        self.assertEqual(SourceQuality.from_label("verified"), SourceQuality.S)

    def test_from_label_authoritative(self):
        self.assertEqual(SourceQuality.from_label("authoritative"), SourceQuality.A)

    def test_from_label_reliable(self):
        self.assertEqual(SourceQuality.from_label("reliable"), SourceQuality.B)

    def test_from_label_uncertain(self):
        self.assertEqual(SourceQuality.from_label("uncertain"), SourceQuality.C)

    def test_from_label_speculative(self):
        self.assertEqual(SourceQuality.from_label("speculative"), SourceQuality.D)

    def test_from_label_single_letter(self):
        self.assertEqual(SourceQuality.from_label("S"), SourceQuality.S)
        self.assertEqual(SourceQuality.from_label("a"), SourceQuality.A)

    def test_from_label_case_insensitive(self):
        self.assertEqual(SourceQuality.from_label("VERIFIED"), SourceQuality.S)
        self.assertEqual(SourceQuality.from_label("Authoritative"), SourceQuality.A)

    def test_from_label_invalid(self):
        with self.assertRaises(ValueError):
            SourceQuality.from_label("nonsense")

    def test_label_property(self):
        self.assertEqual(SourceQuality.S.label, "verified")
        self.assertEqual(SourceQuality.D.label, "speculative")

    def test_grade_letter_property(self):
        self.assertEqual(SourceQuality.S.grade_letter, "S")
        self.assertEqual(SourceQuality.C.grade_letter, "C")


class TestResultQuality(unittest.TestCase):
    """ResultQuality enum tests."""

    def test_grade_ordering(self):
        self.assertGreater(ResultQuality.VERIFIED.value, ResultQuality.TRUSTED.value)
        self.assertGreater(ResultQuality.TRUSTED.value, ResultQuality.SPECULATIVE.value)
        self.assertGreater(ResultQuality.SPECULATIVE.value, ResultQuality.FAILED.value)

    def test_from_label_verified(self):
        self.assertEqual(ResultQuality.from_label("verified"), ResultQuality.VERIFIED)

    def test_from_label_trusted(self):
        self.assertEqual(ResultQuality.from_label("trusted"), ResultQuality.TRUSTED)

    def test_from_label_speculative(self):
        self.assertEqual(ResultQuality.from_label("speculative"), ResultQuality.SPECULATIVE)

    def test_from_label_failed(self):
        self.assertEqual(ResultQuality.from_label("failed"), ResultQuality.FAILED)

    def test_from_label_case_insensitive(self):
        self.assertEqual(ResultQuality.from_label("VERIFIED"), ResultQuality.VERIFIED)
        self.assertEqual(ResultQuality.from_label("Failed"), ResultQuality.FAILED)

    def test_from_label_invalid(self):
        with self.assertRaises(ValueError):
            ResultQuality.from_label("bogus")

    def test_is_failure_property(self):
        self.assertTrue(ResultQuality.FAILED.is_failure)
        self.assertFalse(ResultQuality.VERIFIED.is_failure)
        self.assertFalse(ResultQuality.TRUSTED.is_failure)
        self.assertFalse(ResultQuality.SPECULATIVE.is_failure)

    def test_label_property(self):
        self.assertEqual(ResultQuality.VERIFIED.label, "verified")
        self.assertEqual(ResultQuality.FAILED.label, "failed")


class TestQualityScore(unittest.TestCase):
    """QualityScore dataclass tests."""

    def test_default_values(self):
        qs = QualityScore()
        self.assertEqual(qs.source, SourceQuality.C)
        self.assertEqual(qs.result, ResultQuality.SPECULATIVE)
        self.assertAlmostEqual(qs.confidence, 0.5)
        self.assertEqual(qs.evidence_count, 0)
        self.assertEqual(qs.contradiction_count, 0)

    def test_confidence_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            QualityScore(confidence=-0.1)
        with self.assertRaises(ValueError):
            QualityScore(confidence=1.5)

    def test_negative_evidence_raises(self):
        with self.assertRaises(ValueError):
            QualityScore(evidence_count=-1)

    def test_negative_contradiction_raises(self):
        with self.assertRaises(ValueError):
            QualityScore(contradiction_count=-1)

    def test_invalid_source_type_raises(self):
        with self.assertRaises(TypeError):
            QualityScore(source="S")  # type: ignore

    def test_invalid_result_type_raises(self):
        with self.assertRaises(TypeError):
            QualityScore(result="FAILED")  # type: ignore

    def test_memory_weight_range(self):
        """memory_weight is always in [0, 1]."""
        for source in SourceQuality:
            for result in ResultQuality:
                qs = QualityScore(source=source, result=result)
                w = qs.memory_weight
                self.assertGreaterEqual(w, 0.0)
                self.assertLessEqual(w, 1.0)

    def test_memory_weight_s_verified_highest(self):
        qs = QualityScore(
            source=SourceQuality.S, result=ResultQuality.VERIFIED,
            confidence=1.0, evidence_count=5,
        )
        self.assertGreater(qs.memory_weight, 0.8)

    def test_memory_weight_d_failed_lowest(self):
        qs = QualityScore(
            source=SourceQuality.D, result=ResultQuality.FAILED,
            confidence=0.0, evidence_count=0, contradiction_count=3,
        )
        self.assertLess(qs.memory_weight, 0.2)

    def test_memory_weight_evidence_balance(self):
        """More evidence vs contradictions → higher weight."""
        qs_balanced = QualityScore(
            source=SourceQuality.B, result=ResultQuality.TRUSTED,
            confidence=0.5, evidence_count=3, contradiction_count=3,
        )
        qs_dominant = QualityScore(
            source=SourceQuality.B, result=ResultQuality.TRUSTED,
            confidence=0.5, evidence_count=5, contradiction_count=1,
        )
        self.assertGreater(qs_dominant.memory_weight, qs_balanced.memory_weight)

    def test_decay_tau_s_infinite(self):
        qs = QualityScore(source=SourceQuality.S, result=ResultQuality.TRUSTED)
        self.assertEqual(qs.decay_tau, math.inf)

    def test_decay_tau_a_90_days(self):
        qs = QualityScore(source=SourceQuality.A, result=ResultQuality.TRUSTED)
        self.assertAlmostEqual(qs.decay_tau_days, 90.0, places=1)

    def test_decay_tau_b_30_days(self):
        qs = QualityScore(source=SourceQuality.B, result=ResultQuality.TRUSTED)
        self.assertAlmostEqual(qs.decay_tau_days, 30.0, places=1)

    def test_decay_tau_c_7_days(self):
        qs = QualityScore(source=SourceQuality.C, result=ResultQuality.TRUSTED)
        self.assertAlmostEqual(qs.decay_tau_days, 7.0, places=1)

    def test_decay_tau_d_1_day(self):
        qs = QualityScore(source=SourceQuality.D, result=ResultQuality.TRUSTED)
        self.assertAlmostEqual(qs.decay_tau_days, 1.0, places=1)

    def test_decay_tau_failed_always_infinite(self):
        """Failed results always get infinite tau (persist as anti-pattern)."""
        for source in SourceQuality:
            qs = QualityScore(source=source, result=ResultQuality.FAILED)
            self.assertEqual(qs.decay_tau, math.inf)

    def test_is_anti_pattern(self):
        qs_failed = QualityScore(result=ResultQuality.FAILED)
        qs_ok = QualityScore(result=ResultQuality.TRUSTED)
        self.assertTrue(qs_failed.is_anti_pattern)
        self.assertFalse(qs_ok.is_anti_pattern)

    def test_net_evidence(self):
        qs = QualityScore(evidence_count=5, contradiction_count=2)
        self.assertEqual(qs.net_evidence, 3)

    def test_to_dict_and_from_dict_roundtrip(self):
        qs = QualityScore(
            source=SourceQuality.A, result=ResultQuality.VERIFIED,
            confidence=0.85, evidence_count=3, contradiction_count=1,
        )
        d = qs.to_dict()
        self.assertEqual(d["source"], "A")
        self.assertEqual(d["result"], "VERIFIED")
        self.assertAlmostEqual(d["confidence"], 0.85)
        qs2 = QualityScore.from_dict(d)
        self.assertEqual(qs2.source, SourceQuality.A)
        self.assertEqual(qs2.result, ResultQuality.VERIFIED)
        self.assertAlmostEqual(qs2.confidence, 0.85)
        self.assertEqual(qs2.evidence_count, 3)

    def test_to_dict_infinite_tau_is_none(self):
        qs = QualityScore(source=SourceQuality.S, result=ResultQuality.TRUSTED)
        d = qs.to_dict()
        self.assertIsNone(d["decay_tau_days"])

    def test_repr_contains_key_info(self):
        qs = QualityScore(source=SourceQuality.S, result=ResultQuality.VERIFIED)
        r = repr(qs)
        self.assertIn("S", r)
        self.assertIn("VERIFIED", r)


class TestQualityAssessor(unittest.TestCase):
    """QualityAssessor tests."""

    def setUp(self):
        self.assessor = QualityAssessor()

    def test_assess_source_official(self):
        self.assertEqual(
            self.assessor.assess_source("official documentation"),
            SourceQuality.A,
        )

    def test_assess_source_cross_check(self):
        self.assertEqual(
            self.assessor.assess_source("cross-checked with multiple sources"),
            SourceQuality.S,
        )

    def test_assess_source_reliable(self):
        self.assertEqual(
            self.assessor.assess_source("reliable secondary source"),
            SourceQuality.B,
        )

    def test_assess_source_uncertain(self):
        self.assertEqual(
            self.assessor.assess_source("single source, unverified"),
            SourceQuality.C,
        )

    def test_assess_source_speculative(self):
        self.assertEqual(
            self.assessor.assess_source("this is just a guess"),
            SourceQuality.D,
        )

    def test_assess_source_no_match_defaults_c(self):
        self.assertEqual(
            self.assessor.assess_source("some random text"),
            SourceQuality.C,
        )

    def test_assess_source_empty_defaults_c(self):
        self.assertEqual(self.assessor.assess_source(""), SourceQuality.C)

    def test_assess_source_higher_grade_wins(self):
        """When multiple keywords match, the higher grade wins."""
        # "official" (A) and "guess" (D) both present → A wins
        self.assertEqual(
            self.assessor.assess_source("official documentation but also a guess"),
            SourceQuality.A,
        )

    def test_assess_result_confirmed_verified(self):
        self.assertEqual(
            self.assessor.assess_result(confirmed=True),
            ResultQuality.VERIFIED,
        )

    def test_assess_result_success_trusted(self):
        self.assertEqual(
            self.assessor.assess_result(success=True),
            ResultQuality.TRUSTED,
        )

    def test_assess_result_failure(self):
        self.assertEqual(
            self.assessor.assess_result(success=False),
            ResultQuality.FAILED,
        )

    def test_assess_result_contradiction_overrides(self):
        self.assertEqual(
            self.assessor.assess_result(success=True, contradiction=True),
            ResultQuality.FAILED,
        )

    def test_assess_result_error_overrides(self):
        self.assertEqual(
            self.assessor.assess_result(success=True, error=True),
            ResultQuality.FAILED,
        )

    def test_assess_result_unknown_speculative(self):
        self.assertEqual(
            self.assessor.assess_result(),
            ResultQuality.SPECULATIVE,
        )

    def test_assess_result_confirmed_overrides_success(self):
        """confirmed=True → VERIFIED even if success=False."""
        self.assertEqual(
            self.assessor.assess_result(success=False, confirmed=True),
            ResultQuality.VERIFIED,
        )

    def test_full_assess(self):
        qs = self.assessor.assess(
            source_description="official API docs",
            confirmed=True,
            evidence_count=2,
        )
        self.assertEqual(qs.source, SourceQuality.A)
        self.assertEqual(qs.result, ResultQuality.VERIFIED)
        self.assertEqual(qs.evidence_count, 2)

    def test_full_assess_auto_counts(self):
        """confirmed=True with evidence_count=0 auto-sets evidence to 1."""
        qs = self.assessor.assess(
            source_description="official docs",
            confirmed=True,
        )
        self.assertGreaterEqual(qs.evidence_count, 1)

    def test_full_assess_contradiction_auto_count(self):
        qs = self.assessor.assess(
            source_description="official docs",
            contradiction=True,
        )
        self.assertGreaterEqual(qs.contradiction_count, 1)
        self.assertEqual(qs.result, ResultQuality.FAILED)

    def test_assess_from_dict(self):
        data = {
            "source_description": "peer-reviewed journal",
            "confirmed": True,
            "evidence_count": 3,
        }
        qs = self.assessor.assess_from_dict(data)
        self.assertEqual(qs.source, SourceQuality.A)
        self.assertEqual(qs.result, ResultQuality.VERIFIED)

    def test_assess_from_dict_direct_grades(self):
        data = {"source": "S", "result": "TRUSTED", "confidence": 0.9}
        qs = self.assessor.assess_from_dict(data)
        self.assertEqual(qs.source, SourceQuality.S)
        self.assertEqual(qs.result, ResultQuality.TRUSTED)
        self.assertAlmostEqual(qs.confidence, 0.9)

    def test_update_after_task_success(self):
        current = QualityScore(
            source=SourceQuality.B, result=ResultQuality.SPECULATIVE,
            confidence=0.4, evidence_count=1,
        )
        updated = self.assessor.update_after_task(
            current, success=True, new_evidence=1,
        )
        self.assertEqual(updated.result, ResultQuality.TRUSTED)
        self.assertEqual(updated.evidence_count, 2)
        self.assertGreater(updated.confidence, current.confidence)

    def test_update_after_task_failure_downgrades(self):
        current = QualityScore(
            source=SourceQuality.A, result=ResultQuality.TRUSTED,
            confidence=0.8, evidence_count=2,
        )
        updated = self.assessor.update_after_task(
            current, contradiction=True, new_contradictions=1,
        )
        self.assertEqual(updated.result, ResultQuality.FAILED)
        self.assertEqual(updated.contradiction_count, 1)
        self.assertLess(updated.confidence, current.confidence)

    def test_update_after_task_preserves_source(self):
        current = QualityScore(source=SourceQuality.S, result=ResultQuality.TRUSTED)
        updated = self.assessor.update_after_task(current, success=True)
        self.assertEqual(updated.source, SourceQuality.S)

    def test_update_after_task_confirmed_upgrades(self):
        current = QualityScore(
            source=SourceQuality.B, result=ResultQuality.TRUSTED,
            confidence=0.6, evidence_count=2,
        )
        updated = self.assessor.update_after_task(
            current, confirmed=True, new_evidence=1,
        )
        self.assertEqual(updated.result, ResultQuality.VERIFIED)
        self.assertEqual(updated.evidence_count, 3)


if __name__ == "__main__":
    unittest.main()
