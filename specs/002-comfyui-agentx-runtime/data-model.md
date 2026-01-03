# Data Model: ComfyUI-AgentX Runtime

**Feature**: ComfyUI-AgentX Runtime
**Date**: 2026-01-02
**Status**: Phase 1 Design

## Overview

This document defines the data models for the AgentX runtime, including database schemas (SQLAlchemy), domain entities (Python dataclasses), and event structures for the 4-tier event system.

---

## Database Models (SQLAlchemy)

### 1. AgentSessionModel

Represents a persistent conversation session between user and Claude.

```python
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class AgentSessionModel(Base):
    __tablename__ = "agent_sessions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Business key
    session_id = Column(String(64), unique=True, nullable=False, index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Session state
    state = Column(String(32), nullable=False, default="idle")
    # Possible values: idle, processing, waiting_for_tool, error, closed

    # Configuration (JSON blob)
    config = Column(JSON, nullable=False, default=dict)
    # Example: {"model": "claude-3-5-sonnet-20241022", "max_tokens": 4096, "temperature": 1.0}

    # User context (optional)
    user_id = Column(String(64), nullable=True, index=True)

    # Metadata
    title = Column(String(256), nullable=True)  # Auto-generated from first user message

    # Relationships
    messages = relationship("AgentMessageModel", back_populates="session", cascade="all, delete-orphan")
```

**Indexes**:
- `ix_agent_sessions_session_id` (unique)
- `ix_agent_sessions_user_id` (non-unique)
- `ix_agent_sessions_created_at` (for chronological queries)

**Constraints**:
- `session_id` must match pattern `^agx-[0-9a-f]{32}$`
- `state` must be in allowed enum values

---

### 2. AgentMessageModel

Represents a single message in a conversation (user, assistant, or tool result).

```python
class AgentMessageModel(Base):
    __tablename__ = "agent_messages"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    session_id = Column(String(64), ForeignKey("agent_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)

    # Message identity
    message_id = Column(String(64), unique=True, nullable=False, index=True)

    # Message content
    role = Column(String(16), nullable=False)
    # Possible values: user, assistant

    content = Column(Text, nullable=False)
    # For user: raw text input
    # For assistant: final assembled text response

    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Tool usage tracking
    tool_calls = Column(JSON, nullable=True, default=None)
    # Structure: [{"id": "call_abc123", "name": "get_workflow", "arguments": {...}, "result": {...}, "error": null}, ...]

    # Token usage stats (optional)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # Relationships
    session = relationship("AgentSessionModel", back_populates="messages")
```

**Indexes**:
- `ix_agent_messages_session_id` (for efficient session queries)
- `ix_agent_messages_message_id` (unique)
- `ix_agent_messages_timestamp` (for chronological ordering)

**Constraints**:
- `role` must be 'user' or 'assistant'
- `content` cannot be empty string

---

### 3. AgentEventModel (Optional - for debugging/replay)

Stores low-level events for debugging and session replay.

```python
class AgentEventModel(Base):
    __tablename__ = "agent_events"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    session_id = Column(String(64), ForeignKey("agent_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)

    # Event data
    event_type = Column(String(16), nullable=False, index=True)
    # Possible values: stream, state, message, turn

    event_data = Column(JSON, nullable=False)
    # Structure varies by event_type (see Event Structures below)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Sequence number within session
    sequence = Column(Integer, nullable=False)
```

**Indexes**:
- `ix_agent_events_session_id_sequence` (composite, for ordered replay)
- `ix_agent_events_event_type` (for filtering by type)

**Note**: This table is optional and can be enabled via configuration for debugging. Production deployments may disable it to save storage.

---

## Domain Entities (Python Dataclasses)

### 1. AgentSession

In-memory representation of a conversation session.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

class SessionState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_FOR_TOOL = "waiting_for_tool"
    ERROR = "error"
    CLOSED = "closed"

@dataclass
class AgentSession:
    session_id: str
    created_at: datetime
    updated_at: datetime
    state: SessionState
    config: Dict[str, Any]
    user_id: Optional[str] = None
    title: Optional[str] = None
    messages: List['Message'] = field(default_factory=list)

    @classmethod
    def from_model(cls, model: AgentSessionModel) -> 'AgentSession':
        """Convert SQLAlchemy model to domain entity"""
        return cls(
            session_id=model.session_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            state=SessionState(model.state),
            config=model.config,
            user_id=model.user_id,
            title=model.title,
            messages=[Message.from_model(m) for m in model.messages]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "state": self.state.value,
            "config": self.config,
            "user_id": self.user_id,
            "title": self.title,
            "message_count": len(self.messages)
        }
