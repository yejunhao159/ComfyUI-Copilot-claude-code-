"""
AgentX API Server V2

HTTP server using Runtime V2 with true Agentic Loop capability via claude-agent-sdk.

This is a complete rewrite that uses the new event-driven architecture:
- SystemBus for pub/sub communication
- RuntimeAgent with automatic Agentic Loop
- HTTP Streaming (NDJSON) for real-time updates
"""

import json
import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from aiohttp import web

from ..runtime_v2 import (
    Runtime,
    RuntimeConfig,
    create_runtime,
    RuntimeContainer,
    RuntimeAgent,
    ImageRecord,
    SystemEvent,
    AgentState,
)
from ..mcp_tools.comfyui_tools import get_comfyui_tools, execute_comfyui_tool
from ..mcp_tools.tools.workflow_state import state as workflow_state
from ...utils.logger import get_logger, configure_logging

# Configure logging on import
configure_logging(log_level="INFO")
logger = get_logger(__name__)


# =============================================================================
# Global State
# =============================================================================


class AgentXState:
    """Global state for AgentX runtime."""

    def __init__(self):
        self.runtime: Optional[Runtime] = None
        self.container: Optional[RuntimeContainer] = None
        self.agents: Dict[str, RuntimeAgent] = {}  # session_id -> agent
        self.initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self, config: RuntimeConfig) -> None:
        """Initialize the runtime."""
        async with self._lock:
            if self.initialized:
                return

            logger.info("Initializing AgentX Runtime V2...")

            # Create runtime
            self.runtime = await create_runtime(config)

            # Create default container
            self.container = await self.runtime.create_container("default")

            self.initialized = True
            logger.info("AgentX Runtime V2 initialized successfully")

    async def get_or_create_agent(self, session_id: str, system_prompt: Optional[str] = None) -> RuntimeAgent:
        """Get or create an agent for a session."""
        if session_id in self.agents:
            return self.agents[session_id]

        if not self.container:
            raise RuntimeError("Runtime not initialized")

        # Create image record
        image = ImageRecord(
            image_id=f"image_{session_id}",
            name=f"Session {session_id}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            system_prompt=system_prompt or self.runtime.config.system_prompt,
            model=self.runtime.config.model,
        )

        # Run agent
        agent, reused = await self.container.run_image(image)
        self.agents[session_id] = agent

        logger.info(f"Agent created for session {session_id}", agent_id=agent.agent_id, reused=reused)
        return agent

    async def shutdown(self) -> None:
        """Shutdown the runtime."""
        if self.runtime:
            await self.runtime.shutdown()
            self.initialized = False
            logger.info("AgentX Runtime V2 shutdown")


# Global state instance
_state = AgentXState()


async def ensure_initialized() -> None:
    """Ensure runtime is initialized."""
    if _state.initialized:
        return

    from ..config import AgentConfig as LegacyConfig

    # Load config from environment
    legacy_config = LegacyConfig.from_env()

    config = RuntimeConfig(
        api_key=legacy_config.anthropic_api_key,
        base_url=legacy_config.anthropic_base_url,
        model=legacy_config.model,
        timeout=30000,
        system_prompt="""You are a ComfyUI workflow assistant. You can help users:
- Create, modify, and debug ComfyUI workflows
- Search for and recommend nodes
- Execute workflows and analyze results
- Explain how different nodes work

When working with workflows, always use the available tools to interact with ComfyUI.
Think step by step and verify your actions.""",
    )

    await _state.initialize(config)


# =============================================================================
# Session Handlers
# =============================================================================


async def create_session_handler(request: web.Request) -> web.Response:
    """
    POST /api/agentx/sessions
    Create a new agent session.
    """
    await ensure_initialized()

    try:
        data = await request.json()
        session_id = str(uuid.uuid4())

        # Create agent for session
        system_prompt = data.get("system")
        agent = await _state.get_or_create_agent(session_id, system_prompt)

        return web.json_response({
            "session_id": session_id,
            "agent_id": agent.agent_id,
            "created_at": datetime.utcnow().isoformat(),
            "state": agent.state.value,
        }, status=201)

    except Exception as e:
        logger.exception("Error creating session")
        return web.json_response({"error": str(e)}, status=500)


