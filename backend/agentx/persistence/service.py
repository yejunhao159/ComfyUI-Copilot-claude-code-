"""
AgentX Persistence Service

CRUD operations for sessions, messages, and events.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc, and_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    Base,
    AgentSessionModel,
    AgentMessageModel,
    AgentEventModel,
    MCPToolModel,
    MCPServerModel,
)
from ..runtime.types import (
    AgentSession,
    Message,
    SessionState,
    MessageRole,
    EventType,
)
from ..config import AgentConfig
from ...utils.logger import get_logger

logger = get_logger(__name__)


class PersistenceService:
    """
    Service for persisting agent sessions, messages, and events.

    Features:
    - SQLAlchemy ORM with connection pooling
    - Automatic session management
    - Type conversion between domain and persistence models
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize persistence service.

        Args:
            config: Agent configuration with database URL
        """
        self.config = config

        # Build engine kwargs (SQLite doesn't support pool_size/max_overflow)
        engine_kwargs = {"echo": config.log_level == "DEBUG"}
        if not config.database_url.startswith("sqlite"):
            engine_kwargs["pool_size"] = config.db_pool_size
            engine_kwargs["max_overflow"] = config.db_max_overflow

        self.engine = create_engine(config.database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

        # Create tables if they don't exist
        Base.metadata.create_all(bind=self.engine)
        logger.info("PersistenceService initialized", database_url=config.database_url)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # ============================================
    # Session Operations
    # ============================================

    def create_session(self, session: AgentSession) -> None:
        """
        Create a new agent session.

        Args:
            session: AgentSession domain object
        """
        db = self.get_session()
        try:
            model = AgentSessionModel(
                session_id=session.session_id,
                created_at=session.created_at,
                updated_at=session.updated_at,
                state=session.state,
                config=session.config,
                user_id=session.user_id,
                title=session.title,
            )
            db.add(model)
            db.commit()
            logger.debug("Created session", session_id=session.session_id)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error("Failed to create session", error=str(e))
            raise
        finally:
            db.close()

    def get_session_by_id(self, session_id: str) -> Optional[AgentSession]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            AgentSession or None if not found
        """
        db = self.get_session()
        try:
            model = db.query(AgentSessionModel).filter_by(session_id=session_id).first()
            if not model:
                return None
            return self._session_model_to_domain(model)
        finally:
            db.close()

    def update_session_state(self, session_id: str, state: SessionState) -> None:
        """
        Update session state.

        Args:
            session_id: Session ID
            state: New state
        """
        db = self.get_session()
        try:
            db.query(AgentSessionModel).filter_by(session_id=session_id).update(
                {"state": state, "updated_at": datetime.utcnow()}
            )
            db.commit()
            logger.debug("Updated session state", session_id=session_id, state=state.value)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error("Failed to update session state", session_id=session_id, error=str(e))
            raise
        finally:
            db.close()

    def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[AgentSession]:
        """
        List sessions with pagination.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of sessions
            offset: Offset for pagination

        Returns:
            List of AgentSession objects
        """
        db = self.get_session()
        try:
            query = db.query(AgentSessionModel)
            if user_id:
                query = query.filter_by(user_id=user_id)
            models = query.order_by(desc(AgentSessionModel.updated_at)).limit(limit).offset(offset).all()
            return [self._session_model_to_domain(m) for m in models]
        finally:
            db.close()

    # ============================================
    # Message Operations
    # ============================================

    def save_message(self, message: Message) -> None:
        """
        Save a message to the database.

        Args:
            message: Message domain object
        """
        db = self.get_session()
        try:
            # Convert tool_calls to dict format
            tool_calls_dict = None
            if message.tool_calls:
                tool_calls_dict = [tc.to_dict() for tc in message.tool_calls]

            model = AgentMessageModel(
                message_id=message.message_id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                tool_calls=tool_calls_dict,
                input_tokens=message.input_tokens,
                output_tokens=message.output_tokens,
            )
            db.add(model)
            db.commit()
            logger.debug("Saved message", message_id=message.message_id, session_id=message.session_id)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error("Failed to save message", message_id=message.message_id, error=str(e))
            raise
        finally:
            db.close()

    def get_messages(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Message]:
        """
        Get messages for a session.

        Args:
            session_id: Session ID
            limit: Optional limit (defaults to config page size)
            offset: Offset for pagination

        Returns:
            List of Message objects ordered by timestamp
        """
        db = self.get_session()
        try:
            query = db.query(AgentMessageModel).filter_by(session_id=session_id)
            query = query.order_by(AgentMessageModel.timestamp)

            if limit is None:
                limit = self.config.message_load_page_size

            models = query.limit(limit).offset(offset).all()
            return [self._message_model_to_domain(m) for m in models]
        finally:
            db.close()

    # ============================================
    # Event Operations (Optional, for debugging)
    # ============================================

    def save_event(self, session_id: str, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        Save an event to the database (if event logging is enabled).

        Args:
            session_id: Session ID
            event_type: Type of event
            data: Event data
        """
        if not self.config.enable_event_logging:
            return

        db = self.get_session()
        try:
            model = AgentEventModel(
                session_id=session_id,
                event_type=event_type,
                timestamp=datetime.utcnow(),
                data=data,
            )
            db.add(model)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error("Failed to save event", session_id=session_id, event_type=str(event_type), error=str(e))
        finally:
            db.close()

    # ============================================
    # Helper Methods
    # ============================================

    def _session_model_to_domain(self, model: AgentSessionModel) -> AgentSession:
        """Convert AgentSessionModel to AgentSession."""
        return AgentSession(
            session_id=model.session_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            state=model.state,
            config=model.config,
            user_id=model.user_id,
            title=model.title,
            messages=[],  # Load separately if needed
        )

    def _message_model_to_domain(self, model: AgentMessageModel) -> Message:
        """Convert AgentMessageModel to Message."""
        from ..runtime.types import ToolCall

        # Convert tool_calls from dict to ToolCall objects
        tool_calls = None
        if model.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=tc["arguments"],
                    result=tc.get("result"),
                    error=tc.get("error"),
                )
                for tc in model.tool_calls
            ]

        return Message(
            message_id=model.message_id,
            session_id=model.session_id,
            role=model.role,
            content=model.content,
            timestamp=model.timestamp,
            tool_calls=tool_calls,
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
        )

    def close(self) -> None:
        """Close the database engine."""
        self.engine.dispose()
        logger.info("PersistenceService closed")