```

---

### 2. Message

Represents a single message in the conversation.

```python
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error
        }

@dataclass
class Message:
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tool_calls: Optional[List[ToolCall]] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    @classmethod
    def from_model(cls, model: AgentMessageModel) -> 'Message':
        """Convert SQLAlchemy model to domain entity"""
        tool_calls = None
        if model.tool_calls:
            tool_calls = [ToolCall(**tc) for tc in model.tool_calls]

        return cls(
            message_id=model.message_id,
            session_id=model.session_id,
            role=MessageRole(model.role),
            content=model.content,
            timestamp=model.timestamp,
            tool_calls=tool_calls,
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses"""
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": [tc.to_dict() for tc in self.tool_calls] if self.tool_calls else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens
        }
```

---

### 3. MCPServer

Represents a configured MCP server instance.

```python
from enum import Enum

class MCPServerType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"

class MCPServerStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"

@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection"""
    server_type: MCPServerType
    # For stdio: command and args
    command: Optional[str] = None
    args: Optional[List[str]] = None
    # For SSE: url
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None

@dataclass
class MCPServer:
    name: str
    config: MCPServerConfig
    status: MCPServerStatus = MCPServerStatus.STOPPED
    tools: List['MCPTool'] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.config.server_type.value,
            "status": self.status.value,
            "tool_count": len(self.tools),
            "error": self.error_message
        }
