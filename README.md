# Agent Session Module

Generic session lifecycle & context window management for multi-agent AI applications.

## The Problem

An AI platform has multiple agent types with fundamentally different session semantics:

| Agent | Session Model | Data Pattern |
|-------|--------------|--------------|
| **Chat Agent** | User-initiated, turn-based | Request-response |
| **Voice Agent** | Single long-running session | Continuous stream, emotional continuity |
| **GUI Agent** | Event-driven, no conversation | Real-time UI events |
| **Car Agent** | Ride-based (engine ON→OFF) | 99% telemetry, 1% commands/alerts |

All share one constraint: **token budget is finite**. This module provides a unified framework for session lifecycle and context window eviction across all patterns.

## Architecture

```
SessionManager (generic engine)
├── Session (lifecycle unit)
├── ContextWindow (memory manager with eviction)
└── SessionStrategy (pluggable behavior per agent type)
    ├── ChatSessionStrategy      — Summarize oldest turns
    ├── VoiceSessionStrategy     — Sentiment-weighted retention
    ├── GUISessionStrategy       — LRU eviction
    └── CarSessionStrategy       — Priority-based eviction
```

**Key design principle**: The `SessionStrategy` defines *how sessions work* for each agent type, while `SessionManager` provides the generic engine. Adding a new agent type = one new strategy class, zero core changes.

## Quick Start

```python
from agent_session import SessionManager
from agent_session.strategies import ChatSessionStrategy

# Create a manager for Chat Agent
manager = SessionManager(strategy=ChatSessionStrategy(), max_context_tokens=8000)

# Create a session
session = manager.create_session(user_id="user_123")

# Process events
manager.process_event(session.id, {"role": "user", "content": "Hello!"})
manager.process_event(session.id, {"role": "assistant", "content": "Hi there!"})

# Get context for LLM
context = manager.get_context(session.id)
# → [{"role": "user", "content": "Hello!", ...}, {"role": "assistant", "content": "Hi there!", ...}]
```

## Context Window Eviction

When the token budget is exceeded, entries are evicted based on the strategy's policy:

| Policy | Used By | Behavior |
|--------|---------|----------|
| `SUMMARIZE_OLDEST` | Chat | Summarize oldest turns into compressed summaries |
| `SENTIMENT_WEIGHTED` | Voice | Keep emotional peaks + recent entries |
| `LRU` | GUI | Discard oldest events first |
| `PRIORITY_BASED` | Car | Evict LOW telemetry → NORMAL, never evict CRITICAL/HIGH |

### Car Agent Example

The Car Agent's priority-based eviction is the most nuanced:

```
Data stream: [telemetry, telemetry, ALERT, telemetry, USER_CMD, telemetry]

When token budget exceeded:
  Phase 1: Summarize LOW (telemetry → "avg speed 80km/h over 10min")
  Phase 2: Remove summarized LOW entries
  Phase 3: Remove NORMAL entries (last resort)
  NEVER: Remove CRITICAL (alerts) or HIGH (user commands)
```

## Project Structure

```
src/agent_session/
├── __init__.py
├── models.py              # Session, ContextEntry, enums
├── context_window.py      # ContextWindow + eviction policies
├── manager.py             # SessionManager
└── strategies/
    ├── base.py            # SessionStrategy protocol
    ├── chat.py            # ChatGPT-like agent
    ├── voice.py           # Companion AI
    ├── gui.py             # Event-driven agent
    └── car.py             # Smart cockpit agent
tests/
├── test_models.py
├── test_context_window.py
├── test_strategies.py
└── test_manager.py
```

## Installation

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
