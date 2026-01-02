"""
AgentX SQLAlchemy Models

Database models for sessions, messages, and events.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from ..runtime.types import SessionState, MessageRole, EventType

Base = declarative_base()


class AgentSessionModel(Base):
    """Agent session persistence model"""

    __tablename__ = "agent_sessions"

    # Primary key
    session_id = Column(String(36), primary_key=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String(255), index=True)
    title = Column(String(500))

    # State
    state = Column(Enum(SessionState), nullable=False, default=SessionState.IDLE)

    # Configuration (JSON)
    config = Column(JSON, nullable=False, default=dict)

    # Relationships
    messages = relationship(
        "AgentMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentMessageModel.timestamp",
    )
    events = relationship(
        "AgentEventModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentEventModel.timestamp",
    )

    # Indexes
    __table_args__ = (
        Index("idx_sessions_user_created", "user_id", "created_at"),
        Index("idx_sessions_state", "state"),
    )

    def __repr__(self):
        return f"<AgentSession(id={self.session_id}, state={self.state.value})>"


class AgentMessageModel(Base):
    """Agent message persistence model"""

    __tablename__ = "agent_messages"

    # Primary key
    message_id = Column(String(36), primary_key=True)

    # Foreign key
    session_id = Column(String(36), ForeignKey("agent_sessions.session_id"), nullable=False)

    # Message data
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Tool calls (JSON array)
    tool_calls = Column(JSON)

    # Token usage
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)

    # Optional: Vector embedding for semantic search
    embedding = Column(JSON)

    # Relationships
    session = relationship("AgentSessionModel", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("idx_messages_session_timestamp", "session_id", "timestamp"),
        Index("idx_messages_role", "role"),
    )

    def __repr__(self):
        return f"<AgentMessage(id={self.message_id}, role={self.role.value})>"


class AgentEventModel(Base):
    """Agent event persistence model (optional, for debugging/analytics)"""

    __tablename__ = "agent_events"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    session_id = Column(String(36), ForeignKey("agent_sessions.session_id"), nullable=False)

    # Event data
    event_type = Column(Enum(EventType), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = Column(JSON, nullable=False)

    # Relationships
    session = relationship("AgentSessionModel", back_populates="events")

    # Indexes
    __table_args__ = (
        Index("idx_events_session_type", "session_id", "event_type"),
        Index("idx_events_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<AgentEvent(id={self.id}, type={self.event_type.value})>"


class MCPToolModel(Base):
    """MCP tool metadata (for custom tools)"""

    __tablename__ = "mcp_tools"

    # Primary key
    tool_id = Column(String(36), primary_key=True)

    # Tool metadata
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    server_name = Column(String(255), nullable=False)

    # JSON Schema for parameters
    input_schema = Column(JSON, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (Index("idx_tools_server", "server_name"),)

    def __repr__(self):
        return f"<MCPTool(name={self.name}, server={self.server_name})>"


class MCPServerModel(Base):
    """MCP server configuration"""

    __tablename__ = "mcp_servers"

    # Primary key
    server_id = Column(String(36), primary_key=True)

    # Server metadata
    name = Column(String(255), nullable=False, unique=True)
    transport = Column(String(50), nullable=False)  # "stdio" or "sse"

    # Configuration (JSON)
    config = Column(JSON, nullable=False)

    # State
    enabled = Column(Integer, nullable=False, default=1)  # SQLite boolean

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MCPServer(name={self.name}, transport={self.transport})>"
