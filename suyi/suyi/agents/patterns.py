"""
Multi-Agent Collaboration Patterns — Pipeline, Blackboard, Voting.

Three canonical collaboration patterns for multi-agent systems:

1. **Pipeline** (管道链): Serial data flow — output of agent N is input
   to agent N+1. Suitable for sequential processing stages.

2. **Blackboard** (共享黑板): Shared storage with partition-based
   namespaces and pub/sub notifications. Agents write results and
   read others' results through a shared space.

3. **Voting** (投票决策): Multiple agents vote on a decision. Three
   strategies: majority, weighted, and confidence-based.

Pattern Selection Guide::

    ┌────────────┬──────────────────────────┬─────────────────────┐
    │ Pattern    │ When to Use              │ Data Flow           │
    ├────────────┼──────────────────────────┼─────────────────────┤
    │ Pipeline   │ Sequential stages        │ Linear: A→B→C      │
    │ Blackboard │ Agents share partial     │ Any-to-any via     │
    │            │ results asynchronously   │ shared space       │
    │ Voting     │ Multiple opinions need   │ Fan-out → converge │
    │            │ to be reconciled         │                     │
    └────────────┴──────────────────────────┴─────────────────────┘
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .base import AgentInstance
from ..core.loop import LoopResult


# ═══════════════════════════════════════════════════════════════
#  1. Pipeline (管道链)
# ═══════════════════════════════════════════════════════════════


@dataclass
class PipelineStage:
    """A single stage in a pipeline.

    Attributes:
        agent: The agent instance for this stage.
        name: Optional name for the stage (defaults to agent name).
        transform: Optional function to transform the input before
            passing to the agent. Takes the previous stage's output
            and returns the input string for this stage.
    """

    agent: AgentInstance
    name: str = ""
    transform: Optional[Callable[[str], str]] = None

    def __post_init__(self):
        if not self.name:
            self.name = self.agent.name


@dataclass
class PipelineResult:
    """Result of a pipeline execution.

    Attributes:
        final_output: The output of the last stage.
        stage_outputs: List of (stage_name, output) for each stage.
        success: Whether all stages completed successfully.
        failed_stage: Name of the stage that failed (if any).
        error: Error message if a stage failed.
    """

    final_output: str
    stage_outputs: list[tuple[str, str]] = field(default_factory=list)
    success: bool = True
    failed_stage: str = ""
    error: str = ""

    def __str__(self) -> str:
        return (
            f"PipelineResult(success={self.success}, "
            f"stages={len(self.stage_outputs)}, "
            f"output_len={len(self.final_output)})"
        )


class Pipeline:
    """A pipeline of agents with serial data flow.

    The output of each stage becomes the input to the next stage.
    If a stage fails, the pipeline stops and returns a partial result.

    Usage::

        pipeline = Pipeline([
            PipelineStage(agent=extractor, name="extract"),
            PipelineStage(agent=analyzer, name="analyze"),
            PipelineStage(agent=reporter, name="report"),
        ])
        result = await pipeline.run("Raw input data")
        print(result.final_output)

    With input transformation::

        pipeline = Pipeline([
            PipelineStage(agent=translator, transform=lambda x: f"Translate: {x}"),
            PipelineStage(agent=summarizer),
        ])
    """

    def __init__(self, stages: list[PipelineStage]):
        if not stages:
            raise ValueError("Pipeline requires at least one stage.")
        self.stages = stages

    async def run(self, initial_input: str) -> PipelineResult:
        """Run the pipeline with serial data flow.

        Args:
            initial_input: The input to the first stage.

        Returns:
            PipelineResult with the final output and per-stage outputs.
        """
        stage_outputs: list[tuple[str, str]] = []
        current_input = initial_input

        for stage in self.stages:
            # Apply transform if provided
            stage_input = stage.transform(current_input) if stage.transform else current_input

            try:
                loop_result: LoopResult = await stage.agent.run(stage_input)
                output = loop_result.content

                if not loop_result.is_complete:
                    return PipelineResult(
                        final_output=output,
                        stage_outputs=stage_outputs,
                        success=False,
                        failed_stage=stage.name,
                        error=f"Stage '{stage.name}' ended with status: {loop_result.stop_reason}",
                    )

                stage_outputs.append((stage.name, output))
                current_input = output

            except Exception as e:
                return PipelineResult(
                    final_output="",
                    stage_outputs=stage_outputs,
                    success=False,
                    failed_stage=stage.name,
                    error=str(e),
                )

        return PipelineResult(
            final_output=current_input,
            stage_outputs=stage_outputs,
            success=True,
        )

    def run_sync(self, initial_input: str) -> PipelineResult:
        """Sync convenience method."""
        return asyncio.run(self.run(initial_input))

    @property
    def stage_names(self) -> list[str]:
        """Names of all stages in order."""
        return [s.name for s in self.stages]

    def __repr__(self) -> str:
        return f"Pipeline(stages={self.stage_names})"


# ═══════════════════════════════════════════════════════════════
#  2. Blackboard (共享黑板)
# ═══════════════════════════════════════════════════════════════


@dataclass
class BlackboardEntry:
    """A single entry in the blackboard.

    Attributes:
        partition: The partition name (namespace).
        key: The key within the partition.
        value: The stored value.
        author: Name of the agent that wrote this entry.
        version: Version number (incremented on each write to the same key).
    """

    partition: str
    key: str
    value: Any
    author: str = ""
    version: int = 1


class Blackboard:
    """Shared blackboard with partition-based storage and subscription.

    The blackboard pattern allows multiple agents to share data through
    a common space. Agents can:
        - **Write** results to a partition/key
        - **Read** other agents' results
        - **Subscribe** to changes and get notified when data is written

    Partitions provide namespace isolation — different agents or
    task groups can use separate partitions without key collisions.

    Thread Safety:
        All operations are protected by a threading.Lock, making the
        blackboard safe for concurrent access from multiple threads
        (e.g., when agents run in parallel via ThreadPoolExecutor).

    Usage::

        bb = Blackboard()

        # Write
        bb.write("research", "findings", {"topic": "AI", "summary": "..."})

        # Read
        data = bb.read("research", "findings")

        # Subscribe
        def on_update(entry):
            print(f"New data in {entry.partition}/{entry.key}")
        bb.subscribe("research", on_update)

        # Write triggers notification
        bb.write("research", "findings", {"updated": True})
    """

    def __init__(self):
        # partition → key → BlackboardEntry
        self._data: dict[str, dict[str, BlackboardEntry]] = {}
        # partition → list of callbacks
        self._subscribers: dict[str, list[Callable[[BlackboardEntry], None]]] = {}
        self._lock = threading.RLock()

    # ── Write ───────────────────────────────────────────────────

    def write(
        self,
        partition: str,
        key: str,
        value: Any,
        author: str = "",
    ) -> BlackboardEntry:
        """Write a value to the blackboard.

        If the key already exists, its value is updated and the version
        number is incremented. Subscribers are notified after the write.

        Args:
            partition: The partition name (namespace).
            key: The key within the partition.
            value: The value to store.
            author: Name of the writing agent.

        Returns:
            The created/updated BlackboardEntry.
        """
        with self._lock:
            if partition not in self._data:
                self._data[partition] = {}

            existing = self._data[partition].get(key)
            version = (existing.version + 1) if existing else 1

            entry = BlackboardEntry(
                partition=partition,
                key=key,
                value=value,
                author=author,
                version=version,
            )
            self._data[partition][key] = entry

            # Notify subscribers (outside the lock to prevent deadlock)
            callbacks = list(self._subscribers.get(partition, []))

        # Fire notifications outside the lock
        for callback in callbacks:
            try:
                callback(entry)
            except Exception:
                pass  # Subscriber errors don't break the blackboard

        return entry

    # ── Read ────────────────────────────────────────────────────

    def read(self, partition: str, key: str) -> Optional[Any]:
        """Read a value from the blackboard.

        Args:
            partition: The partition name.
            key: The key within the partition.

        Returns:
            The stored value, or None if not found.
        """
        with self._lock:
            part = self._data.get(partition)
            if part is None:
                return None
            entry = part.get(key)
            return entry.value if entry else None

    def read_entry(self, partition: str, key: str) -> Optional[BlackboardEntry]:
        """Read a full BlackboardEntry (with metadata).

        Returns:
            The BlackboardEntry, or None if not found.
        """
        with self._lock:
            part = self._data.get(partition)
            if part is None:
                return None
            return part.get(key)

    def read_partition(self, partition: str) -> dict[str, Any]:
        """Read all key-value pairs in a partition.

        Returns:
            Dict of key → value, or empty dict if partition doesn't exist.
        """
        with self._lock:
            part = self._data.get(partition)
            if part is None:
                return {}
            return {k: e.value for k, e in part.items()}

    # ── Delete ──────────────────────────────────────────────────

    def delete(self, partition: str, key: str) -> bool:
        """Delete a key from a partition.

        Returns:
            True if the key was found and deleted, False otherwise.
        """
        with self._lock:
            part = self._data.get(partition)
            if part is None:
                return False
            return part.pop(key, None) is not None

    def clear_partition(self, partition: str) -> int:
        """Clear all entries in a partition.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            part = self._data.pop(partition, None)
            return len(part) if part else 0

    # ── Subscribe ───────────────────────────────────────────────

    def subscribe(
        self,
        partition: str,
        callback: Callable[[BlackboardEntry], None],
    ) -> Callable[[], None]:
        """Subscribe to changes in a partition.

        The callback is called whenever a value is written to the
        specified partition. The callback receives the BlackboardEntry.

        Args:
            partition: The partition to watch.
            callback: Function called on each write.

        Returns:
            An unsubscribe function. Call it to remove the subscription.
        """
        with self._lock:
            if partition not in self._subscribers:
                self._subscribers[partition] = []
            self._subscribers[partition].append(callback)

        def unsubscribe():
            with self._lock:
                subs = self._subscribers.get(partition, [])
                if callback in subs:
                    subs.remove(callback)

        return unsubscribe

    def subscriber_count(self, partition: str) -> int:
        """Return the number of subscribers for a partition."""
        with self._lock:
            return len(self._subscribers.get(partition, []))

    # ── Query ───────────────────────────────────────────────────

    def list_partitions(self) -> list[str]:
        """Return all partition names."""
        with self._lock:
            return list(self._data.keys())

    def list_keys(self, partition: str) -> list[str]:
        """Return all keys in a partition."""
        with self._lock:
            part = self._data.get(partition)
            return list(part.keys()) if part else []

    def total_entries(self) -> int:
        """Return total number of entries across all partitions."""
        with self._lock:
            return sum(len(part) for part in self._data.values())

    def __repr__(self) -> str:
        with self._lock:
            partitions = len(self._data)
            entries = self.total_entries()
        return f"Blackboard(partitions={partitions}, entries={entries})"


