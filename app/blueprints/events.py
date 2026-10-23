"""Server-Sent Events endpoint streaming real-time platform events."""
from __future__ import annotations

import queue as _queue
import time
from typing import Any, Iterator, Optional, Union

from flask import Blueprint, Response, jsonify
from flask_login import current_user

from app.services import realtime
from app.services.event_stream import (
    HEARTBEAT_FRAME,
    HEARTBEAT_INTERVAL,
    RECONNECT_DELAY_MS,
    Subscriber,
    broadcaster,
    format_event,
)

bp: Blueprint = Blueprint("events", __name__)

#: How often the stream wakes up to check for new events or a closed socket.
POLL_INTERVAL = 5.0


def _stream_events(subscriber: Subscriber) -> Iterator[str]:
    """Yield Server-Sent Events frames for a single connection.

    A heartbeat comment is flushed every :data:`HEARTBEAT_INTERVAL` seconds so
    that reverse proxies (Caddy/nginx) never drop an idle connection.

    Args:
        subscriber: Handle of the already registered connection.

    Yields:
        Raw SSE frames (retry hint, events, and heartbeats).
    """
    last_activity = time.monotonic()
    try:
        yield f"retry: {RECONNECT_DELAY_MS}\n\n"
        while True:
            try:
                event = subscriber.queue.get(timeout=POLL_INTERVAL)
            except _queue.Empty:
                if time.monotonic() - last_activity >= HEARTBEAT_INTERVAL:
                    yield HEARTBEAT_FRAME
                    last_activity = time.monotonic()
                continue
            yield format_event(event, user_id=subscriber.user_id)
            last_activity = time.monotonic()
    finally:
        broadcaster.unsubscribe(subscriber)


@bp.get("/events")
def events() -> Union[Response, tuple[Any, int]]:
    """Stream ``surplus_new``, ``review_update``, ``expiry_alert``, and ``kpi_update`` events.

    The endpoint requires an authenticated session; anonymous clients receive a
    ``401`` JSON body instead of a redirect so ``EventSource`` fails fast.

    Returns:
        A streaming ``text/event-stream`` response.
    """
    if not current_user.is_authenticated:
        return jsonify(error="Autentikasi diperlukan untuk streamed event."), 401

    subscriber = broadcaster.subscribe(
        user_id=current_user.id,
        role=current_user.role,
        org_id=current_user.org_id,
    )

    realtime.scan_expiry_alerts()

    response = Response(
        _stream_events(subscriber),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    response.call_on_close(lambda: broadcaster.unsubscribe(subscriber))
    return response
