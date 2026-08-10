"""
Environment Dynamics Proxy — models how the environment state changes
over time.

This module implements the **Dynamics** function of the World Proxy
six-function matrix.  It tracks environment snapshots for each service,
records state transitions, and provides predictive analytics:

- **State recording** — capture periodic environment snapshots (state
  dict + health score).
- **Transition tracking** — automatically detect and record state
  changes between consecutive snapshots.
- **Markov-chain prediction** — compute transition probability matrices
  and predict future states.
- **Anomaly detection** — flag current states that deviate from the
  historical distribution.
- **Trend analysis** — determine whether a metric is rising, falling,
  or stable.

Persistence
------------
When a :class:`~suyi.persistence.sqlite_backend.SQLiteBackend` is
injected, all snapshots and transitions are persisted as JSON-serialised
key-value pairs under the ``dynamics:`` namespace.  When no backend is
provided, an in-memory dictionary is used, making the tracker trivially
mockable for unit testing.

Usage::

    from suyi.quality.dynamics_proxy import (
        EnvironmentState,
        StateTransition,
        EnvironmentDynamicsTracker,
    )

    tracker = EnvironmentDynamicsTracker()

    tracker.record_state("api-gateway", {"cpu": 0.45, "mem": 0.60}, 0.95)
    tracker.record_state("api-gateway", {"cpu": 0.80, "mem": 0.65}, 0.70)

    transitions = tracker.get_transitions("api-gateway")
    matrix = tracker.compute_transition_matrix("api-gateway")
    prediction = tracker.predict_state("api-gateway", horizon_steps=3)
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════


class TrendDirection(Enum):
    """Direction of a metric trend over time."""

    RISING = auto()    # metric is increasing
    FALLING = auto()   # metric is decreasing
    STABLE = auto()    # metric is roughly constant

    @property
    def label(self) -> str:
        """Human-readable label."""
        return self.name.lower()


class AnomalyLevel(Enum):
    """Severity level of a detected anomaly."""

    NORMAL = auto()    # within expected range
    WARNING = auto()   # mildly anomalous (1–2 sigma)
    CRITICAL = auto()  # highly anomalous (>2 sigma)

    @property
    def label(self) -> str:
        """Human-readable label."""
        return self.name.lower()

    @property
    def is_anomalous(self) -> bool:
        """``True`` when the level indicates an anomaly."""
        return self != AnomalyLevel.NORMAL


# ═══════════════════════════════════════════════════════════════
#  Dataclasses
# ═══════════════════════════════════════════════════════════════


@dataclass
class EnvironmentState:
    """A single environment snapshot for a service.

    Attributes:
        timestamp:    Unix timestamp (seconds) when the snapshot was taken.
        service_name: Name of the service being observed.
        state_dict:   Arbitrary key-value mapping describing the
                      environment state (e.g. ``{"cpu": 0.45}``).
        health_score: Health score in ``[0.0, 1.0]`` where 1.0 is
                      perfectly healthy.
    """

    timestamp: float
    service_name: str
    state_dict: Dict[str, Any] = field(default_factory=dict)
    health_score: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.health_score <= 1.0):
            raise ValueError(
                f"health_score must be in [0, 1], got {self.health_score}"
            )

    @property
    def state_key(self) -> str:
        """A canonical string representation of the state dict.

        Used as a discrete state identifier for Markov-chain modelling.
        Values are rounded to one decimal place so that minor
        fluctuations don't create an explosion of distinct states.
        """
        if not self.state_dict:
            return "__empty__"
        parts: List[str] = []
        for key in sorted(self.state_dict.keys()):
            val = self.state_dict[key]
            if isinstance(val, float):
                val = round(val, 1)
            parts.append(f"{key}={val}")
        return "|".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "timestamp": self.timestamp,
            "service_name": self.service_name,
            "state_dict": dict(self.state_dict),
            "health_score": self.health_score,
            "state_key": self.state_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentState":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        return cls(
            timestamp=float(data.get("timestamp", 0.0)),
            service_name=data.get("service_name", ""),
            state_dict=data.get("state_dict", {}),
            health_score=float(data.get("health_score", 1.0)),
        )

    def __repr__(self) -> str:
        return (
            f"EnvironmentState(service={self.service_name!r}, "
            f"health={self.health_score:.2f}, "
            f"keys={len(self.state_dict)}, "
            f"t={self.timestamp:.1f})"
        )


@dataclass
class StateTransition:
    """A recorded state transition for a service.

    Attributes:
        from_state:   State key before the transition.
        to_state:     State key after the transition.
        trigger:      Description of what caused the transition
                      (e.g. ``"health_drop"``, ``"config_change"``).
        timestamp:    Unix timestamp when the transition was detected.
        service_name: Name of the service that transitioned.
    """

    from_state: str
    to_state: str
    trigger: str = ""
    timestamp: float = field(default_factory=time.time)
    service_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
            "service_name": self.service_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateTransition":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        return cls(
            from_state=data.get("from_state", ""),
            to_state=data.get("to_state", ""),
            trigger=data.get("trigger", ""),
            timestamp=float(data.get("timestamp", 0.0)),
            service_name=data.get("service_name", ""),
        )

    def __repr__(self) -> str:
        return (
            f"StateTransition(service={self.service_name!r}, "
            f"{self.from_state!r} → {self.to_state!r}, "
            f"trigger={self.trigger!r})"
        )


# ═══════════════════════════════════════════════════════════════
#  EnvironmentDynamicsTracker
# ═══════════════════════════════════════════════════════════════


class EnvironmentDynamicsTracker:
    """Tracks environment state dynamics and provides predictive analytics.

    The tracker records periodic environment snapshots for each service,
    automatically detects state transitions, and offers:

    - **Transition history** — query past state changes within a time
      window.
    - **Markov-chain prediction** — compute a transition probability
      matrix from observed transitions and predict future states.
    - **Anomaly detection** — compare the current health score against
      the historical distribution (mean ± std).
    - **Trend analysis** — determine whether a numeric metric is
      rising, falling, or stable over recent observations.

    Args:
        backend: Optional :class:`SQLiteBackend` for persistence.
            When ``None``, all data is kept in an in-memory dictionary.
    """

    #: Namespace prefix used for all persisted keys.
    _NAMESPACE: str = "dynamics"

    #: Number of recent snapshots used for trend analysis.
    _TREND_WINDOW: int = 10

    #: Threshold (in standard deviations) for *warning*-level anomalies.
    _WARNING_SIGMA: float = 1.0

    #: Threshold (in standard deviations) for *critical*-level anomalies.
    _CRITICAL_SIGMA: float = 2.0

    def __init__(self, backend: Optional[SQLiteBackend] = None) -> None:
        self._backend = backend
        # In-memory cache: service_name -> list[EnvironmentState]
        self._states: Dict[str, List[EnvironmentState]] = defaultdict(list)
        # In-memory cache: service_name -> list[StateTransition]
        self._transitions: Dict[str, List[StateTransition]] = defaultdict(list)
        # Load existing data from backend if available
        if self._backend is not None:
            self._load_from_backend()

    # ------------------------------------------------------------------
    #  State recording
    # ------------------------------------------------------------------

    def record_state(
        self,
        service_name: str,
        state_dict: Dict[str, Any],
        health_score: float = 1.0,
    ) -> EnvironmentState:
        """Record an environment snapshot for a service.

        If a previous snapshot exists for the same service and its
        state key differs, a :class:`StateTransition` is automatically
        created and stored.

        Args:
            service_name: Name of the service being observed.
            state_dict:   Key-value mapping describing the environment.
            health_score: Health score in ``[0.0, 1.0]``.

        Returns:
            The newly created :class:`EnvironmentState`.
        """
        state = EnvironmentState(
            timestamp=time.time(),
            service_name=service_name,
            state_dict=dict(state_dict),
            health_score=health_score,
        )

        # Detect transition from previous state
        prev_states = self._states.get(service_name, [])
        if prev_states:
            prev = prev_states[-1]
            if prev.state_key != state.state_key:
                trigger = self._infer_trigger(prev, state)
                transition = StateTransition(
                    from_state=prev.state_key,
                    to_state=state.state_key,
                    trigger=trigger,
                    timestamp=state.timestamp,
                    service_name=service_name,
                )
                self._transitions[service_name].append(transition)
                self._persist_transition(transition)

        self._states[service_name].append(state)
        self._persist_state(state)
        return state

    # ------------------------------------------------------------------
    #  Transition queries
    # ------------------------------------------------------------------

    def get_transitions(
        self,
        service_name: str,
        time_window: Optional[float] = None,
    ) -> List[StateTransition]:
        """Return state transitions for a service.

        Args:
            service_name: The service to query.
            time_window:  Optional time window in seconds.  Only
                transitions whose timestamp is within
                ``now - time_window`` are returned.  ``None`` returns
                all transitions.

        Returns:
            List of :class:`StateTransition` objects, oldest first.
        """
        transitions = self._transitions.get(service_name, [])
        if time_window is None:
            return list(transitions)
        cutoff = time.time() - time_window
        return [t for t in transitions if t.timestamp >= cutoff]

    def get_states(
        self,
        service_name: str,
        time_window: Optional[float] = None,
    ) -> List[EnvironmentState]:
        """Return recorded states for a service.

        Args:
            service_name: The service to query.
            time_window:  Optional time window in seconds.

        Returns:
            List of :class:`EnvironmentState` objects, oldest first.
        """
        states = self._states.get(service_name, [])
        if time_window is None:
            return list(states)
        cutoff = time.time() - time_window
        return [s for s in states if s.timestamp >= cutoff]

    # ------------------------------------------------------------------
    #  Transition matrix (Markov chain)
    # ------------------------------------------------------------------

    def compute_transition_matrix(
        self,
        service_name: str,
    ) -> Dict[str, Dict[str, float]]:
        """Compute the state transition probability matrix.

        The matrix is a nested dict where ``matrix[from_state][to_state]``
        gives the probability of transitioning from *from_state* to
        *to_state*.  Each row sums to 1.0 (or 0.0 for states that have
        never been left).

        Args:
            service_name: The service whose transitions to analyse.

        Returns:
            A ``Dict[str, Dict[str, float]]`` representing the matrix.
        """
        transitions = self._transitions.get(service_name, [])
        if not transitions:
            return {}

        # Count transitions
        counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for t in transitions:
            counts[t.from_state][t.to_state] += 1

        # Also consider states that were observed but never transitioned
        # from (self-loops).  We add a self-transition for the *current*
        # state so that prediction can stay in place.
        states_for_service = self._states.get(service_name, [])
        if states_for_service:
            current_state = states_for_service[-1].state_key
            if current_state not in counts:
                counts[current_state][current_state] = 1  # absorbent

        # Convert counts to probabilities
        matrix: Dict[str, Dict[str, float]] = {}
        for from_state, to_counts in counts.items():
            total = sum(to_counts.values())
            if total == 0:
                matrix[from_state] = {}
            else:
                matrix[from_state] = {
                    to_state: count / total
                    for to_state, count in to_counts.items()
                }
        return matrix

    # ------------------------------------------------------------------
    #  State prediction
    # ------------------------------------------------------------------

    def predict_state(
        self,
        service_name: str,
        horizon_steps: int = 1,
    ) -> Dict[str, float]:
        """Predict the probability distribution of future states.

        Uses a first-order Markov chain: the current state's row in the
        transition matrix is raised to the *horizon_steps*-th power
        (via repeated matrix multiplication) to produce a probability
        distribution over possible future states.

        Args:
            service_name:  The service to predict for.
            horizon_steps: How many steps ahead to predict (≥ 1).

        Returns:
            ``Dict[str, float]`` mapping state keys to their predicted
            probabilities.  Returns an empty dict if no transitions
            have been recorded.
        """
        if horizon_steps < 1:
            raise ValueError(f"horizon_steps must be ≥ 1, got {horizon_steps}")

        matrix = self.compute_transition_matrix(service_name)
        if not matrix:
            return {}

        states_for_service = self._states.get(service_name, [])
        if not states_for_service:
            return {}

        current_state = states_for_service[-1].state_key

        # If current state has no outgoing transitions, it's absorbent
        if current_state not in matrix or not matrix[current_state]:
            return {current_state: 1.0}

        # Start with the current state's distribution
        dist: Dict[str, float] = dict(matrix[current_state])

        # Collect all states for full matrix operations
        all_states = sorted(matrix.keys())
        for _ in range(horizon_steps - 1):
            new_dist: Dict[str, float] = defaultdict(float)
            for state, prob in dist.items():
                if prob <= 0:
                    continue
                row = matrix.get(state, {})
                if not row:
                    # Absorbent state — stays in place
                    new_dist[state] += prob
                else:
                    for next_state, next_prob in row.items():
                        new_dist[next_state] += prob * next_prob
            dist = dict(new_dist)
            # Normalise to handle floating-point drift
            total = sum(dist.values())
            if total > 0:
                dist = {k: v / total for k, v in dist.items()}

        return dict(dist)

    # ------------------------------------------------------------------
    #  Anomaly detection
    # ------------------------------------------------------------------

    def detect_anomaly(
        self,
        service_name: str,
    ) -> Tuple[AnomalyLevel, float]:
        """Detect whether the current state is anomalous.

        Compares the most recent health score against the historical
        distribution of health scores for the service.  The anomaly
        level is determined by how many standard deviations the current
        value deviates from the historical mean:

        - ``NORMAL``   — within 1 sigma
        - ``WARNING``  — between 1 and 2 sigma
        - ``CRITICAL`` — beyond 2 sigma

        A low absolute health score (< 0.3) is always at least
        ``WARNING``.

        Args:
            service_name: The service to check.

        Returns:
            A tuple of ``(AnomalyLevel, z_score)`` where *z_score* is
            the number of standard deviations from the mean.  Returns
            ``(AnomalyLevel.NORMAL, 0.0)`` if there is insufficient
            history (fewer than 2 data points).
        """
        states = self._states.get(service_name, [])
        if len(states) < 2:
            return AnomalyLevel.NORMAL, 0.0

        scores = [s.health_score for s in states]
        current = scores[-1]
        history = scores[:-1]  # exclude current

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0.0:
            # No variation — anomaly only if current differs from mean
            if abs(current - mean) > 0.01:
                return AnomalyLevel.CRITICAL, float("inf")
            return AnomalyLevel.NORMAL, 0.0

        z_score = abs(current - mean) / std

        if z_score > self._CRITICAL_SIGMA:
            level = AnomalyLevel.CRITICAL
        elif z_score > self._WARNING_SIGMA:
            level = AnomalyLevel.WARNING
        else:
            level = AnomalyLevel.NORMAL

        # Absolute threshold override
        if current < 0.3 and level == AnomalyLevel.NORMAL:
            level = AnomalyLevel.WARNING

        return level, round(z_score, 4)

    # ------------------------------------------------------------------
    #  Trend analysis
    # ------------------------------------------------------------------

    def get_trend(
        self,
        service_name: str,
        metric_name: str,
    ) -> Tuple[TrendDirection, float]:
        """Determine the trend of a specific metric.

        Examines the most recent ``_TREND_WINDOW`` snapshots and
        computes a simple linear slope.  The trend is classified as:

        - ``RISING``  — slope > ``threshold``
        - ``FALLING`` — slope < ``-threshold``
        - ``STABLE``  — otherwise

        The threshold is derived from the magnitude of the metric values
        to avoid false trends on noisy data.

        Args:
            service_name: The service to analyse.
            metric_name:  The key inside ``state_dict`` to track.

        Returns:
            A tuple of ``(TrendDirection, slope)`` where *slope* is the
            average change per snapshot.  Returns
            ``(TrendDirection.STABLE, 0.0)`` if the metric is absent or
            there are fewer than 2 data points.
        """
        states = self._states.get(service_name, [])
        if len(states) < 2:
            return TrendDirection.STABLE, 0.0

        # Collect values for the requested metric
        values: List[float] = []
        for s in states:
            val = s.state_dict.get(metric_name)
            if val is not None and isinstance(val, (int, float)):
                values.append(float(val))

        if len(values) < 2:
            return TrendDirection.STABLE, 0.0

        # Use the most recent window
        window = values[-self._TREND_WINDOW:]
        if len(window) < 2:
            return TrendDirection.STABLE, 0.0

        # Compute average slope (least-squares simplified)
        n = len(window)
        x_mean = (n - 1) / 2.0
        y_mean = sum(window) / n
        numerator = sum(
            (i - x_mean) * (window[i] - y_mean) for i in range(n)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0.0

        # Dynamic threshold: 5% of the mean absolute value, or 0.01 minimum
        mean_abs = abs(y_mean) if y_mean != 0 else 1.0
        threshold = max(0.01, mean_abs * 0.05)

        if slope > threshold:
            direction = TrendDirection.RISING
        elif slope < -threshold:
            direction = TrendDirection.FALLING
        else:
            direction = TrendDirection.STABLE

        return direction, round(slope, 6)

    # ------------------------------------------------------------------
    #  Utility queries
    # ------------------------------------------------------------------

    def get_latest_state(self, service_name: str) -> Optional[EnvironmentState]:
        """Return the most recent state for a service, or ``None``."""
        states = self._states.get(service_name, [])
        return states[-1] if states else None

    def get_service_names(self) -> List[str]:
        """Return a sorted list of all tracked service names."""
        return sorted(self._states.keys())

    def get_state_count(self, service_name: str) -> int:
        """Return the number of recorded states for a service."""
        return len(self._states.get(service_name, []))

    def get_transition_count(self, service_name: str) -> int:
        """Return the number of recorded transitions for a service."""
        return len(self._transitions.get(service_name, []))

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise all tracked data to a dict."""
        return {
            "states": {
                name: [s.to_dict() for s in states]
                for name, states in self._states.items()
            },
            "transitions": {
                name: [t.to_dict() for t in transitions]
                for name, transitions in self._transitions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentDynamicsTracker":
        """Reconstruct a tracker from a serialised dict (in-memory only)."""
        tracker = cls(backend=None)
        for name, state_list in data.get("states", {}).items():
            tracker._states[name] = [
                EnvironmentState.from_dict(s) for s in state_list
            ]
        for name, trans_list in data.get("transitions", {}).items():
            tracker._transitions[name] = [
                StateTransition.from_dict(t) for t in trans_list
            ]
        return tracker

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_trigger(
        prev: EnvironmentState,
        curr: EnvironmentState,
    ) -> str:
        """Infer a human-readable trigger for a state transition."""
        if curr.health_score < prev.health_score - 0.1:
            return "health_drop"
        if curr.health_score > prev.health_score + 0.1:
            return "health_recover"
        return "state_change"

    def _persist_state(self, state: EnvironmentState) -> None:
        """Persist a state snapshot to the backend (if available)."""
        if self._backend is None:
            return
        key = f"{self._NAMESPACE}:state:{state.service_name}:{state.timestamp}"
        self._backend.set(key, state.to_dict())

    def _persist_transition(self, transition: StateTransition) -> None:
        """Persist a transition to the backend (if available)."""
        if self._backend is None:
            return
        key = (
            f"{self._NAMESPACE}:transition:"
            f"{transition.service_name}:{transition.timestamp}"
        )
        self._backend.set(key, transition.to_dict())

    def _load_from_backend(self) -> None:
        """Load all persisted states and transitions from the backend."""
        assert self._backend is not None

        state_keys = self._backend.list_keys(
            pattern=f"{self._NAMESPACE}:state:"
        )
        for key in state_keys:
            data = self._backend.get(key)
            if data is None:
                continue
            state = EnvironmentState.from_dict(data)
            self._states[state.service_name].append(state)

        transition_keys = self._backend.list_keys(
            pattern=f"{self._NAMESPACE}:transition:"
        )
        for key in transition_keys:
            data = self._backend.get(key)
            if data is None:
                continue
            transition = StateTransition.from_dict(data)
            self._transitions[transition.service_name].append(transition)

        # Sort by timestamp to ensure chronological order
        for name in self._states:
            self._states[name].sort(key=lambda s: s.timestamp)
        for name in self._transitions:
            self._transitions[name].sort(key=lambda t: t.timestamp)

    def __repr__(self) -> str:
        n_services = len(self._states)
        n_states = sum(len(v) for v in self._states.values())
        n_transitions = sum(len(v) for v in self._transitions.values())
        backend_type = "SQLiteBackend" if self._backend else "in-memory"
        return (
            f"EnvironmentDynamicsTracker(backend={backend_type}, "
            f"services={n_services}, states={n_states}, "
            f"transitions={n_transitions})"
        )
