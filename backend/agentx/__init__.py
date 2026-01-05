"""
ComfyUI-AgentX Runtime V2

完整的 AgentX 运行时环境，为 ComfyUI 提供 True Agentic Loop 能力。
基于 claude-agent-sdk 和事件驱动架构。
"""

__version__ = "2.0.0"
__author__ = "ComfyUI-Copilot Team"

# Re-export from runtime_v2
from .runtime_v2 import (
    # Core Runtime
    Runtime,
    RuntimeConfig,
    create_runtime,
    # Container
    RuntimeContainer,
    ImageRecord,
    LLMConfig,
    # Agent
    RuntimeAgent,
    AgentConfig,
    # Event Bus
    SystemBus,
    SystemBusImpl,
    # Environment
    ClaudeEnvironment,
    ClaudeEffectorConfig,
    # Types
    SystemEvent,
    StreamEvent,
    StateEvent,
    MessageEvent,
    TurnEvent,
    AgentState,
    AgentLifecycle,
    EventContext,
    Message,
    MessageRole,
    AgentSession,
    SessionState,
)

__all__ = [
    # Core Runtime
    "Runtime",
    "RuntimeConfig",
    "create_runtime",
    # Container
    "RuntimeContainer",
    "ImageRecord",
    "LLMConfig",
    # Agent
    "RuntimeAgent",
    "AgentConfig",
    # Event Bus
    "SystemBus",
    "SystemBusImpl",
    # Environment
    "ClaudeEnvironment",
    "ClaudeEffectorConfig",
    # Types
    "SystemEvent",
    "StreamEvent",
    "StateEvent",
    "MessageEvent",
    "TurnEvent",
    "AgentState",
    "AgentLifecycle",
    "EventContext",
    "Message",
    "MessageRole",
    "AgentSession",
    "SessionState",
    # Meta
    "__version__",
]
