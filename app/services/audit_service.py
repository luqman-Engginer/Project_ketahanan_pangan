"""Audit logging service for important actions."""
from __future__ import annotations

from typing import Any, Optional

from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def _get_request_meta() -> tuple[Optional[int], str]:
    """Return acting user id and a short request context string."""
    user_id: Optional[int] = None
    if has_request_context():
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
        except Exception:
            user_id = None
    return user_id, request.path if has_request_context() else "-"


def log_action(
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist an audit log entry for a critical action.

    Args:
        action: Machine-readable action name (e.g. ``VERIFY_ORGANIZATION``).
        entity: Entity type (e.g. ``organization``).
        entity_id: Primary key of the affected entity.
        metadata: Optional extra context stored in memory only (not persisted).
    """
    try:
        user_id, _ = _get_request_meta()
        log = AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
