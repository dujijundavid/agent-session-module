"""Voice session strategy — long-running companion AI, single session."""

from __future__ import annotations

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


class VoiceSessionStrategy:
    """Single persistent session for companion AI.

    Lifecycle:
    - Create: once per user, persists forever
    - Turn: voice exchange (STT → LLM → TTS)
    - End: never
    - Eviction: sentiment-weighted — keep emotional peaks + recent
    """

    def create_session(self, *, user_id: str, **kwargs) -> Session:
        return Session(
            type=SessionType.VOICE,
            metadata={"user_id": user_id},
        )

    def should_end_session(self, session: Session) -> bool:
        return False  # companion AI — session never ends

    def to_context_entry(self, raw_event: dict) -> ContextEntry:
        # raw_event = {"transcript": "...", "emotion": "happy", "response": "..."}
        emotion = raw_event.get("emotion", "neutral")
        is_emotional = emotion not in ("neutral", "")
        return ContextEntry(
            type=EntryType.VOICE_EXCHANGE,
            content=raw_event.get("transcript", ""),
            role=raw_event.get("role", "user"),
            priority=Priority.HIGH if is_emotional else Priority.NORMAL,
            metadata={"emotion": emotion},
            token_count=estimate_tokens(raw_event.get("transcript", "")),
        )

    def get_eviction_policy(self) -> EvictionPolicy:
        return EvictionPolicy.SENTIMENT_WEIGHTED
