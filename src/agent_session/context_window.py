"""Context window — memory manager with pluggable eviction policies."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime

from agent_session.models import (
    ContextEntry,
    EntryType,
    EvictionPolicy,
    Priority,
    estimate_tokens,
)

log = logging.getLogger(__name__)


class ContextWindow:
    """Manages a bounded list of ContextEntries with configurable eviction.

    The window tracks token usage and evicts entries when the budget is
    exceeded, using the policy specified by the agent's SessionStrategy.
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
    ) -> None:
        self.max_tokens = max_tokens
        self.eviction_policy = eviction_policy
        self._entries: deque[ContextEntry] = deque()
        self._current_tokens = 0

    @property
    def current_tokens(self) -> int:
        return self._current_tokens

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    # ── Public API ─────────────────────────────────────────────────────────

    def add(self, entry: ContextEntry) -> None:
        """Add an entry and evict if over budget."""
        if entry.token_count == 0:
            entry.token_count = estimate_tokens(entry.content)

        self._entries.append(entry)
        self._current_tokens += entry.token_count

        if self._current_tokens > self.max_tokens:
            self._evict(self._current_tokens - self.max_tokens)

    def get_context(self, max_tokens: int | None = None) -> list[ContextEntry]:
        """Return entries sorted for LLM consumption: priority asc + time asc.

        This means CRITICAL entries appear first (stable-sorted by time),
        and the most recent entries appear last — preserving conversation flow.
        """
        budget = max_tokens or self.max_tokens
        result: list[ContextEntry] = []
        running_tokens = 0

        # Sort by priority (desc) then by created_at (asc) within same priority
        sorted_entries = sorted(
            self._entries,
            key=lambda e: (-e.priority.value, e.created_at),
        )

        for entry in sorted_entries:
            tokens = estimate_tokens(entry.display_content)
            if running_tokens + tokens > budget:
                continue  # skip entries that don't fit
            result.append(entry)
            running_tokens += tokens

        # Final sort: preserve chronological order for LLM
        result.sort(key=lambda e: e.created_at)
        return result

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
        self._current_tokens = 0

    # ── Eviction ───────────────────────────────────────────────────────────

    def _evict(self, tokens_to_free: int) -> None:
        """Dispatch to the appropriate eviction strategy."""
        dispatch = {
            EvictionPolicy.SUMMARIZE_OLDEST: self._evict_summarize_oldest,
            EvictionPolicy.SENTIMENT_WEIGHTED: self._evict_sentiment_weighted,
            EvictionPolicy.LRU: self._evict_lru,
            EvictionPolicy.PRIORITY_BASED: self._evict_priority_based,
        }
        handler = dispatch.get(self.eviction_policy, self._evict_lru)
        freed = handler(tokens_to_free)
        if freed > 0:
            log.info(
                "Evicted %d tokens via %s (entries remaining: %d)",
                freed, self.eviction_policy.value, len(self._entries),
            )

    def _remove_entry(self, entry: ContextEntry) -> int:
        """Remove an entry and return its token count."""
        try:
            self._entries.remove(entry)
            tokens = entry.token_count
            self._current_tokens -= tokens
            return tokens
        except ValueError:
            return 0

    def _summarize_entry(self, entry: ContextEntry) -> int:
        """Replace an entry's content with a compressed summary.

        In production this would call an LLM. For the module we use
        a simple truncation heuristic that demonstrates the pattern.
        """
        if entry.is_summarized:
            return 0

        original_tokens = entry.token_count
        # Simple heuristic: keep first 50 chars as "summary"
        summary_text = entry.content[:50] + "..." if len(entry.content) > 50 else entry.content
        entry.summary = f"[Summary] {summary_text}"
        entry.is_summarized = True

        new_tokens = estimate_tokens(entry.summary)
        self._current_tokens -= original_tokens - new_tokens
        entry.token_count = new_tokens
        return original_tokens - new_tokens

    # ── Eviction Strategies ────────────────────────────────────────────────

    def _evict_lru(self, tokens_to_free: int) -> int:
        """Discard the oldest entries first."""
        freed = 0
        while freed < tokens_to_free and self._entries:
            entry = self._entries[0]  # oldest
            freed += self._remove_entry(entry)
        return freed

    def _evict_summarize_oldest(self, tokens_to_free: int) -> int:
        """Summarize the oldest entries to free tokens."""
        freed = 0
        for entry in list(self._entries):
            if freed >= tokens_to_free:
                break
            if not entry.is_summarized:
                freed += self._summarize_entry(entry)
        # If summarizing wasn't enough, fall back to removing summarized entries
        while freed < tokens_to_free and self._entries:
            entry = self._entries[0]
            freed += self._remove_entry(entry)
        return freed

    def _evict_sentiment_weighted(self, tokens_to_free: int) -> int:
        """Evict low-sentiment entries first, keep emotional peaks.

        Uses the 'emotion' field in entry.metadata to compute retention score.
        Entries with strong emotions get a score boost.
        """
        def retention_score(entry: ContextEntry) -> float:
            age = (datetime.now() - entry.created_at).total_seconds()
            emotion_weight = {
                "happy": 3.0, "sad": 3.0, "angry": 2.5, "excited": 3.0,
                "frustrated": 2.0, "neutral": 1.0,
            }.get(entry.metadata.get("emotion", "neutral"), 1.0)
            recency = 1.0 / (1.0 + age / 60.0)  # decay over minutes
            return recency * emotion_weight

        # Sort by retention score ascending — lowest score evicted first
        scored = sorted(self._entries, key=retention_score)
        freed = 0
        for entry in scored:
            if freed >= tokens_to_free:
                break
            freed += self._remove_entry(entry)
        return freed

    def _evict_priority_based(self, tokens_to_free: int) -> int:
        """Evict from lowest priority upward. Never evict CRITICAL.

        LOW entries get aggregated (sampled) before removal.
        """
        freed = 0

        # Phase 1: Summarize LOW entries (telemetry sampling)
        low_entries = [e for e in self._entries if e.priority == Priority.LOW]
        for entry in low_entries:
            if freed >= tokens_to_free:
                break
            if not entry.is_summarized:
                freed += self._summarize_entry(entry)

        # Phase 2: Remove LOW entries if still over budget
        for entry in [e for e in self._entries if e.priority == Priority.LOW]:
            if freed >= tokens_to_free:
                break
            freed += self._remove_entry(entry)

        # Phase 3: Remove NORMAL entries
        for entry in [e for e in self._entries if e.priority == Priority.NORMAL]:
            if freed >= tokens_to_free:
                break
            freed += self._remove_entry(entry)

        # CRITICAL and HIGH are never evicted
        return freed
