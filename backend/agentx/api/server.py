"""
AgentX API Server

aiohttp-based HTTP server with WebSocket support.
"""

import logging
import json
from aiohttp import web
from typing import Dict, Any

from ..config import AgentConfig
from ..runtime import EventBus, AgentEngine, Container
from ..persistence import PersistenceService
from ..mcp_tools.comfyui_tools import get_comfyui_tools, execute_comfyui_tool

logger = logging.getLogger(__name__)


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
        logger.error(f"Error creating session: {e}", exc_info=True)
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

        # If tool calls are present, execute them
        if response.tool_calls:
            for tc in response.tool_calls:
                try:
                    result = await execute_comfyui_tool(tc.name, tc.arguments)
                    tc.result = result
                except Exception as e:
                    tc.error = str(e)
                    logger.error(f"Tool execution error: {e}", exc_info=True)

            # Submit tool results and continue
            for tc in response.tool_calls:
                if tc.result:
                    response = await container.submit_tool_result(
                        session_id=session_id,
                        tool_call_id=tc.id,
                        result=tc.result,
                    )

        return web.json_response(response.to_dict())

    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
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

    logger.info(f"WebSocket connected for session {session_id}")

    try:
        # Send events to WebSocket
        async for event in event_bus.consume(session_id=session_id):
            await ws.send_json(event.to_dict())

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        await ws.close()
        logger.info(f"WebSocket closed for session {session_id}")

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


def create_app(config: AgentConfig) -> web.Application:
    """
    Create aiohttp application with routes.

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
