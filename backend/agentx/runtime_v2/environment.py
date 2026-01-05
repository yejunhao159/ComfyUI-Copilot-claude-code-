"""
ClaudeEnvironment - Claude Agent SDK Integration via Receptor/Effector Pattern

Ported from @agentxjs/runtime/src/environment/

This module integrates with the official claude-agent-sdk to provide
native Claude Code capabilities including:
- Web search
- File operations
- Task execution
- Full Agentic Loop

Architecture:
    ClaudeEnvironment
    ├── ClaudeReceptor (in) - Perceives SDK responses → emits to SystemBus
    └── ClaudeEffector (out) - Subscribes to SystemBus → sends to Claude Agent SDK

The Agentic Loop is handled by claude-agent-sdk internally.
"""

import asyncio
import json
import os
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, AsyncIterator

from .system_bus import SystemBusProducer, SystemBusConsumer, SystemBus
from .types import (
    SystemEvent,
    EventContext,
    StreamEvent,
    DriveableEvent,
    TextDeltaData,
    ToolUseStartData,
    ToolUseStopData,
    ToolResultData,
    MessageStartData,
    MessageStopData,
    ErrorReceivedData,
)

from ...utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Interfaces
# =============================================================================


class Receptor(ABC):
    """
    Receptor - Perceives external input and emits to SystemBus.

    In the Claude context:
    - Receives SDK stream events
    - Converts to DriveableEvent format
    - Emits to SystemBus
    """

    @abstractmethod
    def connect(self, producer: SystemBusProducer) -> None:
        """Connect to SystemBus producer for emitting events."""
        pass


class Effector(ABC):
    """
    Effector - Subscribes to SystemBus and sends to external system.

    In the Claude context:
    - Listens for user_message events
    - Sends to Claude SDK
    """

    @abstractmethod
    def connect(self, consumer: SystemBusConsumer) -> None:
        """Connect to SystemBus consumer for receiving events."""
        pass


class Environment(ABC):
    """
    Environment - Receptor + Effector pair.

    Represents the external system that the Agent interacts with.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Environment name."""
        pass

    @property
    @abstractmethod
    def receptor(self) -> Receptor:
        """Get receptor."""
        pass

    @property
    @abstractmethod
    def effector(self) -> Effector:
        """Get effector."""
        pass

    @abstractmethod
    def dispose(self) -> None:
        """Clean up resources."""
        pass


# =============================================================================
# Receptor Metadata
# =============================================================================


@dataclass
class ReceptorMeta:
    """Metadata passed with each SDK message for event correlation."""
    request_id: str
    context: EventContext


# =============================================================================
# Claude Receptor Implementation
# =============================================================================


