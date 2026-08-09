"""
Tests for the Anti-Pattern Memory system (Phase 13).

Covers:
    - compute_signature: normalisation, tool/error/param inclusion
    - AntiPattern: creation, severity, retrieval_priority, resolution, serialisation
    - AntiPatternStore: register, check_anti_pattern, check_task,
      retrieve, resolve, queries, never-delete guarantee, serialisation
"""

import time
import unittest

from suyi.quality.anti_pattern import (
    AntiPattern,
    AntiPatternStore,
    compute_signature,
)
from suyi.quality.grader import (
    QualityScore,
    ResultQuality,
    SourceQuality,
)


class TestComputeSignature(unittest.TestCase):
    """compute_signature tests."""

    def test_basic_signature(self):
        sig = compute_signature("deploy to production")
        self.assertIsInstance(sig, str)
        self.assertGreater(len(sig), 0)

    def test_lowercase_normalisation(self):
        sig1 = compute_signature("Deploy To Production")
        sig2 = compute_signature("deploy to production")
        self.assertEqual(sig1, sig2)

    def test_punctuation_removed(self):
        sig1 = compute_signature("deploy, to: production!")
        sig2 = compute_signature("deploy to production")
        self.assertEqual(sig1, sig2)

    def test_whitespace_collapsed(self):
        sig1 = compute_signature("deploy   to    production")
        sig2 = compute_signature("deploy to production")
        self.assertEqual(sig1, sig2)

    def test_tool_names_included(self):
        sig = compute_signature("deploy", tool_names=["kubectl", "helm"])
        self.assertIn("tool:kubectl", sig)
        self.assertIn("tool:helm", sig)

    def test_error_type_included(self):
        sig = compute_signature("deploy", error_type="OOMKilled")
        self.assertIn("error:oomkilled", sig)

    def test_key_params_included(self):
        sig = compute_signature("deploy", key_params={"env": "prod", "replicas": 3})
        self.assertIn("param:env=prod", sig)
        self.assertIn("param:replicas=3", sig)

    def test_canonical_ordering(self):
        """Same params in different order → same signature."""
        sig1 = compute_signature("deploy", key_params={"a": 1, "b": 2})
        sig2 = compute_signature("deploy", key_params={"b": 2, "a": 1})
        self.assertEqual(sig1, sig2)

    def test_empty_description(self):
        sig = compute_signature("")
        self.assertEqual(sig, "")

    def test_empty_with_tools(self):
        sig = compute_signature("", tool_names=["kubectl"])
        self.assertIn("tool:kubectl", sig)


class TestAntiPattern(unittest.TestCase):
    """AntiPattern dataclass tests."""

    def test_basic_creation(self):
        ap = AntiPattern(
            task_signature="deploy|to|prod",
            pattern_description="OOM during deploy",
        )
        self.assertEqual(ap.task_signature, "deploy|to|prod")
        self.assertEqual(ap.failure_count, 1)
        self.assertFalse(ap.is_resolved)

    def test_auto_id_generation(self):
        ap = AntiPattern(task_signature="test_sig")
        self.assertGreater(len(ap.id), 0)

    def test_quality_always_failed(self):
        """AntiPattern always has FAILED result quality."""
        ap = AntiPattern(
            task_signature="sig",
            quality=QualityScore(result=ResultQuality.TRUSTED),
        )
        self.assertEqual(ap.quality.result, ResultQuality.FAILED)

    def test_increment_failure(self):
        ap = AntiPattern(task_signature="sig")
        initial_count = ap.failure_count
        ap.increment_failure()
        self.assertEqual(ap.failure_count, initial_count + 1)

    def test_increment_updates_last_seen(self):
        ap = AntiPattern(task_signature="sig")
        old_last = ap.last_seen
        time.sleep(0.01)
        ap.increment_failure()
        self.assertGreater(ap.last_seen, old_last)

    def test_severity_increases_with_failures(self):
        ap = AntiPattern(task_signature="sig")
        initial_severity = ap.severity
        ap.increment_failure()
        ap.increment_failure()
        self.assertGreater(ap.severity, initial_severity)

    def test_resolve_lowers_severity(self):
        ap = AntiPattern(task_signature="sig")
        initial_severity = ap.severity
        ap.resolve("Fixed by increasing memory limit")
        self.assertTrue(ap.is_resolved)
        self.assertLess(ap.severity, initial_severity)
        self.assertEqual(ap.resolution, "Fixed by increasing memory limit")

    def test_retrieval_priority_high(self):
        """Anti-patterns have high retrieval priority (>= 0.5)."""
        ap = AntiPattern(task_signature="sig")
        self.assertGreaterEqual(ap.retrieval_priority, 0.5)

    def test_retrieval_priority_le_one(self):
        ap = AntiPattern(task_signature="sig")
        self.assertLessEqual(ap.retrieval_priority, 1.0)

    def test_to_dict_and_from_dict(self):
        ap = AntiPattern(
            task_signature="test|sig",
            pattern_description="test failure",
            failure_count=3,
        )
        d = ap.to_dict()
        ap2 = AntiPattern.from_dict(d)
        self.assertEqual(ap2.task_signature, "test|sig")
        self.assertEqual(ap2.failure_count, 3)
        self.assertEqual(ap2.pattern_description, "test failure")

    def test_is_anti_pattern_always_true(self):
        ap = AntiPattern(task_signature="sig")
        self.assertTrue(ap.is_anti_pattern)

    def test_repr_contains_key_info(self):
        ap = AntiPattern(task_signature="deploy|prod", pattern_description="OOM")
        r = repr(ap)
        self.assertIn("AntiPattern", r)


