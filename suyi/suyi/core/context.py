"""
Context Assembler — Four-layer context assembly with cache-friendly stable prefix.

Layers (ordered for prefix-cache optimization):
    1. systemPrompt     — identity + project rules (stable, cache-friendly)
    2. toolDefinitions  — available tools (semi-stable)
    3. memorySnapshot   — retrieved memories (per-turn, on-demand)
    4. messages         — conversation history (per-turn, always changing)

The stable prefix (identity + project_rules) is placed at the very front
of the system prompt so that KV-cache hits are maximized. Variable parts
(memory, budget constraints) are appended after the stable prefix,
separated by XML tags for clear semantic boundaries:

    <identity> ... </identity>
    <project_rules> ... </project_rules>
    <memory> ... </memory>              ← per-turn, on-demand
    <budget_constraint> ... </budget_constraint>  ← per-turn, progressive
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from .budget import BudgetStatus


# ── Tool Definition ────────────────────────────────────────────


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""

    name: str
    description: str
    parameters: dict  # JSON Schema

    def to_dict(self) -> dict:
        """Convert to OpenAI-compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── Memory Backend Protocol ────────────────────────────────────


@runtime_checkable
class MemoryBackend(Protocol):
    """
    Protocol for memory retrieval backends.

    Any object with an async `retrieve(query, top_k)` method qualifies.
    The memory system (episodic/semantic/working) will implement this.
    """

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve relevant memory items for the given query.
        Each item should be a dict with at least a 'content' key.
        """
        ...


class InMemoryBackend:
    """Simple in-memory backend for testing — keyword-based matching."""

    def __init__(self, items: Optional[list[dict]] = None):
        self._items: list[dict] = items or []

    def add(self, item: dict) -> None:
        self._items.append(item)

    def add_many(self, items: list[dict]) -> None:
        self._items.extend(items)

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        query_words = set(query.lower().split())
        scored: list[tuple[int, dict]] = []
        for item in self._items:
            text = item.get("content", "").lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:top_k]]


# ── Configuration ──────────────────────────────────────────────


@dataclass
class IdentityConfig:
    """Agent identity — part of the stable prefix (computed once)."""

    name: str = "Suyi"
    description: str = "A self-evolving AI agent that learns from interactions."
    instructions: str = ""


@dataclass
class ProjectRules:
    """Project-level rules — part of the stable prefix (computed once)."""

    rules: list[str] = field(default_factory=list)


# ── Assembled Context ──────────────────────────────────────────


@dataclass
class AssembledContext:
    """
    The fully assembled context for a single LLM call.

    Attributes:
        system_prompt:    Complete system prompt (stable prefix + variable parts)
        tool_defs:        List of tool definitions
        memory_snapshot:  Retrieved memory items (may be empty)
        messages:         Conversation history (user/assistant/tool messages)
        budget_status:    Current budget status snapshot (may be None)
    """

    system_prompt: str
    tool_defs: list[ToolDefinition]
    memory_snapshot: list[dict]
    messages: list[dict]
    budget_status: Optional[BudgetStatus] = None


# ── Context Assembler ──────────────────────────────────────────


class ContextAssembler:
    """
    Assembles the four-layer context for each LLM call.

    The stable prefix (identity + project rules) is computed once at __init__
    and reused for every assembly, maximizing prefix-cache effectiveness.

    Memory is retrieved on-demand using the last user message as a query.
    Budget constraints are injected as natural-language instructions.

    Usage:
        assembler = ContextAssembler(
            identity=IdentityConfig(name="MyAgent", ...),
            project_rules=ProjectRules(rules=["Always be helpful"]),
            tool_defs=[ToolDefinition(...)],
            memory_backend=InMemoryBackend([...]),
        )
        context = await assembler.assemble(history, budget_constraint, budget_status)
    """

    def __init__(
        self,
        identity: Optional[IdentityConfig] = None,
        project_rules: Optional[ProjectRules] = None,
        tool_defs: Optional[list[ToolDefinition]] = None,
        memory_backend: Optional[MemoryBackend] = None,
        max_memory_items: int = 5,
    ):
        self.identity = identity or IdentityConfig()
        self.project_rules = project_rules or ProjectRules()
        self.tool_defs: list[ToolDefinition] = tool_defs or []
        self.memory_backend = memory_backend
        self.max_memory_items = max_memory_items
        # Pre-compute stable prefix — never changes between turns
        self._stable_prefix: str = self._build_stable_prefix()

    def _build_stable_prefix(self) -> str:
        """Build the stable prefix from identity and project rules (XML-tagged)."""
        parts: list[str] = []

        # Identity section
        identity_lines = [
            f"Name: {self.identity.name}",
            f"Role: {self.identity.description}",
        ]
        if self.identity.instructions:
            identity_lines.append(self.identity.instructions)
        parts.append("<identity>\n" + "\n".join(identity_lines) + "\n</identity>")

        # Project rules section
        if self.project_rules.rules:
            rules_text = "\n".join(f"- {r}" for r in self.project_rules.rules)
            parts.append(f"<project_rules>\n{rules_text}\n</project_rules>")

        return "\n\n".join(parts)

    @property
    def stable_prefix(self) -> str:
        """The cached stable prefix (identity + project rules). Never changes."""
        return self._stable_prefix

    def _format_memory(self, items: list[dict]) -> str:
        """Format memory items as an XML-tagged <memory> section."""
        if not items:
            return ""
        lines: list[str] = []
        for item in items:
            content = item.get("content", str(item))
            source = item.get("source", "memory")
            confidence = item.get("confidence")
            meta_parts = [f"source: {source}"]
            if confidence is not None:
                meta_parts.append(f"confidence: {confidence}")
            meta = " (" + ", ".join(meta_parts) + ")"
            lines.append(f"- {content}{meta}")
        return "<memory>\n" + "\n".join(lines) + "\n</memory>"

    def _format_budget_constraint(self, instruction: Optional[str]) -> str:
        """Format budget constraint instruction as an XML-tagged section."""
        if not instruction:
            return ""
        return f"<budget_constraint>\n{instruction}\n</budget_constraint>"

    @staticmethod
    def _get_last_user_message(messages: list[dict]) -> Optional[str]:
        """Extract the last user message content for memory retrieval."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                # Handle list-style content (multimodal)
                if isinstance(content, list):
                    texts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    return " ".join(texts) if texts else None
        return None

    async def assemble(
        self,
        messages: list[dict],
        budget_constraint: Optional[str] = None,
        budget_status: Optional[BudgetStatus] = None,
    ) -> AssembledContext:
        """
        Assemble the full context for an LLM call.

        Args:
            messages:          Conversation history (user/assistant/tool messages)
            budget_constraint: Natural-language budget constraint instruction
            budget_status:     Current budget status snapshot

        Returns:
            AssembledContext with all four layers

        Layer ordering (cache-friendly):
            1. Stable prefix (identity + project_rules) — always first
            2. Memory snapshot (on-demand, per-turn)
            3. Budget constraint (progressive, per-turn)
            4. Messages (passed through, not embedded in system prompt)
        """
        # Layer 1: Stable prefix (cached) — always first for cache hits
        system_parts: list[str] = [self._stable_prefix]

        # Layer 3: Memory snapshot (on-demand retrieval using last user message)
        memory_snapshot: list[dict] = []
        if self.memory_backend is not None:
            query = self._get_last_user_message(messages)
            if query:
                try:
                    memory_snapshot = await self.memory_backend.retrieve(
                        query, top_k=self.max_memory_items
                    )
                except Exception:
                    # Memory retrieval failure should not break the loop
                    memory_snapshot = []

        memory_section = self._format_memory(memory_snapshot)
        if memory_section:
            system_parts.append(memory_section)

        # Budget constraint (variable, appended after stable prefix)
        constraint_section = self._format_budget_constraint(budget_constraint)
        if constraint_section:
            system_parts.append(constraint_section)

        system_prompt = "\n\n".join(system_parts)

        return AssembledContext(
            system_prompt=system_prompt,
            tool_defs=list(self.tool_defs),  # defensive copy
            memory_snapshot=memory_snapshot,
            messages=list(messages),  # defensive copy
            budget_status=budget_status,
        )
