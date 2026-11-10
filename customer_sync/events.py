"""A tiny in-process event bus (the Observer / Publish-Subscribe pattern)."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, TypeVar
from uuid import uuid4

from .models import Customer

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Base class for all events. Every event gets a unique id and timestamp."""

    event_id: str = field(default_factory=lambda: str(uuid4()), kw_only=True)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), kw_only=True
    )


@dataclass(frozen=True)
class CustomerCreated(Event):
    customer: Customer


@dataclass(frozen=True)
class CustomerUpdated(Event):
    before: Customer
    after: Customer

    @property
    def changed_fields(self) -> set[str]:
        """Which fields actually changed (ignoring the timestamp)."""
        fields = ("name", "email", "phone")
        return {f for f in fields if getattr(self.before, f) != getattr(self.after, f)}


E = TypeVar("E", bound=Event)
Handler = Callable[[E], None]


class EventBus:
    """Publishers and subscribers only know about the bus, never about each other.

    That decoupling is the whole point: the repository doesn't know a GraphQL
    API exists, and the sync handler doesn't know where events come from.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        # Walk the MRO so a handler subscribed to `Event` receives every event.
        for event_type in type(event).__mro__:
            for handler in self._handlers.get(event_type, []):
                try:
                    handler(event)
                except Exception:
                    # One failing subscriber must not break the others.
                    log.exception("Handler %r failed for %r", handler, event)
