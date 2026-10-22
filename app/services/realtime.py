"""Real-time domain events published to the SSE broadcaster.

This module translates business changes (surplus published, claim updated,
stock expiring, impact recalculated) into :mod:`app.services.event_stream`
events. It also persists the matching :class:`~app.models.activity.Notification`
rows so the notification badge stays consistent with the live stream.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.extensions import db
from app.models import FoodCategory, InventoryItem, Organization, User
from app.services import impact, notification_service
from app.services.event_stream import (
    EVENT_CLAIM_UPDATE,
    EVENT_EXPIRY_ALERT,
    EVENT_KPI_UPDATE,
    EVENT_SURPLUS_NEW,
    broadcaster,
)

#: Human readable labels for the claim lifecycle.
CLAIM_STATUS_LABELS: dict[str, str] = {
    "pending": "menunggu konfirmasi",
    "approved": "disetujui",
    "picked_up": "sudah diambil",
    "cancelled": "dibatalkan",
}

#: Number of days before expiry that still triggers an alert.
EXPIRY_ALERT_WINDOW_DAYS = 3

#: Dedupe registry so the same item is not alerted twice on the same day.
_expiry_alert_registry: dict[tuple[int, str], date] = {}


def users_of_org(org_id: Optional[int]) -> list[int]:
    """Return the ids of every active user belonging to an organization."""
    if not org_id:
        return []
    rows = db.session.query(User.id).filter(User.org_id == org_id, User.is_active.is_(True)).all()
    return [row[0] for row in rows]


def _receiver_user_ids_in_city(city_id: int) -> list[int]:
    """Return the ids of active receiver users located in a city."""
    rows = (
        db.session.query(User.id)
        .join(Organization, User.org_id == Organization.id)
        .filter(
            Organization.city_id == city_id,
            Organization.type == "receiver",
            User.role == "receiver",
            User.is_active.is_(True),
        )
        .all()
    )
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
    donor_name: str,
    actor_user_id: Optional[int] = None,
) -> None:
    """Announce a newly published surplus listing.

    Args:
        listing: The persisted :class:`~app.models.food.SurplusListing`.
        category_name: Food category label of the listing.
        city_name: City label of the listing.
        donor_name: Organisation that published the listing.
        actor_user_id: User that created the listing (excluded from notifications).
    """
    receivers = [uid for uid in _receiver_user_ids_in_city(listing.city_id) if uid != actor_user_id]
    admins = _admin_user_ids()
    donor_users = users_of_org(listing.org_id)

    payload = {
        "listing_id": listing.id,
        "title": listing.title,
        "category": category_name,
        "qty": float(listing.qty),
        "unit": listing.unit,
        "qty_kg": float(listing.qty_kg),
        "city": city_name,
        "pickup_before": listing.pickup_before.strftime("%d %b %Y, %H:%M"),
        "donor": donor_name,
        "url": f"/surplus/{listing.id}",
    }

    notified = notification_service.notify_users(
        receivers,
        EVENT_SURPLUS_NEW,
        {
            "title": f"Surplus baru: {listing.title}",
            "message": f"{donor_name} recyclerkan {float(listing.qty):g} {listing.unit} di {city_name}.",
            "listing_id": listing.id,
        },
    )

    broadcaster.publish(
        EVENT_SURPLUS_NEW,
        payload,
        target_user_ids=set(receivers) | set(admins) | set(donor_users),
        user_payloads=_unread_payload(notified),
    )


def publish_claim_update(
    claim: Any,
    listing_title: str,
    receiver_name: str,
    city_name: str,
    notify_user_ids: Optional[list[int]] = None,
) -> None:
    """Announce a claim creation or status transition.

    Args:
        claim: The persisted :class:`~app.models.food.Claim`.
        listing_title: Title of the claimed surplus listing.
        receiver_name: Organisation that owns the claim.
        city_name: City of the claimed listing.
        notify_user_ids: Users that should also receive a stored notification.
    """
    donor_users = users_of_org(claim.listing.org_id if claim.listing else None)
    receiver_users = users_of_org(claim.receiver_org_id)
    admins = _admin_user_ids()

    status_label = CLAIM_STATUS_LABELS.get(claim.status, claim.status)
    payload = {
        "claim_id": claim.id,
        "listing_id": claim.listing_id,
        "listing_title": listing_title,
        "status": claim.status,
        "status_label": status_label,
        "receiver": receiver_name,
        "city": city_name,
        "claimed_at": claim.claimed_at.strftime("%d %b %Y, %H:%M") if claim.claimed_at else "-",
    }

    notified = notification_service.notify_users(
        notify_user_ids or [],
        EVENT_CLAIM_UPDATE,
        {
            "title": f"Klaim {status_label}: {listing_title}",
            "message": f"{receiver_name} memperbarui klaim untuk {listing_title} ({city_name}).",
            "claim_id": claim.id,
        },
    )

    broadcaster.publish(
        EVENT_CLAIM_UPDATE,
        payload,
        target_user_ids=set(donor_users) | set(receiver_users) | set(admins),
        user_payloads=_unread_payload(notified),
    )


def publish_expiry_alert(item: Any, category_name: str, org_name: str) -> None:
    """Announce that a stock item is about to expire.

    Args:
        item: The persisted :class:`~app.models.food.InventoryItem`.
        category_name: Food category label of the item.
        org_name: Organisation owning the stock.
    """
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
        "url": "/inventory",
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
    """Broadcast refreshed dashboard KPIs, trend, and distributions."""
    broadcaster.publish(
        EVENT_KPI_UPDATE,
        {
            "kpis": impact.get_dashboard_kpis(),
            "trend": impact.get_daily_rescued_trend(days=14),
            "kategori": impact.get_category_distribution(),
            "wilayah": impact.get_regional_distribution(),
        },
    )


def scan_expiry_alerts() -> int:
    """Publish expiry alerts for every stock item inside the alert window.

    The same item is alerted at most once per day so repeated page loads or
    SSE reconnections never spam the user.

    Returns:
        Number of alerts published during this scan.
    """
    today = date.today()
    horizon = today + timedelta(days=EXPIRY_ALERT_WINDOW_DAYS)

    rows = (
        db.session.query(InventoryItem, FoodCategory.name.label("category_name"), Organization.name.label("org_name"))
        .join(FoodCategory, InventoryItem.category_id == FoodCategory.id)
        .join(Organization, InventoryItem.org_id == Organization.id)
        .filter(InventoryItem.expires_on >= today, InventoryItem.expires_on <= horizon)
        .all()
    )

    published = 0
    for item, category_name, org_name in rows:
        if alert_expiring_item(item, category_name=category_name, org_name=org_name):
            published += 1
    return published


def alert_expiring_item(item: Any, category_name: str, org_name: str) -> bool:
    """Publish an ``expiry_alert`` event for a stock item inside the alert window.

    The alert is emitted at most once per item per day.

    Args:
        item: The persisted :class:`~app.models.food.InventoryItem`.
        category_name: Food category label of the item.
        org_name: Organisation owning the stock.

    Returns:
        True when an alert was published, False when skipped or out of window.
    """
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
    stale = [key for key, value in _expiry_alert_registry.items() if value < cutoff]
    for key in stale:
        _expiry_alert_registry.pop(key, None)
