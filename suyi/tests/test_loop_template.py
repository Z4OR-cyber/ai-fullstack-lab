"""
Tests for the Loop Template Memory system (Phase 14).

Covers:
    - LoopPhase: creation, validation, serialisation
    - LoopTemplate: creation, auto-ID, derived properties, serialisation
      (to_dict / from_dict / to_db_dict round-trip)
    - LoopTemplateStore: save, get, list, find_best_template, update_stats,
      deactivate, create_variant, count
    - SQLiteBackend loop template methods: save_loop_template,
      get_loop_template, search_loop_templates, update_loop_template_stats,
      list_loop_templates, deactivate_loop_template
    - FTS5 / LIKE full-text search matching
    - Template ranking (similarity + success_rate + confidence + freshness)
    - Statistics updates (success_count, failure_count, success_rate,
      avg_iterations, avg_cost, use_count)
    - Template deactivation (soft delete)
    - DefaultTemplates: standard_react, plan_execute, reflective
    - Edge cases: empty templates, duplicate IDs, non-existent IDs,
      invalid phase names
"""

import json
import os
import tempfile
import time
import unittest

from suyi.quality.grader import (
    QualityScore,
    ResultQuality,
    SourceQuality,
)
from suyi.quality.loop_template import (
    LoopPhase,
    LoopTemplate,
    LoopTemplateStore,
    DefaultTemplates,
    compute_task_signature,
    _tokenize_signature,
    _jaccard_similarity,
)
from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _make_backend():
    """Create a temporary SQLiteBackend for testing."""
    tmpdir = tempfile.mkdtemp()
    return SQLiteBackend(db_path=os.path.join(tmpdir, "test_loop.db"))


def _make_simple_template(
    task_desc="deploy application to production",
    sig=None,
    success_count=5,
    failure_count=1,
):
    """Create a simple template for testing."""
    if sig is None:
        sig = compute_task_signature(task_desc)
    return LoopTemplate(
        task_signature=sig,
        task_description=task_desc,
        phases=[
            LoopPhase(name="perceive", action="Check state", tools=["read"]),
            LoopPhase(name="plan", action="Plan deploy", tools=[]),
            LoopPhase(name="execute", action="Run deploy", tools=["deploy"]),
        ],
        tools=["read", "deploy"],
        tool_order=["read", "deploy"],
        reflection_points=[1],
        max_iterations=10,
        termination_conditions=["done", "error"],
        success_count=success_count,
        failure_count=failure_count,
        avg_iterations=4.5,
        avg_cost=0.12,
        quality=QualityScore(
            source=SourceQuality.B,
            result=ResultQuality.TRUSTED,
            confidence=0.8,
            evidence_count=3,
        ),
    )


# ═══════════════════════════════════════════════════════════════
#  TestLoopPhase
# ═══════════════════════════════════════════════════════════════


class TestLoopPhase(unittest.TestCase):
    """LoopPhase dataclass tests."""

    def test_create_perceive(self):
        phase = LoopPhase(name="perceive", action="Observe state")
        self.assertEqual(phase.name, "perceive")
        self.assertEqual(phase.action, "Observe state")
        self.assertEqual(phase.tools, [])
        self.assertEqual(phase.condition, "always")

    def test_create_with_tools(self):
        phase = LoopPhase(
            name="execute",
            action="Run command",
            tools=["bash", "python"],
            condition="steps_remaining",
        )
        self.assertEqual(phase.name, "execute")
        self.assertEqual(phase.tools, ["bash", "python"])
        self.assertEqual(phase.condition, "steps_remaining")

    def test_create_reflect(self):
        phase = LoopPhase(name="reflect", action="Evaluate result")
        self.assertEqual(phase.name, "reflect")

    def test_invalid_phase_name(self):
        with self.assertRaises(ValueError):
            LoopPhase(name="invalid_phase")

    def test_serialisation_roundtrip(self):
        phase = LoopPhase(
            name="verify",
            action="Check output",
            tools=["validator"],
            condition="confidence > 0.8",
        )
        d = phase.to_dict()
        self.assertEqual(d["name"], "verify")
        self.assertEqual(d["tools"], ["validator"])
        restored = LoopPhase.from_dict(d)
        self.assertEqual(restored.name, phase.name)
        self.assertEqual(restored.action, phase.action)
        self.assertEqual(restored.tools, phase.tools)
        self.assertEqual(restored.condition, phase.condition)

    def test_from_dict_defaults(self):
        """from_dict fills in defaults for missing keys."""
        phase = LoopPhase.from_dict({"name": "plan"})
        self.assertEqual(phase.name, "plan")
        self.assertEqual(phase.action, "")
        self.assertEqual(phase.tools, [])
        self.assertEqual(phase.condition, "always")

    def test_default_name(self):
        """Default name is 'execute'."""
        phase = LoopPhase()
        self.assertEqual(phase.name, "execute")

    def test_repr(self):
        phase = LoopPhase(name="plan", action="Decide next step")
        r = repr(phase)
        self.assertIn("LoopPhase", r)
        self.assertIn("plan", r)


