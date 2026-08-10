"""
Tests for Dynamics Proxy and Spatial Proxy modules (World Proxy matrix).

Covers:
    Dynamics:
        - EnvironmentState creation, validation, serialisation, state_key
        - StateTransition creation, serialisation
        - EnvironmentDynamicsTracker:
            record_state, get_transitions, get_states,
            compute_transition_matrix, predict_state,
            detect_anomaly, get_trend,
            utility queries, serialisation, persistence

    Spatial:
        - ServiceNode creation, serialisation
        - ServiceEdge creation, serialisation
        - ServiceTopologyMapper:
            register_node, register_edge, update_node_health,
            get_neighbors, get_outgoing/incoming_edges,
            find_path, find_all_paths,
            get_dependency_graph,
            find_bottlenecks,
            get_capability_map, find_nodes_by_capability,
            suggest_alternatives,
            utility queries, JSON serialisation, persistence
"""

import json
import math
import os
import tempfile
import time
import unittest

from suyi.quality.dynamics_proxy import (
    AnomalyLevel,
    EnvironmentDynamicsTracker,
    EnvironmentState,
    StateTransition,
    TrendDirection,
)
from suyi.quality.spatial_proxy import (
    NodeHealth,
    RelationType,
    ServiceEdge,
    ServiceNode,
    ServiceTopologyMapper,
)
from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  EnvironmentState tests
# ═══════════════════════════════════════════════════════════════


class TestEnvironmentState(unittest.TestCase):
    """EnvironmentState dataclass tests."""

    def test_creation_with_defaults(self):
        state = EnvironmentState(
            timestamp=time.time(),
            service_name="svc-a",
        )
        self.assertEqual(state.service_name, "svc-a")
        self.assertEqual(state.state_dict, {})
        self.assertEqual(state.health_score, 1.0)

    def test_creation_with_full_data(self):
        state = EnvironmentState(
            timestamp=1000.0,
            service_name="svc-a",
            state_dict={"cpu": 0.5, "mem": 0.3},
            health_score=0.8,
        )
        self.assertEqual(state.state_dict["cpu"], 0.5)
        self.assertAlmostEqual(state.health_score, 0.8)

    def test_health_score_validation_lower_bound(self):
        with self.assertRaises(ValueError):
            EnvironmentState(
                timestamp=0.0,
                service_name="svc",
                health_score=-0.1,
            )

    def test_health_score_validation_upper_bound(self):
        with self.assertRaises(ValueError):
            EnvironmentState(
                timestamp=0.0,
                service_name="svc",
                health_score=1.5,
            )

    def test_state_key_canonical(self):
        """state_key is canonical regardless of dict insertion order."""
        s1 = EnvironmentState(
            timestamp=0.0, service_name="s",
            state_dict={"a": 1, "b": 2},
        )
        s2 = EnvironmentState(
            timestamp=0.0, service_name="s",
            state_dict={"b": 2, "a": 1},
        )
        self.assertEqual(s1.state_key, s2.state_key)

    def test_state_key_float_rounding(self):
        """Floats are rounded to 1 decimal in state_key."""
        s1 = EnvironmentState(
            timestamp=0.0, service_name="s",
            state_dict={"cpu": 0.45},
        )
        s2 = EnvironmentState(
            timestamp=0.0, service_name="s",
            state_dict={"cpu": 0.46},
        )
        # 0.45 → 0.5 (round half up), 0.46 → 0.5
        self.assertEqual(s1.state_key, s2.state_key)

    def test_state_key_empty_dict(self):
        state = EnvironmentState(timestamp=0.0, service_name="s")
        self.assertEqual(state.state_key, "__empty__")

    def test_serialisation_roundtrip(self):
        state = EnvironmentState(
            timestamp=12345.0,
            service_name="svc",
            state_dict={"cpu": 0.7, "alive": True},
            health_score=0.9,
        )
        d = state.to_dict()
        restored = EnvironmentState.from_dict(d)
        self.assertEqual(restored.service_name, state.service_name)
        self.assertEqual(restored.health_score, state.health_score)
        self.assertEqual(restored.state_dict, state.state_dict)

    def test_repr(self):
        state = EnvironmentState(
            timestamp=100.0, service_name="svc",
            state_dict={"x": 1}, health_score=0.5,
        )
        r = repr(state)
        self.assertIn("svc", r)
        self.assertIn("0.50", r)


# ═══════════════════════════════════════════════════════════════
#  StateTransition tests
# ═══════════════════════════════════════════════════════════════


