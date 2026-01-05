"""
ClaudeEnvironment - Claude SDK Integration via Receptor/Effector Pattern

Ported from @agentxjs/runtime/src/environment/

This module integrates with the official claude-agent-sdk Python package
to provide true Agentic Loop capability.

Architecture:
    ClaudeEnvironment
    ├── ClaudeReceptor (in) - Perceives Claude SDK responses → emits to SystemBus
    └── ClaudeEffector (out) - Subscribes to SystemBus → sends to Claude SDK

The key insight is that claude-agent-sdk handles the Agentic Loop internally:
    1. Gather Context (tools, previous messages)
    2. Take Action (call tools)
    3. Verify Work (analyze results)
    4. Repeat until task complete

We don't need to manually loop - the SDK does it for us!
"""

import asyncio
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
    cli_path: Optional[str] = None  # Path to Claude CLI (uses bundled if not set)


class ClaudeEffector(Effector):
    """
    ClaudeEffector - Listens to SystemBus and sends to Claude SDK.

    Uses claude-agent-sdk to handle the Agentic Loop automatically.

    Important: The SDK handles tool execution internally!
    We just need to:
    1. Listen for user_message events
    2. Pass to SDK query()
    3. Forward stream events to Receptor
    """

    def __init__(self, config: ClaudeEffectorConfig, receptor: ClaudeReceptor):
        self.config = config
        self.receptor = receptor
        self._is_initialized = False
        self._current_task: Optional[asyncio.Task] = None
        self._current_meta: Optional[ReceptorMeta] = None

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
        Send message to Claude SDK and process responses.

        This is where the magic happens - the SDK handles the Agentic Loop!

        The SDK returns different message types:
        - StreamEvent: Contains raw Claude API streaming events in `event` dict
        - AssistantMessage: Complete assistant response with content blocks
        - ResultMessage: Final result with stats (is_error, session_id, etc.)
        - UserMessage: User input echo
        - SystemMessage: System information
        """
        try:
            # Dynamic import to avoid hard dependency
            from claude_agent_sdk import (
                query,
                ClaudeAgentOptions,
                ResultMessage,
                AssistantMessage,
            )
            from claude_agent_sdk.types import StreamEvent

            # Build options
            options = ClaudeAgentOptions(
                model=self.config.model,
                system_prompt=self.config.system_prompt,
                cwd=self.config.cwd,
                permission_mode="bypassPermissions",  # Agent runs autonomously
            )

            # Add MCP servers if configured
            if self.config.mcp_servers:
                options.mcp_servers = self.config.mcp_servers

            # Add allowed tools if configured
            if self.config.allowed_tools:
                options.allowed_tools = self.config.allowed_tools

            # Resume session if available
            if self.config.resume_session_id:
                options.resume = self.config.resume_session_id

            # Extract prompt text
            if isinstance(message, dict):
                prompt = message.get("content", "")
            elif hasattr(message, "content"):
                prompt = message.content
            else:
                prompt = str(message)

            logger.info(
                "Sending to Claude SDK",
                prompt_preview=prompt[:80],
                model=self.config.model,
                agent_id=self.config.agent_id,
            )

            # Query Claude - the SDK handles the entire Agentic Loop!
            async for sdk_msg in query(prompt=prompt, options=options):
                msg_type = type(sdk_msg).__name__
                logger.debug("SDK message received", msg_type=msg_type, agent_id=self.config.agent_id)

                # Handle StreamEvent - contains raw Claude API events
                if isinstance(sdk_msg, StreamEvent):
                    # StreamEvent has an `event` dict with the raw API event
                    event_data = sdk_msg.event
                    self.receptor.feed(event_data, meta)

                    # Capture session ID
                    if sdk_msg.session_id and self.config.on_session_id_captured:
                        self.config.on_session_id_captured(sdk_msg.session_id)

                # Handle ResultMessage - final result
                elif isinstance(sdk_msg, ResultMessage):
                    logger.info(
                        "SDK query complete",
                        agent_id=self.config.agent_id,
                        is_error=sdk_msg.is_error,
                        num_turns=sdk_msg.num_turns,
                        duration_ms=sdk_msg.duration_ms,
                    )

                    if sdk_msg.is_error:
                        self.receptor.emit_error(
                            sdk_msg.result or "Unknown error",
                            "sdk_error",
                            meta
                        )

                    # Capture session ID
                    if sdk_msg.session_id and self.config.on_session_id_captured:
                        self.config.on_session_id_captured(sdk_msg.session_id)

                # Handle AssistantMessage - process content blocks for tool use info
                elif isinstance(sdk_msg, AssistantMessage):
                    # Content blocks can contain TextBlock, ToolUseBlock, etc.
                    for block in sdk_msg.content:
                        block_type = type(block).__name__
                        logger.debug(
                            "Processing content block",
                            block_type=block_type,
                            agent_id=self.config.agent_id,
                        )

        except asyncio.CancelledError:
            logger.debug("Query cancelled (user interrupt)", agent_id=self.config.agent_id)
            raise

        except ImportError:
            error_msg = "claude-agent-sdk not installed. Install with: pip install claude-agent-sdk"
            logger.error(error_msg, agent_id=self.config.agent_id)
            self.receptor.emit_error(error_msg, "missing_dependency", meta)

        except Exception as e:
            logger.exception(
                "Error in Claude SDK query",
                agent_id=self.config.agent_id,
                error=str(e),
            )
            self.receptor.emit_error(str(e), "runtime_error", meta)

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