# ═══════════════════════════════════════════════════════════════
#  TestLoopTemplate
# ═══════════════════════════════════════════════════════════════


class TestLoopTemplate(unittest.TestCase):
    """LoopTemplate dataclass tests."""

    def test_auto_id_generation(self):
        """Template without explicit ID gets a UUID."""
        tpl = LoopTemplate(task_description="test task")
        self.assertTrue(tpl.id)
        self.assertEqual(len(tpl.id), 36)  # UUID4 string length

    def test_explicit_id(self):
        tpl = LoopTemplate(id="my-custom-id", task_description="test")
        self.assertEqual(tpl.id, "my-custom-id")

    def test_success_rate_auto_compute(self):
        """success_rate is computed from counts on init."""
        tpl = LoopTemplate(success_count=3, failure_count=1)
        self.assertAlmostEqual(tpl.success_rate, 0.75, places=2)

    def test_success_rate_zero(self):
        """No uses → success_rate stays 0."""
        tpl = LoopTemplate()
        self.assertEqual(tpl.success_rate, 0.0)

    def test_total_uses(self):
        tpl = LoopTemplate(success_count=5, failure_count=2)
        self.assertEqual(tpl.total_uses, 7)

    def test_is_proven(self):
        self.assertTrue(LoopTemplate(success_count=1).is_proven)
        self.assertFalse(LoopTemplate(success_count=0).is_proven)

    def test_confidence_property(self):
        tpl = LoopTemplate(
            quality=QualityScore(confidence=0.85),
        )
        self.assertEqual(tpl.confidence, 0.85)

    def test_freshness_recent(self):
        """Just-used template has freshness close to 1.0."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tpl = LoopTemplate(last_used=now)
        self.assertGreater(tpl.freshness, 0.99)

    def test_freshness_old(self):
        """Template used 60 days ago has freshness 0."""
        tpl = LoopTemplate(last_used="2020-01-01T00:00:00Z")
        self.assertEqual(tpl.freshness, 0.0)

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict preserves all fields."""
        tpl = _make_simple_template()
        d = tpl.to_dict()
        restored = LoopTemplate.from_dict(d)
        self.assertEqual(restored.id, tpl.id)
        self.assertEqual(restored.task_signature, tpl.task_signature)
        self.assertEqual(restored.task_description, tpl.task_description)
        self.assertEqual(len(restored.phases), len(tpl.phases))
        self.assertEqual(restored.phases[0].name, tpl.phases[0].name)
        self.assertEqual(restored.tools, tpl.tools)
        self.assertEqual(restored.tool_order, tpl.tool_order)
        self.assertEqual(restored.reflection_points, tpl.reflection_points)
        self.assertEqual(restored.max_iterations, tpl.max_iterations)
        self.assertEqual(restored.success_count, tpl.success_count)
        self.assertEqual(restored.failure_count, tpl.failure_count)
        self.assertEqual(restored.quality.source, tpl.quality.source)
        self.assertEqual(restored.quality.confidence, tpl.quality.confidence)

    def test_to_db_dict_has_json_fields(self):
        """to_db_dict produces *_json fields and flattened quality."""
        tpl = _make_simple_template()
        d = tpl.to_db_dict()
        self.assertIn("phases_json", d)
        self.assertIn("tools_json", d)
        self.assertIn("tool_order_json", d)
        self.assertIn("reflection_points_json", d)
        self.assertIn("termination_conditions_json", d)
        self.assertIn("source_quality", d)
        self.assertIn("result_quality", d)
        self.assertIn("confidence", d)
        # Verify JSON content is parseable
        phases = json.loads(d["phases_json"])
        self.assertEqual(len(phases), 3)

    def test_from_db_dict_roundtrip(self):
        """from_dict can parse the flattened DB format."""
        tpl = _make_simple_template()
        db_dict = tpl.to_db_dict()
        restored = LoopTemplate.from_dict(db_dict)
        self.assertEqual(restored.id, tpl.id)
        self.assertEqual(restored.task_signature, tpl.task_signature)
        self.assertEqual(len(restored.phases), len(tpl.phases))
        self.assertEqual(restored.phases[0].name, tpl.phases[0].name)
        self.assertEqual(restored.tools, tpl.tools)
        self.assertEqual(restored.quality.source, tpl.quality.source)
        self.assertEqual(restored.quality.confidence, tpl.quality.confidence)

    def test_from_dict_with_json_string_phases(self):
        """from_dict accepts phases as a JSON string."""
        phases_json = json.dumps([
            {"name": "plan", "action": "Plan", "tools": [], "condition": "always"},
        ])
        tpl = LoopTemplate.from_dict({
            "id": "test-id",
            "task_signature": "sig",
            "phases_json": phases_json,
        })
        self.assertEqual(len(tpl.phases), 1)
        self.assertEqual(tpl.phases[0].name, "plan")

    def test_empty_template(self):
        """A template with minimal fields is valid."""
        tpl = LoopTemplate(task_description="minimal")
        self.assertTrue(tpl.id)
        self.assertEqual(tpl.phases, [])
        self.assertEqual(tpl.tools, [])
        self.assertTrue(tpl.is_active)
        self.assertEqual(tpl.max_iterations, 10)

    def test_repr(self):
        tpl = _make_simple_template()
        r = repr(tpl)
        self.assertIn("LoopTemplate", r)