async def get_session_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sessions/{session_id}
    Get session details.
    """
    await ensure_initialized()
    session_id = request.match_info["session_id"]

    agent = _state.agents.get(session_id)
    if not agent:
        return web.json_response({"error": "Session not found"}, status=404)

    return web.json_response({
        "session_id": session_id,
        "agent_id": agent.agent_id,
        "state": agent.state.value,
        "lifecycle": agent.lifecycle.value,
        "message_count": len(agent.session.messages),
    })


async def list_sessions_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sessions
    List all sessions.
    """
    await ensure_initialized()

    sessions = []
    for session_id, agent in _state.agents.items():
        sessions.append({
            "session_id": session_id,
            "agent_id": agent.agent_id,
            "state": agent.state.value,
            "message_count": len(agent.session.messages),
        })

    return web.json_response({
        "sessions": sessions,
        "count": len(sessions),
    })


async def get_messages_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sessions/{session_id}/messages
    Get message history.
    """
    await ensure_initialized()
    session_id = request.match_info["session_id"]

    agent = _state.agents.get(session_id)
    if not agent:
        return web.json_response({"error": "Session not found"}, status=404)

    messages = []
    for msg in agent.session.messages:
        messages.append({
            "message_id": msg.message_id,
            "role": msg.role.value,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments, "result": tc.result}
                for tc in (msg.tool_calls or [])
            ] if msg.tool_calls else None,
        })

    return web.json_response({
        "messages": messages,
        "count": len(messages),
    })


# =============================================================================
# Chat Handler with HTTP Streaming
# =============================================================================


async def chat_streaming_handler(request: web.Request) -> web.StreamResponse:
    """
    POST /api/agentx/sessions/{session_id}/chat
    HTTP Streaming chat endpoint using NDJSON.

    This is the main endpoint for chat with Agentic Loop support.

    Request:
        {
            "content": "user message",
            "system": "optional system prompt override"
        }

    Response (NDJSON stream):
        {"type": "start", "turn_id": "..."}
        {"type": "state", "state": "thinking"}
        {"type": "text", "content": "partial text"}
        {"type": "tool_start", "tool_id": "...", "name": "...", "input": {...}}
        {"type": "tool_end", "tool_id": "...", "result": {...}, "success": true}
        {"type": "done", "content": "full text", "executed_tools": [...]}
        {"type": "error", "message": "error message"}
    """
    await ensure_initialized()
    session_id = request.match_info["session_id"]

    # Setup streaming response
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'application/x-ndjson',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )
    await response.prepare(request)

    async def send_event(event_type: str, data: dict = None):
        """Send an event as NDJSON line."""
        event = {"type": event_type}
        if data:
            event.update(data)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        await response.write(line.encode('utf-8'))

    turn_id = str(uuid.uuid4())
    turn_start = time.time()

    try:
        # Parse request
        data = await request.json()
        content = data.get("content")
        if not content:
            await send_event("error", {"message": "content is required"})
            await response.write_eof()
            return response

        system_prompt = data.get("system")

        # Get or create agent
        agent = await _state.get_or_create_agent(session_id, system_prompt)

        # Send start event
        await send_event("start", {"turn_id": turn_id, "session_id": session_id})

        # Track events and executed tools
        all_executed_tools = []
        accumulated_text = ""
        event_queue = asyncio.Queue()

        # Subscribe to events for this agent
        def on_event(event: SystemEvent):
            if event.context and event.context.agent_id == agent.agent_id:
                try:
                    event_queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

        unsubscribe = _state.runtime.events.on_any(on_event)

        try:
            # Start the agent processing in background
            agent_task = asyncio.create_task(agent.receive(content))

            # Process events while agent is working
            done = False
            while not done:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)

                    # Process event
                    if event.type == "state_change":
                        state_data = event.data
                        if hasattr(state_data, "state"):
                            state = state_data.state.value if hasattr(state_data.state, "value") else str(state_data.state)
                        else:
                            state = str(state_data)
                        await send_event("state", {"state": state})

                        if state in ["done", "error", "idle"]:
                            done = True

                    elif event.type == "text_delta":
                        text = event.data.get("text", "") if isinstance(event.data, dict) else ""
                        accumulated_text += text
                        await send_event("text", {"content": text})

                    elif event.type == "tool_use_content_block_start":
                        tool_data = event.data
                        if hasattr(tool_data, "tool_call_id"):
                            await send_event("tool_start", {
                                "tool_id": tool_data.tool_call_id,
                                "name": tool_data.tool_name,
                            })
                        elif isinstance(tool_data, dict):
                            await send_event("tool_start", {
                                "tool_id": tool_data.get("tool_call_id", ""),
                                "name": tool_data.get("tool_name", ""),
                            })

                    elif event.type == "tool_use_content_block_stop":
                        # Tool execution happens automatically in SDK
                        pass

                    elif event.type == "message_stop":
                        done = True

                    elif event.type == "error_received":
                        error_data = event.data
                        if hasattr(error_data, "message"):
                            await send_event("error", {"message": error_data.message})
                        elif isinstance(error_data, dict):
                            await send_event("error", {"message": error_data.get("message", "Unknown error")})
                        done = True

                except asyncio.TimeoutError:
                    # Check if agent task is done
                    if agent_task.done():
                        # Check for exception
                        try:
                            agent_task.result()
                        except Exception as e:
                            await send_event("error", {"message": str(e)})
                        done = True

        finally:
            unsubscribe()

        # Wait for agent task to complete
        try:
            await agent_task
        except Exception as e:
            logger.exception("Agent task error")
            await send_event("error", {"message": str(e)})

        # Send done event
        turn_duration = int((time.time() - turn_start) * 1000)
        await send_event("done", {
            "turn_id": turn_id,
            "content": accumulated_text,
            "duration_ms": turn_duration,
            "executed_tools": all_executed_tools,
        })

        logger.info("Turn complete", turn_id=turn_id, duration_ms=turn_duration)

    except Exception as e:
        logger.exception("Error in chat handler", session_id=session_id)
        await send_event("error", {"message": str(e)})

    await response.write_eof()
    return response


# =============================================================================
# Non-Streaming Message Handler
# =============================================================================


async def send_message_handler(request: web.Request) -> web.Response:
    """
    POST /api/agentx/sessions/{session_id}/messages
    Send a message (non-streaming, collects result and returns).

    Note: For real-time updates, use the /chat endpoint with streaming instead.
    This endpoint waits for the full response before returning.
    """
    await ensure_initialized()
    session_id = request.match_info["session_id"]

    try:
        data = await request.json()
        content = data.get("content")
        if not content:
            return web.json_response({"error": "content is required"}, status=400)

        # Get or create agent
        system_prompt = data.get("system")
        agent = await _state.get_or_create_agent(session_id, system_prompt)

        # Collect response by subscribing to events
        accumulated_text = ""
        executed_tools = []
        error_message = None
        done_event = asyncio.Event()

        def on_event(event: SystemEvent):
            nonlocal accumulated_text, executed_tools, error_message

            if event.context and event.context.agent_id != agent.agent_id:
                return

            if event.type == "text_delta":
                text = event.data.get("text", "") if isinstance(event.data, dict) else ""
                if hasattr(event.data, "text"):
                    text = event.data.text
                accumulated_text += text

            elif event.type == "tool_use_content_block_start":
                tool_data = event.data
                tool_info = {"name": "", "arguments": {}, "result": None}
                if hasattr(tool_data, "tool_name"):
                    tool_info["name"] = tool_data.tool_name
                elif isinstance(tool_data, dict):
                    tool_info["name"] = tool_data.get("tool_name", "")
                executed_tools.append(tool_info)

            elif event.type == "error_received":
                if hasattr(event.data, "message"):
                    error_message = event.data.message
                elif isinstance(event.data, dict):
                    error_message = event.data.get("message", "Unknown error")
                done_event.set()

            elif event.type in ["message_stop", "state_change"]:
                state = None
                if hasattr(event.data, "state"):
                    state = event.data.state.value if hasattr(event.data.state, "value") else str(event.data.state)
                elif isinstance(event.data, dict):
                    state = event.data.get("state", "")

                if event.type == "message_stop" or state in ["done", "idle", "error"]:
                    done_event.set()

        # Subscribe to events
        unsubscribe = _state.runtime.events.on_any(on_event)

        try:
            # Start agent processing
            agent_task = asyncio.create_task(agent.receive(content))

            # Wait for completion with timeout
            try:
                await asyncio.wait_for(done_event.wait(), timeout=120.0)
            except asyncio.TimeoutError:
                error_message = "Request timeout after 120 seconds"

            # Ensure agent task completes
            try:
                await asyncio.wait_for(agent_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                if not error_message:
                    error_message = str(e)

        finally:
            unsubscribe()

        # Build response
        if error_message:
            return web.json_response({
                "error": error_message,
                "content": accumulated_text,
                "executed_tools": executed_tools,
            }, status=500)

        return web.json_response({
            "session_id": session_id,
            "content": accumulated_text,
            "executed_tools": executed_tools if executed_tools else None,
            "message_count": len(agent.session.messages),
        })

    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Error sending message", session_id=session_id)
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Utility Handlers
# =============================================================================


async def health_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/health - Health check."""
    return web.json_response({
        "status": "ok",
        "version": "4.0.0",
        "runtime": "v2",
        "initialized": _state.initialized,
        "agent_count": len(_state.agents),
    })


