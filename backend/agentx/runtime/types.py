"""
AgentX Runtime Type Definitions

核心数据类型：事件、会话、消息、工具调用等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


# ============================================
# Enums
# ============================================


class EventType(str, Enum):
    """4-tier event system"""

    STREAM = "stream"  # Real-time text token streaming
    STATE = "state"  # Agent state transitions
    MESSAGE = "message"  # Complete message finalization
    TURN = "turn"  # Conversation turn completion


class SessionState(str, Enum):
    """Agent session state"""

    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_FOR_TOOL = "waiting_for_tool"
    ERROR = "error"
    CLOSED = "closed"


class AgentState(str, Enum):
    """Agent processing state for StateEvent"""

    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    TOOL_RESULT = "tool_result"
    RESPONDING = "responding"
    DONE = "done"
    ERROR = "error"


class MessageRole(str, Enum):
    """Message role"""

    USER = "user"
    ASSISTANT = "assistant"


# ============================================
# Domain Entities
# ============================================


@dataclass
class ToolCall:
    """Tool call representation"""

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
            "error": self.error,
        }


@dataclass
class Message:
    """Single message in conversation"""

    message_id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tool_calls: Optional[List[ToolCall]] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": [tc.to_dict() for tc in self.tool_calls] if self.tool_calls else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass
class AgentSession:
    """Agent conversation session"""

    session_id: str
    created_at: datetime
    updated_at: datetime
    state: SessionState
    config: Dict[str, Any]
    user_id: Optional[str] = None
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "state": self.state.value,
            "config": self.config,
            "user_id": self.user_id,
            "title": self.title,
            "message_count": len(self.messages),
        }


# ============================================
# Event Structures (4-Tier)
# ============================================


@dataclass
class AgentEvent:
    """Base event structure"""

    type: EventType
    session_id: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StreamEvent(AgentEvent):
    """Real-time text token streaming"""

    def __init__(self, session_id: str, data: str, timestamp: Optional[datetime] = None):
        super().__init__(
            type=EventType.STREAM,
            session_id=session_id,
            data=data,
            timestamp=timestamp or datetime.utcnow(),
        )


@dataclass
class StateEventData:
    """State event data"""

    state: AgentState
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    progress: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "progress": self.progress,
        }


@dataclass
class StateEvent(AgentEvent):
    """Agent state transitions"""

    def __init__(
        self, session_id: str, data: StateEventData, timestamp: Optional[datetime] = None
    ):
        super().__init__(
            type=EventType.STATE,
            session_id=session_id,
            data=data,
            timestamp=timestamp or datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MessageEvent(AgentEvent):
    """Complete message finalization"""

    def __init__(self, session_id: str, data: Message, timestamp: Optional[datetime] = None):
        super().__init__(
            type=EventType.MESSAGE,
            session_id=session_id,
            data=data,
            timestamp=timestamp or datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TurnEventData:
    """Turn event data"""

    turn_id: str
    user_message_id: str
    assistant_message_id: str
    total_tokens: int
    duration_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_message_id": self.user_message_id,
            "assistant_message_id": self.assistant_message_id,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
        }


@dataclass
class TurnEvent(AgentEvent):
    """Conversation turn completion"""

    def __init__(self, session_id: str, data: TurnEventData, timestamp: Optional[datetime] = None):
        super().__init__(
            type=EventType.TURN,
            session_id=session_id,
            data=data,
            timestamp=timestamp or datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }
