"""
AgentX API Server

aiohttp-based HTTP server with WebSocket support.
"""

import json
import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, Any

from ..config import AgentConfig
from ..runtime import EventBus, AgentEngine, Container
from ..persistence import PersistenceService
from ..mcp_tools.comfyui_tools import get_comfyui_tools, execute_comfyui_tool
from ...utils.logger import get_logger

logger = get_logger(__name__)


async def create_session_handler(request: web.Request) -> web.Response:
    """
    POST /api/agentx/sessions
    Create a new agent session.
    """
    container: Container = request.app["container"]

    try:
        data = await request.json()
        user_id = data.get("user_id")
        title = data.get("title")
        config = data.get("config")

        session = await container.create_session(
            user_id=user_id,
            title=title,
            config=config,
        )

        return web.json_response(session.to_dict(), status=201)

    except Exception as e:
        logger.exception("Error creating session (standalone)")
        return web.json_response({"error": str(e)}, status=500)


async def send_message_handler(request: web.Request) -> web.Response:
    """
    POST /api/agentx/sessions/{session_id}/messages
    Send a message to a session and get response.
    """
    container: Container = request.app["container"]
    session_id = request.match_info["session_id"]

    try:
        data = await request.json()
        content = data.get("content")
        if not content:
            return web.json_response({"error": "content is required"}, status=400)

        # Get tools
        tools = get_comfyui_tools()
        system = data.get("system")

        # Send message
        response = await container.send_message(
            session_id=session_id,
            content=content,
            tools=tools,
            system=system,
        )

        # If tool calls are present, execute them all first
        if response.tool_calls:
            tool_results = []
            for tc in response.tool_calls:
                try:
                    result = await execute_comfyui_tool(tc.name, tc.arguments)
                    tc.result = result
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": result
                    })
                except Exception as e:
                    tc.error = str(e)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": {"error": str(e)}
                    })
                    logger.exception("Tool execution error", tool_name=tc.name)

            # Submit all tool results at once and continue
            if tool_results:
                response = await container.submit_tool_results(
                    session_id=session_id,
                    tool_results=tool_results,
                )

        return web.json_response(response.to_dict())

    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Error sending message (standalone)", session_id=session_id)
        return web.json_response({"error": str(e)}, status=500)


async def get_session_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sessions/{session_id}
    Get session details.
    """
    container: Container = request.app["container"]
    session_id = request.match_info["session_id"]

    session = await container.get_session(session_id)
    if not session:
        return web.json_response({"error": "Session not found"}, status=404)

    return web.json_response(session.to_dict())


async def list_sessions_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sessions
    List sessions.
    """
    container: Container = request.app["container"]

    user_id = request.query.get("user_id")
    limit = int(request.query.get("limit", "50"))

    sessions = await container.list_sessions(user_id=user_id, limit=limit)
    return web.json_response({
        "sessions": [s.to_dict() for s in sessions],
        "count": len(sessions),
    })


