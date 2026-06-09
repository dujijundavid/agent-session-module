"""Tests for core models."""

from agent_session.models import (
    ContextEntry,
    EntryType,
    Priority,
    Session,
    SessionStatus,
    SessionType,
    estimate_tokens,
)


class TestSession:
    def test_create_default(self):
        s = Session(type=SessionType.CHAT)
        assert s.type == SessionType.CHAT
        assert s.status == SessionStatus.ACTIVE
        assert len(s.id) == 12
        assert s.metadata == {}

    def test_idle_seconds_increases(self):
        s = Session(type=SessionType.VOICE)
        assert s.idle_seconds >= 0

    def test_touch_updates_activity(self):
        s = Session(type=SessionType.CAR)
        old = s.last_activity_at
        s.touch()
        assert s.last_activity_at >= old


class TestContextEntry:
    def test_display_content_raw(self):
        e = ContextEntry(content="hello", type=EntryType.MESSAGE)
        assert e.display_content == "hello"

    def test_display_content_summary(self):
        e = ContextEntry(
            content="hello world this is a long message",
            type=EntryType.MESSAGE,
            summary="[Summary] hello world...",
            is_summarized=True,
        )
        assert e.display_content == "[Summary] hello world..."


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_english_text(self):
        tokens = estimate_tokens("Hello world, this is a test.")
        assert tokens >= 1

    def test_cjk_text(self):
        tokens = estimate_tokens("你好世界这是一个测试")
        assert tokens >= 1

    def test_mixed_text(self):
        tokens = estimate_tokens("Hello 你好 world 世界")
        assert tokens >= 1
