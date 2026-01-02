"""
ComfyUI-AgentX Runtime

完整的 AgentX 运行时环境，为 ComfyUI 提供 Claude Code 能力。
基于事件驱动架构，支持 MCP 协议和持久化会话管理。
"""

__version__ = "1.0.0"
__author__ = "ComfyUI-Copilot Team"

from .runtime.agent_engine import AgentEngine
from .runtime.container import Container
from .runtime.event_bus import EventBus
from .runtime.types import (
    EventType,
    SessionState,
    AgentEvent,
    AgentSession,
    Message,
    MessageRole,
    ToolCall,
)

__all__ = [
    "AgentEngine",
    "Container",
    "EventBus",
    "EventType",
    "SessionState",
    "AgentEvent",
    "AgentSession",
    "Message",
    "MessageRole",
    "ToolCall",
    "__version__",
]