async def stream_events_handler(request: web.Request) -> web.WebSocketResponse:
    """
    WebSocket /api/agentx/sessions/{session_id}/stream
    Stream events for a session.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    session_id = request.match_info["session_id"]
    event_bus: EventBus = request.app["event_bus"]

    logger.info("WebSocket connected (standalone)", session_id=session_id)

    try:
        # Send events to WebSocket
        async for event in event_bus.consume(session_id=session_id):
            await ws.send_json(event.to_dict())

    except Exception as e:
        logger.exception("WebSocket error", session_id=session_id)
    finally:
        await ws.close()
        logger.info("WebSocket closed", session_id=session_id)

    return ws


async def on_startup(app: web.Application) -> None:
    """Initialize application state on startup."""
    config: AgentConfig = app["config"]

    # Initialize components
    event_bus = EventBus(maxsize=config.event_queue_maxsize)
    await event_bus.start()

    persistence = PersistenceService(config)
    agent_engine = AgentEngine(config, event_bus)
    container = Container(config, event_bus, agent_engine, persistence)

    # Store in app
    app["event_bus"] = event_bus
    app["persistence"] = persistence
    app["agent_engine"] = agent_engine
    app["container"] = container

    logger.info("AgentX API server started")


async def on_cleanup(app: web.Application) -> None:
    """Cleanup on shutdown."""
    if "event_bus" in app:
        await app["event_bus"].stop()
    if "agent_engine" in app:
        await app["agent_engine"].close()
    if "persistence" in app:
        app["persistence"].close()

    logger.info("AgentX API server stopped")


# Global state for ComfyUI integration
_agentx_state = {}


async def init_agentx_state():
    """Initialize AgentX state for ComfyUI integration."""
    if _agentx_state.get("initialized"):
        return

    config = AgentConfig.from_env()

    event_bus = EventBus(maxsize=config.event_queue_maxsize)
    await event_bus.start()

    persistence = PersistenceService(config)
    agent_engine = AgentEngine(config, event_bus)
    container = Container(config, event_bus, agent_engine, persistence)

    _agentx_state["config"] = config
    _agentx_state["event_bus"] = event_bus
    _agentx_state["persistence"] = persistence
    _agentx_state["agent_engine"] = agent_engine
    _agentx_state["container"] = container
    _agentx_state["initialized"] = True

    logger.info("AgentX state initialized")


def get_container() -> Container:
    """Get the global container instance."""
    return _agentx_state.get("container")


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return _agentx_state.get("event_bus")


# ComfyUI-compatible handlers
async def comfy_create_session_handler(request: web.Request) -> web.Response:
    """POST /api/agentx/sessions - Create session (ComfyUI compatible)."""
    await init_agentx_state()
    container = get_container()

    try:
        data = await request.json()
        session = await container.create_session(
            user_id=data.get("user_id"),
            title=data.get("title"),
            config=data.get("config"),
        )
        return web.json_response(session.to_dict(), status=201)
    except Exception as e:
        logger.exception("Error creating session (comfy)")
        return web.json_response({"error": str(e)}, status=500)


async def comfy_send_message_handler(request: web.Request) -> web.Response:
    """POST /api/agentx/sessions/{session_id}/messages - Send message."""
    await init_agentx_state()
    container = get_container()
    session_id = request.match_info["session_id"]

    try:
        data = await request.json()
        content = data.get("content")
        if not content:
            return web.json_response({"error": "content is required"}, status=400)

        tools = get_comfyui_tools()
        response = await container.send_message(
            session_id=session_id,
            content=content,
            tools=tools,
            system=data.get("system"),
        )

        # Execute tool calls if present - loop until no more tool calls
        all_executed_tools = []
        # No practical limit - personal use, let Claude work freely
        # Using a very high number as a safeguard against infinite loops only
        max_iterations = 200
        iteration = 0

        while response.tool_calls and iteration < max_iterations:
            iteration += 1
            logger.info("Processing tool calls", iteration=iteration, tools=[tc.name for tc in response.tool_calls])

            tool_results = []
            for tc in response.tool_calls:
                try:
                    result = await execute_comfyui_tool(tc.name, tc.arguments)
                    tc.result = result
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": result
                    })
                    # Store executed tool info for frontend
                    tool_info = {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result": result
                    }
                    all_executed_tools.append(tool_info)
                    logger.info("Tool executed", tool_name=tc.name, has_workflow_data='workflow_data' in tc.arguments if tc.arguments else False)
                except Exception as e:
                    tc.error = str(e)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": {"error": str(e)}
                    })
                    logger.error("Tool execution error", tool_name=tc.name, error=str(e))

            if tool_results:
                response = await container.submit_tool_results(
                    session_id=session_id,
                    tool_results=tool_results,
                )

        # Include ALL executed tools in response for frontend
        result = response.to_dict()
        if all_executed_tools:
            result["executed_tools"] = all_executed_tools
            logger.info("Returning executed tools to frontend", tool_count=len(all_executed_tools))
            # Log specifically if update_workflow was called
            for tool in all_executed_tools:
                if tool["name"] == "update_workflow":
                    logger.info("update_workflow found in response", workflow_data_keys=list(tool['arguments'].get('workflow_data', {}).keys()) if tool['arguments'] else [])

        return web.json_response(result)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Error sending message (comfy)", session_id=session_id)
        return web.json_response({"error": str(e)}, status=500)


async def comfy_get_session_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/sessions/{session_id} - Get session."""
    await init_agentx_state()
    container = get_container()
    session_id = request.match_info["session_id"]

    session = await container.get_session(session_id)
    if not session:
        return web.json_response({"error": "Session not found"}, status=404)

    return web.json_response(session.to_dict())


