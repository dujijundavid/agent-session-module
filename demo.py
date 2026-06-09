"""Demo: all 4 agent types using the Session Module.

Run: python demo.py
"""

from agent_session import SessionManager
from agent_session.strategies.chat import ChatSessionStrategy
from agent_session.strategies.voice import VoiceSessionStrategy
from agent_session.strategies.gui import GUISessionStrategy
from agent_session.strategies.car import CarSessionStrategy


def demo_chat():
    """Chat Agent — like ChatGPT."""
    print("=" * 60)
    print("📱 Chat Agent (ChatGPT-like)")
    print("=" * 60)

    manager = SessionManager(strategy=ChatSessionStrategy(), max_context_tokens=200)
    session = manager.create_session(user_id="alice")

    events = [
        {"role": "user", "content": "What's the weather in Shanghai?"},
        {"role": "assistant", "content": "It's 28°C and partly cloudy in Shanghai today."},
        {"role": "user", "content": "Should I bring an umbrella?"},
        {"role": "assistant", "content": "There's a 30% chance of rain, so maybe a small one."},
    ]
    for evt in events:
        manager.process_event(session.id, evt)

    ctx = manager.get_context(session.id)
    print(f"Session: {session.id} | Entries: {len(ctx)}")
    for c in ctx:
        print(f"  [{c['role']:9s}] {c['content']}")
    print()


def demo_voice():
    """Voice Agent — companion AI with emotional continuity."""
    print("=" * 60)
    print("🎙️  Voice Agent (Companion AI)")
    print("=" * 60)

    manager = SessionManager(strategy=VoiceSessionStrategy(), max_context_tokens=200)
    session = manager.create_session(user_id="bob")

    events = [
        {"transcript": "Good morning!", "emotion": "neutral"},
        {"transcript": "I got promoted today!", "emotion": "happy"},
        {"transcript": "How do I cook pasta?", "emotion": "neutral"},
        {"transcript": "My dog is sick, I'm worried", "emotion": "sad"},
        {"transcript": "Tell me a joke", "emotion": "neutral"},
    ]
    for evt in events:
        manager.process_event(session.id, evt)

    ctx = manager.get_context(session.id)
    print(f"Session: {session.id} | Entries: {len(ctx)} (never ends)")
    for c in ctx:
        emotion = c["metadata"].get("emotion", "?")
        print(f"  [{emotion:8s}] {c['content']}")
    print()


def demo_gui():
    """GUI Agent — event-driven, no conversation."""
    print("=" * 60)
    print("🖥️  GUI Agent (Event-driven)")
    print("=" * 60)

    manager = SessionManager(strategy=GUISessionStrategy(), max_context_tokens=150)
    session = manager.create_session(app_id="dashboard_app")

    events = [
        {"event_type": "click", "data": {"button": "refresh"}},
        {"event_type": "scroll", "data": {"position": 300}},
        {"event_type": "api_call", "data": {"endpoint": "/api/users", "status": 200}},
        {"event_type": "click", "data": {"button": "export"}},
    ]
    for evt in events:
        manager.process_event(session.id, evt)

    ctx = manager.get_context(session.id)
    print(f"Session: {session.id} | Entries: {len(ctx)}")
    for c in ctx:
        etype = c["metadata"].get("event_type", "?")
        print(f"  [{etype:8s}] {c['content']}")
    print()


def demo_car():
    """Car Agent — smart cockpit with asymmetric data."""
    print("=" * 60)
    print("🚗 Car Agent (Smart Cockpit)")
    print("=" * 60)

    manager = SessionManager(strategy=CarSessionStrategy(), max_context_tokens=300)
    session = manager.create_session(vehicle_id="VIN_WDD123", ride_id="RIDE_001")

    # 1. Critical alert
    manager.process_event(session.id, {
        "source": "alert", "data": {"type": "COLLISION_WARNING", "severity": "HIGH"},
    })
    # 2. User command
    manager.process_event(session.id, {
        "source": "user", "data": {"command": "navigate_to", "destination": "Airport"},
    })
    # 3. Flood with telemetry
    for i in range(30):
        manager.process_event(session.id, {
            "source": "telemetry",
            "data": {"speed": 60 + i, "rpm": 2000 + i * 50, "fuel": 45 - i * 0.3},
        })

    ctx = manager.get_context(session.id)
    print(f"Session: {session.id} | Entries retained: {len(ctx)} / 32 total")
    for c in ctx:
        src = c["metadata"].get("source", "?")
        print(f"  [{src:10s}] priority={c['priority']:8s} | {c['content'][:60]}")

    # End ride
    session.metadata["engine_off"] = True
    ok = manager.process_event(session.id, {"source": "telemetry", "data": {"speed": 0}})
    print(f"\nEngine OFF → session ended: {not ok}")
    print()


if __name__ == "__main__":
    demo_chat()
    demo_voice()
    demo_gui()
    demo_car()
    print("✅ All 4 agent types demonstrated successfully!")
