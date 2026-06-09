"""GUI session strategy — event-driven, no conversation."""

from __future__ import annotations

import json

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


class GUISessionStrategy:
    """Event-driven agent that reacts to UI events, not conversation.

    Lifecycle:
    - Create: app starts
    - Turn: event + agent decision
    - End: app backgrounded / shutdown
    - Eviction: LRU — only recent events matter
    """

    def create_session(self, *, app_id: str, **kwargs) -> Session:
        return Session(
            type=SessionType.GUI,
            metadata={"app_id": app_id},
        )

    def should_end_session(self, session: Session) -> bool:
        return session.status.value == "paused"

    def to_context_entry(self, raw_event: dict) -> ContextEntry:
        # raw_event = {"event_type": "click"|"scroll"|"api_call", "data": {...}}
        return ContextEntry(
            type=EntryType.SYSTEM_EVENT,
            content=json.dumps(raw_event.get("data", {})),
            metadata={"event_type": raw_event.get("event_type", "unknown")},
            priority=Priority.LOW,
            token_count=estimate_tokens(json.dumps(raw_event.get("data", {}))),
        )

    def get_eviction_policy(self) -> EvictionPolicy:
        return EvictionPolicy.LRU