async def comfy_list_sessions_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/sessions - List sessions."""
    await init_agentx_state()
    container = get_container()

    user_id = request.query.get("user_id")
    limit = int(request.query.get("limit", "50"))

    sessions = await container.list_sessions(user_id=user_id, limit=limit)
    return web.json_response({
        "sessions": [s.to_dict() for s in sessions],
        "count": len(sessions),
    })


async def comfy_get_messages_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/sessions/{session_id}/messages - Get message history."""
    await init_agentx_state()
    container = get_container()
    session_id = request.match_info["session_id"]

    session = await container.get_session(session_id)
    if not session:
        return web.json_response({"error": "Session not found"}, status=404)

    messages = [m.to_dict() for m in session.messages]
    return web.json_response({
        "messages": messages,
        "count": len(messages),
    })


async def comfy_stream_events_handler(request: web.Request) -> web.WebSocketResponse:
    """WebSocket /api/agentx/sessions/{session_id}/stream - Stream events with bidirectional messaging."""
    await init_agentx_state()
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    session_id = request.match_info["session_id"]
    event_bus = get_event_bus()
    container = get_container()

    logger.info("WebSocket connected (comfy)", session_id=session_id)

    async def handle_incoming_messages():
        """Handle incoming messages from the frontend."""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "message":
                        content = data.get("content")
                        system = data.get("system")
                        if content:
                            logger.info("WebSocket received message", content_preview=content[:50])
                            await process_message_streaming(session_id, content, system, ws, container)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from WebSocket")
                except Exception as e:
                    logger.exception("Error processing WebSocket message")
                    await ws.send_json({"type": "error", "data": {"message": str(e)}})
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("WebSocket error", error=str(ws.exception()))
                break

    async def forward_events():
        """Forward events from event bus to WebSocket."""
        try:
            async for event in event_bus.consume(session_id=session_id):
                if ws.closed:
                    break
                await ws.send_json(event.to_dict())
        except Exception as e:
            if not ws.closed:
                logger.exception("Event forwarding error", session_id=session_id)

    try:
        # Run both tasks concurrently
        await asyncio.gather(
            handle_incoming_messages(),
            forward_events(),
            return_exceptions=True
        )
    except Exception as e:
        logger.exception("WebSocket error (comfy)", session_id=session_id)
    finally:
        if not ws.closed:
            await ws.close()
        logger.info("WebSocket closed (comfy)", session_id=session_id)

    return ws


