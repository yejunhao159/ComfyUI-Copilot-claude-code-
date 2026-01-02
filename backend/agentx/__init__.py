"""
ComfyUI-AgentX Runtime

完整的 AgentX 运行时环境，为 ComfyUI 提供 Claude Code 能力。
基于事件驱动架构，支持 MCP 协议和持久化会话管理。
"""

__version__ = "1.0.0"
__author__ = "ComfyUI-Copilot Team"

# Core type definitions
from .runtime.types import (
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

# Runtime components
from .runtime.event_bus import EventBus
from .runtime.agent_engine import AgentEngine
from .runtime.container import Container

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
    # Meta
    "__version__",
]
