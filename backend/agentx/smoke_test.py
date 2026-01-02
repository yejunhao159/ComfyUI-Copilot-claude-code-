"""
Quick smoke test to verify AgentX runtime can be imported
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

print("Testing AgentX Runtime imports...")

# Test type imports
print("✓ Importing types...")
from backend.agentx.runtime.types import (
    EventType,
    SessionState,
    AgentState,
    MessageRole,
    StreamEvent,
    StateEvent,
    MessageEvent,
    TurnEvent,
    AgentSession,
    Message,
    ToolCall,
)

# Test EventBus
print("✓ Importing EventBus...")
from backend.agentx.runtime.event_bus import EventBus

# Test persistence models
print("✓ Importing persistence models...")
from backend.agentx.persistence.models import (
    Base,
    AgentSessionModel,
    AgentMessageModel,
    AgentEventModel,
)

# Test persistence service
print("✓ Importing PersistenceService...")
from backend.agentx.persistence.service import PersistenceService

# Test config
print("✓ Importing AgentConfig...")
from backend.agentx.config import AgentConfig

print("\n✅ All imports successful!")
print("\nTesting basic functionality...")

# Test EventBus creation
bus = EventBus(maxsize=10)
print(f"✓ Created EventBus with maxsize=10, current size: {bus.qsize()}")

# Test event creation
event = StreamEvent(session_id="test", data="Hello")
print(f"✓ Created StreamEvent: type={event.type.value}, session={event.session_id}")

# Test config (without API key)
try:
    config = AgentConfig(
        anthropic_api_key="test-key",
        database_url="sqlite:///test.db",
    )
    print(f"✓ Created AgentConfig: model={config.model}, db={config.database_url}")
except Exception as e:
    print(f"✗ Failed to create config: {e}")

# Test AgentEngine and Container imports
print("✓ Importing AgentEngine and Container...")
from backend.agentx.runtime.agent_engine import AgentEngine
from backend.agentx.runtime.container import Container

# Test API server
print("✓ Importing API server...")
from backend.agentx.api import create_app

# Test MCP tools
print("✓ Importing MCP tools...")
from backend.agentx.mcp_tools.comfyui_tools import get_comfyui_tools

tools = get_comfyui_tools()
print(f"✓ Loaded {len(tools)} ComfyUI tools: {[t['name'] for t in tools]}")

print("\n✅ Smoke test passed!")