async def sync_workflow_handler(request: web.Request) -> web.Response:
    """POST /api/agentx/sync/workflow - Sync workflow from frontend."""
    await ensure_initialized()

    try:
        data = await request.json()
        workflow = data.get("workflow", {})
        node_count = data.get("node_count", 0)

        workflow_state.workflow = workflow

        logger.info("Synced workflow from canvas", node_count=node_count)

        return web.json_response({
            "success": True,
            "message": f"Workflow synced: {node_count} nodes",
            "node_count": node_count,
        })
    except Exception as e:
        logger.exception("Error syncing workflow")
        return web.json_response({"error": str(e)}, status=500)


async def get_workflow_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/sync/workflow - Get current workflow."""
    await ensure_initialized()

    try:
        return web.json_response({
            "workflow": workflow_state.workflow,
            "node_count": len(workflow_state.workflow),
        })
    except Exception as e:
        logger.exception("Error getting workflow")
        return web.json_response({"error": str(e)}, status=500)


async def get_logs_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/logs - Get execution logs."""
    import os

    try:
        lines = min(int(request.query.get("lines", "100")), 1000)
        level_filter = request.query.get("level", "").upper()
        search_term = request.query.get("search", "")

        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_path = os.path.join(current_dir, "backend", "logs", "agentx.log")

        if not os.path.exists(log_path):
            return web.json_response({
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            })

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        if level_filter:
            all_lines = [line for line in all_lines if f"| {level_filter}" in line]

        if search_term:
            all_lines = [line for line in all_lines if search_term.lower() in line.lower()]

        log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        parsed_logs = []
        for line in log_lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split(" | ", 4)
            if len(parts) >= 4:
                parsed_logs.append({
                    "timestamp": parts[0],
                    "level": parts[1].strip(),
                    "location": parts[2] if len(parts) > 2 else "",
                    "message": parts[3] if len(parts) > 3 else "",
                    "context": parts[4] if len(parts) > 4 else "",
                    "raw": line
                })
            else:
                parsed_logs.append({
                    "timestamp": "",
                    "level": "INFO",
                    "location": "",
                    "message": line,
                    "context": "",
                    "raw": line
                })

        return web.json_response({
            "logs": parsed_logs,
            "total_lines": len(all_lines),
            "returned_lines": len(parsed_logs),
        })

    except Exception as e:
        logger.exception("Error reading logs")
        return web.json_response({"error": str(e)}, status=500)


