"""
SystemBus - Central Event Bus for AgentX Runtime

Ported from @agentxjs/runtime/src/internal/SystemBusImpl.ts

The SystemBus is the central nervous system of the AgentX runtime.
All components communicate through the bus using typed events.

Features:
    - Type-safe event subscription
    - Priority-based handler execution
    - Custom filters
    - One-time subscriptions
    - Producer/Consumer restricted views

Usage:
    bus = SystemBusImpl()

    # Subscribe to specific event type
    unsubscribe = bus.on("text_delta", lambda e: print(e.data))

    # Subscribe with filter
    bus.on("text_delta", handler, filter=lambda e: e.context.agent_id == "agent-1")

    # Subscribe to all events
    bus.on_any(lambda e: log(e))

    # Emit event
    bus.emit(SystemEvent(type="text_delta", ...))
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Optional, List, Dict, Any, Union
from dataclasses import dataclass

from .types import SystemEvent, EventContext

from ...utils.logger import get_logger

logger = get_logger(__name__)


# Type aliases
Unsubscribe = Callable[[], None]
EventHandler = Callable[[SystemEvent], None]
AsyncEventHandler = Callable[[SystemEvent], Any]  # Coroutine
EventFilter = Callable[[SystemEvent], bool]


@dataclass
class SubscribeOptions:
    """
    Options for event subscription.

    Attributes:
        filter: Only trigger handler for events that pass the filter
        priority: Higher numbers execute first (default: 0)
        once: Auto-unsubscribe after first trigger
    """
    filter: Optional[EventFilter] = None
    priority: int = 0
    once: bool = False


class SystemBusProducer(ABC):
    """
    Write-only view of SystemBus.

    Used to give components the ability to emit events
    without exposing subscription capabilities.
    """

    @abstractmethod
    def emit(self, event: SystemEvent) -> None:
        """Emit an event to the bus."""
        pass

    @abstractmethod
    def emit_batch(self, events: List[SystemEvent]) -> None:
        """Emit multiple events."""
        pass


class SystemBusConsumer(ABC):
    """
    Read-only view of SystemBus.

    Used to safely expose event subscription to external code
    without allowing them to emit events.
    """

    @abstractmethod
    def on(
        self,
        event_type: Union[str, List[str]],
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        """Subscribe to event type(s)."""
        pass

    @abstractmethod
    def on_any(
        self,
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        """Subscribe to all events."""
        pass

    @abstractmethod
    def once(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Unsubscribe:
        """Subscribe once (auto-unsubscribe after trigger)."""
        pass


class SystemBus(SystemBusProducer, SystemBusConsumer):
    """
    Full SystemBus interface - both producer and consumer.

    Internal use only. External components should use
    asProducer() or asConsumer() for restricted views.
    """

    @abstractmethod
    def as_producer(self) -> SystemBusProducer:
        """Get write-only view."""
        pass

    @abstractmethod
    def as_consumer(self) -> SystemBusConsumer:
        """Get read-only view."""
        pass

    @abstractmethod
    def destroy(self) -> None:
        """Clean up resources."""
        pass


@dataclass
class _Subscription:
    """Internal subscription record."""
    id: int
    event_type: Union[str, List[str], None]  # None = wildcard (*)
    handler: EventHandler
    filter: Optional[EventFilter]
    priority: int
    once: bool


class SystemBusImpl(SystemBus):
    """
    SystemBus implementation.

    Thread-safe pub/sub event bus with priority ordering.
    """

    def __init__(self):
        self._subscriptions: List[_Subscription] = []
        self._next_id = 0
        self._is_destroyed = False
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None

        # Cached restricted views
        self._producer_view: Optional[SystemBusProducer] = None
        self._consumer_view: Optional[SystemBusConsumer] = None

    def emit(self, event: SystemEvent) -> None:
        """Emit an event to the bus."""
        if self._is_destroyed:
            return
        self._dispatch(event)

    def emit_batch(self, events: List[SystemEvent]) -> None:
        """Emit multiple events."""
        for event in events:
            self.emit(event)

    def on(
        self,
        event_type: Union[str, List[str]],
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        """Subscribe to event type(s)."""
        if self._is_destroyed:
            return lambda: None

        opts = options or SubscribeOptions()
        subscription = _Subscription(
            id=self._next_id,
            event_type=event_type,
            handler=handler,
            filter=opts.filter,
            priority=opts.priority,
            once=opts.once,
        )
        self._next_id += 1
        self._subscriptions.append(subscription)
        self._sort_by_priority()

        return lambda: self._remove_subscription(subscription.id)

    def on_any(
        self,
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        """Subscribe to all events."""
        if self._is_destroyed:
            return lambda: None

        opts = options or SubscribeOptions()
        subscription = _Subscription(
            id=self._next_id,
            event_type=None,  # Wildcard
            handler=handler,
            filter=opts.filter,
            priority=opts.priority,
            once=opts.once,
        )
        self._next_id += 1
        self._subscriptions.append(subscription)
        self._sort_by_priority()

        return lambda: self._remove_subscription(subscription.id)

    def once(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Unsubscribe:
        """Subscribe once."""
        return self.on(event_type, handler, SubscribeOptions(once=True))

    def as_producer(self) -> SystemBusProducer:
        """Get write-only view."""
        if not self._producer_view:
            self._producer_view = _ProducerView(self)
        return self._producer_view

    def as_consumer(self) -> SystemBusConsumer:
        """Get read-only view."""
        if not self._consumer_view:
            self._consumer_view = _ConsumerView(self)
        return self._consumer_view

    def destroy(self) -> None:
        """Clean up resources."""
        if self._is_destroyed:
            return
        self._is_destroyed = True
        self._subscriptions.clear()
        logger.debug("SystemBus destroyed")

    def _dispatch(self, event: SystemEvent) -> None:
        """Dispatch event to matching handlers."""
        to_remove: List[int] = []

        for sub in self._subscriptions:
            # Check type match
            if not self._matches_type(sub.event_type, event.type):
                continue

            # Check filter
            if sub.filter and not sub.filter(event):
                continue

            # Call handler
            try:
                sub.handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler error: {e}",
                    extra={
                        "event_type": event.type,
                        "subscription_type": sub.event_type,
                    },
                    exc_info=True,
                )

            # Mark for removal if once
            if sub.once:
                to_remove.append(sub.id)

        # Remove one-time subscriptions
        for sub_id in to_remove:
            self._remove_subscription(sub_id)

    def _matches_type(
        self,
        subscription_type: Union[str, List[str], None],
        event_type: str,
    ) -> bool:
        """Check if subscription type matches event type."""
        if subscription_type is None:  # Wildcard
            return True
        if isinstance(subscription_type, list):
            return event_type in subscription_type
        return subscription_type == event_type

    def _sort_by_priority(self) -> None:
        """Sort subscriptions by priority (descending)."""
        self._subscriptions.sort(key=lambda s: s.priority, reverse=True)

    def _remove_subscription(self, sub_id: int) -> None:
        """Remove subscription by ID."""
        self._subscriptions = [s for s in self._subscriptions if s.id != sub_id]


class _ProducerView(SystemBusProducer):
    """Write-only view of SystemBus."""

    def __init__(self, bus: SystemBusImpl):
        self._bus = bus

    def emit(self, event: SystemEvent) -> None:
        self._bus.emit(event)

    def emit_batch(self, events: List[SystemEvent]) -> None:
        self._bus.emit_batch(events)


class _ConsumerView(SystemBusConsumer):
    """Read-only view of SystemBus."""

    def __init__(self, bus: SystemBusImpl):
        self._bus = bus

    def on(
        self,
        event_type: Union[str, List[str]],
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        return self._bus.on(event_type, handler, options)

    def on_any(
        self,
        handler: EventHandler,
        options: Optional[SubscribeOptions] = None,
    ) -> Unsubscribe:
        return self._bus.on_any(handler, options)

    def once(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Unsubscribe:
        return self._bus.once(event_type, handler)
