"""
ClaudeEnvironment - Anthropic SDK Integration via Receptor/Effector Pattern

Ported from @agentxjs/runtime/src/environment/

This module integrates with the official anthropic Python SDK
to provide Agentic Loop capability with tool execution.

Architecture:
    ClaudeEnvironment
    ├── ClaudeReceptor (in) - Perceives API responses → emits to SystemBus
    └── ClaudeEffector (out) - Subscribes to SystemBus → sends to Anthropic API

The Agentic Loop is implemented manually:
    1. Send message to Claude
    2. If Claude wants to use tools → execute tools → send results back
    3. Repeat until Claude returns end_turn (no more tool calls)
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, AsyncIterator

import anthropic

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
    ClaudeEffector - Listens to SystemBus and sends to Anthropic API.

    Uses the anthropic SDK directly with manual Agentic Loop implementation.

    The Agentic Loop:
    1. Send message to Claude with available tools
    2. If Claude wants to use tools → execute tools → send results back
    3. Repeat until Claude returns end_turn (no more tool calls)
    """

    # Maximum number of agentic loop iterations to prevent infinite loops
    MAX_ITERATIONS = 20

    def __init__(self, config: ClaudeEffectorConfig, receptor: ClaudeReceptor):
        self.config = config
        self.receptor = receptor
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._current_task: Optional[asyncio.Task] = None
        self._current_meta: Optional[ReceptorMeta] = None
        self._conversation_history: List[Dict[str, Any]] = []
        self._tools: List[Dict[str, Any]] = []
        self._tool_executor: Optional[Callable] = None

    def set_tools(self, tools: List[Dict[str, Any]], executor: Callable) -> None:
        """
        Set available tools and their executor.

        Args:
            tools: List of tool definitions in Anthropic format
            executor: Async function to execute tools: (tool_name, tool_input) -> result
        """
        self._tools = tools
        self._tool_executor = executor
        logger.debug(f"Tools configured: {[t.get('name') for t in tools]}")

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Get or create Anthropic client."""
        if not self._client:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout / 1000,  # Convert ms to seconds
            )
        return self._client

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
        Send message to Anthropic API and implement Agentic Loop.

        This implements the full agentic loop:
        1. Send user message to Claude
        2. Stream the response
        3. If tool_use blocks are present, execute tools and continue
        4. Repeat until end_turn
        """
        try:
            client = self._get_client()

            # Extract prompt text
            if isinstance(message, dict):
                prompt = message.get("content", "")
            elif hasattr(message, "content"):
                prompt = message.content
            else:
                prompt = str(message)

            # Add user message to history
            self._conversation_history.append({
                "role": "user",
                "content": prompt,
            })

            logger.info(
                "Sending to Anthropic API",
                prompt_preview=prompt[:80],
                model=self.config.model,
                agent_id=self.config.agent_id,
            )

            # Agentic Loop
            iteration = 0
            while iteration < self.MAX_ITERATIONS:
                iteration += 1
                logger.debug(f"Agentic loop iteration {iteration}", agent_id=self.config.agent_id)

                # Build request parameters
                params = {
                    "model": self.config.model or "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": self._conversation_history,
                }

                # Add system prompt if configured
                if self.config.system_prompt:
                    params["system"] = self.config.system_prompt

                # Add tools if configured
                if self._tools:
                    params["tools"] = self._tools

                # Stream the response
                tool_use_blocks = []
                assistant_content = []

                async with client.messages.stream(**params) as stream:
                    async for event in stream:
                        # Convert to dict format for receptor
                        event_dict = self._event_to_dict(event)
                        if event_dict:
                            self.receptor.feed(event_dict, meta)

                        # Track tool use blocks
                        if event.type == "content_block_start":
                            if hasattr(event, "content_block") and event.content_block.type == "tool_use":
                                tool_use_blocks.append({
                                    "type": "tool_use",
                                    "id": event.content_block.id,
                                    "name": event.content_block.name,
                                    "input": {},
                                })

                    # Get final message
                    final_message = await stream.get_final_message()

                # Process final message content
                for block in final_message.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        # Update tool_use_blocks with actual input
                        for tb in tool_use_blocks:
                            if tb["id"] == block.id:
                                tb["input"] = block.input

                # Add assistant message to history
                self._conversation_history.append({
                    "role": "assistant",
                    "content": assistant_content,
                })

                # Check stop reason
                if final_message.stop_reason == "end_turn":
                    logger.info(
                        "Agentic loop complete (end_turn)",
                        iterations=iteration,
                        agent_id=self.config.agent_id,
                    )
                    break

                elif final_message.stop_reason == "tool_use":
                    # Execute tools and continue loop
                    if not self._tool_executor:
                        logger.warning("Tool use requested but no executor configured")
                        break

                    tool_results = []
                    for block in final_message.content:
                        if block.type == "tool_use":
                            logger.info(
                                f"Executing tool: {block.name}",
                                tool_id=block.id,
                                agent_id=self.config.agent_id,
                            )

                            try:
                                result = await self._tool_executor(block.name, block.input)
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result) if not isinstance(result, str) else result,
                                })

                                # Emit tool result event
                                self.receptor.feed({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "tool_name": block.name,
                                    "result": result,
                                }, meta)

                            except Exception as e:
                                logger.exception(f"Tool execution failed: {block.name}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"Error: {str(e)}",
                                    "is_error": True,
                                })

                    # Add tool results to history
                    self._conversation_history.append({
                        "role": "user",
                        "content": tool_results,
                    })

                else:
                    # Unknown stop reason, exit loop
                    logger.warning(
                        f"Unknown stop reason: {final_message.stop_reason}",
                        agent_id=self.config.agent_id,
                    )
                    break

            if iteration >= self.MAX_ITERATIONS:
                logger.warning(
                    f"Agentic loop reached max iterations ({self.MAX_ITERATIONS})",
                    agent_id=self.config.agent_id,
                )

        except asyncio.CancelledError:
            logger.debug("Query cancelled (user interrupt)", agent_id=self.config.agent_id)
            raise

        except anthropic.APIError as e:
            logger.exception(
                "Anthropic API error",
                agent_id=self.config.agent_id,
                error=str(e),
            )
            self.receptor.emit_error(str(e), "api_error", meta)

        except Exception as e:
            logger.exception(
                "Error in Anthropic API query",
                agent_id=self.config.agent_id,
                error=str(e),
            )
            self.receptor.emit_error(str(e), "runtime_error", meta)

    def _event_to_dict(self, event: Any) -> Optional[Dict[str, Any]]:
        """Convert anthropic stream event to dict format for receptor."""
        event_type = event.type

        if event_type == "message_start":
            return {
                "type": "message_start",
                "message": {
                    "id": event.message.id if hasattr(event, "message") else "",
                    "model": event.message.model if hasattr(event, "message") else "",
                },
            }

        elif event_type == "content_block_start":
            block = event.content_block
            return {
                "type": "content_block_start",
                "index": event.index,
                "content_block": {
                    "type": block.type,
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                },
            }

        elif event_type == "content_block_delta":
            delta = event.delta
            delta_dict = {"type": delta.type}
            if delta.type == "text_delta":
                delta_dict["text"] = delta.text
            elif delta.type == "input_json_delta":
                delta_dict["partial_json"] = delta.partial_json
            return {
                "type": "content_block_delta",
                "index": event.index,
                "delta": delta_dict,
            }

        elif event_type == "content_block_stop":
            return {
                "type": "content_block_stop",
                "index": event.index,
            }

        elif event_type == "message_delta":
            return {
                "type": "message_delta",
                "delta": {
                    "stop_reason": event.delta.stop_reason if hasattr(event.delta, "stop_reason") else None,
                },
            }

        elif event_type == "message_stop":
            return {
                "type": "message_stop",
            }

        return None

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history = []

    def dispose(self) -> None:
        """Clean up resources."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        if self._client:
            # Note: AsyncAnthropic doesn't have explicit close
            self._client = None
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
