"""Session strategy protocol — pluggable behavior per agent type."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent_session.models import ContextEntry, EvictionPolicy, Session


@runtime_checkable
class SessionStrategy(Protocol):
    """Interface that each agent type must implement.

    The strategy answers:
    - How is a session created and ended?
    - How is raw data converted to a ContextEntry?
    - What eviction policy does the context window use?
    """

    def create_session(self, **kwargs) -> Session: ...
    def should_end_session(self, session: Session) -> bool: ...
    def to_context_entry(self, raw_event: dict) -> ContextEntry: ...
    def get_eviction_policy(self) -> EvictionPolicy: ...
