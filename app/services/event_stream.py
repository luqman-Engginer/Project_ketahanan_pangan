"""In-memory Server-Sent Events broadcaster.

The broadcaster lives inside the single gunicorn worker process (gevent worker,
1 worker) and therefore keeps every connected client in the same memory space.
No Redis / message broker is required.

Each connection owns its own queue (``gevent.queue.Queue`` when gevent is
available, otherwise the standard library queue) so that a slow client can never
block the publishers.
"""
from __future__ import annotations

import json
import queue as _queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

try:  # pragma: no cover - gevent only exists in the production image
    from gevent.queue import Queue as EventQueue

    QUEUE_BACKEND = "gevent"
except ImportError:  # pragma: no cover - local development fallback
    from queue import Queue as EventQueue  # type: ignore[assignment]

    QUEUE_BACKEND = "stdlib"

# Event types streamed to the browser (PRD section 4, point 6).
EVENT_SURPLUS_NEW = "surplus_new"
EVENT_CLAIM_UPDATE = "claim_update"
EVENT_EXPIRY_ALERT = "expiry_alert"
EVENT_KPI_UPDATE = "kpi_update"

EVENT_TYPES: tuple[str, ...] = (
    EVENT_SURPLUS_NEW,
    EVENT_CLAIM_UPDATE,
    EVENT_EXPIRY_ALERT,
    EVENT_KPI_UPDATE,
)

#: Heartbeat (comment frame) is flushed every N seconds to keep proxies alive.
HEARTBEAT_INTERVAL = 25
#: Browser reconnect delay advertised through the ``retry`` field (milliseconds).
RECONNECT_DELAY_MS = 5000
#: Maximum number of buffered events per connection before the oldest is dropped.
MAX_QUEUE_SIZE = 100

HEARTBEAT_FRAME = ": heartbeat\n\n"


@dataclass
class Event:
    """A single event ready to be streamed to the browser."""

    id: int
    type: str
    data: dict[str, Any]
    target_user_ids: Optional[frozenset[int]] = None
    user_payloads: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass
class Subscriber:
    """A connected SSE client with its own queue and identity."""

    user_id: int
    role: str
    org_id: Optional[int]
    queue: Any
    connected_at: float


class EventBroadcaster:
    """Fan-out broadcaster keeping one queue per connected SSE client."""

    def __init__(self, max_queue_size: int = MAX_QUEUE_SIZE) -> None:
        """Create an empty broadcaster.

        Args:
            max_queue_size: Maximum buffered events per connection.
        """
        self._subscribers: dict[int, Subscriber] = {}
        self._lock = threading.Lock()
        self._sequence = 0
        self._max_queue_size = max_queue_size

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def subscribe(self, user_id: int, role: str, org_id: Optional[int]) -> Subscriber:
        """Register a new SSE connection and return its subscriber handle.

        Args:
            user_id: Primary key of the authenticated user.
            role: Role of the authenticated user.
            org_id: Organization id bound to the user, if any.

        Returns:
            The subscriber handle owning a dedicated queue.
        """
        subscriber = Subscriber(
            user_id=user_id,
            role=role,
            org_id=org_id,
            queue=EventQueue(maxsize=self._max_queue_size),
            connected_at=time.monotonic(),
        )
        with self._lock:
            self._subscribers[id(subscriber)] = subscriber
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a subscriber and release its queue.

        Args:
            subscriber: Handle returned by :meth:`subscribe`.
        """
        with self._lock:
            self._subscribers.pop(id(subscriber), None)

    def subscriber_count(self) -> int:
        """Return the number of currently connected SSE clients."""
        with self._lock:
            return len(self._subscribers)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        target_user_ids: Optional[Iterable[int]] = None,
        user_payloads: Optional[dict[int, dict[str, Any]]] = None,
    ) -> Event:
        """Broadcast an event to the eligible subscribers.

        Args:
            event_type: One of :data:`EVENT_TYPES`.
            data: JSON-serialisable payload shared by every recipient.
            target_user_ids: Restrict delivery to these user ids (``None`` = all).
            user_payloads: Per-user payload overrides merged on delivery.

        Returns:
            The published event, useful for testing and logging.
        """
        with self._lock:
            self._sequence += 1
            event = Event(
                id=self._sequence,
                type=event_type,
                data=data,
                target_user_ids=(
                    frozenset(target_user_ids) if target_user_ids is not None else None
                ),
                user_payloads=dict(user_payloads or {}),
            )
            subscribers = list(self._subscribers.values())

        for subscriber in subscribers:
            if event.target_user_ids is not None and subscriber.user_id not in event.target_user_ids:
                continue
            self._offer(subscriber.queue, event)
        return event

    @staticmethod
    def _offer(target_queue: Any, event: Event) -> None:
        """Push an event into a subscriber queue, dropping the oldest when full."""
        try:
            target_queue.put_nowait(event)
            return
        except Exception:  # pragma: no cover - queue full
            pass
        try:
            target_queue.get_nowait()
        except Exception:  # pragma: no cover - queue unexpectedly empty
            pass
        try:
            target_queue.put_nowait(event)
        except Exception:  # pragma: no cover - subscriber is gone
            pass


#: Process-wide broadcaster instance shared by every request handler.
broadcaster = EventBroadcaster()


def format_event(event: Event, user_id: Optional[int] = None) -> str:
    """Render an event as a Server-Sent Events frame.

    Args:
        event: Event to serialise.
        user_id: Recipient id used to merge per-user payload overrides.

    Returns:
        The complete SSE frame, terminated by a blank line.
    """
    payload = dict(event.data)
    if user_id is not None:
        payload.update(event.user_payloads.get(user_id, {}))
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return f"id: {event.id}\nevent: {event.type}\ndata: {body}\n\n"
