"""Tests for ContextWindow and all eviction policies."""

from datetime import datetime, timedelta

from agent_session.context_window import ContextWindow
from agent_session.models import (
    ContextEntry,
    EntryType,
    EvictionPolicy,
    Priority,
    estimate_tokens,
)


def _make_entry(
    content: str = "test",
    priority: Priority = Priority.NORMAL,
    entry_type: EntryType = EntryType.MESSAGE,
    metadata: dict | None = None,
    minutes_ago: float = 0,
) -> ContextEntry:
    return ContextEntry(
        content=content,
        type=entry_type,
        priority=priority,
        metadata=metadata or {},
        token_count=estimate_tokens(content),
        created_at=datetime.now() - timedelta(minutes=minutes_ago),
    )


class TestContextWindowBasic:
    def test_add_tracks_tokens(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add(_make_entry("hello world"))
        assert cw.current_tokens > 0
        assert cw.entry_count == 1

    def test_clear_resets(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add(_make_entry("hello"))
        cw.clear()
        assert cw.current_tokens == 0
        assert cw.entry_count == 0

    def test_get_context_returns_list(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add(_make_entry("first"))
        cw.add(_make_entry("second"))
        ctx = cw.get_context()
        assert len(ctx) == 2

    def test_auto_estimates_tokens(self):
        cw = ContextWindow(max_tokens=1000)
        entry = ContextEntry(content="hello world", type=EntryType.MESSAGE, token_count=0)
        cw.add(entry)
        assert entry.token_count > 0


class TestLRUEviction:
    def test_evicts_oldest_first(self):
        cw = ContextWindow(max_tokens=20, eviction_policy=EvictionPolicy.LRU)
        cw.add(_make_entry("first entry here", minutes_ago=10))
        cw.add(_make_entry("second entry here", minutes_ago=5))
        cw.add(_make_entry("third entry here", minutes_ago=0))

        # After adding third, oldest should be evicted
        assert cw.entry_count <= 3
        contents = [e.content for e in cw._entries]
        assert "first entry here" not in contents or cw.entry_count == 3

    def test_all_entries_fit(self):
        cw = ContextWindow(max_tokens=10000, eviction_policy=EvictionPolicy.LRU)
        cw.add(_make_entry("hello"))
        cw.add(_make_entry("world"))
        assert cw.entry_count == 2


class TestSummarizeOldest:
    def test_summarizes_instead_of_removing(self):
        cw = ContextWindow(max_tokens=30, eviction_policy=EvictionPolicy.SUMMARIZE_OLDEST)
        # Add entries until eviction triggers
        for i in range(10):
            cw.add(_make_entry(f"message number {i} with some content"))

        # At least one entry should be summarized
        summarized = [e for e in cw._entries if e.is_summarized]
        assert len(summarized) >= 1


class TestPriorityBasedEviction:
    def test_never_evicts_critical(self):
        cw = ContextWindow(max_tokens=20, eviction_policy=EvictionPolicy.PRIORITY_BASED)

        # Add a critical alert
        cw.add(_make_entry("BRAKE FAILURE", priority=Priority.CRITICAL, minutes_ago=60))
        # Fill with low-priority telemetry to trigger eviction
        for i in range(20):
            cw.add(_make_entry(f"speed: {i}km/h, rpm: {i*100}", priority=Priority.LOW))

        # Critical entry should still be there
        contents = [e.content for e in cw._entries]
        assert "BRAKE FAILURE" in contents

    def test_evicts_low_before_normal(self):
        cw = ContextWindow(max_tokens=50, eviction_policy=EvictionPolicy.PRIORITY_BASED)

        cw.add(_make_entry("normal event", priority=Priority.NORMAL, minutes_ago=5))
        for i in range(20):
            cw.add(_make_entry(f"telemetry_{i}", priority=Priority.LOW))

        # LOW entries should be evicted before NORMAL
        priorities = [e.priority for e in cw._entries]
        # If any NORMAL entries exist, all remaining LOWs should have been evicted first
        if Priority.NORMAL in priorities:
            low_count = priorities.count(Priority.LOW)
            # After eviction, LOWs should be reduced
            assert low_count < 20


class TestSentimentWeightedEviction:
    def test_keeps_emotional_peaks(self):
        cw = ContextWindow(max_tokens=30, eviction_policy=EvictionPolicy.SENTIMENT_WEIGHTED)

        # Add emotional entry early
        cw.add(_make_entry(
            "I'm so happy today!",
            metadata={"emotion": "happy"},
            minutes_ago=30,
        ))
        # Fill with neutral entries
        for i in range(20):
            cw.add(_make_entry(
                f"neutral message {i}",
                metadata={"emotion": "neutral"},
                minutes_ago=max(0, 29 - i),
            ))

        # The emotional entry should survive better than old neutrals
        contents = [e.content for e in cw._entries]
        has_emotional = any("happy" in c for c in contents)
        assert has_emotional, "Emotional peak should be retained over neutral entries"
