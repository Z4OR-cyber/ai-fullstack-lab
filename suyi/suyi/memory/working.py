"""Working Memory — manages the current conversation context.

This is the shortest-lived memory layer, holding only the active conversation.
Each call to :meth:`WorkingMemory.build_context` dynamically assembles the
minimal context needed within the token budget.  When the budget is
exceeded, older messages are compressed into a running summary, allowing
the conversation to continue without losing important context.

Token budget uses three threshold levels (the "constraint→instruction"
translator pattern — budget status is converted to natural-language
guidance injected into the system prompt):

================================  ============  ==================
Level                             Threshold     Action
================================  ============  ==================
``normal``                        < 70 %        No action
``approaching``                   ≥ 70 %        Gentle reminder
``critical``                      ≥ 85 %        Explicit length limits
``compacting``                    ≥ 90 %        Emergency compression
================================  ============  ==================
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..utils.token_counter import (
    estimate_message_tokens,
    estimate_tokens,
)


class BudgetStatus:
    """Snapshot of the current token-budget usage.

    Encapsulates the raw numbers *and* the derived natural-language
    instructions that can be injected into the LLM prompt to steer
    behaviour when the budget tightens.

    Attributes:
        used: Tokens currently consumed.
        budget: Total token budget.
        ratio: ``used / budget`` (may exceed 1.0 if over budget).
        level: One of ``'normal'``, ``'approaching'``, ``'critical'``,
            ``'compacting'``.
        instructions: Human-readable instruction string (empty when
            ``level == 'normal'``).
    """

    THRESHOLDS: Dict[str, float] = {
        'approaching': 0.70,
        'critical': 0.85,
        'compacting': 0.90,
    }

    def __init__(self, used: int, budget: int) -> None:
        self.used = used
        self.budget = budget
        self.ratio: float = used / budget if budget > 0 else 0.0
        self.level: str = self._determine_level()
        self.instructions: str = self._generate_instructions()

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------
    def _determine_level(self) -> str:
        """Map the usage ratio to a threshold level."""
        if self.ratio >= self.THRESHOLDS['compacting']:
            return 'compacting'
        if self.ratio >= self.THRESHOLDS['critical']:
            return 'critical'
        if self.ratio >= self.THRESHOLDS['approaching']:
            return 'approaching'
        return 'normal'

    def _generate_instructions(self) -> str:
        """Translate the budget level into natural-language instructions.

        This is the *constraint→instruction translator*: instead of
        silently truncating context, we tell the model *why* it should
        be concise and *what* to do about it.
        """
        pct = f"{self.ratio:.0%}"
        if self.level == 'normal':
            return ""
        if self.level == 'approaching':
            return (
                f"[Budget notice] Context usage at {pct}. "
                "Be mindful of response length; avoid unnecessary repetition."
            )
        if self.level == 'critical':
            return (
                f"[Budget warning] Context usage at {pct}. "
                "Keep responses concise. Do not repeat previously stated "
                "information. Summarise rather than expand."
            )
        # compacting
        return (
            f"[Budget critical] Context usage at {pct}. "
            "Emergency compression active. Minimise output strictly. "
            "Reference summaries for prior context. Output only essential "
            "information."
        )

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    @property
    def is_over_budget(self) -> bool:
        """True when usage exceeds 100 % of the budget."""
        return self.ratio >= 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (for logging / JSON persistence)."""
        return {
            'used': self.used,
            'budget': self.budget,
            'ratio': round(self.ratio, 4),
            'level': self.level,
            'instructions': self.instructions,
        }

    def __repr__(self) -> str:
        return (
            f"BudgetStatus(used={self.used}, budget={self.budget}, "
            f"ratio={self.ratio:.2%}, level={self.level!r})"
        )


