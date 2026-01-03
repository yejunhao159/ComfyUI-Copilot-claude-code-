"""
Unit tests for EventBus
"""

import pytest
import asyncio
from backend.agentx.runtime.event_bus import EventBus
from backend.agentx.runtime.types import StreamEvent, StateEvent, StateEventData, AgentState, EventType


@pytest.mark.asyncio
async def test_event_bus_publish_consume():
    """Test basic publish and consume"""
    bus = EventBus(maxsize=10)
    event = StreamEvent(session_id="test-session", data="Hello World")

    await bus.publish(event)
    assert bus.qsize() == 1

    # Consume one event
    async for consumed in bus.consume():
        assert consumed.type == EventType.STREAM
        assert consumed.session_id == "test-session"
        assert consumed.data == "Hello World"
        break


@pytest.mark.asyncio
async def test_event_bus_subscribe():
    """Test event subscription with handlers"""
    bus = EventBus()
    received_events = []

    async def handler(event):
        received_events.append(event)

    await bus.subscribe(EventType.STREAM, handler)
    await bus.start()

    # Publish event
    event = StreamEvent(session_id="test-session", data="Test")
    await bus.publish(event)

    # Wait for handler to process
    await asyncio.sleep(0.1)
    await bus.stop()

    assert len(received_events) == 1
    assert received_events[0].data == "Test"


@pytest.mark.asyncio
async def test_event_bus_filter_by_type():
    """Test filtering events by type"""
    bus = EventBus()

    # Publish different event types
    await bus.publish(StreamEvent(session_id="s1", data="stream"))
    await bus.publish(
        StateEvent(session_id="s1", data=StateEventData(state=AgentState.THINKING))
    )

    # Consume only STREAM events
    count = 0
    async for event in bus.consume(event_types=[EventType.STREAM]):
        assert event.type == EventType.STREAM
        count += 1
        if count >= 1:
            break

    assert count == 1


@pytest.mark.asyncio
async def test_event_bus_backpressure():
    """Test bounded queue with backpressure"""
    bus = EventBus(maxsize=2)

    # Fill queue
    await bus.publish(StreamEvent(session_id="s1", data="1"))
    await bus.publish(StreamEvent(session_id="s1", data="2"))

    assert bus.qsize() == 2

    # Next publish should timeout (queue full)
    with pytest.raises(asyncio.QueueFull):
        await bus.publish(StreamEvent(session_id="s1", data="3"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