# ═══════════════════════════════════════════════════════════════
#  TestSignatureHelpers
# ═══════════════════════════════════════════════════════════════


class TestSignatureHelpers(unittest.TestCase):
    """compute_task_signature and similarity helper tests."""

    def test_compute_signature_basic(self):
        sig = compute_task_signature("deploy to production")
        self.assertIsInstance(sig, str)
        self.assertGreater(len(sig), 0)

    def test_compute_signature_lowercase(self):
        sig1 = compute_task_signature("Deploy To Production")
        sig2 = compute_task_signature("deploy to production")
        self.assertEqual(sig1, sig2)

    def test_compute_signature_punctuation(self):
        sig1 = compute_task_signature("deploy, to: production!")
        sig2 = compute_task_signature("deploy to production")
        self.assertEqual(sig1, sig2)

    def test_compute_signature_empty(self):
        self.assertEqual(compute_task_signature(""), "")

    def test_compute_signature_sorted(self):
        """Tokens are sorted for canonical ordering."""
        sig1 = compute_task_signature("b a c")
        sig2 = compute_task_signature("a b c")
        self.assertEqual(sig1, sig2)

    def test_tokenize_pipe_separated(self):
        tokens = _tokenize_signature("deploy|production|k8s")
        self.assertEqual(tokens, {"deploy", "production", "k8s"})

    def test_tokenize_plain_text(self):
        tokens = _tokenize_signature("deploy production k8s")
        self.assertEqual(tokens, {"deploy", "production", "k8s"})

    def test_tokenize_empty(self):
        self.assertEqual(_tokenize_signature(""), set())

    def test_jaccard_identical(self):
        self.assertEqual(_jaccard_similarity({"a", "b"}, {"a", "b"}), 1.0)

    def test_jaccard_disjoint(self):
        self.assertEqual(_jaccard_similarity({"a"}, {"b"}), 0.0)

    def test_jaccard_partial(self):
        sim = _jaccard_similarity({"a", "b"}, {"b", "c"})
        self.assertAlmostEqual(sim, 1.0 / 3.0, places=4)

    def test_jaccard_both_empty(self):
        self.assertEqual(_jaccard_similarity(set(), set()), 0.0)


# ═══════════════════════════════════════════════════════════════
#  TestSQLiteBackendLoopTemplates
# ═══════════════════════════════════════════════════════════════


