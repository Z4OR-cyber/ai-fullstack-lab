"""
Evolution Report Generator — structured reporting for bilevel loop evolution.

This module implements Phase 17 of the ALA (Adaptive Loop Architecture)
self-evolution system.  It provides a :class:`EvolutionReportGenerator`
that accepts a :class:`BilevelLoop` after it has run one or more tasks
and produces a comprehensive, structured evolution report.

Report sections
---------------

1.  **Task Overview** — total tasks, success/failure counts, overall
    success rate, total iterations, total token cost.
2.  **Template Evolution Timeline** — templates created, variants
    produced, and how template statistics changed over the run.
3.  **Forgetting Engine Summary** — memory evaluation actions
    (DEGRADE / COMPRESS / PURGE) and their counts.
4.  **Strategy Mutation History** — mutations proposed, applied,
    target dimensions, and expected improvements.
5.  **A/B Experiment Results** — experiments created, sample counts,
    success rates, statistical significance, and winners.
6.  **Performance Comparison** — before vs. after metrics (first half
    vs. second half of the run): success rate, avg iterations, avg
    token cost.
7.  **Key Findings** — automated analysis of the evolution data,
    highlighting trends, warnings, and notable events.
8.  **Recommendations** — actionable suggestions for further
    improvement.

Output formats
--------------

- :meth:`EvolutionReport.to_dict` — Python dict (JSON-serialisable).
- :meth:`EvolutionReport.to_markdown` — Markdown string.
- :meth:`EvolutionReport.to_json` — JSON string.
- :meth:`EvolutionReport.save_to_file` — write to a file path.

Design principles
-----------------

- **Pure Python + stdlib** — no new external dependencies.
- **Non-invasive** — reads data from the BilevelLoop and its
  sub-components without modifying any state.
- **Resilient** — gracefully handles missing data (e.g., when no
  mutations occurred or no experiments were created).
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .bilevel_loop import (
    BilevelLoop,
    TaskResult,
    ExecutionLog,
    ExecutionLogEntry,
    TriggerType,
)
from .grader import QualityScore, ResultQuality, SourceQuality
from .forgetting import ForgettingAction, ForgettingEngine, MemoryRecord
from .anti_pattern import AntiPattern, AntiPatternStore
from .loop_template import LoopTemplate, LoopTemplateStore
from .strategy_evolver import (
    ProcessReflection,
    MutationType,
    StrategyEvolver,
    Experiment,
    ExperimentResult,
    ABTestFramework,
)


# ═══════════════════════════════════════════════════════════════
#  EvolutionReport — the report container
# ═══════════════════════════════════════════════════════════════


class EvolutionReport:
    """A structured evolution report with multiple output formats.

    Created by :class:`EvolutionReportGenerator.generate`.  Stores
    the report data as a plain dict and provides convenience methods
    for serialisation.

    Attributes:
        data: The full report data dict.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data: Dict[str, Any] = data

    # ------------------------------------------------------------------
    #  Output formats
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Return the report as a JSON-serialisable dict."""
        return self._data

    def to_json(self, indent: int = 2) -> str:
        """Return the report as a JSON string.

        Args:
            indent: Number of spaces for indentation.

        Returns:
            A JSON string representation of the report.
        """
        return json.dumps(self._data, indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Return the report as a Markdown string.

        The markdown includes all sections: task overview, template
        evolution, forgetting summary, mutation history, A/B results,
        performance comparison, key findings, and recommendations.
        """
        d = self._data
        lines: List[str] = []

        # ── Header ──────────────────────────────────────────────
        lines.append("# Evolution Report")
        lines.append("")
        lines.append(f"> Generated at: {d.get('generated_at', 'N/A')}")
        lines.append(f"> Total tasks: {d.get('task_overview', {}).get('total_tasks', 0)}")
        lines.append(f"> Evolution cycles: {d.get('task_overview', {}).get('evolution_cycles', 0)}")
        lines.append("")

        # ── 1. Task Overview ────────────────────────────────────
        overview = d.get("task_overview", {})
        lines.append("## 1. Task Overview")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total tasks | {overview.get('total_tasks', 0)} |")
        lines.append(f"| Successful | {overview.get('successful', 0)} |")
        lines.append(f"| Failed | {overview.get('failed', 0)} |")
        lines.append(f"| Success rate | {overview.get('success_rate', 0.0):.1%} |")
        lines.append(f"| Total iterations | {overview.get('total_iterations', 0)} |")
        lines.append(f"| Total token cost | {overview.get('total_token_cost', 0.0):.1f} |")
        lines.append(f"| Avg iterations/task | {overview.get('avg_iterations', 0.0):.2f} |")
        lines.append(f"| Avg token cost/task | {overview.get('avg_token_cost', 0.0):.1f} |")
        lines.append(f"| Evolution cycles | {overview.get('evolution_cycles', 0)} |")
        lines.append(f"| Active templates | {overview.get('active_templates', 0)} |")
        lines.append("")

        # ── 2. Template Evolution Timeline ──────────────────────
        timeline = d.get("template_evolution", {})
        lines.append("## 2. Template Evolution Timeline")
        lines.append("")
        lines.append(f"- Total templates: {timeline.get('total_templates', 0)}")
        lines.append(f"- Default templates: {timeline.get('default_templates', 0)}")
        lines.append(f"- Variant templates: {timeline.get('variant_templates', 0)}")
        lines.append(f"- Templates with successful uses: {timeline.get('proven_templates', 0)}")
        lines.append("")

        templates = timeline.get("templates", [])
        if templates:
            lines.append("| Template ID | Signature | Uses | Success Rate | Phases | Parent |")
            lines.append("|-------------|-----------|------|--------------|--------|--------|")
            for t in templates:
                tid = t.get("id", "")[:12]
                sig = t.get("task_signature", "")[:30]
                uses = t.get("use_count", 0)
                sr = t.get("success_rate", 0.0)
                phases = t.get("phase_count", 0)
                parent = t.get("parent_id", "") or "—"
                parent = parent[:12] if parent else "—"
                lines.append(f"| {tid} | {sig} | {uses} | {sr:.0%} | {phases} | {parent} |")
            lines.append("")

        # ── 3. Forgetting Engine Summary ────────────────────────
        forgetting = d.get("forgetting_summary", {})
        lines.append("## 3. Forgetting Engine Summary")
        lines.append("")
        lines.append("| Action | Count |")
        lines.append("|--------|-------|")
        actions = forgetting.get("actions", {})
        for action_name in ("DEGRADE", "COMPRESS", "PURGE"):
            count = actions.get(action_name, 0)
            lines.append(f"| {action_name} | {count} |")
        lines.append(f"| **Total evaluated** | {forgetting.get('total_evaluated', 0)} |")
        lines.append("")
        if forgetting.get("compress_count", 0) > 0:
            lines.append(f"> {forgetting['compress_count']} memory(ies) were compressed (episodic to semantic).")
            lines.append("")

        # ── 4. Strategy Mutation History ────────────────────────
        mutations = d.get("mutation_history", {})
        lines.append("## 4. Strategy Mutation History")
        lines.append("")
        lines.append(f"- Total mutations: {mutations.get('total_mutations', 0)}")
        mutation_types = mutations.get("mutation_types", {})
        if mutation_types:
            lines.append(f"- Mutation type breakdown:")
            for mt, count in sorted(mutation_types.items()):
                lines.append(f"  - {mt}: {count}")
        lines.append("")

        records = mutations.get("records", [])
        if records:
            lines.append("| # | Type | Target Dimension | Expected Improvement | Composite Score |")
            lines.append("|---|------|-------------------|---------------------|-----------------|")
            for i, m in enumerate(records, 1):
                mt = m.get("mutation_type", "")
                dim = m.get("target_dimension", "")
                ei = m.get("expected_improvement", 0.0)
                cs = m.get("reflection_composite", 0.0)
                lines.append(f"| {i} | {mt} | {dim} | {ei:.2f} | {cs:.2f} |")
            lines.append("")

        # ── 5. A/B Experiment Results ───────────────────────────
        ab_tests = d.get("ab_test_results", {})
        lines.append("## 5. A/B Experiment Results")
        lines.append("")
        lines.append(f"- Total experiments: {ab_tests.get('total_experiments', 0)}")
        lines.append(f"- Completed: {ab_tests.get('completed', 0)}")
        lines.append(f"- Running: {ab_tests.get('running', 0)}")
        lines.append("")

        experiments = ab_tests.get("experiments", [])
        if experiments:
            lines.append("| Experiment | Control SR | Variant SR | Significant | Winner |")
            lines.append("|------------|------------|------------|-------------|--------|")
            for exp in experiments:
                name = exp.get("name", "")[:20]
                ctrl_sr = exp.get("control_success_rate", 0.0)
                var_sr = exp.get("variant_success_rate", 0.0)
                sig = "Yes" if exp.get("is_significant") else "No"
                winner = exp.get("winner", "tie")
                lines.append(f"| {name} | {ctrl_sr:.0%} | {var_sr:.0%} | {sig} | {winner} |")
            lines.append("")

        # ── 6. Performance Comparison ───────────────────────────
        perf = d.get("performance_comparison", {})
        lines.append("## 6. Performance Comparison (Before vs. After)")
        lines.append("")
        before = perf.get("before", {})
        after = perf.get("after", {})
        lines.append("| Metric | Before | After | Change |")
        lines.append("|--------|--------|-------|--------|")

        def _change_str(b: float, a: float, lower_is_better: bool = False) -> str:
            if b == 0:
                return "N/A"
            diff = a - b
            pct = (diff / b) * 100
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
            good = (diff < 0) if lower_is_better else (diff > 0)
            emoji = "✅" if (good or diff == 0) else "⚠️"
            return f"{arrow} {pct:+.1f}% {emoji}"

        lines.append(
            f"| Success rate | {before.get('success_rate', 0):.1%} | "
            f"{after.get('success_rate', 0):.1%} | "
            f"{_change_str(before.get('success_rate', 0), after.get('success_rate', 0))} |"
        )
        lines.append(
            f"| Avg iterations | {before.get('avg_iterations', 0):.2f} | "
            f"{after.get('avg_iterations', 0):.2f} | "
            f"{_change_str(before.get('avg_iterations', 0), after.get('avg_iterations', 0), lower_is_better=True)} |"
        )
        lines.append(
            f"| Avg token cost | {before.get('avg_token_cost', 0):.1f} | "
            f"{after.get('avg_token_cost', 0):.1f} | "
            f"{_change_str(before.get('avg_token_cost', 0), after.get('avg_token_cost', 0), lower_is_better=True)} |"
        )
        lines.append("")

        # ── 7. Key Findings ─────────────────────────────────────
        findings = d.get("key_findings", [])
        lines.append("## 7. Key Findings")
        lines.append("")
        if findings:
            for f in findings:
                lines.append(f"- {f}")
        else:
            lines.append("- No significant findings.")
        lines.append("")

        # ── 8. Recommendations ──────────────────────────────────
        recs = d.get("recommendations", [])
        lines.append("## 8. Recommendations")
        lines.append("")
        if recs:
            for i, r in enumerate(recs, 1):
                lines.append(f"{i}. {r}")
        else:
            lines.append("- No recommendations at this time.")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  File output
    # ------------------------------------------------------------------
    def save_to_file(self, path: str, fmt: str = "markdown") -> str:
        """Save the report to a file.

        Args:
            path: File path to write to.
            fmt:  Output format — ``"markdown"``, ``"json"``, or
                  ``"dict"`` (writes JSON with full indentation).

        Returns:
            The absolute path of the saved file.
        """
        if fmt == "json":
            content = self.to_json()
        else:
            content = self.to_markdown()

        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_path

    # ------------------------------------------------------------------
    #  Convenience
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        overview = self._data.get("task_overview", {})
        return (
            f"EvolutionReport(tasks={overview.get('total_tasks', 0)}, "
            f"evolved={overview.get('evolution_cycles', 0)}, "
            f"success_rate={overview.get('success_rate', 0.0):.1%})"
        )

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data


