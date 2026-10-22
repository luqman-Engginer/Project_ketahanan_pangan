"""Notification routes: user alert feed and status tracking."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import notification_service

bp: Blueprint = Blueprint("notification", __name__, url_prefix="/notifikasi")


@bp.get("/")
@login_required
def notification_page() -> str:
    """Render the notification feed filtered by read state."""
    show = request.args.get("show", "semua")
    items = notification_service.get_notifications(
        user_id=current_user.id,
        unread_only=(show == "unread"),
    )
    unread_count = notification_service.get_unread_count(current_user.id)

    return render_template(
        "notification/index.html",
        notifications=items,
        unread_count=unread_count,
        show=show,
    )


@bp.post("/tandai-dibaca")
@login_required
def mark_all_read():
    """Mark all unread notifications of the current user as read."""
    notification_service.mark_all_as_read(current_user.id)
    return redirect(url_for("notification.notification_page"))