async def process_message_streaming(session_id: str, content: str, system: str, ws: web.WebSocketResponse, container: Container):
    """Process a message and stream results via WebSocket."""
    import uuid
    from datetime import datetime
    from ..runtime.types import TurnEventData

    turn_start = datetime.utcnow()

    try:
        tools = get_comfyui_tools()
        response = await container.send_message(
            session_id=session_id,
            content=content,
            tools=tools,
            system=system,
        )

        # Execute tool calls if present - loop until no more tool calls
        all_executed_tools = []
        max_iterations = 200
        iteration = 0

        while response.tool_calls and iteration < max_iterations:
            iteration += 1
            logger.info("[WS] Processing tool calls", iteration=iteration, tools=[tc.name for tc in response.tool_calls])

            # Send tool_use events to frontend
            for tc in response.tool_calls:
                await ws.send_json({
                    "type": "tool_use",
                    "data": {
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments
                    }
                })

            tool_results = []
            for tc in response.tool_calls:
                try:
                    result = await execute_comfyui_tool(tc.name, tc.arguments)
                    tc.result = result
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": result
                    })
                    tool_info = {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result": result
                    }
                    all_executed_tools.append(tool_info)

                    # Send tool_result event
                    await ws.send_json({
                        "type": "tool_result",
                        "data": {
                            "tool_use_id": tc.id,
                            "content": result
                        }
                    })
                except Exception as e:
                    tc.error = str(e)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "result": {"error": str(e)}
                    })
                    logger.error("[WS] Tool execution error", tool_name=tc.name, error=str(e))

            if tool_results:
                response = await container.submit_tool_results(
                    session_id=session_id,
                    tool_results=tool_results,
                )

        # Send final message content if present
        if response.content:
            await ws.send_json({
                "type": "message",
                "data": {
                    "content": response.content
                }
            })

        # Send turn complete event with executed tools
        turn_duration = int((datetime.utcnow() - turn_start).total_seconds() * 1000)
        await ws.send_json({
            "type": "turn",
            "data": {
                "turn_id": str(uuid.uuid4()),
                "user_message_id": "",
                "assistant_message_id": response.message_id if hasattr(response, 'message_id') else "",
                "total_tokens": (response.input_tokens or 0) + (response.output_tokens or 0),
                "duration_ms": turn_duration,
                "executed_tools": all_executed_tools
            }
        })
        logger.info("[WS] Turn complete", executed_tool_count=len(all_executed_tools))

    except Exception as e:
        logger.exception("[WS] Error processing message", session_id=session_id)
        await ws.send_json({
            "type": "error",
            "data": {"message": str(e)}
        })


async def comfy_health_handler(request: web.Request) -> web.Response:
    """GET /api/agentx/health - Health check."""
    return web.json_response({
        "status": "ok",
        "version": "3.0.0",
        "initialized": _agentx_state.get("initialized", False),
    })


async def comfy_get_logs_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/logs - Get execution logs.

    Query params:
        lines: Number of lines to return (default: 100, max: 1000)
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        search: Search term to filter logs
    """
    import os

    try:
        lines = min(int(request.query.get("lines", "100")), 1000)
        level_filter = request.query.get("level", "").upper()
        search_term = request.query.get("search", "")

        # Find log file
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_path = os.path.join(current_dir, "backend", "logs", "agentx.log")

        if not os.path.exists(log_path):
            return web.json_response({
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            })

        # Read log file (tail)
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        # Filter by level if specified
        if level_filter:
            all_lines = [line for line in all_lines if f"| {level_filter}" in line]

        # Filter by search term if specified
        if search_term:
            all_lines = [line for line in all_lines if search_term.lower() in line.lower()]

        # Get last N lines
        log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Parse log lines into structured format
        parsed_logs = []
        for line in log_lines:
            line = line.strip()
            if not line:
                continue

            # Parse format: "2024-01-04 12:00:00 | LEVEL | location | message | context"
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
            "filters": {
                "level": level_filter or None,
                "search": search_term or None,
                "lines": lines
            }
        })

    except Exception as e:
        logger.exception("Error reading logs")
        return web.json_response({"error": str(e)}, status=500)


async def comfy_clear_logs_handler(request: web.Request) -> web.Response:
    """
    DELETE /api/agentx/logs - Clear log file.
    """
    import os

    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_path = os.path.join(current_dir, "backend", "logs", "agentx.log")

        if os.path.exists(log_path):
            # Truncate the file
            with open(log_path, 'w') as f:
                f.write("")
            logger.info("Log file cleared")
            return web.json_response({"success": True, "message": "Logs cleared"})
        else:
            return web.json_response({"success": True, "message": "Log file not found"})

    except Exception as e:
        logger.exception("Error clearing logs")
        return web.json_response({"error": str(e)}, status=500)


async def comfy_sync_workflow_handler(request: web.Request) -> web.Response:
    """
    POST /api/agentx/sync/workflow - Sync workflow from frontend canvas.

    This allows the frontend to upload the current canvas workflow,
    so Claude can read and analyze it.
    """
    await init_agentx_state()

    try:
        data = await request.json()
        workflow = data.get("workflow", {})
        node_count = data.get("node_count", 0)

        # Import and update the workflow state
        from ..mcp_tools.tools.workflow_state import state
        state.workflow = workflow

        logger.info("Synced workflow from canvas", node_count=node_count)

        return web.json_response({
            "success": True,
            "message": f"Workflow synced: {node_count} nodes",
            "node_count": node_count,
        })
    except Exception as e:
        logger.exception("Error syncing workflow")
        return web.json_response({"error": str(e)}, status=500)


async def comfy_get_current_workflow_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/sync/workflow - Get the current workflow state.

    Returns the workflow that Claude is currently working with.
    """
    await init_agentx_state()

    try:
        from ..mcp_tools.tools.workflow_state import state
        workflow = state.workflow

        return web.json_response({
            "workflow": workflow,
            "node_count": len(workflow),
        })
    except Exception as e:
        logger.exception("Error getting workflow")
        return web.json_response({"error": str(e)}, status=500)


