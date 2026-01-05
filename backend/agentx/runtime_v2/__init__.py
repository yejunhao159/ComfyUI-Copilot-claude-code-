"""
AgentX Runtime V2 - Python Port of AgentX TypeScript

This is a complete port of the AgentX TypeScript architecture to Python,
using the official claude-agent-sdk for true Agentic Loop capability.

Architecture:

    ┌─────────────────────────────────────────────────────────────────┐
    │                         AgentX Runtime                          │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   ┌─────────┐     ┌──────────┐     ┌──────────────────────┐   │
    │   │ Runtime │────▶│Container │────▶│ Agent (RuntimeAgent) │   │
    │   └─────────┘     └──────────┘     └──────────────────────┘   │
    │        │               │                      │                │
    │        │               │           ┌──────────┴──────────┐    │
    │        │               │           │                     │    │
    │        ▼               ▼           ▼                     ▼    │
    │   ┌─────────┐   ┌──────────┐  ┌─────────┐      ┌──────────┐  │
    │   │SystemBus│◀──│ Session  │  │ Engine  │      │Environment│  │
    │   └─────────┘   └──────────┘  └─────────┘      └──────────┘  │
    │        │                           │                  │       │
    │        │                           │           ┌──────┴─────┐ │
    │        │                           │           │            │ │
    │        ▼                           ▼           ▼            ▼ │
    │   ┌─────────┐              ┌──────────┐  ┌────────┐  ┌───────┐│
    │   │ Events  │              │MealyMach │  │Receptor│  │Effector│
    │   │ (Pub/Sub│              │(state)   │  │(in)    │  │(out)   ││
    │   └─────────┘              └──────────┘  └────────┘  └───────┘│
    │                                                               │
    └─────────────────────────────────────────────────────────────────┘

Key Concepts:
    - SystemBus: Central event bus for all component communication
    - Container: Runtime isolation boundary for Agent instances
    - Agent: Complete runtime entity (LLM + Sandbox + Session + Engine)
    - Environment: Receptor (perceives) + Effector (acts) pattern
    - Session: Conversation history and persistence

The key difference from V1 is that V2 uses claude-agent-sdk for the
true Agentic Loop (Gather Context → Take Action → Verify Work → Repeat).
"""

from .system_bus import SystemBus, SystemBusImpl
from .types import (
    SystemEvent,
    StreamEvent,
    StateEvent,
    MessageEvent,
    TurnEvent,
    DriveableEvent,
    AgentState,
    AgentLifecycle,
    EventContext,
    Message,
    MessageRole,
    AgentSession,
    SessionState,
)
from .agent import RuntimeAgent, AgentConfig
from .container import RuntimeContainer, ImageRecord, LLMConfig
from .runtime import Runtime, RuntimeConfig, create_runtime
from .environment import ClaudeEnvironment, ClaudeEffectorConfig
from .mcp_integration import (
    create_comfyui_mcp_server,
    get_comfyui_tool_definitions,
    create_tool_result,
    create_error_result,
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
    # MCP Integration
    "create_comfyui_mcp_server",
    "get_comfyui_tool_definitions",
    "create_tool_result",
    "create_error_result",
    # Types
    "SystemEvent",
    "StreamEvent",
    "StateEvent",
    "MessageEvent",
    "TurnEvent",
    "DriveableEvent",
    "AgentState",
    "AgentLifecycle",
    "EventContext",
    "Message",
    "MessageRole",
    "AgentSession",
    "SessionState",
]