class ClaudeReceptor(Receptor):
    """
    ClaudeReceptor - Perceives Claude SDK responses and emits DriveableEvents.

    Converts Claude SDK stream events to SystemEvent format.
    """

    def __init__(self):
        self._producer: Optional[SystemBusProducer] = None
        self._current_meta: Optional[ReceptorMeta] = None

        # Block context for tracking state across events
        self._current_block_type: Optional[str] = None  # "text" | "tool_use"
        self._current_block_index: int = 0
        self._current_tool_id: Optional[str] = None
        self._current_tool_name: Optional[str] = None
        self._last_stop_reason: Optional[str] = None

    def connect(self, producer: SystemBusProducer) -> None:
        """Connect to SystemBus producer."""
        self._producer = producer
        logger.debug("ClaudeReceptor connected to SystemBusProducer")

    def feed(self, sdk_event: Dict[str, Any], meta: ReceptorMeta) -> None:
        """
        Feed an SDK stream event.

        Args:
            sdk_event: Raw event from Claude SDK
            meta: Request metadata for correlation
        """
        self._current_meta = meta
        self._process_stream_event(sdk_event)

    def emit_interrupted(self, reason: str, meta: Optional[ReceptorMeta] = None) -> None:
        """Emit interrupted event."""
        event_meta = meta or self._current_meta
        self._emit_to_bus(SystemEvent(
            type="interrupted",
            timestamp=int(time.time() * 1000),
            source="environment",
            category="stream",
            intent="notification",
            data={"reason": reason},
            context=event_meta.context if event_meta else None,
            request_id=event_meta.request_id if event_meta else None,
            broadcastable=False,
        ))

    def emit_error(self, message: str, error_code: Optional[str] = None, meta: Optional[ReceptorMeta] = None) -> None:
        """Emit error_received event."""
        event_meta = meta or self._current_meta
        self._emit_to_bus(SystemEvent(
            type="error_received",
            timestamp=int(time.time() * 1000),
            source="environment",
            category="stream",
            intent="notification",
            data=ErrorReceivedData(message=message, error_code=error_code),
            context=event_meta.context if event_meta else None,
            request_id=event_meta.request_id if event_meta else None,
            broadcastable=False,
        ))

    def _process_stream_event(self, sdk_event: Dict[str, Any]) -> None:
        """Process SDK stream event and emit DriveableEvent."""
        event_type = sdk_event.get("type")
        meta = self._current_meta

        if event_type == "message_start":
            # Reset context
            self._current_block_type = None
            self._current_block_index = 0
            self._current_tool_id = None
            self._current_tool_name = None

            message = sdk_event.get("message", {})
            self._emit_to_bus(SystemEvent(
                type="message_start",
                timestamp=int(time.time() * 1000),
                source="environment",
                category="stream",
                intent="notification",
                data=MessageStartData(
                    message_id=message.get("id", ""),
                    model=message.get("model", ""),
                ),
                context=meta.context if meta else None,
                request_id=meta.request_id if meta else None,
                broadcastable=False,
            ))

        elif event_type == "content_block_start":
            content_block = sdk_event.get("content_block", {})
            block_type = content_block.get("type")
            self._current_block_index = sdk_event.get("index", 0)

            if block_type == "text":
                self._current_block_type = "text"
                self._emit_to_bus(SystemEvent(
                    type="text_content_block_start",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data={"index": self._current_block_index},
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))

            elif block_type == "tool_use":
                self._current_block_type = "tool_use"
                self._current_tool_id = content_block.get("id")
                self._current_tool_name = content_block.get("name")
                self._emit_to_bus(SystemEvent(
                    type="tool_use_content_block_start",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data=ToolUseStartData(
                        tool_call_id=self._current_tool_id or "",
                        tool_name=self._current_tool_name or "",
                    ),
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))

        elif event_type == "content_block_delta":
            delta = sdk_event.get("delta", {})
            delta_type = delta.get("type")

            if delta_type == "text_delta":
                self._emit_to_bus(SystemEvent(
                    type="text_delta",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data=TextDeltaData(text=delta.get("text", "")),
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))

            elif delta_type == "input_json_delta":
                self._emit_to_bus(SystemEvent(
                    type="input_json_delta",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data={"partial_json": delta.get("partial_json", "")},
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))

        elif event_type == "content_block_stop":
            if self._current_block_type == "tool_use":
                self._emit_to_bus(SystemEvent(
                    type="tool_use_content_block_stop",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data={
                        "tool_call_id": self._current_tool_id,
                        "tool_name": self._current_tool_name,
                    },
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))
            else:
                self._emit_to_bus(SystemEvent(
                    type="text_content_block_stop",
                    timestamp=int(time.time() * 1000),
                    source="environment",
                    category="stream",
                    intent="notification",
                    data={"index": self._current_block_index},
                    context=meta.context if meta else None,
                    request_id=meta.request_id if meta else None,
                    broadcastable=False,
                ))

            # Reset block state
            self._current_block_type = None
            self._current_tool_id = None
            self._current_tool_name = None

        elif event_type == "message_delta":
            delta = sdk_event.get("delta", {})
            if delta.get("stop_reason"):
                self._last_stop_reason = delta["stop_reason"]

        elif event_type == "message_stop":
            self._emit_to_bus(SystemEvent(
                type="message_stop",
                timestamp=int(time.time() * 1000),
                source="environment",
                category="stream",
                intent="notification",
                data=MessageStopData(
                    stop_reason=self._last_stop_reason or "end_turn",
                ),
                context=meta.context if meta else None,
                request_id=meta.request_id if meta else None,
                broadcastable=False,
            ))
            self._last_stop_reason = None

    def _emit_to_bus(self, event: SystemEvent) -> None:
        """Emit event to SystemBus."""
        if self._producer:
            self._producer.emit(event)


