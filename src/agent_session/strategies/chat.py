"""Chat session strategy — turn-based, user-initiated (ChatGPT pattern)."""

from __future__ import annotations

from datetime import timedelta

from agent_session.models import (
    ContextEntry,
    EntryType,
    EvictionPolicy,
    Priority,
    Session,
    SessionType,
    estimate_tokens,
)
from agent_session.strategies.base import SessionStrategy


class ChatSessionStrategy:
    """Turn-based sessions. User initiates a new chat, exchanges messages.

    Lifecycle:
    - Create: user opens a new chat
    - Turn: user message + AI reply
    - End: user closes chat or idle > 2 hours
    - Eviction: summarize oldest turns on overflow
    """

    IDLE_TIMEOUT = timedelta(hours=2)

    def create_session(self, *, user_id: str, **kwargs) -> Session:
        return Session(
            type=SessionType.CHAT,
            metadata={"user_id": user_id},
        )

    def should_end_session(self, session: Session) -> bool:
        return session.idle_seconds > self.IDLE_TIMEOUT.total_seconds()

    def to_context_entry(self, raw_event: dict) -> ContextEntry:
        # raw_event = {"role": "user"|"assistant", "content": "..."}
        return ContextEntry(
            type=EntryType.MESSAGE,
            content=raw_event["content"],
            role=raw_event.get("role", "user"),
            priority=Priority.HIGH,
            token_count=estimate_tokens(raw_event.get("content", "")),
        )

    def get_eviction_policy(self) -> EvictionPolicy:
        return EvictionPolicy.SUMMARIZE_OLDEST