```

---

### 4. MCPTool

Describes an available tool from an MCP server.

```python
@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema
    server_name: str  # Which MCP server provides this tool

    def to_claude_format(self) -> Dict[str, Any]:
        """Convert to Claude API tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "server": self.server_name
        }
```

---

## Event Structures (4-Tier System)

### 1. StreamEvent

Real-time text token streaming from Claude API.

```python
from enum import Enum

class EventType(str, Enum):
    STREAM = "stream"
    STATE = "state"
    MESSAGE = "message"
    TURN = "turn"

@dataclass
class StreamEvent:
    type: EventType = EventType.STREAM
    session_id: str = ""
    data: str = ""  # Single text token
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
```

**Example JSON**:
```json
{
  "type": "stream",
  "session_id": "agx-abc123",
  "data": "The workflow error is caused by",
  "timestamp": "2026-01-02T10:30:45.123Z"
}
```

---

### 2. StateEvent

Agent state transitions and tool execution status.

```python
class AgentState(str, Enum):
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    TOOL_RESULT = "tool_result"
    RESPONDING = "responding"
    DONE = "done"
    ERROR = "error"

@dataclass
class StateEventData:
    state: AgentState
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    progress: Optional[str] = None  # Human-readable progress message

@dataclass
class StateEvent:
    type: EventType = EventType.STATE
    session_id: str = ""
    data: StateEventData = field(default_factory=StateEventData)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": {
                "state": self.data.state.value,
                "tool_name": self.data.tool_name,
                "tool_call_id": self.data.tool_call_id,
                "progress": self.data.progress
            },
            "timestamp": self.timestamp.isoformat()
        }
```

**Example JSON** (tool call):
```json
{
  "type": "state",
  "session_id": "agx-abc123",
  "data": {
    "state": "calling_tool",
    "tool_name": "get_workflow",
    "tool_call_id": "call_xyz789",
    "progress": "Reading current workflow..."
  },
  "timestamp": "2026-01-02T10:30:46.456Z"
}
```

---

### 3. MessageEvent

Complete message finalization (user or assistant).

```python
@dataclass
class MessageEventData:
    message_id: str
    role: MessageRole
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

@dataclass
class MessageEvent:
    type: EventType = EventType.MESSAGE
    session_id: str = ""
    data: MessageEventData = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": {
                "message_id": self.data.message_id,
                "role": self.data.role.value,
                "content": self.data.content,
                "tool_calls": self.data.tool_calls,
                "input_tokens": self.data.input_tokens,
                "output_tokens": self.data.output_tokens
            },
            "timestamp": self.timestamp.isoformat()
        }
```

**Example JSON**:
```json
{
  "type": "message",
  "session_id": "agx-abc123",
  "data": {
    "message_id": "msg-def456",
    "role": "assistant",
    "content": "I found the issue in your workflow...",
    "tool_calls": [
      {
        "id": "call_xyz789",
        "name": "get_workflow",
        "arguments": {},
        "result": {"workflow": {...}}
      }
    ],
    "input_tokens": 1523,
    "output_tokens": 487
  },
  "timestamp": "2026-01-02T10:30:52.789Z"
}
```

---

### 4. TurnEvent

Conversation turn completion (one full request-response cycle).

```python
@dataclass
class TurnEventData:
    turn_id: str
    user_message_id: str
    assistant_message_id: str
    total_tokens: int
    duration_ms: int  # Milliseconds from user input to assistant completion

@dataclass
class TurnEvent:
    type: EventType = EventType.TURN
    session_id: str = ""
    data: TurnEventData = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": {
                "turn_id": self.data.turn_id,
                "user_message_id": self.data.user_message_id,
                "assistant_message_id": self.data.assistant_message_id,
                "total_tokens": self.data.total_tokens,
                "duration_ms": self.data.duration_ms
            },
            "timestamp": self.timestamp.isoformat()
        }
```

**Example JSON**:
```json
{
  "type": "turn",
  "session_id": "agx-abc123",
  "data": {
    "turn_id": "turn-ghi012",
    "user_message_id": "msg-jkl345",
    "assistant_message_id": "msg-def456",
    "total_tokens": 2010,
    "duration_ms": 6234
  },
  "timestamp": "2026-01-02T10:30:52.789Z"
}
```

---

## Configuration Schema

Agent runtime configuration (from environment or database).

```python
@dataclass
class AgentConfig:
    # Claude API
    anthropic_api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    temperature: float = 1.0

    # Database
    database_url: str = "sqlite:///agentx_sessions.db"

    # MCP Servers
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    # Example: [{"name": "comfyui", "type": "internal"}, {"name": "filesystem", "type": "stdio", "command": "mcp-server-filesystem", "args": []}]

    # WebSocket
    websocket_heartbeat_interval: int = 30  # seconds
    websocket_timeout: int = 300  # seconds

    # Performance
    event_queue_maxsize: int = 1000
    message_load_page_size: int = 100

    # Debugging
    enable_event_logging: bool = False  # Whether to persist AgentEventModel
    log_level: str = "INFO"
```

---

## Validation Rules

### Session ID
- Format: `agx-{uuid4_hex}` (e.g., `agx-a1b2c3d4e5f6...`)
- Length: 36 characters
- Unique across all sessions

### Message ID
- Format: `msg-{uuid4_hex}`
- Length: 36 characters
- Unique across all messages

### Tool Call ID
- Format: `call-{uuid4_hex}` or Claude's format `toolu_01ABC...`
- Unique within a message

### State Transitions
Valid state transitions for AgentSession:
```
idle → processing
processing → waiting_for_tool
waiting_for_tool → processing
processing → idle (success)
processing → error (failure)
error → idle (retry)
* → closed (user action)
```

---

## Relationships Diagram

```
AgentSession (1) ──────┬───── (*) AgentMessage
                       │
                       └───── (*) AgentEvent (optional)

MCPServer (1) ─────────────── (*) MCPTool

(No direct FK relationship between sessions and MCP servers)
```

---

## Migration Strategy

### Initial Schema Creation
Use Alembic for schema migrations:

```python
# alembic/versions/001_initial_schema.py
def upgrade():
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(64), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('state', sa.String(32), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(64), nullable=True),
        sa.Column('title', sa.String(256), nullable=True)
    )
    op.create_index('ix_agent_sessions_session_id', 'agent_sessions', ['session_id'])
    # ... (continue for other tables)
```

### Future Migrations
- v002: Add `agent_events` table (if debugging enabled)
- v003: Add `user_preferences` for per-user MCP server configs
- v004: Add `workflow_snapshots` for checkpoint management

---

## Summary

This data model provides:
- **Persistent storage** via SQLAlchemy models (sessions, messages, events)
- **Domain entities** for in-memory business logic (AgentSession, Message, MCPServer, MCPTool)
- **Event structures** for real-time streaming (Stream, State, Message, Turn events)
- **Configuration schema** for runtime behavior
- **Validation rules** ensuring data integrity

Next: See `contracts/agentx-api.yaml` for HTTP/WebSocket API definitions using these models.
