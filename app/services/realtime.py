"""Real-time domain events published to the SSE broadcaster."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.extensions import db
from app.models import FoodCategory, InventoryItem, Organization, User
from app.services import impact, notification_service
from app.services.event_stream import (
    EVENT_EXPIRY_ALERT,
    EVENT_KPI_UPDATE,
    EVENT_REVIEW_UPDATE,
    EVENT_SURPLUS_NEW,
    broadcaster,
)

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending": "menunggu review",
    "approved": "disetujui",
    "rejected": "ditolak",
}

EXPIRY_ALERT_WINDOW_DAYS = 3
_expiry_alert_registry: dict[tuple[int, str], date] = {}


def users_of_org(org_id: Optional[int]) -> list[int]:
    """Return the ids of every active user belonging to an organization."""
    if not org_id:
        return []
    rows = db.session.query(User.id).filter(User.org_id == org_id, User.is_active.is_(True)).all()
    return [row[0] for row in rows]


def _admin_user_ids() -> list[int]:
    """Return the ids of every active platform administrator."""
    rows = db.session.query(User.id).filter(User.role == "admin", User.is_active.is_(True)).all()
    return [row[0] for row in rows]


def _unread_payload(user_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Build per-user payload overrides carrying the fresh unread counter."""
    return {uid: {"unread_count": notification_service.get_unread_count(uid)} for uid in user_ids}


def publish_surplus_new(
    listing: Any,
    category_name: str,
    city_name: str,
    supplier_name: str,
    actor_user_id: Optional[int] = None,
) -> None:
    """Announce a new pending listing and notify administrators."""
    admins = _admin_user_ids()
    owner_users = users_of_org(listing.org_id)
    payload = {
        "listing_id": listing.id,
        "title": listing.title,
        "category": category_name,
        "qty": float(listing.qty),
        "unit": listing.unit,
        "qty_kg": float(listing.qty_kg),
        "city": city_name,
        "pickup_before": listing.pickup_before.strftime("%d %b %Y, %H:%M"),
        "supplier": supplier_name,
        "review_status": listing.review_status,
        "url": f"/admin/pasokan/{listing.id}",
    }
    notified = notification_service.notify_users(
        [uid for uid in admins if uid != actor_user_id],
        EVENT_SURPLUS_NEW,
        {
            "title": f"Pasokan menunggu review: {listing.title}",
            "message": f"{supplier_name} mengirim {float(listing.qty):g} {listing.unit} untuk ditinjau.",
            "listing_id": listing.id,
        },
    )
    broadcaster.publish(
        EVENT_SURPLUS_NEW,
        payload,
        target_user_ids=set(admins) | set(owner_users),
        user_payloads=_unread_payload(notified),
    )


def publish_review_update(listing: Any, reviewer_name: str) -> None:
    """Announce an admin review decision to the owning supplier."""
    owner_users = users_of_org(listing.org_id)
    status_label = REVIEW_STATUS_LABELS.get(listing.review_status, listing.review_status)
    payload = {
        "listing_id": listing.id,
        "title": listing.title,
        "review_status": listing.review_status,
        "status_label": status_label,
        "review_note": listing.review_note or "",
        "reviewed_by": reviewer_name,
        "url": f"/supplier/pasokan/{listing.id}",
    }
    notified = notification_service.notify_users(
        owner_users,
        EVENT_REVIEW_UPDATE,
        {
            "title": f"Pasokan {status_label}: {listing.title}",
            "message": listing.review_note or f"Admin telah meninjau pasokan Anda.",
            "listing_id": listing.id,
        },
    )
    broadcaster.publish(
        EVENT_REVIEW_UPDATE,
        payload,
        target_user_ids=set(owner_users) | set(_admin_user_ids()),
        user_payloads=_unread_payload(notified),
    )


def publish_expiry_alert(item: Any, category_name: str, org_name: str) -> None:
    """Announce that a stock item is about to expire."""
    days_left = (item.expires_on - date.today()).days
    owner_users = users_of_org(item.org_id)
    payload = {
        "item_id": item.id,
        "name": item.name,
        "category": category_name,
        "qty": float(item.qty),
        "unit": item.unit,
        "expires_on": item.expires_on.strftime("%d %b %Y"),
        "days_left": days_left,
        "days_label": "Hari ini" if days_left == 0 else f"H-{days_left}",
        "org": org_name,
        "url": "/supplier/stok",
    }
    notified = notification_service.notify_users(
        owner_users,
        EVENT_EXPIRY_ALERT,
        {
            "title": f"Mendekati kedaluwarsa: {item.name}",
            "message": f"{item.name} ({float(item.qty):g} {item.unit}) harus dipakai sebelum {payload['expires_on']}.",
            "item_id": item.id,
        },
    )
    broadcaster.publish(
        EVENT_EXPIRY_ALERT,
        payload,
        target_user_ids=set(owner_users),
        user_payloads=_unread_payload(notified),
    )


def publish_kpi_update() -> None:
    """Broadcast refreshed platform KPIs to administrators only."""
    broadcaster.publish(
        EVENT_KPI_UPDATE,
        {
            "kpis": impact.get_dashboard_kpis(),
            "trend": impact.get_daily_rescued_trend(days=14),
            "kategori": impact.get_category_distribution(),
            "wilayah": impact.get_regional_distribution(),
        },
        target_user_ids=set(_admin_user_ids()),
    )


def scan_expiry_alerts() -> int:
    """Publish expiry alerts for every stock item inside the alert window."""
    today = date.today()
    horizon = today + timedelta(days=EXPIRY_ALERT_WINDOW_DAYS)
    rows = (
        db.session.query(InventoryItem, FoodCategory.name.label("category_name"), Organization.name.label("org_name"))
        .join(FoodCategory, InventoryItem.category_id == FoodCategory.id)
        .join(Organization, InventoryItem.org_id == Organization.id)
        .filter(InventoryItem.expires_on >= today, InventoryItem.expires_on <= horizon)
        .all()
    )
    return sum(
        1 for item, category_name, org_name in rows
        if alert_expiring_item(item, category_name=category_name, org_name=org_name)
    )


def alert_expiring_item(item: Any, category_name: str, org_name: str) -> bool:
    """Publish an expiry alert at most once per item per day."""
    today = date.today()
    horizon = today + timedelta(days=EXPIRY_ALERT_WINDOW_DAYS)
    if not (today <= item.expires_on <= horizon):
        return False
    _prune_expiry_registry()
    key = (item.id, item.expires_on.isoformat())
    if _expiry_alert_registry.get(key) == today:
        return False
    _expiry_alert_registry[key] = today
    publish_expiry_alert(item, category_name=category_name, org_name=org_name)
    return True


def _prune_expiry_registry() -> None:
    """Drop alert registry entries older than one week."""
    cutoff = date.today() - timedelta(days=7)
    for key in [key for key, value in _expiry_alert_registry.items() if value < cutoff]:
        _expiry_alert_registry.pop(key, None)