class WorkingMemory:
    """Working Memory — the active conversation context manager.

    Responsibilities
    ----------------
    1. **Store messages** of the current conversation turn-by-turn.
    2. **Assemble minimal context** each time :meth:`build_context` is
       called, fitting messages into the token budget from newest to
       oldest.
    3. **Compress overflow** — messages that do not fit are summarised
       into a compact text block so the model retains awareness of
       earlier conversation without the full token cost.
    4. **Report budget status** — a :class:`BudgetStatus` is returned
       alongside the assembled context so callers can react to
       approaching limits.

    Design notes
    ------------
    - ``self.messages`` is **never mutated** by ``build_context`` — all
      messages are preserved for episodic-memory logging at session end.
    - Compression is a *pure view-level* operation; the on-the-fly
      summary is recomputed each call but is cheap for typical
      conversation lengths.
    - Retrieved memories from episodic / semantic layers can be
      *injected* via :meth:`inject_memories` and will appear at the top
      of the assembled context.

    Attributes:
        token_budget: Maximum tokens allowed in the context window.
        system_prompt: The system prompt (nearly constant → cache-friendly).
        messages: All messages in the current session (never compressed away).
    """

    # Maximum characters allowed in the compressed summary.
    _MAX_SUMMARY_CHARS: int = 3000

    def __init__(
        self,
        token_budget: int = 8192,
        system_prompt: str = "",
    ) -> None:
        self.token_budget = token_budget
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, Any]] = []

        # Summary carried over from a *previous* session (loaded from
        # episodic memory by MemoryManager).
        self._prev_session_summary: str = ""

        # Retrieved memories to inject at the top of the context.
        self._injected_memories: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    #  Message management
    # ------------------------------------------------------------------
    def set_system_prompt(self, prompt: str) -> None:
        """Replace the system prompt."""
        self.system_prompt = prompt

    def add_message(
        self,
        role: str,
        content: str,
        **metadata: Any,
    ) -> None:
        """Append a message to the current session.

        Args:
            role: Message role — ``'user'``, ``'assistant'``, ``'tool'``,
                or ``'system'``.
            content: Message content text.
            **metadata: Extra fields stored on the message dict, e.g.
                ``tool_calls=[...]``, ``tool_results=[...]``.
        """
        msg: Dict[str, Any] = {
            'role': role,
            'content': content,
            'timestamp': time.time(),
        }
        msg.update(metadata)
        self.messages.append(msg)

    def inject_memories(self, memories: List[Dict[str, Any]]) -> None:
        """Set retrieved memories to prepend to the assembled context.

        Typically called by :class:`~evoagent.memory.MemoryManager` after
        querying episodic / semantic memory.

        Args:
            memories: List of memory entry dicts.  Each should have at
                least a ``content`` key.
        """
        self._injected_memories = list(memories)

    def set_prev_session_summary(self, summary: str) -> None:
        """Set a summary from the previous conversation session."""
        self._prev_session_summary = summary

    # ------------------------------------------------------------------
    #  Context assembly
    # ------------------------------------------------------------------
    def build_context(self) -> Dict[str, Any]:
        """Assemble the conversation context within the token budget.

        The assembly order (mirrors the four-layer context pattern):

        1. **system_prompt** (nearly constant — cache-friendly)
        2. **injected memories** (retrieved from episodic / semantic)
        3. **previous-session summary** (if any)
        4. **compressed summary** of old messages in *this* session
        5. **recent messages** (newest-first fitting)

        Returns:
            A dict with keys:

            - ``system_prompt`` (*str*) — the system prompt.
            - ``messages`` (*list[dict]*) — assembled message list.
            - ``budget_status`` (*BudgetStatus*) — usage snapshot.
        """
        # --- Layer 1: system prompt ---
        system_tokens = estimate_tokens(self.system_prompt)

        # --- Layer 2: injected memories ---
        memory_text = self._format_injected_memories()
        memory_tokens = estimate_tokens(memory_text)

        # --- Layer 3: previous-session summary ---
        prev_summary_tokens = estimate_tokens(self._prev_session_summary)

        # Fixed cost (layers 1–3)
        fixed_tokens = system_tokens + memory_tokens + prev_summary_tokens
        remaining = self.token_budget - fixed_tokens
        if remaining < 0:
            remaining = 0

        # --- Iterative fit: messages + compressed summary ---
        # Start by trying to fit all messages; if the total (messages +
        # compressed summary of the rest) exceeds the budget, progressively
        # drop more messages from the front and re-compress.
        included: List[Dict[str, Any]] = []
        comp_summary = ""
        msg_tokens_used = 0
        comp_tokens = 0

        max_iterations = min(len(self.messages) + 1, 50)
        drop_count = 0

        for _ in range(max_iterations):
            # Messages to try including (from the end, skipping dropped ones)
            candidate_msgs = self.messages[drop_count:]
            included = []
            msg_tokens_used = 0

            # Reserve up to 25% of remaining for the summary (if there
            # are messages to compress); otherwise give it all to messages.
            has_excluded = drop_count > 0
            if has_excluded:
                summary_budget = int(remaining * 0.25)
                msg_budget = remaining - summary_budget
            else:
                msg_budget = remaining

            for msg in reversed(candidate_msgs):
                mt = estimate_message_tokens(msg)
                if msg_tokens_used + mt > msg_budget:
                    break
                included.insert(0, msg)
                msg_tokens_used += mt

            # Compress excluded messages
            new_excluded_count = len(self.messages) - len(included) - drop_count
            # The actual excluded = all messages before `included`
            included_start = len(self.messages) - len(included)
            excluded = self.messages[:included_start]

            if excluded:
                comp_summary = self._compress_messages(excluded)
                comp_tokens = estimate_tokens(comp_summary)
                # Check if total fits
                total = msg_tokens_used + comp_tokens
                if total <= remaining or len(included) == 0:
                    # Fits, or can't reduce further
                    break
                # Doesn't fit — drop one more message from the front
                drop_count += 1
            else:
                comp_summary = ""
                comp_tokens = 0
                break

        # Cap the summary if it's still too large
        if comp_summary:
            summary_budget = remaining - msg_tokens_used
            if summary_budget < 10:
                summary_budget = 10
            comp_summary = self._truncate_summary(comp_summary, summary_budget)
            comp_tokens = estimate_tokens(comp_summary)

        # --- Assemble final message list ---
        final_messages: List[Dict[str, Any]] = []

        if memory_text:
            final_messages.append({'role': 'system', 'content': memory_text})

        if self._prev_session_summary:
            final_messages.append({
                'role': 'system',
                'content': f"[Previous session summary]\n{self._prev_session_summary}",
            })

        if comp_summary:
            final_messages.append({
                'role': 'system',
                'content': f"[Earlier in this session]\n{comp_summary}",
            })

        final_messages.extend(included)

        # --- Budget status ---
        total_used = (
            system_tokens + memory_tokens + prev_summary_tokens
            + comp_tokens + msg_tokens_used
        )
        budget_status = BudgetStatus(total_used, self.token_budget)

        return {
            'system_prompt': self.system_prompt,
            'messages': final_messages,
            'budget_status': budget_status,
        }

    # ------------------------------------------------------------------
    #  Compression
    # ------------------------------------------------------------------
    @staticmethod
    def _compress_messages(messages: List[Dict[str, Any]]) -> str:
        """Compress a list of messages into a compact text summary.

        Strategy: keep role labels and tool-call names, truncate content
        to a fixed length.  This is a *lossy* extractive compression —
        the goal is to preserve enough signal for the model to maintain
        conversational coherence, not to perfectly reproduce the original.

        Args:
            messages: Messages to compress.

        Returns:
            A multi-line summary string.
        """
        parts: List[str] = []
        max_content_len = 150

        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            # Truncate long content
            if len(content) > max_content_len:
                content = content[:max_content_len] + '...'

            # Preserve tool-call metadata (just the names)
            tool_calls = msg.get('tool_calls') or []
            tool_info = ""
            if tool_calls:
                names = [
                    tc.get('name') or tc.get('function', {}).get('name', '?')
                    for tc in tool_calls
                ]
                tool_info = f" [tools: {', '.join(names)}]"

            parts.append(f"[{role}{tool_info}] {content}")

        return "\n".join(parts)

    @staticmethod
    def _truncate_summary(summary: str, max_tokens: int) -> str:
        """Truncate a summary to fit within *max_tokens*.

        Keeps the most recent lines (which are the most relevant).

        Args:
            summary: The summary text.
            max_tokens: Maximum tokens allowed.

        Returns:
            Truncated summary string.
        """
        from ..utils.token_counter import estimate_tokens

        if not summary or estimate_tokens(summary) <= max_tokens:
            return summary

        lines = summary.split('\n')
        # Keep removing oldest lines until it fits
        while lines and estimate_tokens('\n'.join(lines)) > max_tokens:
            lines.pop(0)

        if not lines:
            # Even one line is too long — hard truncate
            chars_per_token = 3  # conservative average
            max_chars = max_tokens * chars_per_token
            return summary[-max_chars:] if len(summary) > max_chars else summary

        result = '\n'.join(lines)
        # Final check — hard truncate if still over
        if estimate_tokens(result) > max_tokens:
            chars_per_token = 3
            max_chars = max_tokens * chars_per_token
            result = result[-max_chars:] if len(result) > max_chars else result

        return result

    def _format_injected_memories(self) -> str:
        """Format injected memories into a system message block."""
        if not self._injected_memories:
            return ""
        lines = ["[Relevant memories from past sessions]"]
        for mem in self._injected_memories:
            content = mem.get('content', str(mem))
            tags = mem.get('tags')
            tag_str = f" (tags: {', '.join(tags)})" if tags else ""
            confidence = mem.get('confidence')
            conf_str = f" [confidence: {confidence:.2f}]" if confidence else ""
            lines.append(f"- {content}{tag_str}{conf_str}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  Utilities
    # ------------------------------------------------------------------
    def get_turn_count(self) -> int:
        """Return the total number of messages in the current session."""
        return len(self.messages)

    def export_session(self) -> List[Dict[str, Any]]:
        """Export all messages for episodic-memory logging.

        Returns a shallow copy of the message list so the caller can
        mutate it freely.
        """
        return [dict(msg) for msg in self.messages]

    def clear(self) -> None:
        """Reset working memory for a new conversation session."""
        self.messages = []
        self._prev_session_summary = ""
        self._injected_memories = []

    def __repr__(self) -> str:
        return (
            f"WorkingMemory(messages={len(self.messages)}, "
            f"budget={self.token_budget})"
        )
