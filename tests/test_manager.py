"""Tests for SessionManager — the orchestrator."""

from agent_session.manager import SessionManager
from agent_session.models import SessionStatus
from agent_session.strategies.chat import ChatSessionStrategy
from agent_session.strategies.car import CarSessionStrategy


class TestManagerWithChat:
    def setup_method(self):
        self.manager = SessionManager(strategy=ChatSessionStrategy(), max_context_tokens=500)

    def test_create_session(self):
        session = self.manager.create_session(user_id="u1")
        assert session is not None
        assert session.metadata["user_id"] == "u1"

    def test_process_event(self):
        session = self.manager.create_session(user_id="u1")
        ok = self.manager.process_event(session.id, {
            "role": "user", "content": "Hello, how are you?"
        })
        assert ok is True
        ctx = self.manager.get_context(session.id)
        assert len(ctx) == 1
        assert ctx[0]["content"] == "Hello, how are you?"

    def test_process_event_on_ended_session_fails(self):
        session = self.manager.create_session(user_id="u1")
        self.manager.end_session(session.id)
        ok = self.manager.process_event(session.id, {
            "role": "user", "content": "Should not work"
        })
        assert ok is False

    def test_end_session(self):
        session = self.manager.create_session(user_id="u1")
        result = self.manager.end_session(session.id)
        assert result is True
        assert session.status == SessionStatus.ENDED

    def test_end_nonexistent_session(self):
        result = self.manager.end_session("fake_id")
        assert result is False

    def test_list_sessions(self):
        self.manager.create_session(user_id="u1")
        self.manager.create_session(user_id="u2")
        sessions = self.manager.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_filtered(self):
        s1 = self.manager.create_session(user_id="u1")
        self.manager.create_session(user_id="u2")
        self.manager.end_session(s1.id)
        active = self.manager.list_sessions(status=SessionStatus.ACTIVE)
        assert len(active) == 1

    def test_multiple_events_context_grows(self):
        session = self.manager.create_session(user_id="u1")
        for i in range(5):
            self.manager.process_event(session.id, {
                "role": "user", "content": f"Message {i}"
            })
        ctx = self.manager.get_context(session.id)
        assert len(ctx) >= 1  # at least some context retained


class TestManagerWithCar:
    def test_car_session_priority_eviction(self):
        manager = SessionManager(strategy=CarSessionStrategy(), max_context_tokens=100)

        session = manager.create_session(vehicle_id="VIN001")

        # Add a critical alert
        manager.process_event(session.id, {
            "source": "alert",
            "data": {"type": "COLLISION_WARNING"},
        })

        # Flood with telemetry
        for i in range(50):
            manager.process_event(session.id, {
                "source": "telemetry",
                "data": {"speed": i, "rpm": i * 100, "temp": 90},
            })

        # Add a user command
        manager.process_event(session.id, {
            "source": "user",
            "data": {"command": "turn_on_ac"},
        })

        ctx = manager.get_context(session.id)

        # Critical alert should survive
        alerts = [c for c in ctx if c["priority"] == "CRITICAL"]
        assert len(alerts) >= 1, "Critical alerts should never be evicted"

        # User command should survive
        commands = [c for c in ctx if c["priority"] == "HIGH"]
        assert len(commands) >= 1, "User commands should be retained over telemetry"

    def test_car_session_ends_on_engine_off(self):
        manager = SessionManager(strategy=CarSessionStrategy(), max_context_tokens=1000)
        session = manager.create_session(vehicle_id="VIN001")
        session.metadata["engine_off"] = True

        ok = manager.process_event(session.id, {
            "source": "telemetry",
            "data": {"speed": 0},
        })
        assert ok is False  # session should have ended