class TestStateTransition(unittest.TestCase):
    """StateTransition dataclass tests."""

    def test_creation(self):
        t = StateTransition(
            from_state="A",
            to_state="B",
            trigger="health_drop",
            timestamp=100.0,
            service_name="svc",
        )
        self.assertEqual(t.from_state, "A")
        self.assertEqual(t.to_state, "B")
        self.assertEqual(t.trigger, "health_drop")

    def test_serialisation_roundtrip(self):
        t = StateTransition(
            from_state="old",
            to_state="new",
            trigger="config_change",
            timestamp=999.0,
            service_name="svc-x",
        )
        restored = StateTransition.from_dict(t.to_dict())
        self.assertEqual(restored.from_state, "old")
        self.assertEqual(restored.to_state, "new")
        self.assertEqual(restored.trigger, "config_change")
        self.assertEqual(restored.service_name, "svc-x")

    def test_default_timestamp(self):
        t = StateTransition(from_state="A", to_state="B")
        self.assertGreater(t.timestamp, 0)


# ═══════════════════════════════════════════════════════════════
#  EnvironmentDynamicsTracker tests
# ═══════════════════════════════════════════════════════════════


class TestEnvironmentDynamicsTracker(unittest.TestCase):
    """EnvironmentDynamicsTracker core functionality tests."""

    def setUp(self) -> None:
        self.tracker = EnvironmentDynamicsTracker()

    def test_record_state_returns_environment_state(self):
        state = self.tracker.record_state("svc", {"cpu": 0.5}, 0.9)
        self.assertIsInstance(state, EnvironmentState)
        self.assertEqual(state.service_name, "svc")

    def test_record_state_stores_in_memory(self):
        self.tracker.record_state("svc", {"cpu": 0.5}, 0.9)
        self.assertEqual(self.tracker.get_state_count("svc"), 1)

    def test_record_multiple_states(self):
        for i in range(5):
            self.tracker.record_state("svc", {"cpu": i * 0.1}, 1.0 - i * 0.1)
        self.assertEqual(self.tracker.get_state_count("svc"), 5)

    def test_transition_detected_on_state_change(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        self.tracker.record_state("svc", {"cpu": 0.9}, 1.0)
        transitions = self.tracker.get_transitions("svc")
        self.assertEqual(len(transitions), 1)
        self.assertNotEqual(transitions[0].from_state, transitions[0].to_state)

    def test_no_transition_when_state_unchanged(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        transitions = self.tracker.get_transitions("svc")
        self.assertEqual(len(transitions), 0)

    def test_transition_trigger_health_drop(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        self.tracker.record_state("svc", {"cpu": 0.9}, 0.3)
        transitions = self.tracker.get_transitions("svc")
        self.assertEqual(transitions[0].trigger, "health_drop")

    def test_transition_trigger_health_recover(self):
        self.tracker.record_state("svc", {"cpu": 0.9}, 0.3)
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        transitions = self.tracker.get_transitions("svc")
        self.assertEqual(transitions[0].trigger, "health_recover")

    def test_get_transitions_with_time_window(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        self.tracker.record_state("svc", {"cpu": 0.2}, 1.0)
        # With a large window, all transitions should be returned
        transitions = self.tracker.get_transitions("svc", time_window=3600.0)
        self.assertEqual(len(transitions), 1)
        # With None, all transitions are returned
        transitions_all = self.tracker.get_transitions("svc")
        self.assertEqual(len(transitions_all), 1)
        # Manually add an old transition to test filtering
        old_transition = StateTransition(
            from_state="old", to_state="new",
            timestamp=time.time() - 7200,  # 2 hours ago
            service_name="svc",
        )
        self.tracker._transitions["svc"].append(old_transition)
        recent = self.tracker.get_transitions("svc", time_window=3600.0)
        self.assertEqual(len(recent), 1)  # only the recent one
        all_t = self.tracker.get_transitions("svc")
        self.assertEqual(len(all_t), 2)  # both

    def test_get_transitions_nonexistent_service(self):
        result = self.tracker.get_transitions("nonexistent")
        self.assertEqual(result, [])

    def test_get_states_with_time_window(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 1.0)
        # With a large window, all states should be returned
        states = self.tracker.get_states("svc", time_window=3600.0)
        self.assertEqual(len(states), 1)
        # With None, all states are returned
        states_all = self.tracker.get_states("svc")
        self.assertEqual(len(states_all), 1)
        # Manually add an old state to test filtering
        old_state = EnvironmentState(
            timestamp=time.time() - 7200,  # 2 hours ago
            service_name="svc",
            state_dict={"cpu": 0.9},
            health_score=0.5,
        )
        self.tracker._states["svc"].append(old_state)
        recent = self.tracker.get_states("svc", time_window=3600.0)
        self.assertEqual(len(recent), 1)  # only the recent one
        all_s = self.tracker.get_states("svc")
        self.assertEqual(len(all_s), 2)  # both

    def test_compute_transition_matrix_basic(self):
        # Record a sequence of state transitions
        for cpu in [0.1, 0.5, 0.1, 0.5, 0.1]:
            self.tracker.record_state("svc", {"cpu": cpu}, 1.0)
        matrix = self.tracker.compute_transition_matrix("svc")
        self.assertGreater(len(matrix), 0)
        # Each row should sum to ~1.0 (or be absorbent)
        for row in matrix.values():
            if row:
                total = sum(row.values())
                self.assertAlmostEqual(total, 1.0, places=5)

    def test_compute_transition_matrix_empty(self):
        matrix = self.tracker.compute_transition_matrix("no-svc")
        self.assertEqual(matrix, {})

    def test_predict_state_returns_distribution(self):
        for cpu in [0.1, 0.5, 0.1, 0.5, 0.1]:
            self.tracker.record_state("svc", {"cpu": cpu}, 1.0)
        prediction = self.tracker.predict_state("svc", horizon_steps=1)
        self.assertIsInstance(prediction, dict)
        # Probabilities should sum to ~1.0
        total = sum(prediction.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_predict_state_multiple_steps(self):
        for cpu in [0.1, 0.5, 0.1, 0.5, 0.1, 0.5]:
            self.tracker.record_state("svc", {"cpu": cpu}, 1.0)
        prediction = self.tracker.predict_state("svc", horizon_steps=3)
        self.assertIsInstance(prediction, dict)
        total = sum(prediction.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_predict_state_no_data(self):
        prediction = self.tracker.predict_state("no-svc", horizon_steps=2)
        self.assertEqual(prediction, {})

    def test_predict_state_invalid_horizon(self):
        with self.assertRaises(ValueError):
            self.tracker.predict_state("svc", horizon_steps=0)

    def test_detect_anomaly_normal(self):
        # Record stable history then a normal current value
        for i in range(5):
            self.tracker.record_state("svc", {"x": i}, 0.9)
        level, z = self.tracker.detect_anomaly("svc")
        self.assertEqual(level, AnomalyLevel.NORMAL)

    def test_detect_anomaly_critical(self):
        # Record stable high health then a sudden drop
        for _ in range(5):
            self.tracker.record_state("svc", {"x": 1}, 0.95)
        self.tracker.record_state("svc", {"x": 2}, 0.1)
        level, z = self.tracker.detect_anomaly("svc")
        self.assertIn(level, (AnomalyLevel.WARNING, AnomalyLevel.CRITICAL))

    def test_detect_anomaly_insufficient_data(self):
        self.tracker.record_state("svc", {"x": 1}, 0.9)
        level, z = self.tracker.detect_anomaly("svc")
        self.assertEqual(level, AnomalyLevel.NORMAL)
        self.assertEqual(z, 0.0)

    def test_detect_anomaly_low_health_override(self):
        # History with no variation but low current health
        for _ in range(5):
            self.tracker.record_state("svc", {"x": 1}, 0.95)
        self.tracker.record_state("svc", {"x": 1}, 0.2)
        level, z = self.tracker.detect_anomaly("svc")
        # std=0 and current differs from mean → critical
        self.assertIn(level, (AnomalyLevel.WARNING, AnomalyLevel.CRITICAL))

    def test_get_trend_rising(self):
        for i in range(10):
            self.tracker.record_state("svc", {"cpu": i * 0.1}, 1.0)
        direction, slope = self.tracker.get_trend("svc", "cpu")
        self.assertEqual(direction, TrendDirection.RISING)
        self.assertGreater(slope, 0)

    def test_get_trend_falling(self):
        for i in range(10):
            self.tracker.record_state("svc", {"cpu": 1.0 - i * 0.1}, 1.0)
        direction, slope = self.tracker.get_trend("svc", "cpu")
        self.assertEqual(direction, TrendDirection.FALLING)
        self.assertLess(slope, 0)

    def test_get_trend_stable(self):
        for _ in range(10):
            self.tracker.record_state("svc", {"cpu": 0.5}, 1.0)
        direction, slope = self.tracker.get_trend("svc", "cpu")
        self.assertEqual(direction, TrendDirection.STABLE)
        self.assertAlmostEqual(slope, 0.0, places=5)

    def test_get_trend_nonexistent_metric(self):
        self.tracker.record_state("svc", {"cpu": 0.5}, 1.0)
        self.tracker.record_state("svc", {"cpu": 0.6}, 1.0)
        direction, slope = self.tracker.get_trend("svc", "nonexistent")
        self.assertEqual(direction, TrendDirection.STABLE)
        self.assertEqual(slope, 0.0)

    def test_get_trend_insufficient_data(self):
        self.tracker.record_state("svc", {"cpu": 0.5}, 1.0)
        direction, slope = self.tracker.get_trend("svc", "cpu")
        self.assertEqual(direction, TrendDirection.STABLE)

    def test_get_latest_state(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 0.9)
        self.tracker.record_state("svc", {"cpu": 0.2}, 0.8)
        latest = self.tracker.get_latest_state("svc")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.health_score, 0.8)

    def test_get_latest_state_nonexistent(self):
        self.assertIsNone(self.tracker.get_latest_state("no-svc"))

    def test_get_service_names(self):
        self.tracker.record_state("svc-a", {}, 1.0)
        self.tracker.record_state("svc-b", {}, 1.0)
        names = self.tracker.get_service_names()
        self.assertEqual(names, ["svc-a", "svc-b"])

    def test_serialisation_roundtrip(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 0.9)
        self.tracker.record_state("svc", {"cpu": 0.5}, 0.7)
        data = self.tracker.to_dict()
        restored = EnvironmentDynamicsTracker.from_dict(data)
        self.assertEqual(restored.get_state_count("svc"), 2)
        self.assertEqual(restored.get_transition_count("svc"), 1)

    def test_repr(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 0.9)
        r = repr(self.tracker)
        self.assertIn("in-memory", r)
        self.assertIn("services=1", r)


# ═══════════════════════════════════════════════════════════════
#  EnvironmentDynamicsTracker persistence tests
# ═══════════════════════════════════════════════════════════════


class TestDynamicsTrackerPersistence(unittest.TestCase):
    """Tests for SQLiteBackend persistence of EnvironmentDynamicsTracker."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test_dynamics.db")
        self.backend = SQLiteBackend(db_path=self.db_path)
        self.tracker = EnvironmentDynamicsTracker(backend=self.backend)

    def tearDown(self) -> None:
        self.backend.close()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_persist_and_reload(self):
        self.tracker.record_state("svc", {"cpu": 0.1}, 0.9)
        self.tracker.record_state("svc", {"cpu": 0.5}, 0.7)
        self.backend.close()

        # Reopen backend and create new tracker
        backend2 = SQLiteBackend(db_path=self.db_path)
        tracker2 = EnvironmentDynamicsTracker(backend=backend2)
        self.assertEqual(tracker2.get_state_count("svc"), 2)
        self.assertEqual(tracker2.get_transition_count("svc"), 1)
        backend2.close()

    def test_persist_multiple_services(self):
        self.tracker.record_state("svc-a", {"cpu": 0.1}, 0.9)
        self.tracker.record_state("svc-b", {"cpu": 0.2}, 0.8)
        self.tracker.record_state("svc-a", {"cpu": 0.5}, 0.7)
        self.backend.close()

        backend2 = SQLiteBackend(db_path=self.db_path)
        tracker2 = EnvironmentDynamicsTracker(backend=backend2)
        self.assertEqual(tracker2.get_state_count("svc-a"), 2)
        self.assertEqual(tracker2.get_state_count("svc-b"), 1)
        self.assertEqual(tracker2.get_transition_count("svc-a"), 1)
        backend2.close()


# ═══════════════════════════════════════════════════════════════
#  ServiceNode tests
# ═══════════════════════════════════════════════════════════════


class TestServiceNode(unittest.TestCase):
    """ServiceNode dataclass tests."""

    def test_creation_with_defaults(self):
        node = ServiceNode(name="svc")
        self.assertEqual(node.name, "svc")
        self.assertEqual(node.node_type, "service")
        self.assertEqual(node.capabilities, [])
        self.assertEqual(node.endpoint, "")
        self.assertEqual(node.health, NodeHealth.UNKNOWN)

    def test_creation_with_full_data(self):
        node = ServiceNode(
            name="api-gateway",
            node_type="gateway",
            capabilities=["routing", "auth"],
            endpoint="/api",
            health=NodeHealth.HEALTHY,
            metadata={"version": "1.0"},
        )
        self.assertEqual(node.node_type, "gateway")
        self.assertIn("routing", node.capabilities)
        self.assertEqual(node.health, NodeHealth.HEALTHY)

    def test_serialisation_roundtrip(self):
        node = ServiceNode(
            name="db",
            node_type="database",
            capabilities=["storage", "query"],
            endpoint="localhost:5432",
            health=NodeHealth.DEGRADED,
            metadata={"engine": "postgres"},
        )
        restored = ServiceNode.from_dict(node.to_dict())
        self.assertEqual(restored.name, "db")
        self.assertEqual(restored.health, NodeHealth.DEGRADED)
        self.assertEqual(restored.capabilities, ["storage", "query"])

    def test_health_from_label(self):
        self.assertEqual(NodeHealth.from_label("healthy"), NodeHealth.HEALTHY)
        self.assertEqual(NodeHealth.from_label("degraded"), NodeHealth.DEGRADED)
        self.assertEqual(NodeHealth.from_label("unknown_label"), NodeHealth.UNKNOWN)

    def test_health_is_available(self):
        self.assertTrue(NodeHealth.HEALTHY.is_available)
        self.assertTrue(NodeHealth.DEGRADED.is_available)
        self.assertFalse(NodeHealth.UNHEALTHY.is_available)
        self.assertFalse(NodeHealth.UNKNOWN.is_available)

    def test_repr(self):
        node = ServiceNode(name="svc", node_type="microservice", health=NodeHealth.HEALTHY)
        r = repr(node)
        self.assertIn("svc", r)
        self.assertIn("microservice", r)


# ═══════════════════════════════════════════════════════════════
#  ServiceEdge tests
# ═══════════════════════════════════════════════════════════════


class TestServiceEdge(unittest.TestCase):
    """ServiceEdge dataclass tests."""

    def test_creation(self):
        edge = ServiceEdge(
            from_node="a",
            to_node="b",
            relation_type=RelationType.DEPENDS_ON,
            weight=2.0,
        )
        self.assertEqual(edge.from_node, "a")
        self.assertEqual(edge.to_node, "b")
        self.assertEqual(edge.relation_type, RelationType.DEPENDS_ON)

    def test_serialisation_roundtrip(self):
        edge = ServiceEdge(
            from_node="x",
            to_node="y",
            relation_type=RelationType.CALLS,
            weight=0.5,
            metadata={"protocol": "grpc"},
        )
        restored = ServiceEdge.from_dict(edge.to_dict())
        self.assertEqual(restored.from_node, "x")
        self.assertEqual(restored.to_node, "y")
        self.assertEqual(restored.relation_type, RelationType.CALLS)
        self.assertEqual(restored.weight, 0.5)

    def test_relation_type_from_label(self):
        self.assertEqual(RelationType.from_label("depends_on"), RelationType.DEPENDS_ON)
        self.assertEqual(RelationType.from_label("calls"), RelationType.CALLS)
        self.assertEqual(RelationType.from_label("unknown"), RelationType.CUSTOM)

    def test_repr(self):
        edge = ServiceEdge(from_node="a", to_node="b", relation_type=RelationType.CALLS)
        r = repr(edge)
        self.assertIn("a", r)
        self.assertIn("b", r)


# ═══════════════════════════════════════════════════════════════
#  ServiceTopologyMapper tests
# ═══════════════════════════════════════════════════════════════


class TestServiceTopologyMapper(unittest.TestCase):
    """ServiceTopologyMapper core functionality tests."""

    def setUp(self) -> None:
        self.mapper = ServiceTopologyMapper()
        # Register a small topology:
        #   gateway → auth → db
        #   gateway → user-svc → db
        #   user-svc → cache
        self.mapper.register_node("gateway", "gateway", ["routing", "auth"], "/api")
        self.mapper.register_node("auth", "microservice", ["auth"], "/auth")
        self.mapper.register_node("user-svc", "microservice", ["user"], "/users")
        self.mapper.register_node("db", "database", ["storage", "query"], "localhost:5432")
        self.mapper.register_node("cache", "cache", ["cache"], "localhost:6379")
        self.mapper.register_edge("gateway", "auth", RelationType.DEPENDS_ON, 1.0)
        self.mapper.register_edge("gateway", "user-svc", RelationType.DEPENDS_ON, 1.0)
        self.mapper.register_edge("auth", "db", RelationType.DEPENDS_ON, 1.0)
        self.mapper.register_edge("user-svc", "db", RelationType.DEPENDS_ON, 1.0)
        self.mapper.register_edge("user-svc", "cache", RelationType.CALLS, 0.5)

    def test_node_count(self):
        self.assertEqual(self.mapper.node_count(), 5)

    def test_edge_count(self):
        self.assertEqual(self.mapper.edge_count(), 5)

    def test_has_node(self):
        self.assertTrue(self.mapper.has_node("gateway"))
        self.assertFalse(self.mapper.has_node("nonexistent"))

    def test_has_edge(self):
        self.assertTrue(self.mapper.has_edge("gateway", "auth"))
        self.assertFalse(self.mapper.has_edge("auth", "gateway"))

    def test_register_node_returns_node(self):
        node = self.mapper.register_node("new-svc", "microservice", ["custom"])
        self.assertIsInstance(node, ServiceNode)
        self.assertEqual(node.name, "new-svc")

    def test_register_node_update_existing(self):
        self.mapper.register_node("gateway", "api-gateway", ["new-cap"], "/v2")
        node = self.mapper.get_node("gateway")
        self.assertEqual(node.node_type, "api-gateway")
        self.assertIn("new-cap", node.capabilities)

    def test_register_edge_returns_edge(self):
        edge = self.mapper.register_edge("auth", "cache", RelationType.CALLS, 0.3)
        self.assertIsInstance(edge, ServiceEdge)
        self.assertEqual(edge.from_node, "auth")

    def test_register_edge_nonexistent_node(self):
        result = self.mapper.register_edge("gateway", "nonexistent")
        self.assertIsNone(result)

    def test_register_edge_update_existing(self):
        self.mapper.register_edge("gateway", "auth", RelationType.DEPENDS_ON, 5.0)
        edges = self.mapper.get_outgoing_edges("gateway")
        auth_edges = [e for e in edges if e.to_node == "auth"]
        self.assertEqual(len(auth_edges), 1)
        self.assertEqual(auth_edges[0].weight, 5.0)

    def test_update_node_health(self):
        self.assertTrue(self.mapper.update_node_health("db", NodeHealth.DEGRADED))
        self.assertEqual(self.mapper.get_node("db").health, NodeHealth.DEGRADED)

    def test_update_node_health_nonexistent(self):
        self.assertFalse(self.mapper.update_node_health("no-svc", NodeHealth.HEALTHY))

    def test_get_neighbors_both(self):
        neighbors = self.mapper.get_neighbors("user-svc")
        self.assertIn("gateway", neighbors)  # incoming
        self.assertIn("db", neighbors)       # outgoing
        self.assertIn("cache", neighbors)    # outgoing

    def test_get_neighbors_out_only(self):
        neighbors = self.mapper.get_neighbors("gateway", direction="out")
        self.assertIn("auth", neighbors)
        self.assertIn("user-svc", neighbors)
        self.assertNotIn("db", neighbors)

    def test_get_neighbors_in_only(self):
        neighbors = self.mapper.get_neighbors("db", direction="in")
        self.assertIn("auth", neighbors)
        self.assertIn("user-svc", neighbors)

    def test_get_neighbors_nonexistent(self):
        self.assertEqual(self.mapper.get_neighbors("no-svc"), [])

    def test_find_path_direct(self):
        path = self.mapper.find_path("gateway", "auth")
        self.assertIsNotNone(path)
        self.assertEqual(path, ["gateway", "auth"])

    def test_find_path_multi_hop(self):
        path = self.mapper.find_path("gateway", "db")
        self.assertIsNotNone(path)
        self.assertEqual(path[0], "gateway")
        self.assertEqual(path[-1], "db")
        self.assertLessEqual(len(path), 3)  # shortest path

    def test_find_path_same_node(self):
        path = self.mapper.find_path("gateway", "gateway")
        self.assertEqual(path, ["gateway"])

    def test_find_path_no_path(self):
        # cache has no outgoing edges to db
        path = self.mapper.find_path("cache", "db")
        self.assertIsNone(path)

    def test_find_path_with_exclude(self):
        # Exclude auth → must route through user-svc
        path = self.mapper.find_path("gateway", "db", exclude={"auth"})
        self.assertIsNotNone(path)
        self.assertNotIn("auth", path)

    def test_find_path_exclude_makes_unreachable(self):
        # If we exclude both intermediate nodes, no path exists
        path = self.mapper.find_path("gateway", "db", exclude={"auth", "user-svc"})
        self.assertIsNone(path)

    def test_find_all_paths(self):
        paths = self.mapper.find_all_paths("gateway", "db")
        self.assertGreaterEqual(len(paths), 2)  # via auth and via user-svc
        for p in paths:
            self.assertEqual(p[0], "gateway")
            self.assertEqual(p[-1], "db")

    def test_find_all_paths_no_path(self):
        paths = self.mapper.find_all_paths("cache", "gateway")
        self.assertEqual(paths, [])

    def test_get_dependency_graph(self):
        graph = self.mapper.get_dependency_graph()
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertEqual(len(graph["nodes"]), 5)
        self.assertEqual(len(graph["edges"]), 5)

    def test_get_capability_map(self):
        cap_map = self.mapper.get_capability_map()
        self.assertIn("auth", cap_map)
        self.assertIn("gateway", cap_map["auth"])
        self.assertIn("auth", cap_map["auth"])  # both gateway and auth provide auth
        self.assertIn("storage", cap_map)
        self.assertIn("db", cap_map["storage"])

    def test_find_nodes_by_capability(self):
        nodes = self.mapper.find_nodes_by_capability("auth")
        self.assertIn("gateway", nodes)
        self.assertIn("auth", nodes)

    def test_find_nodes_by_capability_nonexistent(self):
        nodes = self.mapper.find_nodes_by_capability("nonexistent-cap")
        self.assertEqual(nodes, [])

    def test_find_bottlenecks(self):
        """
        Topology:
            gateway → auth → db
            gateway → user-svc → db
            user-svc → cache

        db is a bottleneck: both paths from gateway to db end at db,
        but db is the sink, not an intermediate node.
        In this topology, no intermediate node is on ALL paths
        from gateway to db (auth is on one path, user-svc on the other).
        So bottlenecks should be empty.
        """
        bottlenecks = self.mapper.find_bottlenecks()
        # No single intermediate node is common to all paths
        self.assertEqual(bottlenecks, [])

    def test_find_bottlenecks_with_chokepoint(self):
        """
        Build a topology where 'bottleneck' is on all paths:
            src → bottleneck → dst1
            src → bottleneck → dst2
        """
        m = ServiceTopologyMapper()
        m.register_node("src", "service")
        m.register_node("bottleneck", "service")
        m.register_node("dst1", "service")
        m.register_node("dst2", "service")
        m.register_edge("src", "bottleneck")
        m.register_edge("bottleneck", "dst1")
        m.register_edge("bottleneck", "dst2")
        # Also add an alternative path to dst1 via dst2
        m.register_edge("dst2", "dst1")
        # bottleneck is on all paths from src to dst1 and dst2
        bottlenecks = m.find_bottlenecks()
        self.assertIn("bottleneck", bottlenecks)

    def test_suggest_alternatives_with_detour(self):
        """
        gateway → auth → db
        gateway → user-svc → db

        If auth fails, there's an alternative via user-svc.
        """
        result = self.mapper.suggest_alternatives("auth")
        self.assertGreater(len(result["affected_pairs"]), 0)
        # At least one pair should have an alternative path
        has_alt = any(
            alt["alternative_path"] is not None
            for alt in result["alternatives"]
        )
        self.assertTrue(has_alt)

    def test_suggest_alternatives_no_detour(self):
        """
        If db fails, no alternative path exists for pairs that go to db.
        """
        result = self.mapper.suggest_alternatives("db")
        # Pairs that ended at db are now unreachable
        self.assertGreater(len(result["unreachable_pairs"]), 0)

    def test_suggest_alternatives_nonexistent_node(self):
        result = self.mapper.suggest_alternatives("nonexistent")
        self.assertEqual(result["affected_pairs"], [])
        self.assertEqual(result["alternatives"], [])

    def test_suggest_alternatives_unaffected_node(self):
        """
        cache is a leaf (no outgoing edges) — it can only be a destination,
        never an intermediate node.  When it fails, pairs ending at cache
        are affected but have no alternative path (all unreachable).
        Crucially, cache does NOT affect any other pairs in the topology.
        """
        result = self.mapper.suggest_alternatives("cache")
        # All affected pairs must end at cache (it's never an intermediate)
        for src, dst in result["affected_pairs"]:
            self.assertEqual(dst, "cache")
        # No alternative paths exist (cache is the destination, can't bypass)
        has_alt = any(
            alt["alternative_path"] is not None
            for alt in result["alternatives"]
        )
        self.assertFalse(has_alt)
        # All affected pairs are unreachable
        self.assertEqual(len(result["affected_pairs"]),
                         len(result["unreachable_pairs"]))

    def test_get_all_nodes(self):
        nodes = self.mapper.get_all_nodes()
        self.assertEqual(len(nodes), 5)

    def test_get_all_edges(self):
        edges = self.mapper.get_all_edges()
        self.assertEqual(len(edges), 5)

    def test_json_serialisation_roundtrip(self):
        json_str = self.mapper.to_json()
        restored = ServiceTopologyMapper.from_json(json_str)
        self.assertEqual(restored.node_count(), 5)
        self.assertEqual(restored.edge_count(), 5)
        # Verify path still works after restoration
        path = restored.find_path("gateway", "db")
        self.assertIsNotNone(path)

    def test_dict_serialisation_roundtrip(self):
        data = self.mapper.to_dict()
        restored = ServiceTopologyMapper.from_dict(data)
        self.assertEqual(restored.node_count(), 5)
        # Verify capability map
        cap_map = restored.get_capability_map()
        self.assertIn("auth", cap_map)

    def test_repr(self):
        r = repr(self.mapper)
        self.assertIn("in-memory", r)
        self.assertIn("nodes=5", r)


# ═══════════════════════════════════════════════════════════════
#  ServiceTopologyMapper persistence tests
# ═══════════════════════════════════════════════════════════════


class TestTopologyMapperPersistence(unittest.TestCase):
    """Tests for SQLiteBackend persistence of ServiceTopologyMapper."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test_spatial.db")
        self.backend = SQLiteBackend(db_path=self.db_path)
        self.mapper = ServiceTopologyMapper(backend=self.backend)

    def tearDown(self) -> None:
        self.backend.close()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_persist_and_reload(self):
        self.mapper.register_node("gateway", "gateway", ["routing"])
        self.mapper.register_node("auth", "microservice", ["auth"])
        self.mapper.register_edge("gateway", "auth", RelationType.DEPENDS_ON, 1.0)
        self.backend.close()

        backend2 = SQLiteBackend(db_path=self.db_path)
        mapper2 = ServiceTopologyMapper(backend=backend2)
        self.assertEqual(mapper2.node_count(), 2)
        self.assertEqual(mapper2.edge_count(), 1)
        self.assertTrue(mapper2.has_edge("gateway", "auth"))
        backend2.close()

    def test_persist_with_health(self):
        self.mapper.register_node("svc", "service", health=NodeHealth.DEGRADED)
        self.backend.close()

        backend2 = SQLiteBackend(db_path=self.db_path)
        mapper2 = ServiceTopologyMapper(backend=backend2)
        node = mapper2.get_node("svc")
        self.assertEqual(node.health, NodeHealth.DEGRADED)
        backend2.close()

    def test_persist_update_health(self):
        self.mapper.register_node("svc", "service", health=NodeHealth.HEALTHY)
        self.mapper.update_node_health("svc", NodeHealth.UNHEALTHY)
        self.backend.close()

        backend2 = SQLiteBackend(db_path=self.db_path)
        mapper2 = ServiceTopologyMapper(backend=backend2)
        node = mapper2.get_node("svc")
        self.assertEqual(node.health, NodeHealth.UNHEALTHY)
        backend2.close()


# ═══════════════════════════════════════════════════════════════
#  Integration / edge-case tests
# ═══════════════════════════════════════════════════════════════


class TestProxyModulesIntegration(unittest.TestCase):
    """Integration tests combining Dynamics and Spatial proxies."""

    def test_dynamics_with_spatial_health_changes(self):
        """Track health changes as a service in the topology degrades."""
        mapper = ServiceTopologyMapper()
        mapper.register_node("gateway", "gateway", health=NodeHealth.HEALTHY)
        mapper.register_node("auth", "microservice", health=NodeHealth.HEALTHY)
        mapper.register_edge("gateway", "auth")

        tracker = EnvironmentDynamicsTracker()

        # Simulate health degradation
        tracker.record_state("auth", {"latency": 0.05}, 0.95)
        tracker.record_state("auth", {"latency": 0.15}, 0.80)
        tracker.record_state("auth", {"latency": 0.30}, 0.60)

        # Detect anomaly
        level, z = tracker.detect_anomaly("auth")
        self.assertTrue(level.is_anomalous)

        # Update topology to reflect degradation
        mapper.update_node_health("auth", NodeHealth.DEGRADED)

        # Suggest alternatives (no alternative path in this simple topology)
        result = mapper.suggest_alternatives("auth")
        # auth is a leaf, so no paths go through it
        # But if we had a path through auth, it would be affected
        self.assertIsInstance(result, dict)

    def test_trend_prediction_combined(self):
        """Use trend analysis to inform state prediction."""
        tracker = EnvironmentDynamicsTracker()

        # Simulate oscillating between two states (odd count for symmetry)
        for i in range(9):
            cpu = 0.1 if i % 2 == 0 else 0.5
            health = 1.0 if i % 2 == 0 else 0.7
            tracker.record_state("svc", {"cpu": cpu}, health)

        # Trend should be stable (symmetric oscillation)
        direction, slope = tracker.get_trend("svc", "cpu")
        self.assertEqual(direction, TrendDirection.STABLE)

        # Prediction should still give a distribution
        prediction = tracker.predict_state("svc", horizon_steps=2)
        self.assertGreater(len(prediction), 0)

    def test_empty_mapper_operations(self):
        """Operations on an empty mapper should not crash."""
        mapper = ServiceTopologyMapper()
        self.assertEqual(mapper.node_count(), 0)
        self.assertEqual(mapper.edge_count(), 0)
        self.assertEqual(mapper.get_neighbors("any"), [])
        self.assertIsNone(mapper.find_path("a", "b"))
        self.assertEqual(mapper.find_bottlenecks(), [])
        self.assertEqual(mapper.get_capability_map(), {})
        result = mapper.suggest_alternatives("any")
        self.assertEqual(result["affected_pairs"], [])

    def test_empty_tracker_operations(self):
        """Operations on an empty tracker should not crash."""
        tracker = EnvironmentDynamicsTracker()
        self.assertEqual(tracker.get_state_count("any"), 0)
        self.assertEqual(tracker.get_transitions("any"), [])
        self.assertEqual(tracker.compute_transition_matrix("any"), {})
        self.assertEqual(tracker.predict_state("any", 1), {})
        level, z = tracker.detect_anomaly("any")
        self.assertEqual(level, AnomalyLevel.NORMAL)


if __name__ == "__main__":
    unittest.main()
