"""Tests for all four session strategies."""

from agent_session.models import EvictionPolicy, Priority, SessionStatus, SessionType
from agent_session.strategies.chat import ChatSessionStrategy
from agent_session.strategies.voice import VoiceSessionStrategy
from agent_session.strategies.gui import GUISessionStrategy
from agent_session.strategies.car import CarSessionStrategy


class TestChatStrategy:
    def setup_method(self):
        self.strategy = ChatSessionStrategy()

    def test_create_session(self):
        session = self.strategy.create_session(user_id="u1")
        assert session.type == SessionType.CHAT
        assert session.metadata["user_id"] == "u1"

    def test_to_context_entry(self):
        entry = self.strategy.to_context_entry({"role": "user", "content": "Hello!"})
        assert entry.content == "Hello!"
        assert entry.role == "user"
        assert entry.priority == Priority.HIGH

    def test_eviction_policy(self):
        assert self.strategy.get_eviction_policy() == EvictionPolicy.SUMMARIZE_OLDEST


class TestVoiceStrategy:
    def setup_method(self):
        self.strategy = VoiceSessionStrategy()

    def test_create_session(self):
        session = self.strategy.create_session(user_id="u1")
        assert session.type == SessionType.VOICE

    def test_never_ends(self):
        session = self.strategy.create_session(user_id="u1")
        assert self.strategy.should_end_session(session) is False

    def test_emotional_entry_gets_high_priority(self):
        entry = self.strategy.to_context_entry({
            "transcript": "I'm so sad",
            "emotion": "sad",
        })
        assert entry.priority == Priority.HIGH
        assert entry.metadata["emotion"] == "sad"

    def test_neutral_entry_gets_normal_priority(self):
        entry = self.strategy.to_context_entry({
            "transcript": "How's the weather?",
            "emotion": "neutral",
        })
        assert entry.priority == Priority.NORMAL

    def test_eviction_policy(self):
        assert self.strategy.get_eviction_policy() == EvictionPolicy.SENTIMENT_WEIGHTED


class TestGUIStrategy:
    def setup_method(self):
        self.strategy = GUISessionStrategy()

    def test_create_session(self):
        session = self.strategy.create_session(app_id="my_app")
        assert session.type == SessionType.GUI
        assert session.metadata["app_id"] == "my_app"

    def test_to_context_entry(self):
        entry = self.strategy.to_context_entry({
            "event_type": "click",
            "data": {"button": "submit"},
        })
        assert entry.priority == Priority.LOW
        assert entry.metadata["event_type"] == "click"

    def test_ends_when_paused(self):
        session = self.strategy.create_session(app_id="a")
        session.status = SessionStatus.PAUSED
        assert self.strategy.should_end_session(session) is True

    def test_eviction_policy(self):
        assert self.strategy.get_eviction_policy() == EvictionPolicy.LRU


class TestCarStrategy:
    def setup_method(self):
        self.strategy = CarSessionStrategy()

    def test_create_session(self):
        session = self.strategy.create_session(vehicle_id="VIN123", ride_id="R001")
        assert session.type == SessionType.CAR
        assert session.metadata["vehicle_id"] == "VIN123"

    def test_alert_is_critical(self):
        entry = self.strategy.to_context_entry({
            "source": "alert",
            "data": {"type": "BRAKE_FAILURE"},
        })
        assert entry.priority == Priority.CRITICAL

    def test_user_command_is_high(self):
        entry = self.strategy.to_context_entry({
            "source": "user",
            "data": {"command": "turn_on_ac"},
        })
        assert entry.priority == Priority.HIGH

    def test_telemetry_is_low(self):
        entry = self.strategy.to_context_entry({
            "source": "telemetry",
            "data": {"speed": 80, "rpm": 3000},
        })
        assert entry.priority == Priority.LOW

    def test_ends_on_engine_off(self):
        session = self.strategy.create_session(vehicle_id="VIN123")
        session.metadata["engine_off"] = True
        assert self.strategy.should_end_session(session) is True

    def test_eviction_policy(self):
        assert self.strategy.get_eviction_policy() == EvictionPolicy.PRIORITY_BASED