# ═══════════════════════════════════════════════════════════════
#  3. Voting (投票决策)
# ═══════════════════════════════════════════════════════════════


class VotingStrategy(Enum):
    """Voting decision strategies.

    - **MAJORITY**: The option with the most votes wins (one agent = one vote).
    - **WEIGHTED**: The option with the highest total weight wins.
    - **CONFIDENCE**: The option with the highest total confidence wins.
    """

    MAJORITY = "majority"
    WEIGHTED = "weighted"
    CONFIDENCE = "confidence"


@dataclass
class Vote:
    """A single vote from an agent.

    Attributes:
        voter: Name of the voting agent.
        choice: The option being voted for.
        weight: Vote weight (default 1.0). Used in weighted voting.
        confidence: Confidence score 0.0-1.0 (default 1.0). Used in
            confidence voting.
        reason: Optional reasoning for the vote.
    """

    voter: str
    choice: str
    weight: float = 1.0
    confidence: float = 1.0
    reason: str = ""


@dataclass
class VoteResult:
    """Result of a voting decision.

    Attributes:
        winner: The winning choice (empty string if no votes or tie).
        strategy: The voting strategy used.
        votes: All votes cast.
        tallies: Per-choice tally scores (depends on strategy).
        margin: Difference between winner and runner-up.
        is_tie: True if there was a tie.
        total_votes: Total number of votes cast.
    """

    winner: str
    strategy: VotingStrategy
    votes: list[Vote] = field(default_factory=list)
    tallies: dict[str, float] = field(default_factory=dict)
    margin: float = 0.0
    is_tie: bool = False
    total_votes: int = 0

    def __str__(self) -> str:
        return (
            f"VoteResult(winner={self.winner!r}, "
            f"strategy={self.strategy.value}, "
            f"votes={self.total_votes}, "
            f"margin={self.margin:.2f})"
        )


