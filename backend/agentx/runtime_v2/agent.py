"""
RuntimeAgent - Complete Runtime Agent Entity

Ported from @agentxjs/runtime/src/internal/RuntimeAgent.ts

RuntimeAgent is the complete runtime entity that combines:
    - Engine: Event processing (MealyMachine state transitions)
    - Environment: Claude SDK integration (Receptor + Effector)
    - Session: Conversation history
    - Interactor: User input handling

Architecture:
    ┌───────────────────────────────────────────────────────────────┐
    │                        RuntimeAgent                           │
    ├───────────────────────────────────────────────────────────────┤
    │                                                               │
    │   AgentInteractor (in)              BusDriver (out)          │
    │       │                                  │                    │
    │       │ emit user_message                │ listen DriveableEvent
    │       ▼                                  ▼                    │
    │   SystemBus ─────────────────────────────────────────        │
    │       │                                  │                    │
    │       ▼                                  │                    │
    │   ClaudeEffector                         │                    │
    │       │                                  │                    │
    │       ▼                                  │                    │
    │   Claude SDK (Agentic Loop)              │                    │
    │       │                                  │                    │
    │       ▼                                  │                    │
    │   ClaudeReceptor ────────────────────────┘                   │
    │                                          │                    │
    │                                          ▼                    │
    │                               AgentEngine.handleStreamEvent() │
    │                                          │                    │
    │                                          ▼                    │
    │                               BusPresenter (persist + emit)   │
    │                                                               │
    └───────────────────────────────────────────────────────────────┘
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable

from .system_bus import SystemBus, SystemBusProducer, SystemBusConsumer
from .types import (
    SystemEvent,
    EventContext,
    StreamEvent,
    AgentState,
    AgentLifecycle,
    Message,
    MessageRole,
    AgentSession,
    SessionState,
    StateEvent,
    StateEventData,
)
from .environment import ClaudeEnvironment, ClaudeEffectorConfig

from ...utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Agent Configuration
# =============================================================================


@dataclass
class AgentConfig:
    """Agent configuration."""
    agent_id: str
    container_id: str
    session_id: str

    # LLM Configuration
    api_key: str
    base_url: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    system_prompt: Optional[str] = None

    # Runtime Configuration
    cwd: Optional[str] = None
    timeout: int = 30000  # ms

    # MCP Configuration
    mcp_servers: Optional[Dict[str, Any]] = None
    allowed_tools: Optional[List[str]] = None

    # Session Resume
    resume_session_id: Optional[str] = None


# =============================================================================
# Agent Interactor (Input Handling)
# =============================================================================


class AgentInteractor:
    """
    AgentInteractor - Handles user input (the "in" side).

    Responsibilities:
    - Build UserMessage from user input
    - Persist message to session
    - Emit user_message to SystemBus
    """

    def __init__(
        self,
        producer: SystemBusProducer,
        session: AgentSession,
        context: EventContext,
    ):
        self._producer = producer
        self._session = session
        self._context = context

    async def receive(self, content: str, request_id: str) -> None:
        """
        Receive user input.

        Args:
            content: User message content
            request_id: Request ID for correlation
        """
        from datetime import datetime

        # Create user message
        message = Message(
            message_id=str(uuid.uuid4()),
            session_id=self._session.session_id,
            role=MessageRole.USER,
            content=content,
            timestamp=datetime.utcnow(),
        )

        # Add to session
        self._session.messages.append(message)

        # Emit to bus - this triggers ClaudeEffector
        self._producer.emit(SystemEvent(
            type="user_message",
            timestamp=int(time.time() * 1000),
            source="agent",
            category="message",
            intent="notification",
            data=message,
            context=self._context,
            request_id=request_id,
        ))

        logger.debug(f"user_message emitted: {content[:50]}...")

    def interrupt(self, request_id: Optional[str] = None) -> None:
        """Send interrupt signal."""
        self._producer.emit(SystemEvent(
            type="interrupt",
            timestamp=int(time.time() * 1000),
            source="agent",
            category="lifecycle",
            intent="request",
            data={},
            context=self._context,
            request_id=request_id,
        ))


# =============================================================================
# Bus Driver (Output Handling)
# =============================================================================


class BusDriver:
    """
    BusDriver - Listens to DriveableEvents (the "out" side).

    Responsibilities:
    - Subscribe to DriveableEvents on SystemBus
    - Filter by agent_id
    - Convert to StreamEvent
    - Forward to AgentEngine
    """

    # DriveableEvent types
    DRIVEABLE_TYPES = [
        "message_start",
        "message_delta",
        "message_stop",
        "text_content_block_start",
        "text_delta",
        "text_content_block_stop",
        "tool_use_content_block_start",
        "input_json_delta",
        "tool_use_content_block_stop",
        "tool_result",
        "interrupted",
        "error_received",
    ]

    def __init__(
        self,
        consumer: SystemBusConsumer,
        agent_id: str,
        on_stream_event: Callable[[StreamEvent], None],
        on_stream_complete: Optional[Callable[[str], None]] = None,
    ):
        self._agent_id = agent_id
        self._on_stream_event = on_stream_event
        self._on_stream_complete = on_stream_complete

        # Subscribe to all events
        self._unsubscribe = consumer.on_any(self._handle_event)
        logger.debug(f"BusDriver subscribed for agent {agent_id}")

    def _handle_event(self, event: SystemEvent) -> None:
        """Handle incoming event."""
        # Check if it's a DriveableEvent for this agent
        if not self._is_driveable_for_agent(event):
            return

        logger.debug(f"BusDriver received: {event.type}")

        # Convert to StreamEvent
        stream_event = self._to_stream_event(event)
        self._on_stream_event(stream_event)

        # Notify completion
        if event.type == "message_stop":
            if self._on_stream_complete:
                self._on_stream_complete("message_stop")
        elif event.type == "interrupted":
            if self._on_stream_complete:
                self._on_stream_complete("interrupted")

    def _is_driveable_for_agent(self, event: SystemEvent) -> bool:
        """Check if event is a DriveableEvent for this agent."""
        # Must be from environment
        if event.source != "environment":
            return False

        # Must be a driveable type
        if event.type not in self.DRIVEABLE_TYPES:
            return False

        # Must have context with matching agent_id
        # Events without context are rejected to prevent cross-agent event leakage
        if not event.context:
            logger.warning(
                f"Rejecting event without context: {event.type}",
                agent_id=self._agent_id,
            )
            return False

        if event.context.agent_id != self._agent_id:
            return False

        return True

    def _to_stream_event(self, event: SystemEvent) -> StreamEvent:
        """Convert SystemEvent to lightweight StreamEvent."""
        data = {}

        if event.type == "text_delta":
            if hasattr(event.data, "text"):
                data["text"] = event.data.text
            elif isinstance(event.data, dict):
                data["text"] = event.data.get("text", "")

        elif event.type == "tool_use_content_block_start":
            if hasattr(event.data, "tool_call_id"):
                data["tool_call_id"] = event.data.tool_call_id
                data["tool_name"] = event.data.tool_name
            elif isinstance(event.data, dict):
                data["tool_call_id"] = event.data.get("tool_call_id", "")
                data["tool_name"] = event.data.get("tool_name", "")

        elif event.type == "message_stop":
            if hasattr(event.data, "stop_reason"):
                data["stop_reason"] = event.data.stop_reason
            elif isinstance(event.data, dict):
                data["stop_reason"] = event.data.get("stop_reason", "end_turn")

        elif event.type == "error_received":
            if hasattr(event.data, "message"):
                data["message"] = event.data.message
                data["error_code"] = event.data.error_code
            elif isinstance(event.data, dict):
                data["message"] = event.data.get("message", "")
                data["error_code"] = event.data.get("error_code")

        return StreamEvent(
            type=event.type,
            timestamp=event.timestamp,
            data=data,
        )

    def dispose(self) -> None:
        """Stop listening."""
        self._unsubscribe()
        logger.debug(f"BusDriver disposed for agent {self._agent_id}")


# =============================================================================
# Bus Presenter (Output & Persistence)
# =============================================================================


class BusPresenter:
    """
    BusPresenter - Forwards processed events to SystemBus.

    Responsibilities:
    - Receive processed events from AgentEngine
    - Convert to SystemEvent with full context
    - Emit to SystemBus for clients
    - Persist messages to session
    """

    def __init__(
        self,
        producer: SystemBusProducer,
        session: AgentSession,
        context: EventContext,
    ):
        self._producer = producer
        self._session = session
        self._context = context

    def present(self, event_type: str, data: Any) -> None:
        """Present an event to the bus."""
        category = self._get_category(event_type)

        # Build SystemEvent
        system_event = SystemEvent(
            type=event_type,
            timestamp=int(time.time() * 1000),
            source="agent",
            category=category,
            intent="notification",
            data=data,
            context=self._context,
            broadcastable=True,  # Send to clients
        )

        self._producer.emit(system_event)

        # Persist message events
        if category == "message" and isinstance(data, Message):
            self._session.messages.append(data)

    def _get_category(self, event_type: str) -> str:
        """Get event category from type."""
        if event_type in ["user_message", "assistant_message", "tool_call_message", "tool_result_message", "error_message"]:
            return "message"
        if event_type in ["turn_request", "turn_response"]:
            return "turn"
        if event_type.endswith("_delta") or event_type.endswith("_start") or event_type.endswith("_stop"):
            return "stream"
        return "state"


# =============================================================================
# Runtime Agent
# =============================================================================


class RuntimeAgent:
    """
    RuntimeAgent - Complete Runtime Agent Entity.

    Combines all components for a fully functional agent with
    true Agentic Loop capability via claude-agent-sdk.
    """

    def __init__(
        self,
        config: AgentConfig,
        bus: SystemBus,
        session: AgentSession,
    ):
        self.agent_id = config.agent_id
        self.container_id = config.container_id
        self.session_id = config.session_id
        self.created_at = int(time.time() * 1000)

        self._config = config
        self._bus = bus
        self._session = session
        self._lifecycle = AgentLifecycle.INITIALIZING
        self._state = AgentState.IDLE

        # Build context
        self._context = EventContext(
            container_id=config.container_id,
            agent_id=config.agent_id,
            session_id=config.session_id,
        )

        # Create components
        self._producer = bus.as_producer()
        self._consumer = bus.as_consumer()

        # Create environment (Claude SDK integration)
        env_config = ClaudeEffectorConfig(
            agent_id=config.agent_id,
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            system_prompt=config.system_prompt,
            cwd=config.cwd,
            timeout=config.timeout,
            mcp_servers=config.mcp_servers,
            allowed_tools=config.allowed_tools,
            resume_session_id=config.resume_session_id,
        )
        self._environment = ClaudeEnvironment(env_config)

        # Connect environment to bus
        self._environment.receptor.connect(self._producer)
        self._environment.effector.connect(self._consumer)

        # Create interactor (input handling)
        self._interactor = AgentInteractor(self._producer, session, self._context)

        # Create presenter (output handling)
        self._presenter = BusPresenter(self._producer, session, self._context)

        # Create driver (event forwarding)
        self._driver = BusDriver(
            self._consumer,
            config.agent_id,
            on_stream_event=self._handle_stream_event,
            on_stream_complete=self._handle_stream_complete,
        )

        self._lifecycle = AgentLifecycle.RUNNING
        logger.info(
            "RuntimeAgent created",
            agent_id=config.agent_id,
            container_id=config.container_id,
            session_id=config.session_id,
            model=config.model,
        )

    @property
    def lifecycle(self) -> AgentLifecycle:
        """Get current lifecycle state."""
        return self._lifecycle

    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state

    @property
    def session(self) -> AgentSession:
        """Get session."""
        return self._session

    async def receive(self, content: str, request_id: Optional[str] = None) -> None:
        """
        Send a message to the agent.

        This is the main entry point for user interaction.
        The message will be processed through the full Agentic Loop.

        Args:
            content: User message content
            request_id: Optional request ID for correlation
        """
        if self._lifecycle != AgentLifecycle.RUNNING:
            raise RuntimeError(f"Cannot send message to {self._lifecycle.value} agent")

        # Update state
        self._state = AgentState.THINKING
        self._emit_state_change()

        # Forward to interactor - this triggers the entire Agentic Loop
        await self._interactor.receive(
            content,
            request_id or f"req_{uuid.uuid4().hex[:8]}",
        )

    def interrupt(self, request_id: Optional[str] = None) -> None:
        """Interrupt current operation."""
        logger.debug(f"Interrupting agent {self.agent_id}")
        self._interactor.interrupt(request_id)

    async def stop(self) -> None:
        """Stop the agent (preserves session)."""
        if self._lifecycle == AgentLifecycle.DESTROYED:
            raise RuntimeError("Cannot stop destroyed agent")
        self._lifecycle = AgentLifecycle.STOPPED
        logger.info("Agent stopped", agent_id=self.agent_id)

    async def resume(self) -> None:
        """Resume a stopped agent."""
        if self._lifecycle == AgentLifecycle.DESTROYED:
            raise RuntimeError("Cannot resume destroyed agent")
        self._lifecycle = AgentLifecycle.RUNNING
        logger.info("Agent resumed", agent_id=self.agent_id)

    async def destroy(self) -> None:
        """Destroy the agent (cleanup everything)."""
        if self._lifecycle != AgentLifecycle.DESTROYED:
            self._driver.dispose()
            self._environment.dispose()
            self._lifecycle = AgentLifecycle.DESTROYED
            logger.info("Agent destroyed", agent_id=self.agent_id)

    def _handle_stream_event(self, event: StreamEvent) -> None:
        """Handle stream event from BusDriver."""
        logger.debug(f"Stream event: {event.type}")

        # Update state based on event
        if event.type == "message_start":
            self._state = AgentState.RESPONDING
            self._emit_state_change()

        elif event.type == "tool_use_content_block_start":
            self._state = AgentState.CALLING_TOOL
            self._emit_state_change()

        elif event.type == "message_stop":
            self._state = AgentState.DONE
            self._emit_state_change()

        elif event.type == "error_received":
            self._state = AgentState.ERROR
            self._emit_state_change()

        # Forward to presenter for client broadcast
        self._presenter.present(event.type, event.data)

    def _handle_stream_complete(self, reason: str) -> None:
        """Handle stream completion."""
        logger.debug(f"Stream complete: {reason}")
        self._state = AgentState.IDLE

    def _emit_state_change(self) -> None:
        """Emit state change event."""
        self._producer.emit(SystemEvent(
            type="state_change",
            timestamp=int(time.time() * 1000),
            source="agent",
            category="state",
            intent="notification",
            data=StateEventData(state=self._state),
            context=self._context,
            broadcastable=True,
        ))
