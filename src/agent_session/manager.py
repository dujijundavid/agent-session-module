"""SessionManager — the generic engine that ties sessions, strategies, and context windows."""

from __future__ import annotations

import logging
from typing import Any

from agent_session.context_window import ContextWindow
from agent_session.models import Session, SessionStatus
from agent_session.strategies.base import SessionStrategy

log = logging.getLogger(__name__)


class SessionManager:
    """Orchestrates session lifecycle across different agent types.

    Usage:
        strategy = ChatSessionStrategy()
        manager = SessionManager(strategy=strategy, max_context_tokens=8000)

        session = manager.create_session(user_id="u123")
        manager.process_event(session.id, {"role": "user", "content": "Hello!"})
        context = manager.get_context(session.id)
    """

    def __init__(
        self,
        strategy: SessionStrategy,
        max_context_tokens: int = 8000,
    ) -> None:
        self._strategy = strategy
        self._max_tokens = max_context_tokens
        self._sessions: dict[str, Session] = {}
        self._context_windows: dict[str, ContextWindow] = {}

    # ── Session Lifecycle ──────────────────────────────────────────────────

    def create_session(self, **kwargs: Any) -> Session:
        """Create a new session using the configured strategy."""
        session = self._strategy.create_session(**kwargs)
        self._sessions[session.id] = session
        self._context_windows[session.id] = ContextWindow(
            max_tokens=self._max_tokens,
            eviction_policy=self._strategy.get_eviction_policy(),
        )
        log.info("Session created: %s (type=%s)", session.id, session.type.value)
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        """End a session. Returns True if session was found and ended."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.status = SessionStatus.ENDED
        log.info("Session ended: %s", session_id)
        return True

    def list_sessions(self, status: SessionStatus | None = None) -> list[Session]:
        """List sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sessions

    # ── Event Processing ───────────────────────────────────────────────────

    def process_event(self, session_id: str, raw_event: dict) -> bool:
        """Convert a raw event to a ContextEntry and add it to the window.

        Also checks if the session should be ended (strategy-defined condition).
        Returns True if the event was processed, False if session not found or ended.
        """
        session = self._sessions.get(session_id)
        if not session or session.status == SessionStatus.ENDED:
            return False

        # Check if session should end before processing
        if self._strategy.should_end_session(session):
            self.end_session(session_id)
            return False

        # Convert and store
        entry = self._strategy.to_context_entry(raw_event)
        self._context_windows[session_id].add(entry)
        session.touch()
        return True

    def get_context(self, session_id: str, max_tokens: int | None = None) -> list[dict]:
        """Get the current context for LLM consumption.

        Returns a list of dicts suitable for serialization.
        """
        window = self._context_windows.get(session_id)
        if not window:
            return []

        entries = window.get_context(max_tokens)
        return [
            {
                "id": e.id,
                "type": e.type.value,
                "role": e.role,
                "content": e.display_content,
                "priority": e.priority.name,
                "metadata": e.metadata,
                "token_count": e.token_count,
                "is_summarized": e.is_summarized,
            }
            for e in entries
        ]

    def get_context_window(self, session_id: str) -> ContextWindow | None:
        """Direct access to the ContextWindow (for testing / debugging)."""
        return self._context_windows.get(session_id)