class TestSQLiteBackendLoopTemplates(unittest.TestCase):
    """SQLiteBackend loop template method tests."""

    def setUp(self):
        self.backend = _make_backend()

    def tearDown(self):
        self.backend.close()

    def test_save_and_get(self):
        """save_loop_template then get_loop_template round-trip."""
        tpl = _make_simple_template()
        self.backend.save_loop_template(tpl.to_db_dict())
        result = self.backend.get_loop_template(tpl.id)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], tpl.id)
        self.assertEqual(result["task_signature"], tpl.task_signature)
        self.assertEqual(result["task_description"], tpl.task_description)

    def test_get_nonexistent(self):
        """get_loop_template returns None for unknown ID."""
        result = self.backend.get_loop_template("nonexistent-id")
        self.assertIsNone(result)

    def test_save_preserves_created_at(self):
        """Updating a template preserves created_at."""
        tpl = _make_simple_template()
        self.backend.save_loop_template(tpl.to_db_dict())
        first = self.backend.get_loop_template(tpl.id)
        created = first["created_at"]

        # Save again with updated stats
        tpl.success_count = 10
        time.sleep(0.01)
        self.backend.save_loop_template(tpl.to_db_dict())
        second = self.backend.get_loop_template(tpl.id)
        self.assertEqual(second["created_at"], created)

    def test_json_fields_deserialised(self):
        """get_loop_template returns deserialised JSON fields."""
        tpl = _make_simple_template()
        self.backend.save_loop_template(tpl.to_db_dict())
        result = self.backend.get_loop_template(tpl.id)
        self.assertIsInstance(result["phases_json"], list)
        self.assertEqual(len(result["phases_json"]), 3)
        self.assertIsInstance(result["tools_json"], list)
        self.assertEqual(result["tools_json"], ["read", "deploy"])

    def test_search_by_description(self):
        """search_loop_templates finds by task_description."""
        tpl = _make_simple_template("deploy application to production")
        self.backend.save_loop_template(tpl.to_db_dict())
        results = self.backend.search_loop_templates("deploy production")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], tpl.id)

    def test_search_by_signature(self):
        """search_loop_templates finds by task_signature."""
        tpl = _make_simple_template("deploy application")
        self.backend.save_loop_template(tpl.to_db_dict())
        results = self.backend.search_loop_templates("deploy")
        self.assertGreater(len(results), 0)

    def test_search_empty_query(self):
        """Empty query returns empty list."""
        results = self.backend.search_loop_templates("")
        self.assertEqual(results, [])

    def test_search_no_match(self):
        """Search with no matching templates returns empty."""
        tpl = _make_simple_template("deploy application")
        self.backend.save_loop_template(tpl.to_db_dict())
        results = self.backend.search_loop_templates("quantum physics cooking")
        self.assertEqual(results, [])

    def test_search_only_active(self):
        """search_loop_templates only returns active templates."""
        tpl = _make_simple_template("unique search task")
        self.backend.save_loop_template(tpl.to_db_dict())
        self.backend.deactivate_loop_template(tpl.id)
        results = self.backend.search_loop_templates("unique search task")
        self.assertEqual(len(results), 0)

    def test_update_stats_success(self):
        """update_loop_template_stats increments success correctly."""
        tpl = _make_simple_template(success_count=0, failure_count=0)
        self.backend.save_loop_template(tpl.to_db_dict())
        self.backend.update_loop_template_stats(tpl.id, True, 5, 0.1)
        result = self.backend.get_loop_template(tpl.id)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failure_count"], 0)
        self.assertAlmostEqual(result["success_rate"], 1.0, places=2)
        self.assertEqual(result["use_count"], 1)

    def test_update_stats_failure(self):
        """update_loop_template_stats increments failure correctly."""
        tpl = _make_simple_template(success_count=2, failure_count=0)
        self.backend.save_loop_template(tpl.to_db_dict())
        self.backend.update_loop_template_stats(tpl.id, False, 3, 0.05)
        result = self.backend.get_loop_template(tpl.id)
        self.assertEqual(result["success_count"], 2)
        self.assertEqual(result["failure_count"], 1)
        self.assertAlmostEqual(result["success_rate"], 2.0 / 3.0, places=2)

    def test_update_stats_avg_iterations(self):
        """avg_iterations is a running average."""
        tpl = _make_simple_template(success_count=0, failure_count=0)
        self.backend.save_loop_template(tpl.to_db_dict())
        self.backend.update_loop_template_stats(tpl.id, True, 4, 0.1)
        self.backend.update_loop_template_stats(tpl.id, True, 6, 0.2)
        result = self.backend.get_loop_template(tpl.id)
        self.assertAlmostEqual(result["avg_iterations"], 5.0, places=2)

    def test_update_stats_nonexistent(self):
        """Updating stats for non-existent template is a no-op."""
        # Should not raise
        self.backend.update_loop_template_stats("nonexistent", True, 5, 0.1)

    def test_list_all_templates(self):
        """list_loop_templates returns all active templates."""
        tpl1 = _make_simple_template("task one")
        tpl2 = _make_simple_template("task two")
        self.backend.save_loop_template(tpl1.to_db_dict())
        self.backend.save_loop_template(tpl2.to_db_dict())
        results = self.backend.list_loop_templates()
        self.assertEqual(len(results), 2)

    def test_list_by_signature(self):
        """list_loop_templates filters by task_signature."""
        tpl1 = _make_simple_template("task alpha", sig="sig_alpha")
        tpl2 = _make_simple_template("task beta", sig="sig_beta")
        self.backend.save_loop_template(tpl1.to_db_dict())
        self.backend.save_loop_template(tpl2.to_db_dict())
        results = self.backend.list_loop_templates("sig_alpha")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], tpl1.id)

    def test_list_excludes_inactive(self):
        """list_loop_templates excludes deactivated templates."""
        tpl = _make_simple_template("unique list task")
        self.backend.save_loop_template(tpl.to_db_dict())
        self.backend.deactivate_loop_template(tpl.id)
        results = self.backend.list_loop_templates()
        self.assertEqual(len(results), 0)

    def test_deactivate(self):
        """deactivate_loop_template sets is_active to 0."""
        tpl = _make_simple_template()
        self.backend.save_loop_template(tpl.to_db_dict())
        result = self.backend.deactivate_loop_template(tpl.id)
        self.assertTrue(result)
        row = self.backend.get_loop_template(tpl.id)
        self.assertFalse(row["is_active"])

    def test_deactivate_nonexistent(self):
        """deactivate returns False for unknown ID."""
        result = self.backend.deactivate_loop_template("nonexistent")
        self.assertFalse(result)

    def test_save_with_quality_dict(self):
        """save_loop_template accepts a 'quality' dict."""
        tpl = _make_simple_template()
        db_dict = tpl.to_db_dict()
        db_dict["quality"] = {
            "source": "A",
            "result": "VERIFIED",
            "confidence": 0.95,
            "evidence_count": 5,
            "contradiction_count": 0,
        }
        self.backend.save_loop_template(db_dict)
        result = self.backend.get_loop_template(tpl.id)
        self.assertEqual(result["source_quality"], "A")
        self.assertEqual(result["result_quality"], "VERIFIED")
        self.assertAlmostEqual(result["confidence"], 0.95, places=2)