class TestAntiPatternStore(unittest.TestCase):
    """AntiPatternStore tests."""

    def setUp(self):
        self.store = AntiPatternStore()

    def test_empty_store(self):
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(len(self.store), 0)

    def test_register_new(self):
        ap = self.store.register(
            task_signature="deploy|prod",
            pattern_description="OOM error",
        )
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(ap.failure_count, 1)
        self.assertEqual(ap.pattern_description, "OOM error")

    def test_register_existing_increments(self):
        self.store.register("deploy|prod", "first failure")
        ap = self.store.register("deploy|prod", "second failure")
        self.assertEqual(ap.failure_count, 2)
        self.assertIn("first failure", ap.pattern_description)
        self.assertIn("second failure", ap.pattern_description)

    def test_register_from_failure(self):
        ap = self.store.register_from_failure(
            task_description="deploy to prod",
            error_message="OOMKilled",
            tool_names=["kubectl"],
            error_type="OOM",
        )
        self.assertGreater(len(ap.task_signature), 0)
        self.assertIn("OOMKilled", ap.pattern_description)
        self.assertEqual(self.store.count(), 1)

    def test_check_anti_pattern_match(self):
        self.store.register("deploy|prod", "failure")
        self.assertTrue(self.store.check_anti_pattern("deploy|prod"))

    def test_check_anti_pattern_no_match(self):
        self.store.register("deploy|prod", "failure")
        self.assertFalse(self.store.check_anti_pattern("unknown|sig"))

    def test_check_anti_pattern_empty_store(self):
        self.assertFalse(self.store.check_anti_pattern("anything"))

    def test_check_task_convenience(self):
        self.store.register_from_failure(
            task_description="deploy to prod",
            error_message="OOM",
            tool_names=["kubectl"],
        )
        self.assertTrue(self.store.check_task(
            "deploy to prod", tool_names=["kubectl"],
        ))

    def test_check_task_no_match(self):
        self.store.register_from_failure("deploy to prod", "OOM")
        self.assertFalse(self.store.check_task("completely different task"))

    def test_get_matching_patterns_exact(self):
        self.store.register("deploy|prod", "failure 1")
        matches = self.store.get_matching_patterns("deploy|prod")
        self.assertEqual(len(matches), 1)

    def test_get_matching_patterns_partial(self):
        self.store.register("deploy|prod|kubectl", "failure 1")
        # Partial overlap should match
        matches = self.store.get_matching_patterns("deploy|prod|helm")
        self.assertGreaterEqual(len(matches), 1)

    def test_get_matching_patterns_sorted_by_severity(self):
        self.store.register("deploy|prod", "f1")
        ap = self.store.register("deploy|prod", "f2")  # increment
        ap = self.store.register("deploy|prod", "f3")  # increment again
        self.store.register("scale|down", "f4")
        matches = self.store.get_matching_patterns("deploy|prod")
        if len(matches) > 1:
            self.assertGreaterEqual(matches[0].severity, matches[1].severity)

    def test_retrieve_with_signature(self):
        self.store.register("deploy|prod", "failure")
        results = self.store.retrieve(task_signature="deploy|prod")
        self.assertGreater(len(results), 0)

    def test_retrieve_without_signature(self):
        self.store.register("deploy|prod", "failure 1")
        self.store.register("scale|down", "failure 2")
        results = self.store.retrieve()
        self.assertEqual(len(results), 2)

    def test_retrieve_top_k(self):
        for i in range(5):
            self.store.register(f"sig_{i}", f"failure {i}")
        results = self.store.retrieve(top_k=2)
        self.assertEqual(len(results), 2)

    def test_retrieve_excludes_resolved_by_default(self):
        self.store.register("deploy|prod", "failure")
        self.store.resolve("deploy|prod", "fixed")
        results = self.store.retrieve()
        self.assertEqual(len(results), 0)

    def test_retrieve_includes_resolved_when_requested(self):
        self.store.register("deploy|prod", "failure")
        self.store.resolve("deploy|prod", "fixed")
        results = self.store.retrieve(include_resolved=True)
        self.assertEqual(len(results), 1)

    def test_resolve_by_signature(self):
        self.store.register("deploy|prod", "failure")
        self.assertTrue(self.store.resolve("deploy|prod", "fixed it"))
        ap = self.store.get_by_signature("deploy|prod")
        self.assertTrue(ap.is_resolved)

    def test_resolve_by_id(self):
        ap = self.store.register("deploy|prod", "failure")
        self.assertTrue(self.store.resolve_by_id(ap.id, "fixed"))
        self.assertTrue(ap.is_resolved)

    def test_resolve_nonexistent(self):
        self.assertFalse(self.store.resolve("nonexistent", "fix"))

    def test_get_by_id(self):
        ap = self.store.register("deploy|prod", "failure")
        found = self.store.get_by_id(ap.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.task_signature, "deploy|prod")

    def test_get_by_id_not_found(self):
        self.assertIsNone(self.store.get_by_id("nonexistent"))

    def test_get_by_signature(self):
        self.store.register("deploy|prod", "failure")
        ap = self.store.get_by_signature("deploy|prod")
        self.assertIsNotNone(ap)

    def test_get_by_signature_not_found(self):
        self.assertIsNone(self.store.get_by_signature("nonexistent"))

    def test_get_all(self):
        self.store.register("sig1", "f1")
        self.store.register("sig2", "f2")
        all_patterns = self.store.get_all()
        self.assertEqual(len(all_patterns), 2)

    def test_get_unresolved(self):
        self.store.register("sig1", "f1")
        self.store.register("sig2", "f2")
        self.store.resolve("sig1", "fixed")
        unresolved = self.store.get_unresolved()
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].task_signature, "sig2")

    def test_get_high_severity(self):
        ap = self.store.register("sig1", "f1")
        for _ in range(5):
            ap.increment_failure()
        high = self.store.get_high_severity(threshold=0.5)
        self.assertGreater(len(high), 0)

    def test_count_unresolved(self):
        self.store.register("sig1", "f1")
        self.store.register("sig2", "f2")
        self.store.resolve("sig1", "fixed")
        self.assertEqual(self.store.count_unresolved(), 1)

    def test_never_delete_guarantee(self):
        """The store has no delete method and raises if attempted."""
        self.store.register("sig1", "f1")
        with self.assertRaises(NotImplementedError):
            self.store._delete_is_forbidden()

    def test_serialisation_roundtrip(self):
        self.store.register("sig1", "failure 1")
        self.store.register("sig2", "failure 2")
        d = self.store.to_dict()
        store2 = AntiPatternStore.from_dict(d)
        self.assertEqual(store2.count(), 2)
        self.assertTrue(store2.check_anti_pattern("sig1"))

    def test_init_with_patterns(self):
        ap1 = AntiPattern(task_signature="sig1", pattern_description="f1")
        ap2 = AntiPattern(task_signature="sig2", pattern_description="f2")
        store = AntiPatternStore(patterns=[ap1, ap2])
        self.assertEqual(store.count(), 2)

    def test_repr(self):
        self.store.register("sig1", "f1")
        r = repr(self.store)
        self.assertIn("AntiPatternStore", r)
        self.assertIn("total=1", r)


if __name__ == "__main__":
    unittest.main()
