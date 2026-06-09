"""Core data models and enums for the session module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class SessionType(Enum):
    CHAT = "chat"
    VOICE = "voice"
    GUI = "gui"
    CAR = "car"


class SessionStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class EntryType(Enum):
    MESSAGE = "message"
    VOICE_EXCHANGE = "voice_exchange"
    SYSTEM_EVENT = "system_event"
    TELEMETRY = "telemetry"


class Priority(Enum):
    CRITICAL = 4
    HIGH = 3
    NORMAL = 2
    LOW = 1


class EvictionPolicy(Enum):
    SUMMARIZE_OLDEST = "summarize_oldest"
    SENTIMENT_WEIGHTED = "sentiment_weighted"
    LRU = "lru"
    PRIORITY_BASED = "priority_based"


# ── Models ─────────────────────────────────────────────────────────────────────

@dataclass
class Session:
    """A single agent session — the lifecycle unit."""

    type: SessionType
    status: SessionStatus = SessionStatus.ACTIVE
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def touch(self) -> None:
        """Update last_activity_at to now."""
        self.last_activity_at = datetime.now()

    @property
    def idle_seconds(self) -> float:
        return (datetime.now() - self.last_activity_at).total_seconds()


@dataclass
class ContextEntry:
    """A single atom in the context window — message, event, or telemetry."""

    content: str
    type: EntryType
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    role: str = ""
    priority: Priority = Priority.NORMAL
    metadata: dict = field(default_factory=dict)
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    summary: str | None = None
    is_summarized: bool = False

    @property
    def display_content(self) -> str:
        """Return summary if available, otherwise raw content."""
        return self.summary if self.is_summarized and self.summary else self.content


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (English), ~2 chars per token (CJK)."""
    if not text:
        return 0
    cjk_chars = sum(1 for c in text if "一" <= c <= "鿿")
    other_chars = len(text) - cjk_chars
    return max(1, (cjk_chars + 1) // 2 + other_chars // 4)