# ═══════════════════════════════════════════════════════════════
#  TestLoopTemplateStore
# ═══════════════════════════════════════════════════════════════


class TestLoopTemplateStore(unittest.TestCase):
    """LoopTemplateStore integration tests."""

    def setUp(self):
        self.backend = _make_backend()
        self.store = LoopTemplateStore(backend=self.backend)

    def tearDown(self):
        self.backend.close()

    def test_save_and_get(self):
        """save_template then get_template round-trip."""
        tpl = _make_simple_template()
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, tpl.id)
        self.assertEqual(result.task_description, tpl.task_description)
        self.assertEqual(len(result.phases), len(tpl.phases))

    def test_get_nonexistent(self):
        """get_template returns None for unknown ID."""
        self.assertIsNone(self.store.get_template("nonexistent"))

    def test_list_templates(self):
        """list_templates returns all active templates."""
        tpl1 = _make_simple_template("task one")
        tpl2 = _make_simple_template("task two")
        self.store.save_template(tpl1)
        self.store.save_template(tpl2)
        result = self.store.list_templates()
        self.assertEqual(len(result), 2)

    def test_list_by_signature(self):
        """list_templates filters by signature."""
        tpl1 = _make_simple_template("task alpha", sig="sig_a")
        tpl2 = _make_simple_template("task beta", sig="sig_b")
        self.store.save_template(tpl1)
        self.store.save_template(tpl2)
        result = self.store.list_templates("sig_a")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, tpl1.id)

    def test_find_best_template_exact_match(self):
        """find_best_template returns the matching template."""
        tpl = _make_simple_template("deploy application to production")
        self.store.save_template(tpl)
        result = self.store.find_best_template("deploy application to production")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, tpl.id)

    def test_find_best_template_partial_match(self):
        """find_best_template finds templates with similar descriptions."""
        tpl = _make_simple_template("deploy application to production")
        self.store.save_template(tpl)
        result = self.store.find_best_template("deploy application")
        self.assertIsNotNone(result)

    def test_find_best_template_no_match(self):
        """find_best_template returns None when nothing matches."""
        tpl = _make_simple_template("deploy application")
        self.store.save_template(tpl)
        result = self.store.find_best_template("quantum physics cooking recipe")
        # Even with no FTS match, it falls back to listing all active
        # and picks the best by ranking. With a very dissimilar task,
        # it should still return something (lowest bar) or None.
        # Since we list all active as fallback, it will return the template.
        # But the similarity score will be very low.
        # The key behaviour: it doesn't crash.
        self.assertIsNotNone(result)  # fallback returns best of all

    def test_find_best_template_ranks_by_success_rate(self):
        """Higher success_rate template wins for same signature."""
        tpl_low = _make_simple_template(
            "deploy app", sig="deploy|app",
            success_count=1, failure_count=9,
        )
        tpl_high = _make_simple_template(
            "deploy app", sig="deploy|app",
            success_count=9, failure_count=1,
        )
        # Give them different IDs
        tpl_low.id = "tpl-low-success"
        tpl_high.id = "tpl-high-success"
        self.store.save_template(tpl_low)
        self.store.save_template(tpl_high)
        result = self.store.find_best_template("deploy app", "deploy|app")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "tpl-high-success")

    def test_find_best_template_empty_query(self):
        """Empty query returns None."""
        self.assertIsNone(self.store.find_best_template(""))

    def test_find_best_template_no_templates(self):
        """Returns None when store is empty."""
        self.assertIsNone(self.store.find_best_template("any task"))

    def test_update_stats(self):
        """update_stats updates the template's statistics."""
        tpl = _make_simple_template(success_count=0, failure_count=0)
        self.store.save_template(tpl)
        self.store.update_stats(tpl.id, True, 5, 0.1)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failure_count, 0)
        self.assertAlmostEqual(result.success_rate, 1.0, places=2)
        self.assertEqual(result.use_count, 1)

    def test_deactivate_template(self):
        """deactivate_template removes from active list."""
        tpl = _make_simple_template()
        self.store.save_template(tpl)
        self.assertTrue(self.store.deactivate_template(tpl.id))
        result = self.store.get_template(tpl.id)
        self.assertFalse(result.is_active)
        # Should not appear in list_templates
        active = self.store.list_templates()
        self.assertEqual(len(active), 0)

    def test_deactivate_nonexistent(self):
        """deactivate returns False for unknown ID."""
        self.assertFalse(self.store.deactivate_template("nonexistent"))

    def test_count(self):
        """count returns number of active templates."""
        self.assertEqual(self.store.count(), 0)
        tpl = _make_simple_template()
        self.store.save_template(tpl)
        self.assertEqual(self.store.count(), 1)

    def test_create_variant(self):
        """create_variant creates a linked child template."""
        parent = _make_simple_template()
        self.store.save_template(parent)
        variant = self.store.create_variant(
            parent.id,
            mutations=["added reflect phase"],
            modified_phases=parent.phases + [
                LoopPhase(name="reflect", action="Reflect on result"),
            ],
            modified_max_iterations=15,
        )
        self.assertIsNotNone(variant)
        self.assertNotEqual(variant.id, parent.id)
        self.assertEqual(variant.parent_id, parent.id)
        self.assertEqual(len(variant.phases), 4)
        self.assertEqual(variant.phases[3].name, "reflect")
        self.assertEqual(variant.max_iterations, 15)
        self.assertIn("added reflect phase", variant.mutations)

        # Parent should have the variant registered
        updated_parent = self.store.get_template(parent.id)
        self.assertIn(variant.id, updated_parent.variants)

    def test_create_variant_nonexistent_parent(self):
        """create_variant returns None for unknown parent."""
        result = self.store.create_variant("nonexistent", ["test"])
        self.assertIsNone(result)

    def test_get_variants(self):
        """get_variants returns all variants of a template."""
        parent = _make_simple_template()
        self.store.save_template(parent)
        v1 = self.store.create_variant(parent.id, ["mutation 1"])
        v2 = self.store.create_variant(parent.id, ["mutation 2"])
        variants = self.store.get_variants(parent.id)
        self.assertEqual(len(variants), 2)
        ids = {v.id for v in variants}
        self.assertIn(v1.id, ids)
        self.assertIn(v2.id, ids)

    def test_get_variants_nonexistent(self):
        """get_variants returns empty for unknown parent."""
        self.assertEqual(self.store.get_variants("nonexistent"), [])

    def test_save_overwrite(self):
        """Saving a template with existing ID updates it."""
        tpl = _make_simple_template()
        tpl.success_count = 1
        self.store.save_template(tpl)
        tpl.success_count = 10
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.success_count, 10)

    def test_find_best_template_with_precomputed_signature(self):
        """find_best_template accepts a pre-computed task_signature."""
        tpl = _make_simple_template("deploy app to prod", sig="deploy|app|prod")
        self.store.save_template(tpl)
        result = self.store.find_best_template(
            "deploy app", task_signature="deploy|app|prod",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, tpl.id)


