"""
AgentX Runtime Core

核心运行时组件：AgentEngine（Claude 集成）、EventBus（事件系统）、
Container（会话管理）和类型定义。
"""

# Always available: type definitions
from .types import (
    EventType,
    SessionState,
    AgentState,
    MessageRole,
    AgentEvent,
    StreamEvent,
    StateEvent,
    MessageEvent,
    TurnEvent,
    AgentSession,
    Message,
    ToolCall,
)

# Import runtime components
from .event_bus import EventBus
from .agent_engine import AgentEngine
from .container import Container

__all__ = [
    # Types
    "EventType",
    "SessionState",
    "AgentState",
    "MessageRole",
    "AgentEvent",
    "StreamEvent",
    "StateEvent",
    "MessageEvent",
    "TurnEvent",
    "AgentSession",
    "Message",
    "ToolCall",
    # Components
    "EventBus",
    "AgentEngine",
    "Container",
]
