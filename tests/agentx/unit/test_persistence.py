"""
Unit tests for PersistenceService
"""

import pytest
import os
import tempfile
from datetime import datetime
from backend.agentx.config import AgentConfig
from backend.agentx.persistence import PersistenceService
from backend.agentx.runtime.types import AgentSession, Message, SessionState, MessageRole


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield f"sqlite:///{path}"
    os.unlink(path)


@pytest.fixture
def persistence_service(temp_db):
    """Create a PersistenceService with temp database"""
    config = AgentConfig(
        anthropic_api_key="test-key",
        database_url=temp_db,
        log_level="DEBUG",
    )
    service = PersistenceService(config)
    yield service
    service.close()


def test_create_and_get_session(persistence_service):
    """Test session creation and retrieval"""
    session = AgentSession(
        session_id="test-123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        state=SessionState.IDLE,
        config={"model": "claude-3-5-sonnet-20241022"},
        user_id="user-1",
        title="Test Session",
    )

    persistence_service.create_session(session)
    retrieved = persistence_service.get_session_by_id("test-123")

    assert retrieved is not None
    assert retrieved.session_id == "test-123"
    assert retrieved.state == SessionState.IDLE
    assert retrieved.user_id == "user-1"
    assert retrieved.title == "Test Session"


def test_update_session_state(persistence_service):
    """Test session state updates"""
    session = AgentSession(
        session_id="test-456",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        state=SessionState.IDLE,
        config={},
    )

    persistence_service.create_session(session)
    persistence_service.update_session_state("test-456", SessionState.PROCESSING)

    retrieved = persistence_service.get_session_by_id("test-456")
    assert retrieved.state == SessionState.PROCESSING


def test_save_and_get_messages(persistence_service):
    """Test message persistence"""
    # Create session first
    session = AgentSession(
        session_id="test-789",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        state=SessionState.IDLE,
        config={},
    )
    persistence_service.create_session(session)

    # Save messages
    msg1 = Message(
        message_id="msg-1",
        session_id="test-789",
        role=MessageRole.USER,
        content="Hello",
        timestamp=datetime.utcnow(),
    )
    msg2 = Message(
        message_id="msg-2",
        session_id="test-789",
        role=MessageRole.ASSISTANT,
        content="Hi there!",
        timestamp=datetime.utcnow(),
        input_tokens=10,
        output_tokens=5,
    )

    persistence_service.save_message(msg1)
    persistence_service.save_message(msg2)

    # Retrieve messages
    messages = persistence_service.get_messages("test-789")

    assert len(messages) == 2
    assert messages[0].message_id == "msg-1"
    assert messages[0].role == MessageRole.USER
    assert messages[1].message_id == "msg-2"
    assert messages[1].role == MessageRole.ASSISTANT
    assert messages[1].input_tokens == 10


def test_list_sessions(persistence_service):
    """Test session listing with pagination"""
    # Create multiple sessions
    for i in range(5):
        session = AgentSession(
            session_id=f"session-{i}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            state=SessionState.IDLE,
            config={},
            user_id="user-1",
        )
        persistence_service.create_session(session)

    # List all sessions
    sessions = persistence_service.list_sessions(user_id="user-1", limit=10)
    assert len(sessions) == 5

    # Test pagination
    page1 = persistence_service.list_sessions(user_id="user-1", limit=2, offset=0)
    page2 = persistence_service.list_sessions(user_id="user-1", limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].session_id != page2[0].session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
