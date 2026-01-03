"""
AgentX Event Bus Implementation

Pub/Sub event system with bounded queue and backpressure handling.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Callable, AsyncIterator, Optional, Set
from .types import AgentEvent, EventType

logger = logging.getLogger(__name__)


class EventBus:
    """
    Event bus for publishing and consuming agent events.

    Features:
    - Bounded queue with configurable size
    - Backpressure handling via queue blocking
    - Type-based event filtering
    - Multiple subscribers per event type
    - Session-based event filtering
    """

    def __init__(self, maxsize: int = 1000):
        """
        Initialize event bus.

        Args:
            maxsize: Maximum queue size (default: 1000)
        """
        self._queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._session_subscribers: Dict[str, Set[EventType]] = defaultdict(set)
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None

    async def publish(self, event: AgentEvent) -> None:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish

        Raises:
            asyncio.QueueFull: If queue is full and timeout expires
        """
        try:
            # Put with timeout to avoid indefinite blocking
            await asyncio.wait_for(self._queue.put(event), timeout=5.0)
            logger.debug(f"Published event: {event.type.value} for session {event.session_id}")
        except asyncio.TimeoutError:
            logger.error(f"Event queue full, dropping event: {event.type.value}")
            raise asyncio.QueueFull("Event queue is full")

    async def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[AgentEvent], None],
        session_id: Optional[str] = None
    ) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of events to subscribe to
            handler: Async callback function to handle events
            session_id: Optional session ID filter
        """
        self._subscribers[event_type].append(handler)
        if session_id:
            self._session_subscribers[session_id].add(event_type)
        logger.debug(f"Subscribed to {event_type.value} events")

    async def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[AgentEvent], None]
    ) -> None:
        """
        Unsubscribe from events.

        Args:
            event_type: Event type to unsubscribe from
            handler: Handler to remove
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed from {event_type.value} events")

    async def consume(
        self,
        event_types: Optional[List[EventType]] = None,
        session_id: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """
        Consume events from the bus.

        Args:
            event_types: Optional filter for event types
            session_id: Optional filter for session ID

        Yields:
            Matching events
        """
        while True:
            event = await self._queue.get()

            # Apply filters
            if event_types and event.type not in event_types:
                continue
            if session_id and event.session_id != session_id:
                continue

            yield event
            self._queue.task_done()

    async def start(self) -> None:
        """Start the event bus consumer."""
        if self._running:
            logger.warning("EventBus already running")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the event bus consumer."""
        if not self._running:
            return

        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def _consume_loop(self) -> None:
        """Internal consumer loop that dispatches events to subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Dispatch to subscribers
                handlers = self._subscribers.get(event.type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}", exc_info=True)

                self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in event consumer loop: {e}", exc_info=True)

    def qsize(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()

    def is_running(self) -> bool:
        """Check if event bus is running."""
        return self._running

    async def wait_empty(self) -> None:
        """Wait until all events are processed."""
        await self._queue.join()