async def agentx_ui_handler(request: web.Request) -> web.Response:
    """
    GET /api/agentx/ - Serve AgentX UI index.html
    """
    import os
    # Find the dist directory relative to this file
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    index_path = os.path.join(current_dir, "dist", "agentx_web", "index.html")

    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    else:
        return web.Response(text=f"AgentX UI not found at {index_path}", status=404)


async def agentx_static_handler(request: web.Request) -> web.FileResponse:
    """
    GET /api/agentx/assets/{filename} - Serve static assets
    """
    import os
    filename = request.match_info.get('filename', '')
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    file_path = os.path.join(current_dir, "dist", "agentx_web", "assets", filename)

    if os.path.exists(file_path) and os.path.isfile(file_path):
        return web.FileResponse(file_path)
    else:
        raise web.HTTPNotFound()


def create_agentx_routes() -> list:
    """
    Create AgentX routes for ComfyUI PromptServer integration.

    Returns:
        List of aiohttp route definitions
    """
    return [
        # UI routes (must be before API routes)
        web.get("/api/agentx/", agentx_ui_handler),
        web.get("/api/agentx/assets/{filename}", agentx_static_handler),
        # API routes
        web.post("/api/agentx/sessions", comfy_create_session_handler),
        web.post("/api/agentx/sessions/{session_id}/messages", comfy_send_message_handler),
        web.get("/api/agentx/sessions/{session_id}/messages", comfy_get_messages_handler),
        web.get("/api/agentx/sessions/{session_id}", comfy_get_session_handler),
        web.get("/api/agentx/sessions", comfy_list_sessions_handler),
        web.get("/api/agentx/sessions/{session_id}/stream", comfy_stream_events_handler),
        web.get("/api/agentx/health", comfy_health_handler),
        # Log routes
        web.get("/api/agentx/logs", comfy_get_logs_handler),
        web.delete("/api/agentx/logs", comfy_clear_logs_handler),
        # Workflow sync routes
        web.post("/api/agentx/sync/workflow", comfy_sync_workflow_handler),
        web.get("/api/agentx/sync/workflow", comfy_get_current_workflow_handler),
    ]


def create_app(config: AgentConfig) -> web.Application:
    """
    Create standalone aiohttp application with routes.

    Args:
        config: AgentConfig instance

    Returns:
        Configured aiohttp application
    """
    app = web.Application()
    app["config"] = config

    # Register routes
    app.router.add_post("/api/agentx/sessions", create_session_handler)
    app.router.add_post("/api/agentx/sessions/{session_id}/messages", send_message_handler)
    app.router.add_get("/api/agentx/sessions/{session_id}", get_session_handler)
    app.router.add_get("/api/agentx/sessions", list_sessions_handler)
    app.router.add_get("/api/agentx/sessions/{session_id}/stream", stream_events_handler)

    # Register lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app
