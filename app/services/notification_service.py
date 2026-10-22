"""Notification service for user notifications."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from app.extensions import db
from app.models import Notification


def get_notifications(user_id: int, unread_only: bool = False) -> list[dict[str, Any]]:
    """Retrieve notifications for a user."""
    query = Notification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))

    items = query.order_by(Notification.created_at.desc()).all()
    results: list[dict[str, Any]] = []

    for item in items:
        payload = item.payload_json or {}
        results.append(
            {
                "id": item.id,
                "type": item.type,
                "title": payload.get("title", "Notifikasi FoodLoop"),
                "body": payload.get("message", "-"),
                "time": item.created_at.strftime("%d %b, %H:%M"),
                "read": item.read_at is not None,
            }
        )
    return results


def get_unread_count(user_id: Optional[int]) -> int:
    """Return number of unread notifications for a user."""
    if not user_id:
        return 0
    return Notification.query.filter_by(user_id=user_id, read_at=None).count()


def mark_all_as_read(user_id: int) -> None:
    """Mark all unread notifications of a user as read."""
    now = datetime.utcnow()
    Notification.query.filter_by(user_id=user_id, read_at=None).update({"read_at": now})
    db.session.commit()


def create_notification(user_id: int, type: str, payload: dict[str, Any]) -> Notification:
    """Persist a single notification for a user.

    Args:
        user_id: Recipient user id.
        type: Notification type (mirrors the SSE event name).
        payload: JSON payload stored alongside the notification.

    Returns:
        The persisted Notification instance.
    """
    notification = Notification(user_id=user_id, type=type, payload_json=payload)
    db.session.add(notification)
    return notification


def notify_users(
    user_ids: Iterable[int],
    type: str,
    payload: dict[str, Any],
) -> list[int]:
    """Create notifications for several users in a single transaction.

    Args:
        user_ids: Recipients of the notification.
        type: Notification type (mirrors the SSE event name).
        payload: JSON payload stored alongside every notification.

    Returns:
        List of user ids that actually received a notification.
    """
    recipients = [uid for uid in dict.fromkeys(user_ids) if uid]
    if not recipients:
        return []

    for user_id in recipients:
        create_notification(user_id, type, payload)
    db.session.commit()
    return recipients

