"""Car session strategy — ride-based, high-throughput telemetry stream."""

from __future__ import annotations

import json
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


class CarSessionStrategy:
    """Ride-based session for smart cockpit agent.

    Lifecycle:
    - Create: engine ON (new ride)
    - Turn: telemetry batch + user command
    - End: engine OFF or idle > 30 minutes
    - Eviction: priority-based — alerts pinned, telemetry sampled

    The defining characteristic is asymmetric data:
    ~99% low-priority telemetry, ~1% critical alerts / user commands.
    """

    IDLE_TIMEOUT = timedelta(minutes=30)

    # Map raw event source to priority
    SOURCE_PRIORITY = {
        "alert": Priority.CRITICAL,
        "user": Priority.HIGH,
        "telemetry": Priority.LOW,
    }

    def create_session(self, *, vehicle_id: str, ride_id: str | None = None, **kwargs) -> Session:
        return Session(
            type=SessionType.CAR,
            metadata={"vehicle_id": vehicle_id, "ride_id": ride_id},
        )

    def should_end_session(self, session: Session) -> bool:
        return (
            session.metadata.get("engine_off", False)
            or session.idle_seconds > self.IDLE_TIMEOUT.total_seconds()
        )

    def to_context_entry(self, raw_event: dict) -> ContextEntry:
        # raw_event = {"source": "telemetry"|"user"|"alert", "data": {...}}
        source = raw_event.get("source", "telemetry")
        data = raw_event.get("data", {})
        content = json.dumps(data)

        return ContextEntry(
            type=EntryType.TELEMETRY if source == "telemetry" else EntryType.MESSAGE,
            content=content,
            priority=self.SOURCE_PRIORITY.get(source, Priority.LOW),
            metadata={"source": source},
            token_count=estimate_tokens(content),
        )

    def get_eviction_policy(self) -> EvictionPolicy:
        return EvictionPolicy.PRIORITY_BASED