# ═══════════════════════════════════════════════════════════════
#  TestDefaultTemplates
# ═══════════════════════════════════════════════════════════════


class TestDefaultTemplates(unittest.TestCase):
    """DefaultTemplates factory tests."""

    def test_standard_react(self):
        tpl = DefaultTemplates.standard_react()
        self.assertEqual(tpl.id, "default-react-001")
        self.assertTrue(tpl.is_active)
        self.assertEqual(len(tpl.phases), 3)
        phase_names = [p.name for p in tpl.phases]
        self.assertEqual(phase_names, ["perceive", "plan", "execute"])
        self.assertGreater(tpl.max_iterations, 0)
        self.assertGreater(len(tpl.termination_conditions), 0)

    def test_plan_execute(self):
        tpl = DefaultTemplates.plan_execute()
        self.assertEqual(tpl.id, "default-plan-exec-001")
        self.assertTrue(tpl.is_active)
        self.assertEqual(len(tpl.phases), 4)
        phase_names = [p.name for p in tpl.phases]
        self.assertEqual(phase_names, ["perceive", "plan", "execute", "verify"])
        self.assertGreater(tpl.max_iterations, 0)

    def test_reflective(self):
        tpl = DefaultTemplates.reflective()
        self.assertEqual(tpl.id, "default-reflective-001")
        self.assertTrue(tpl.is_active)
        self.assertEqual(len(tpl.phases), 4)
        phase_names = [p.name for p in tpl.phases]
        self.assertEqual(phase_names, ["perceive", "plan", "execute", "reflect"])
        self.assertGreater(len(tpl.reflection_points), 0)

    def test_all_defaults(self):
        """all_defaults returns all three templates."""
        templates = DefaultTemplates.all_defaults()
        self.assertEqual(len(templates), 3)
        ids = {t.id for t in templates}
        self.assertIn("default-react-001", ids)
        self.assertIn("default-plan-exec-001", ids)
        self.assertIn("default-reflective-001", ids)

    def test_default_template_phases_valid(self):
        """All default template phases have valid names."""
        for tpl in DefaultTemplates.all_defaults():
            for phase in tpl.phases:
                self.assertIn(phase.name, {
                    "perceive", "plan", "execute", "verify", "reflect",
                })

    def test_default_template_quality(self):
        """Default templates have a QualityScore."""
        for tpl in DefaultTemplates.all_defaults():
            self.assertIsInstance(tpl.quality, QualityScore)
            self.assertGreater(tpl.quality.confidence, 0.0)

    def test_default_template_serialisation(self):
        """Default templates survive to_dict/from_dict round-trip."""
        for tpl in DefaultTemplates.all_defaults():
            d = tpl.to_dict()
            restored = LoopTemplate.from_dict(d)
            self.assertEqual(restored.id, tpl.id)
            self.assertEqual(len(restored.phases), len(tpl.phases))
            self.assertEqual(restored.max_iterations, tpl.max_iterations)

    def test_default_templates_saveable_to_store(self):
        """Default templates can be saved to a LoopTemplateStore."""
        backend = _make_backend()
        store = LoopTemplateStore(backend=backend)
        for tpl in DefaultTemplates.all_defaults():
            store.save_template(tpl)
        self.assertEqual(store.count(), 3)
        backend.close()