# ═══════════════════════════════════════════════════════════════
#  EvolutionReportGenerator
# ═══════════════════════════════════════════════════════════════


class EvolutionReportGenerator:
    """Generates structured evolution reports from BilevelLoop results.

    After a :class:`BilevelLoop` has executed one or more tasks, pass
    it to this generator to produce a comprehensive :class:`EvolutionReport`
    covering all aspects of the evolution cycle.

    The generator reads data from:
    - ``bilevel_loop.results`` — task results and their metadata.
    - ``bilevel_loop.evolution_loop`` — evolution state.
    - ``bilevel_loop.evolution_loop.template_store`` — templates.
    - ``bilevel_loop.evolution_loop.strategy_evolver`` — mutations.
    - ``bilevel_loop.evolution_loop.ab_test_framework`` — experiments.
    - ``bilevel_loop.evolution_loop.forgetting_engine`` — memory actions.
    - ``bilevel_loop.evolution_loop.anti_pattern_store`` — failures.

    Args:
        bilevel_loop: The :class:`BilevelLoop` after running tasks.
        forgetting_evaluations: Optional list of
            ``(MemoryRecord, ForgettingAction)`` tuples from explicit
            forgetting engine evaluations.  If provided, these are
            included in the forgetting summary.
    """

    def __init__(
        self,
        bilevel_loop: BilevelLoop,
        forgetting_evaluations: Optional[List[Tuple[MemoryRecord, ForgettingAction]]] = None,
    ) -> None:
        self._loop = bilevel_loop
        self._forgetting_evals = forgetting_evaluations or []

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def generate(self) -> EvolutionReport:
        """Generate the full evolution report.

        Returns:
            An :class:`EvolutionReport` with all sections populated.
        """
        data: Dict[str, Any] = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "task_overview": self._collect_task_overview(),
            "template_evolution": self._collect_template_evolution(),
            "forgetting_summary": self._collect_forgetting_summary(),
            "mutation_history": self._collect_mutation_history(),
            "ab_test_results": self._collect_ab_test_results(),
            "performance_comparison": self._collect_performance_comparison(),
            "key_findings": self._collect_key_findings(),
            "recommendations": self._collect_recommendations(),
        }
        return EvolutionReport(data)

    # ------------------------------------------------------------------
    #  Section collectors
    # ------------------------------------------------------------------

    def _collect_task_overview(self) -> Dict[str, Any]:
        """Collect task-level overview metrics."""
        results = self._loop.results
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        total_iters = sum(r.iterations for r in results)
        total_cost = sum(r.token_cost for r in results)
        success_rate = successful / total if total > 0 else 0.0
        avg_iters = total_iters / total if total > 0 else 0.0
        avg_cost = total_cost / total if total > 0 else 0.0

        # Count active templates
        evo = self._loop.evolution_loop
        store = evo.template_store
        try:
            active_templates = store.count()
        except Exception:
            active_templates = len(store.list_templates())

        return {
            "total_tasks": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 4),
            "total_iterations": total_iters,
            "total_token_cost": round(total_cost, 2),
            "avg_iterations": round(avg_iters, 4),
            "avg_token_cost": round(avg_cost, 2),
            "evolution_cycles": self._loop.evolution_count,
            "active_templates": active_templates,
        }

    def _collect_template_evolution(self) -> Dict[str, Any]:
        """Collect template evolution timeline data."""
        evo = self._loop.evolution_loop
        store = evo.template_store

        try:
            all_templates = store.list_templates()
        except Exception:
            all_templates = []

        # Also try to get all templates including inactive
        try:
            all_count = store.count_all()
        except Exception:
            all_count = len(all_templates)

        default_count = sum(1 for t in all_templates if t.parent_id is None)
        variant_count = sum(1 for t in all_templates if t.parent_id is not None)
        proven_count = sum(1 for t in all_templates if t.is_proven)

        templates_data: List[Dict[str, Any]] = []
        for t in all_templates:
            templates_data.append({
                "id": t.id,
                "task_signature": t.task_signature,
                "task_description": t.task_description,
                "use_count": t.use_count,
                "success_count": t.success_count,
                "failure_count": t.failure_count,
                "success_rate": round(t.success_rate, 4),
                "avg_iterations": round(t.avg_iterations, 4),
                "avg_cost": round(t.avg_cost, 4),
                "phase_count": len(t.phases),
                "parent_id": t.parent_id,
                "mutations": list(t.mutations),
                "is_active": t.is_active,
                "confidence": round(t.confidence, 4),
                "created_at": t.created_at,
                "last_used": t.last_used,
            })

        return {
            "total_templates": all_count,
            "default_templates": default_count,
            "variant_templates": variant_count,
            "proven_templates": proven_count,
            "templates": templates_data,
        }

    def _collect_forgetting_summary(self) -> Dict[str, Any]:
        """Collect forgetting engine evaluation summary."""
        evo = self._loop.evolution_loop
        engine = evo.forgetting_engine

        action_counts: Dict[str, int] = {
            "DEGRADE": 0,
            "COMPRESS": 0,
            "PURGE": 0,
        }
        total_evaluated = 0
        details: List[Dict[str, Any]] = []

        # Include explicit evaluations
        for record, action in self._forgetting_evals:
            action_counts[action.name] += 1
            total_evaluated += 1
            try:
                retention = engine.retention(record)
            except Exception:
                retention = 0.0
            details.append({
                "memory_id": record.id,
                "action": action.name,
                "retention": round(retention, 4),
                "is_anti_pattern": record.is_anti_pattern,
                "is_episodic": record.is_episodic,
            })

        return {
            "total_evaluated": total_evaluated,
            "actions": action_counts,
            "compress_count": action_counts["COMPRESS"],
            "purge_count": action_counts["PURGE"],
            "degrade_count": action_counts["DEGRADE"],
            "is_dry_run": engine.is_dry_run,
            "details": details,
        }

    def _collect_mutation_history(self) -> Dict[str, Any]:
        """Collect strategy mutation history."""
        evo = self._loop.evolution_loop
        evolver = evo.strategy_evolver
        backend = getattr(evolver, "_backend", None)

        records: List[Dict[str, Any]] = []
        if backend is not None:
            try:
                raw_records = backend.list_mutation_history(limit=100)
                for r in raw_records:
                    records.append({
                        "template_id": r.get("template_id", ""),
                        "parent_id": r.get("parent_id", ""),
                        "mutation_type": r.get("mutation_type", ""),
                        "description": r.get("description", ""),
                        "rationale": r.get("rationale", ""),
                        "expected_improvement": float(
                            r.get("expected_improvement", 0.0)
                        ),
                        "reflection_composite": float(
                            r.get("reflection_composite", 0.0)
                        ),
                        "target_dimension": r.get("target_dimension", ""),
                        "created_at": r.get("created_at", ""),
                    })
            except Exception:
                pass

        # Mutation type breakdown
        mutation_types: Dict[str, int] = {}
        for r in records:
            mt = r.get("mutation_type", "UNKNOWN")
            mutation_types[mt] = mutation_types.get(mt, 0) + 1

        return {
            "total_mutations": len(records),
            "mutation_types": mutation_types,
            "records": records,
        }

    def _collect_ab_test_results(self) -> Dict[str, Any]:
        """Collect A/B test experiment results."""
        evo = self._loop.evolution_loop
        ab_test = evo.ab_test_framework

        experiments_data: List[Dict[str, Any]] = []
        completed = 0
        running = 0

        try:
            all_experiments = ab_test.list_experiments()
        except Exception:
            all_experiments = []

        # Also get completed experiments
        try:
            completed_exps = ab_test.list_experiments(status="completed")
        except Exception:
            completed_exps = []

        for exp in all_experiments:
            exp_data: Dict[str, Any] = {
                "id": exp.id,
                "name": exp.name,
                "control_template_id": exp.control_template_id,
                "variant_template_id": exp.variant_template_id,
                "min_samples": exp.min_samples,
                "status": exp.status,
                "winner": exp.winner,
                "created_at": exp.created_at,
                "completed_at": exp.completed_at,
            }

            # Try to get evaluation result if completed
            if exp.status == "completed":
                completed += 1
                # Try to find the result in evolution_loop's results
                for er in evo.experiment_results:
                    if er.experiment_id == exp.id:
                        exp_data.update({
                            "control_success_rate": round(er.control_success_rate, 4),
                            "variant_success_rate": round(er.variant_success_rate, 4),
                            "control_samples": er.control_samples,
                            "variant_samples": er.variant_samples,
                            "is_significant": er.is_significant,
                            "p_value": er.p_value,
                            "wilson_significant": er.wilson_significant,
                            "message": er.message,
                        })
                        break
                else:
                    # Try evaluating again to get fresh results
                    try:
                        result = ab_test.evaluate(exp.id)
                        exp_data.update({
                            "control_success_rate": round(result.control_success_rate, 4),
                            "variant_success_rate": round(result.variant_success_rate, 4),
                            "control_samples": result.control_samples,
                            "variant_samples": result.variant_samples,
                            "is_significant": result.is_significant,
                            "p_value": result.p_value,
                            "wilson_significant": result.wilson_significant,
                            "message": result.message,
                        })
                    except Exception:
                        exp_data.update({
                            "control_success_rate": 0.0,
                            "variant_success_rate": 0.0,
                            "control_samples": 0,
                            "variant_samples": 0,
                            "is_significant": False,
                            "p_value": 1.0,
                            "wilson_significant": False,
                            "message": "Evaluation data unavailable.",
                        })
            else:
                running += 1
                exp_data.update({
                    "control_success_rate": 0.0,
                    "variant_success_rate": 0.0,
                    "control_samples": 0,
                    "variant_samples": 0,
                    "is_significant": False,
                    "p_value": 1.0,
                    "wilson_significant": False,
                    "message": "Experiment still running.",
                })

            experiments_data.append(exp_data)

        return {
            "total_experiments": len(all_experiments),
            "completed": completed,
            "running": running,
            "experiments": experiments_data,
        }

    def _collect_performance_comparison(self) -> Dict[str, Any]:
        """Collect before/after performance comparison.

        Splits the task results into first half and second half and
        computes metrics for each.
        """
        results = self._loop.results
        total = len(results)

        if total < 2:
            return {
                "before": {"success_rate": 0.0, "avg_iterations": 0.0, "avg_token_cost": 0.0, "task_count": 0},
                "after": {"success_rate": 0.0, "avg_iterations": 0.0, "avg_token_cost": 0.0, "task_count": 0},
                "improvement": {},
            }

        midpoint = total // 2
        before_results = results[:midpoint] if midpoint > 0 else results[:1]
        after_results = results[midpoint:] if midpoint > 0 else results[1:]

        before = self._compute_metrics(before_results)
        after = self._compute_metrics(after_results)

        # Compute improvement deltas
        improvement: Dict[str, float] = {}
        for key in ("success_rate", "avg_iterations", "avg_token_cost"):
            b = before.get(key, 0.0)
            a = after.get(key, 0.0)
            if b != 0:
                improvement[key] = round(a - b, 4)
            else:
                improvement[key] = 0.0

        return {
            "before": before,
            "after": after,
            "improvement": improvement,
        }

    def _collect_key_findings(self) -> List[str]:
        """Automatically analyse the evolution data for key findings."""
        findings: List[str] = []
        overview = self._collect_task_overview()
        mutations = self._collect_mutation_history()
        forgetting = self._collect_forgetting_summary()
        ab = self._collect_ab_test_results()
        perf = self._collect_performance_comparison()
        evo = self._loop.evolution_loop

        # Finding: success rate
        sr = overview.get("success_rate", 0.0)
        if sr >= 0.8:
            findings.append(f"High overall success rate ({sr:.0%}) — the system is performing well.")
        elif sr >= 0.5:
            findings.append(f"Moderate success rate ({sr:.0%}) — room for improvement.")
        else:
            findings.append(f"Low success rate ({sr:.0%}) — significant issues need attention.")

        # Finding: evolution activity
        evo_cycles = overview.get("evolution_cycles", 0)
        if evo_cycles > 0:
            findings.append(f"{evo_cycles} evolution cycle(s) executed, indicating active self-improvement.")
        else:
            findings.append("No evolution cycles were triggered — consider adjusting trigger thresholds.")

        # Finding: mutations
        total_mutations = mutations.get("total_mutations", 0)
        if total_mutations > 0:
            findings.append(f"{total_mutations} mutation(s) proposed and applied to templates.")
            # Highlight most common mutation type
            mt = mutations.get("mutation_types", {})
            if mt:
                most_common = max(mt, key=mt.get)
                findings.append(f"Most common mutation type: {most_common} ({mt[most_common]} occurrence(s)).")
        else:
            findings.append("No mutations were proposed — templates may already be well-optimised.")

        # Finding: forgetting
        compress_count = forgetting.get("compress_count", 0)
        purge_count = forgetting.get("purge_count", 0)
        if compress_count > 0:
            findings.append(f"Forgetting engine compressed {compress_count} memory(ies) (episodic to semantic).")
        if purge_count > 0:
            findings.append(f"Forgetting engine purged {purge_count} memory(ies).")
        if compress_count == 0 and purge_count == 0:
            findings.append("No aggressive forgetting actions (COMPRESS/PURGE) were triggered.")

        # Finding: A/B tests
        total_exp = ab.get("total_experiments", 0)
        completed_exp = ab.get("completed", 0)
        if total_exp > 0:
            variant_wins = sum(
                1 for e in ab.get("experiments", [])
                if e.get("winner") == "variant"
            )
            findings.append(
                f"{total_exp} A/B experiment(s) created, {completed_exp} completed, "
                f"{variant_wins} variant win(s)."
            )
        else:
            findings.append("No A/B experiments were created.")

        # Finding: anti-patterns
        ap_store = evo.anti_pattern_store
        ap_count = ap_store.count()
        if ap_count > 0:
            unresolved = ap_store.count_unresolved()
            findings.append(
                f"{ap_count} anti-pattern(s) registered ({unresolved} unresolved) — "
                f"failure patterns are being captured."
            )
        else:
            findings.append("No anti-patterns registered — no failures detected.")

        # Finding: performance trend
        before_sr = perf.get("before", {}).get("success_rate", 0.0)
        after_sr = perf.get("after", {}).get("success_rate", 0.0)
        if before_sr > 0 and after_sr > before_sr:
            findings.append(
                f"Success rate improved from {before_sr:.0%} to {after_sr:.0%} — "
                f"evolution is having a positive effect."
            )
        elif before_sr > 0 and after_sr < before_sr:
            findings.append(
                f"Success rate declined from {before_sr:.0%} to {after_sr:.0%} — "
                f"investigate potential regressions."
            )

        return findings

    def _collect_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on the report data."""
        recs: List[str] = []
        overview = self._collect_task_overview()
        mutations = self._collect_mutation_history()
        ab = self._collect_ab_test_results()
        perf = self._collect_performance_comparison()
        evo = self._loop.evolution_loop

        # Recommendation: low success rate
        sr = overview.get("success_rate", 0.0)
        if sr < 0.5:
            recs.append(
                "Investigate failing tasks and register more detailed anti-patterns "
                "to prevent repeated failures."
            )

        # Recommendation: no mutations
        total_mutations = mutations.get("total_mutations", 0)
        if total_mutations == 0:
            recs.append(
                "No mutations were applied. Consider lowering the mutation threshold "
                "or introducing more diverse tasks to trigger evolution."
            )

        # Recommendation: running experiments
        running_exp = ab.get("running", 0)
        if running_exp > 0:
            recs.append(
                f"{running_exp} A/B experiment(s) are still running. "
                f"Record more trial results to reach statistical significance."
            )

        # Recommendation: performance decline
        before_sr = perf.get("before", {}).get("success_rate", 0.0)
        after_sr = perf.get("after", {}).get("success_rate", 0.0)
        if before_sr > 0 and after_sr < before_sr:
            recs.append(
                "Performance declined in the second half. Review recent mutations "
                "and consider rolling back harmful changes."
            )

        # Recommendation: high token cost
        avg_cost = overview.get("avg_token_cost", 0.0)
        if avg_cost > 500:
            recs.append(
                f"Average token cost is high ({avg_cost:.0f}). Consider adding "
                f"cost-reduction mutations (REMOVE_PHASE, REMOVE_TOOL)."
            )

        # Recommendation: unresolved anti-patterns
        ap_store = evo.anti_pattern_store
        unresolved = ap_store.count_unresolved()
        if unresolved > 2:
            recs.append(
                f"{unresolved} unresolved anti-patterns. Prioritise finding "
                f"resolutions for the highest-severity patterns."
            )

        # Recommendation: template diversity
        template_evo = self._collect_template_evolution()
        variant_count = template_evo.get("variant_templates", 0)
        if variant_count == 0 and overview.get("evolution_cycles", 0) > 0:
            recs.append(
                "Evolution ran but produced no template variants. "
                "Check mutation thresholds and reflection scoring."
            )

        if not recs:
            recs.append(
                "System is performing well. Continue monitoring and "
                "consider expanding task diversity for further evolution."
            )

        return recs

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_metrics(results: List[TaskResult]) -> Dict[str, Any]:
        """Compute aggregate metrics for a list of task results.

        Args:
            results: List of :class:`TaskResult` objects.

        Returns:
            Dict with success_rate, avg_iterations, avg_token_cost,
            and task_count.
        """
        total = len(results)
        if total == 0:
            return {
                "success_rate": 0.0,
                "avg_iterations": 0.0,
                "avg_token_cost": 0.0,
                "task_count": 0,
            }
        successful = sum(1 for r in results if r.success)
        total_iters = sum(r.iterations for r in results)
        total_cost = sum(r.token_cost for r in results)
        return {
            "success_rate": round(successful / total, 4),
            "avg_iterations": round(total_iters / total, 4),
            "avg_token_cost": round(total_cost / total, 2),
            "task_count": total,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionReportGenerator("
            f"tasks={self._loop.result_count}, "
            f"evolved={self._loop.evolution_count})"
        )