async def clear_logs_handler(request: web.Request) -> web.Response:
    """DELETE /api/agentx/logs - Clear log file."""
    import os

    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_path = os.path.join(current_dir, "backend", "logs", "agentx.log")

        if os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write("")
            logger.info("Log file cleared")
            return web.json_response({"success": True, "message": "Logs cleared"})
        else:
            return web.json_response({"success": True, "message": "Log file not found"})

    except Exception as e:
        logger.exception("Error clearing logs")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Route Registration
# =============================================================================


def create_agentx_routes_v2() -> list:
    """
    Create AgentX V2 routes for ComfyUI PromptServer integration.

    Returns:
        List of aiohttp route definitions
    """
    return [
        # Session management
        web.post("/api/agentx/sessions", create_session_handler),
        web.get("/api/agentx/sessions", list_sessions_handler),
        web.get("/api/agentx/sessions/{session_id}", get_session_handler),
        web.get("/api/agentx/sessions/{session_id}/messages", get_messages_handler),

        # Chat (main endpoint)
        web.post("/api/agentx/sessions/{session_id}/chat", chat_streaming_handler),

        # Legacy message endpoint (for backward compatibility)
        web.post("/api/agentx/sessions/{session_id}/messages", send_message_handler),

        # Utility endpoints
        web.get("/api/agentx/health", health_handler),
        web.post("/api/agentx/sync/workflow", sync_workflow_handler),
        web.get("/api/agentx/sync/workflow", get_workflow_handler),
        web.get("/api/agentx/logs", get_logs_handler),
        web.delete("/api/agentx/logs", clear_logs_handler),
    ]


# =============================================================================
# Lifecycle Hooks
# =============================================================================


async def on_startup(app: web.Application) -> None:
    """Initialize on startup."""
    await ensure_initialized()
    logger.info("AgentX API Server V2 started")


async def on_cleanup(app: web.Application) -> None:
    """Cleanup on shutdown."""
    await _state.shutdown()
    logger.info("AgentX API Server V2 stopped")
