"""
AgentX Session Container

Session lifecycle management and conversation state tracking.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, List
from .types import AgentSession, Message, SessionState, MessageRole
from .event_bus import EventBus
from .agent_engine import AgentEngine
from ..persistence import PersistenceService
from ..config import AgentConfig
from ...utils.logger import get_logger

logger = get_logger(__name__)


class Container:
    """
    Session container for managing agent conversations.

    Features:
    - Session lifecycle (create/get/update/close)
    - Message history management
    - Automatic persistence
    - Event bus integration
    """

    def __init__(
        self,
        config: AgentConfig,
        event_bus: EventBus,
        agent_engine: AgentEngine,
        persistence: PersistenceService,
    ):
        """
        Initialize container.

        Args:
            config: Agent configuration
            event_bus: EventBus instance
            agent_engine: AgentEngine instance
            persistence: PersistenceService instance
        """
        self.config = config
        self.event_bus = event_bus
        self.agent_engine = agent_engine
        self.persistence = persistence

        # In-memory session cache
        self._sessions: Dict[str, AgentSession] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

        logger.info("Container initialized")

    async def create_session(
        self,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> AgentSession:
        """
        Create a new agent session.

        Args:
            user_id: Optional user ID
            title: Optional session title
            config: Optional session-specific configuration

        Returns:
            Created AgentSession
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = AgentSession(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            state=SessionState.IDLE,
            config=config or {},
            user_id=user_id,
            title=title,
            messages=[],
        )

        # Cache session
        self._sessions[session_id] = session
        self._locks[session_id] = asyncio.Lock()

        # Persist to database
        self.persistence.create_session(session)

        logger.info("Session created", session_id=session_id, user_id=user_id, title=title)
        return session

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Get session by ID (from cache or database).

        Args:
            session_id: Session ID

        Returns:
            AgentSession or None if not found
        """
        # Check cache first
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Load from database
        session = self.persistence.get_session_by_id(session_id)
        if session:
            # Load messages
            messages = self.persistence.get_messages(session_id)
            session.messages = messages

            # Cache session
            self._sessions[session_id] = session
            self._locks[session_id] = asyncio.Lock()

            logger.debug("Loaded session from database", session_id=session_id, message_count=len(messages))
            return session

        return None

    async def send_message(
        self,
        session_id: str,
        content: str,
        tools: Optional[List[Dict]] = None,
        system: Optional[str] = None,
    ) -> Message:
        """
        Send a user message and get assistant response.

        Args:
            session_id: Session ID
            content: User message content
            tools: Optional tool definitions
            system: Optional system prompt

        Returns:
            Assistant response message

        Raises:
            ValueError: If session not found or in invalid state
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Acquire session lock to prevent concurrent modifications
        async with self._locks[session_id]:
            # Check state
            if session.state == SessionState.CLOSED:
                raise ValueError(f"Session is closed: {session_id}")

            if session.state == SessionState.PROCESSING:
                raise ValueError(f"Session is already processing: {session_id}")

            # Update state to PROCESSING
            session.state = SessionState.PROCESSING
            session.updated_at = datetime.utcnow()
            self.persistence.update_session_state(session_id, SessionState.PROCESSING)

            try:
                # Create user message
                user_message = Message(
                    message_id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=MessageRole.USER,
                    content=content,
                    timestamp=datetime.utcnow(),
                )

                # Add to session and persist
                session.messages.append(user_message)
                self.persistence.save_message(user_message)

                # Generate response
                response = await self.agent_engine.generate(
                    session_id=session_id,
                    messages=session.messages,
                    tools=tools,
                    system=system,
                )

                # Add response to session and persist
                session.messages.append(response)
                self.persistence.save_message(response)

                # Update state
                if response.tool_calls:
                    session.state = SessionState.WAITING_FOR_TOOL
                else:
                    session.state = SessionState.IDLE

                session.updated_at = datetime.utcnow()
                self.persistence.update_session_state(session_id, session.state)

                logger.info(
                    "Message processed",
                    session_id=session_id,
                    has_tool_calls=bool(response.tool_calls),
                    tool_count=len(response.tool_calls) if response.tool_calls else 0,
                    state=session.state.value
                )
                return response

            except Exception as e:
                # Update state to ERROR
                session.state = SessionState.ERROR
                session.updated_at = datetime.utcnow()
                self.persistence.update_session_state(session_id, SessionState.ERROR)
                logger.exception("Error processing message", session_id=session_id)
                raise

    async def submit_tool_results(
        self,
        session_id: str,
        tool_results: List[Dict],
    ) -> Message:
        """
        Submit all tool execution results at once and continue generation.

        Args:
            session_id: Session ID
            tool_results: List of {"tool_call_id": str, "result": dict}

        Returns:
            Assistant response message
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._locks[session_id]:
            if session.state != SessionState.WAITING_FOR_TOOL:
                raise ValueError(f"Session not waiting for tool: {session_id}")

            # Find the assistant message with tool calls
            last_assistant_msg = None
            for msg in reversed(session.messages):
                if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
                    last_assistant_msg = msg
                    break

            if not last_assistant_msg:
                raise ValueError("No pending tool call found")

            # Update all tool call results
            result_map = {tr["tool_call_id"]: tr["result"] for tr in tool_results}
            for tc in last_assistant_msg.tool_calls:
                if tc.id in result_map:
                    tc.result = result_map[tc.id]

            # Create a single user message with ALL tool results
            from .types import ToolCall
            tool_calls_with_results = []
            for tc in last_assistant_msg.tool_calls:
                if tc.result is not None:
                    tool_calls_with_results.append(ToolCall(
                        id=tc.id,
                        name=tc.name,
                        arguments=tc.arguments,
                        result=tc.result,
                    ))

            tool_result_message = Message(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role=MessageRole.USER,
                content="",  # Tool results are in tool_calls
                timestamp=datetime.utcnow(),
                tool_calls=tool_calls_with_results,
            )

            session.messages.append(tool_result_message)
            self.persistence.save_message(tool_result_message)

            # Update state to PROCESSING
            session.state = SessionState.PROCESSING
            self.persistence.update_session_state(session_id, SessionState.PROCESSING)

            # Continue generation
            response = await self.agent_engine.generate(
                session_id=session_id,
                messages=session.messages,
            )

            # Add response to session
            session.messages.append(response)
            self.persistence.save_message(response)

            # Update state - check if more tool calls needed
            if response.tool_calls:
                session.state = SessionState.WAITING_FOR_TOOL
            else:
                session.state = SessionState.IDLE
            session.updated_at = datetime.utcnow()
            self.persistence.update_session_state(session_id, session.state)

            return response

    async def close_session(self, session_id: str) -> None:
        """
        Close a session.

        Args:
            session_id: Session ID
        """
        session = await self.get_session(session_id)
        if not session:
            return

        async with self._locks[session_id]:
            session.state = SessionState.CLOSED
            session.updated_at = datetime.utcnow()
            self.persistence.update_session_state(session_id, SessionState.CLOSED)

            # Remove from cache
            self._sessions.pop(session_id, None)
            self._locks.pop(session_id, None)

            logger.info("Session closed", session_id=session_id)

    async def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 50
    ) -> List[AgentSession]:
        """
        List sessions for a user.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of sessions

        Returns:
            List of AgentSession objects
        """
        return self.persistence.list_sessions(user_id=user_id, limit=limit)