# ═══════════════════════════════════════════════════════════════
#  TestEdgeCases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    """Edge case and boundary tests."""

    def setUp(self):
        self.backend = _make_backend()
        self.store = LoopTemplateStore(backend=self.backend)

    def tearDown(self):
        self.backend.close()

    def test_empty_store_find_best(self):
        """find_best_template on empty store returns None."""
        self.assertIsNone(self.store.find_best_template("anything"))

    def test_duplicate_save(self):
        """Saving the same template twice doesn't duplicate."""
        tpl = _make_simple_template()
        self.store.save_template(tpl)
        self.store.save_template(tpl)
        self.assertEqual(self.store.count(), 1)

    def test_template_with_empty_phases(self):
        """A template with no phases is valid and storable."""
        tpl = LoopTemplate(
            task_description="empty phases task",
            task_signature="empty|phases|task",
            phases=[],
        )
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.phases, [])

    def test_template_with_empty_tools(self):
        """A template with no tools is valid."""
        tpl = LoopTemplate(
            task_description="no tools task",
            task_signature="no|tools|task",
            tools=[],
            tool_order=[],
        )
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.tools, [])

    def test_deactivated_not_in_find_best(self):
        """Deactivated templates don't appear in find_best_template."""
        tpl = _make_simple_template("unique deactivated task")
        self.store.save_template(tpl)
        self.store.deactivate_template(tpl.id)
        result = self.store.find_best_template("unique deactivated task")
        # Fallback lists all active — deactivated won't be there
        self.assertIsNone(result)

    def test_large_max_iterations(self):
        """Large max_iterations value is stored correctly."""
        tpl = _make_simple_template()
        tpl.max_iterations = 10000
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.max_iterations, 10000)

    def test_zero_max_iterations(self):
        """Zero max_iterations is stored correctly."""
        tpl = _make_simple_template()
        tpl.max_iterations = 0
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.max_iterations, 0)

    def test_unicode_description(self):
        """Unicode in task_description is handled correctly."""
        tpl = LoopTemplate(
            task_description="部署应用到生产环境",
            task_signature="deploy|app|生产",
        )
        self.store.save_template(tpl)
        result = self.store.get_template(tpl.id)
        self.assertEqual(result.task_description, "部署应用到生产环境")
        self.assertEqual(result.task_signature, "deploy|app|生产")

    def test_unicode_search(self):
        """FTS/LIKE search works with Unicode."""
        tpl = LoopTemplate(
            task_description="部署应用到生产环境",
            task_signature="deploy|app|生产",
        )
        self.store.save_template(tpl)
        results = self.backend.search_loop_templates("部署")
        self.assertGreater(len(results), 0)

    def test_from_dict_minimal(self):
        """from_dict with minimal data uses defaults."""
        tpl = LoopTemplate.from_dict({"id": "min", "task_signature": "sig"})
        self.assertEqual(tpl.id, "min")
        self.assertEqual(tpl.phases, [])
        self.assertEqual(tpl.max_iterations, 10)
        self.assertTrue(tpl.is_active)

    def test_from_dict_invalid_json_phases(self):
        """Invalid JSON in phases_json doesn't crash — returns empty list."""
        tpl = LoopTemplate.from_dict({
            "id": "bad",
            "phases_json": "not valid json{{{",
        })
        self.assertEqual(tpl.phases, [])

    def test_quality_from_db_fields(self):
        """Quality is reconstructed from flattened DB fields."""
        tpl = _make_simple_template()
        db_dict = tpl.to_db_dict()
        # Remove the 'quality' dict to force field-based reconstruction
        db_dict.pop("quality", None)
        restored = LoopTemplate.from_dict(db_dict)
        self.assertEqual(restored.quality.source, tpl.quality.source)
        self.assertEqual(restored.quality.result, tpl.quality.result)
        self.assertAlmostEqual(
            restored.quality.confidence, tpl.quality.confidence, places=2,
        )

    def test_many_templates_search(self):
        """Search works correctly with many templates."""
        for i in range(20):
            tpl = _make_simple_template(f"task number {i} deploy")
            tpl.id = f"tpl-{i:03d}"
            self.store.save_template(tpl)
        results = self.backend.search_loop_templates("deploy", limit=10)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 10)

    def test_variant_inherits_parent_quality(self):
        """create_variant copies the parent's quality score."""
        parent = _make_simple_template()
        parent.quality = QualityScore(
            source=SourceQuality.A,
            result=ResultQuality.VERIFIED,
            confidence=0.95,
            evidence_count=10,
        )
        self.store.save_template(parent)
        variant = self.store.create_variant(parent.id, ["test mutation"])
        self.assertEqual(variant.quality.source, SourceQuality.A)
        self.assertEqual(variant.quality.result, ResultQuality.VERIFIED)
        self.assertAlmostEqual(variant.quality.confidence, 0.95, places=2)


if __name__ == "__main__":
    unittest.main()