# =============================================================================
# Claude Effector Implementation
# =============================================================================


@dataclass
class ClaudeEffectorConfig:
    """Configuration for ClaudeEffector."""
    agent_id: str
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    cwd: Optional[str] = None
    session_id: Optional[str] = None
    resume_session_id: Optional[str] = None
    timeout: int = 30000  # ms
    mcp_servers: Optional[Dict[str, Any]] = None
    allowed_tools: Optional[List[str]] = None
    on_session_id_captured: Optional[Callable[[str], None]] = None
    cli_path: Optional[str] = None  # Path to Claude CLI (auto-detected if not set)


def _find_system_claude_cli() -> Optional[str]:
    """Find system-installed Claude CLI."""
    # Try which command first
    if cli := shutil.which("claude"):
        return cli

    # Common installation locations
    locations = [
        os.path.expanduser("~/.npm-global/bin/claude"),
        "/usr/local/bin/claude",
        os.path.expanduser("~/.local/bin/claude"),
        os.path.expanduser("~/node_modules/.bin/claude"),
        os.path.expanduser("~/.yarn/bin/claude"),
        os.path.expanduser("~/.claude/local/claude"),
    ]

    for path in locations:
        if os.path.exists(path) and os.path.isfile(path):
            return path

    return None


class ClaudeEffector(Effector):
    """
    ClaudeEffector - Listens to SystemBus and sends to Claude Agent SDK.

    Uses the official claude-agent-sdk which provides:
    - Native Claude Code capabilities (web search, file operations, etc.)
    - Full Agentic Loop handled internally by the SDK
    - Built-in tool execution via Claude CLI
    """

    def __init__(self, config: ClaudeEffectorConfig, receptor: ClaudeReceptor):
        self.config = config
        self.receptor = receptor
        self._current_task: Optional[asyncio.Task] = None
        self._current_meta: Optional[ReceptorMeta] = None
        self._tools: List[Dict[str, Any]] = []
        self._tool_executor: Optional[Callable] = None
        self._cli_path: Optional[str] = None
        self._mcp_server = None  # SDK MCP server for custom tools

        # Find CLI path
        self._cli_path = config.cli_path or _find_system_claude_cli()
        if self._cli_path:
            logger.info(f"Using Claude CLI: {self._cli_path}")
        else:
            logger.warning("System Claude CLI not found, will use SDK bundled CLI")

    def set_tools(self, tools: List[Dict[str, Any]], executor: Callable) -> None:
        """
        Set available tools and their executor.

        Creates an SDK MCP server to provide custom tools to claude-agent-sdk.
        This allows ComfyUI tools to be used alongside native Claude Code tools.

        Args:
            tools: List of tool definitions in Anthropic format
            executor: Async function to execute tools: (tool_name, tool_input) -> result
        """
        self._tools = tools
        self._tool_executor = executor

        # Note: MCP server creation is disabled for now due to SDK compatibility issues
        # The frontend will detect workflow JSON in messages and load it to canvas
        self._mcp_server = None

        logger.info(f"Configured {len(tools)} ComfyUI tools for agent")

    def _create_mcp_server(self, tools: List[Dict[str, Any]], executor: Callable):
        """
        Create an SDK MCP server for custom tools.

        Uses claude_agent_sdk.create_sdk_mcp_server to create an in-process
        MCP server that provides ComfyUI tools to the SDK.
        """
        try:
            from claude_agent_sdk import create_sdk_mcp_server, tool as sdk_tool

            # Store executor in instance for closure access
            self._stored_executor = executor

            # Convert Anthropic tool definitions to SDK tools using @tool decorator
            sdk_tools = []
            for tool_def in tools:
                tool_name = tool_def.get("name", "")
                tool_desc = tool_def.get("description", "")
                tool_schema = tool_def.get("input_schema", {})

                # Create SDK tool using decorator
                # We need to capture tool_name in closure
                def create_tool_func(name: str, exec_func: Callable):
                    @sdk_tool(name, tool_desc, tool_schema)
                    async def tool_handler(args: dict):
                        try:
                            result = await exec_func(name, args)
                            return {
                                "content": [
                                    {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}
                                ]
                            }
                        except Exception as e:
                            return {
                                "content": [
                                    {"type": "text", "text": f"Error: {str(e)}"}
                                ],
                                "isError": True
                            }
                    return tool_handler

                sdk_tools.append(create_tool_func(tool_name, executor))

            # Create MCP server
            server = create_sdk_mcp_server(
                name="comfyui",
                version="1.0.0",
                tools=sdk_tools,
            )

            return server

        except ImportError as e:
            logger.warning(f"Failed to import SDK MCP tools: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to create MCP server: {e}")
            return None

    def connect(self, consumer: SystemBusConsumer) -> None:
        """Connect to SystemBus consumer."""
        logger.debug(f"ClaudeEffector connected, agent_id={self.config.agent_id}")

        # Listen for user_message events
        consumer.on("user_message", self._handle_user_message)

        # Listen for interrupt events
        consumer.on("interrupt", self._handle_interrupt)

    def _handle_user_message(self, event: SystemEvent) -> None:
        """Handle user_message event."""
        # Filter by agent_id
        if event.context and event.context.agent_id != self.config.agent_id:
            return

        logger.debug(f"user_message received for agent {self.config.agent_id}")

        # Extract message
        message = event.data
        meta = ReceptorMeta(
            request_id=event.request_id or "",
            context=event.context or EventContext(),
        )

        # Start async query
        self._current_meta = meta
        self._current_task = asyncio.create_task(self._send(message, meta))

    def _handle_interrupt(self, event: SystemEvent) -> None:
        """Handle interrupt event."""
        # Filter by agent_id
        if event.context and event.context.agent_id != self.config.agent_id:
            return

        logger.debug(f"interrupt received for agent {self.config.agent_id}")

        # Cancel current task
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self.receptor.emit_interrupted("user_interrupt", self._current_meta)

    async def _send(self, message: Any, meta: ReceptorMeta) -> None:
        """
        Send message to Claude Agent SDK.

        Uses claude-agent-sdk which provides native Claude Code capabilities
        including web search, file operations, task execution, etc.
        """
        try:
            # Import SDK here to avoid import errors if not installed
            from claude_agent_sdk import query, ClaudeAgentOptions
            from claude_agent_sdk.types import (
                SystemMessage,
                AssistantMessage,
                ResultMessage,
                UserMessage,
                StreamEvent as SDKStreamEvent,
            )

            # Extract prompt text
            if isinstance(message, dict):
                prompt = message.get("content", "")
            elif hasattr(message, "content"):
                prompt = message.content
            else:
                prompt = str(message)

            logger.info(
                "Sending to Claude Agent SDK",
                prompt_preview=prompt[:80],
                model=self.config.model,
                agent_id=self.config.agent_id,
            )

            # Build environment variables
            env = dict(os.environ)
            if self.config.base_url:
                env["ANTHROPIC_BASE_URL"] = self.config.base_url
            if self.config.api_key:
                env["ANTHROPIC_API_KEY"] = self.config.api_key

            # Build MCP servers config
            mcp_servers = dict(self.config.mcp_servers or {})
            if self._mcp_server:
                mcp_servers["comfyui"] = self._mcp_server

            # Build SDK options
            options = ClaudeAgentOptions(
                model=self.config.model or "claude-sonnet-4-20250514",
                permission_mode="bypassPermissions",
                env=env,
                system_prompt=self.config.system_prompt,
                cwd=self.config.cwd,
                mcp_servers=mcp_servers,
                allowed_tools=self.config.allowed_tools,
                resume=self.config.resume_session_id,
                cli_path=self._cli_path,
            )

            # Emit message_start
            self.receptor.feed({
                "type": "message_start",
                "message": {
                    "id": f"msg_{meta.request_id}",
                    "model": self.config.model or "claude-sonnet-4-20250514",
                },
            }, meta)

            # Track response content
            response_text = ""
            has_content = False

            # Query SDK
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, SystemMessage):
                    logger.debug(f"SDK SystemMessage: subtype={msg.subtype}")
                    # Capture session_id if callback is set
                    if msg.subtype == "init" and self.config.on_session_id_captured:
                        data = msg.data or {}
                        session_id = data.get("session_id")
                        if session_id:
                            self.config.on_session_id_captured(session_id)

                elif isinstance(msg, AssistantMessage):
                    # Process content blocks
                    for i, block in enumerate(msg.content):
                        if hasattr(block, "text"):
                            if not has_content:
                                # Emit text block start
                                self.receptor.feed({
                                    "type": "content_block_start",
                                    "index": i,
                                    "content_block": {"type": "text"},
                                }, meta)
                                has_content = True

                            # Emit text delta
                            self.receptor.feed({
                                "type": "content_block_delta",
                                "index": i,
                                "delta": {"type": "text_delta", "text": block.text},
                            }, meta)
                            response_text += block.text

                            # Emit text block stop
                            self.receptor.feed({
                                "type": "content_block_stop",
                                "index": i,
                            }, meta)

                        elif hasattr(block, "name"):
                            # Tool use block
                            self.receptor.feed({
                                "type": "content_block_start",
                                "index": i,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": getattr(block, "id", f"tool_{i}"),
                                    "name": block.name,
                                },
                            }, meta)
                            self.receptor.feed({
                                "type": "content_block_stop",
                                "index": i,
                            }, meta)

                elif isinstance(msg, UserMessage):
                    # Tool results from SDK
                    logger.debug("SDK UserMessage (tool result)")

                elif isinstance(msg, ResultMessage):
                    logger.debug(f"SDK ResultMessage: subtype={msg.subtype}")

                elif isinstance(msg, SDKStreamEvent):
                    # Forward stream events
                    event = msg.event
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                self.receptor.feed({
                                    "type": "content_block_delta",
                                    "index": 0,
                                    "delta": {"type": "text_delta", "text": text},
                                }, meta)
                                response_text += text

            # Emit message_delta with stop reason
            self.receptor.feed({
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
            }, meta)

            # Emit message_stop
            self.receptor.feed({
                "type": "message_stop",
            }, meta)

            logger.info(
                "Claude Agent SDK query complete",
                response_length=len(response_text),
                agent_id=self.config.agent_id,
            )

        except asyncio.CancelledError:
            logger.debug("Query cancelled (user interrupt)", agent_id=self.config.agent_id)
            raise

        except Exception as e:
            logger.exception(
                "Error in Claude Agent SDK query",
                agent_id=self.config.agent_id,
                error=str(e),
            )
            self.receptor.emit_error(str(e), "sdk_error", meta)

    def clear_history(self) -> None:
        """Clear conversation history."""
        # With claude-agent-sdk, history is managed by the SDK
        pass

    def dispose(self) -> None:
        """Clean up resources."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        logger.debug("ClaudeEffector disposed")


# =============================================================================
# Claude Environment
# =============================================================================


class ClaudeEnvironment(Environment):
    """
    ClaudeEnvironment - Claude SDK Environment.

    Combines ClaudeReceptor and ClaudeEffector for full bidirectional
    communication with Claude SDK.
    """

    def __init__(self, config: ClaudeEffectorConfig):
        self._receptor = ClaudeReceptor()
        self._effector = ClaudeEffector(config, self._receptor)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def receptor(self) -> Receptor:
        return self._receptor

    @property
    def effector(self) -> Effector:
        return self._effector

    def dispose(self) -> None:
        """Clean up resources."""
        self._effector.dispose()