class Voting:
    """Multi-agent voting with majority, weighted, and confidence strategies.

    Agents cast votes for options. The voting system tallies votes
    according to the chosen strategy and determines a winner.

    Usage::

        voting = Voting(strategy=VotingStrategy.WEIGHTED)
        voting.add_vote(Vote("agent1", "option_a", weight=2.0, confidence=0.9))
        voting.add_vote(Vote("agent2", "option_b", weight=1.0, confidence=0.7))
        voting.add_vote(Vote("agent3", "option_a", weight=1.5, confidence=0.8))
        result = voting.decide()
        print(result.winner)  # "option_a" (total weight: 3.5 vs 1.0)

    Strategies:
        - **Majority**: Counts votes (1 per agent). Highest count wins.
        - **Weighted**: Sums weights. Highest total weight wins.
        - **Confidence**: Sums confidence scores. Highest total wins.
    """

    def __init__(self, strategy: VotingStrategy = VotingStrategy.MAJORITY):
        self.strategy = strategy
        self._votes: list[Vote] = []

    def add_vote(
        self,
        voter: str,
        choice: str,
        weight: float = 1.0,
        confidence: float = 1.0,
        reason: str = "",
    ) -> Vote:
        """Add a vote to the voting.

        Args:
            voter: Name of the voting agent.
            choice: The option being voted for.
            weight: Vote weight (default 1.0).
            confidence: Confidence score 0.0-1.0 (default 1.0).
            reason: Optional reasoning.

        Returns:
            The created Vote object.
        """
        vote = Vote(
            voter=voter,
            choice=choice,
            weight=weight,
            confidence=confidence,
            reason=reason,
        )
        self._votes.append(vote)
        return vote

    def add_vote_obj(self, vote: Vote) -> None:
        """Add a pre-constructed Vote object."""
        self._votes.append(vote)

    @property
    def votes(self) -> list[Vote]:
        """All votes cast so far."""
        return list(self._votes)

    @property
    def vote_count(self) -> int:
        """Total number of votes."""
        return len(self._votes)

    @property
    def choices(self) -> set[str]:
        """All unique choices that received votes."""
        return {v.choice for v in self._votes}

    def decide(self) -> VoteResult:
        """Tally votes and determine the winner.

        Returns:
            VoteResult with the winner and detailed tallies.

        Ties:
            If two or more choices have the same top score, the result
            has is_tie=True and winner is the first one encountered
            (deterministic by insertion order).
        """
        if not self._votes:
            return VoteResult(
                winner="",
                strategy=self.strategy,
                votes=[],
                tallies={},
                margin=0.0,
                is_tie=False,
                total_votes=0,
            )

        # Tally based on strategy
        tallies: dict[str, float] = {}

        for vote in self._votes:
            if vote.choice not in tallies:
                tallies[vote.choice] = 0.0

            if self.strategy == VotingStrategy.MAJORITY:
                tallies[vote.choice] += 1.0
            elif self.strategy == VotingStrategy.WEIGHTED:
                tallies[vote.choice] += vote.weight
            elif self.strategy == VotingStrategy.CONFIDENCE:
                tallies[vote.choice] += vote.confidence

        # Find winner
        sorted_choices = sorted(tallies.items(), key=lambda x: -x[1])

        if len(sorted_choices) == 1:
            winner = sorted_choices[0][0]
            margin = sorted_choices[0][1]
            is_tie = False
        else:
            winner = sorted_choices[0][0]
            margin = sorted_choices[0][1] - sorted_choices[1][1]
            is_tie = abs(margin) < 1e-9  # Floating point comparison

        return VoteResult(
            winner=winner,
            strategy=self.strategy,
            votes=list(self._votes),
            tallies=tallies,
            margin=margin,
            is_tie=is_tie,
            total_votes=len(self._votes),
        )

    def reset(self) -> None:
        """Clear all votes for a new round."""
        self._votes.clear()

    def __repr__(self) -> str:
        return (
            f"Voting(strategy={self.strategy.value}, "
            f"votes={len(self._votes)}, "
            f"choices={sorted(self.choices)})"
        )
