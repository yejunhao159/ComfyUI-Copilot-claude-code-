"""
AgentX Runtime V2 - Type Definitions

Ported from @agentxjs/types TypeScript package.

Event Architecture (4-Layer):
    Stream: Raw LLM stream events (text_delta, tool_use_start, etc.)
    State: Agent state transitions (idle → thinking → responding → done)
    Message: Complete message events (user_message, assistant_message)
    Turn: Request-response cycle events (turn_request, turn_response)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Literal, Union
from datetime import datetime


# =============================================================================
# Agent State
# =============================================================================


class AgentState(str, Enum):
    """Agent state machine states."""
    IDLE = "idle"
    THINKING = "thinking"
    RESPONDING = "responding"
    CALLING_TOOL = "calling_tool"
    WAITING_FOR_TOOL = "waiting_for_tool"
    DONE = "done"
    ERROR = "error"


class AgentLifecycle(str, Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPED = "stopped"
    DESTROYED = "destroyed"


class SessionState(str, Enum):
    """Session states."""
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_FOR_TOOL = "waiting_for_tool"
    CLOSED = "closed"
    ERROR = "error"


# =============================================================================
# Event Context
# =============================================================================


@dataclass
class EventContext:
    """
    Context attached to events for routing and correlation.

    Used by SystemBus to filter events by agent/container/session.
    """
    container_id: Optional[str] = None
    image_id: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None


# =============================================================================
# Base Event Types
# =============================================================================


EventSource = Literal["environment", "agent", "container", "session", "command", "system"]
EventCategory = Literal["stream", "state", "message", "turn", "lifecycle", "request", "response"]
EventIntent = Literal["notification", "request", "result", "error"]


@dataclass
class SystemEvent:
    """
    Base system event - all events on the bus extend this.

    Attributes:
        type: Event type identifier
        timestamp: Unix timestamp in milliseconds
        source: Where the event originated
        category: Event layer (stream/state/message/turn)
        intent: What the event wants to accomplish
        data: Event-specific payload
        context: Routing context
        request_id: Optional correlation ID
        broadcastable: Whether event should be sent to clients
    """
    type: str
    timestamp: int
    source: EventSource
    category: EventCategory
    intent: EventIntent
    data: Any = None
    context: Optional[EventContext] = None
    request_id: Optional[str] = None
    broadcastable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "type": self.type,
            "timestamp": self.timestamp,
            "source": self.source,
            "category": self.category,
            "intent": self.intent,
            "data": self.data,
        }
        if self.context:
            result["context"] = {
                "containerId": self.context.container_id,
                "imageId": self.context.image_id,
                "agentId": self.context.agent_id,
                "sessionId": self.context.session_id,
            }
        if self.request_id:
            result["requestId"] = self.request_id
        return result


# =============================================================================
# Stream Layer Events (DriveableEvents)
# =============================================================================


@dataclass
class DriveableEvent(SystemEvent):
    """
    DriveableEvent - Events that can drive the Agent's state machine.

    These are emitted by ClaudeReceptor from Claude SDK responses.
    """
    pass


@dataclass
class StreamEvent:
    """
    Lightweight stream event for AgentEngine processing.

    This is the internal representation used by the Mealy Machine,
    separate from SystemEvent which has full context.
    """
    type: str
    timestamp: int
    data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Stream Event Data Types
# =============================================================================


@dataclass
class MessageStartData:
    """Data for message_start event."""
    message_id: str
    model: str


@dataclass
class TextDeltaData:
    """Data for text_delta event."""
    text: str


@dataclass
class ToolUseStartData:
    """Data for tool_use_start event."""
    tool_call_id: str
    tool_name: str


@dataclass
class InputJsonDeltaData:
    """Data for input_json_delta event."""
    partial_json: str


@dataclass
class ToolUseStopData:
    """Data for tool_use_stop event."""
    tool_call_id: str
    tool_name: str
    input: Dict[str, Any]


@dataclass
class ToolResultData:
    """Data for tool_result event."""
    tool_call_id: str
    result: Any
    is_error: bool = False


@dataclass
class MessageStopData:
    """Data for message_stop event."""
    stop_reason: str  # "end_turn" | "tool_use" | "max_tokens" | "stop_sequence"
    stop_sequence: Optional[str] = None


@dataclass
class ErrorReceivedData:
    """Data for error_received event."""
    message: str
    error_code: Optional[str] = None


# =============================================================================
# State Layer Events
# =============================================================================


@dataclass
class StateEventData:
    """Data for state change events."""
    state: AgentState
    previous_state: Optional[AgentState] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class StateEvent(SystemEvent):
    """State change event."""
    data: StateEventData = None  # type: ignore

    def __post_init__(self):
        self.category = "state"
        self.source = "agent"
        self.intent = "notification"


# =============================================================================
# Message Layer Events
# =============================================================================


class MessageRole(str, Enum):
    """Message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ToolCall:
    """Tool call representation."""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None


@dataclass
class Message:
    """
    Message in a conversation.

    Attributes:
        message_id: Unique message identifier
        session_id: Parent session ID
        role: Message role (user/assistant/system)
        content: Text content
        timestamp: When the message was created
        tool_calls: Optional list of tool calls
        input_tokens: Token usage (input)
        output_tokens: Token usage (output)
    """
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tool_calls: Optional[List[ToolCall]] = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class MessageEvent(SystemEvent):
    """Message event (user_message, assistant_message, etc.)."""
    data: Message = None  # type: ignore

    def __post_init__(self):
        self.category = "message"
        self.source = "agent"
        self.intent = "notification"


# =============================================================================
# Turn Layer Events
# =============================================================================


@dataclass
class TurnEventData:
    """Data for turn events."""
    turn_id: str
    user_message_id: str
    assistant_message_id: str
    total_tokens: int = 0
    duration_ms: int = 0


@dataclass
class TurnEvent(SystemEvent):
    """Turn event (request-response cycle)."""
    data: TurnEventData = None  # type: ignore

    def __post_init__(self):
        self.category = "turn"
        self.source = "agent"
        self.intent = "notification"


# =============================================================================
# Session Types
# =============================================================================


@dataclass
class AgentSession:
    """Agent session with conversation history."""
    session_id: str
    created_at: datetime
    updated_at: datetime
    state: SessionState
    messages: List[Message] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
