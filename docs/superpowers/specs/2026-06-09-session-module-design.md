# Session Module Design Spec

> **Date**: 2026-06-09
> **Context**: System design interview — generic session lifecycle + context window management for multi-agent AI apps
> **Language**: Python 3.12+
> **Approach**: Strategy Pattern

---

## Problem

An AI platform has 4 agent types with fundamentally different session semantics:

| Agent | Session Model | Data Pattern |
|-------|--------------|--------------|
| **Chat Agent** | User-initiated, turn-based | Request-response |
| **Voice Agent** | Single long-running session | Continuous stream, emotional continuity matters |
| **GUI Agent** | Event-driven, no conversation | Real-time UI events |
| **Car Agent** | Ride-based (engine ON→OFF) | 99% telemetry, 1% user commands/alerts |

All 4 share one problem: **token budget is finite**. The module must manage session lifecycle and context window eviction across all patterns.

---

## Architecture

```
SessionManager (generic engine)
├── Session (lifecycle unit)
├── ContextWindow (memory manager with eviction)
└── SessionStrategy (pluggable behavior per agent type)
    ├── ChatSessionStrategy
    ├── VoiceSessionStrategy
    ├── GUISessionStrategy
    └── CarSessionStrategy
```

---

## Core Protocols

### Session

```python
class Session:
    id: str
    type: SessionType        # CHAT | VOICE | GUI | CAR
    status: SessionStatus    # ACTIVE | PAUSED | ENDED
    created_at: datetime
    metadata: dict           # agent-specific (user_id, ride_id, etc.)
```

### ContextEntry (the universal atom)

```python
@dataclass
class ContextEntry:
    id: str
    type: EntryType            # MESSAGE | VOICE_EXCHANGE | SYSTEM_EVENT | TELEMETRY
    content: str
    role: str = ""             # user / assistant / system
    priority: Priority = NORMAL  # CRITICAL > HIGH > NORMAL > LOW
    metadata: dict
    token_count: int
    created_at: datetime
    summary: str | None = None
    is_summarized: bool = False
```

### ContextWindow (memory manager)

```python
class ContextWindow(Protocol):
    def add(self, entry: ContextEntry) -> None: ...
    def get_context(self, max_tokens: int) -> list[ContextEntry]: ...
    def compress(self) -> None: ...
    def clear(self) -> None: ...
```

### SessionStrategy (pluggable behavior)

```python
class SessionStrategy(Protocol):
    def create_session(self, **kwargs) -> Session: ...
    def should_end_session(self, session: Session) -> bool: ...
    def to_context_entry(self, raw_event: dict) -> ContextEntry: ...
    def get_eviction_policy(self) -> EvictionPolicy: ...
```

---

## Eviction Policies

| Policy | Used By | Logic |
|--------|---------|-------|
| `SUMMARIZE_OLDEST` | Chat | Summarize oldest turns via LLM abstraction |
| `SENTIMENT_WEIGHTED` | Voice | Keep emotional peaks + recent entries |
| `LRU` | GUI | Discard oldest events first |
| `PRIORITY_BASED` | Car | Evict LOW (telemetry → sampled) → NORMAL → keep CRITICAL/HIGH |

---

## Strategy Details

### ChatSessionStrategy
- **Session trigger**: User creates new chat
- **Turn semantics**: User message + AI reply
- **Context**: Full conversation, summarize oldest on overflow
- **End condition**: User closes or idle > 2 hours

### VoiceSessionStrategy
- **Session trigger**: Single persistent session
- **Turn semantics**: Voice exchange (STT→LLM→TTS)
- **Context**: Rolling window, sentiment-weighted retention
- **End condition**: Never (companion AI)

### GUISessionStrategy
- **Session trigger**: App lifecycle
- **Turn semantics**: Event + agent decision
- **Context**: Only recent events, LRU eviction
- **End condition**: App backgrounded / shutdown

### CarSessionStrategy
- **Session trigger**: Engine ON (new ride)
- **Turn semantics**: Telemetry batch + user command
- **Context**: Tiered priority — alerts pinned, commands kept, telemetry sampled
- **End condition**: Engine OFF or idle > 30 minutes

---

## File Structure

```
agent-session-module/
├── src/
│   └── agent_session/
│       ├── __init__.py
│       ├── models.py          # Session, ContextEntry, enums
│       ├── context_window.py  # ContextWindow base + eviction policies
│       ├── manager.py         # SessionManager
│       └── strategies/
│           ├── __init__.py
│           ├── base.py        # SessionStrategy protocol
│           ├── chat.py
│           ├── voice.py
│           ├── gui.py
│           └── car.py
├── tests/
│   ├── test_models.py
│   ├── test_context_window.py
│   ├── test_manager.py
│   ├── test_chat_strategy.py
│   ├── test_voice_strategy.py
│   ├── test_gui_strategy.py
│   └── test_car_strategy.py
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-09-session-module-design.md
├── pyproject.toml
└── README.md
```

---

## Success Criteria

1. Each strategy can be used independently — Chat team doesn't touch Car code
2. Adding a new agent type = new strategy class, no core changes (OCP)
3. Context window eviction is configurable per strategy
4. All tests pass, no external dependencies for core module
5. Demo script shows all 4 agent types working with the SessionManager
