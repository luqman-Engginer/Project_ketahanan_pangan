"""Surplus food board, detail views, and discussion service."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import or_

from app.extensions import db
from app.models import City, Comment, FoodCategory, Organization, SurplusListing, User
from app.services import realtime

_DB_TO_UI_STATUS = {
    "available": "tersedia",
    "claimed": "diklaim",
    "picked_up": "diambil",
    "expired": "kedaluwarsa",
    "cancelled": "dibatalkan",
}

_UI_TO_DB_STATUS = {v: k for k, v in _DB_TO_UI_STATUS.items()}


def get_surplus_listings(
    search_query: Optional[str] = None,
    category_name: Optional[str] = None,
    city_name: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieve surplus listings filtered by search query, category, city, and status.

    Args:
        search_query: Text query matching title or notes.
        category_name: Filter by food category name.
        city_name: Filter by city name.
        status_filter: UI status string ('tersedia', 'diklaim', etc.) or DB status.

    Returns:
        List of formatted surplus listing dictionaries for the board.
    """
    query = (
        db.session.query(
            SurplusListing,
            FoodCategory.name.label("category_name"),
            City.name.label("city_name"),
            Organization.name.label("donor_name"),
            Organization.address.label("donor_address"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .join(Organization, SurplusListing.org_id == Organization.id)
    )

    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(or_(SurplusListing.title.ilike(term), SurplusListing.notes.ilike(term)))

    if category_name:
        query = query.filter(FoodCategory.name == category_name.strip())

    if city_name:
        query = query.filter(City.name == city_name.strip())

    if status_filter and status_filter != "semua":
        db_status = _UI_TO_DB_STATUS.get(status_filter, status_filter)
        query = query.filter(SurplusListing.status == db_status)

    listings = query.order_by(SurplusListing.created_at.desc()).all()

    results: list[dict[str, Any]] = []
    for item, cat, city, donor, addr in listings:
        tone_index = (item.id % 5) + 1
        ui_status = _DB_TO_UI_STATUS.get(item.status, item.status)
        results.append(
            {
                "id": item.id,
                "title": item.title,
                "category": cat,
                "qty": f"{item.qty:g}",
                "unit": item.unit,
                "city": city,
                "address": addr or f"Area {city}",
                "pickup_before": item.pickup_before.strftime("%d %b %Y, %H:%M WIB"),
                "status": ui_status,
                "db_status": item.status,
                "donor": donor,
                "donor_id": item.org_id,
                "tone": f"tone-{tone_index}",
                "views": (item.id * 7 + 13) % 95 + 15,
                "created_at": item.created_at.strftime("%d %b %Y, %H:%M"),
                "excerpt": (item.notes[:75] + "...") if item.notes and len(item.notes) > 75 else (item.notes or "Pangan surplus layak konsumsi."),
                "description": item.notes or "Pangan surplus siap disalurkan kepada mitra penerima.",
            }
        )
    return results


def get_surplus_detail(listing_id: int) -> Optional[dict[str, Any]]:
    """Retrieve full detail for a single surplus listing including comments.

    Args:
        listing_id: Primary key of the listing.

    Returns:
        Formatted listing dictionary, or None if not found.
    """
    row = (
        db.session.query(
            SurplusListing,
            FoodCategory.name.label("category_name"),
            City.name.label("city_name"),
            Organization.name.label("donor_name"),
            Organization.address.label("donor_address"),
            Organization.phone.label("donor_phone"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .join(Organization, SurplusListing.org_id == Organization.id)
        .filter(SurplusListing.id == listing_id)
        .first()
    )

    if not row:
        return None

    item, cat, city, donor, addr, phone = row
    tone_index = (item.id % 5) + 1
    ui_status = _DB_TO_UI_STATUS.get(item.status, item.status)

    # Fetch comments
    comments_query = (
        db.session.query(Comment, User.name.label("user_name"), User.role.label("user_role"))
        .join(User, Comment.user_id == User.id)
        .filter(Comment.listing_id == listing_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    comments_list: list[dict[str, Any]] = []
    for c, u_name, u_role in comments_query:
        role_label = "Donor" if u_role == "donor" else ("Penerima" if u_role == "receiver" else "Admin")
        comments_list.append(
            {
                "id": c.id,
                "author": u_name,
                "role": role_label,
                "time": c.created_at.strftime("%d %b, %H:%M"),
                "body": c.body,
                "parent_id": c.parent_id,
            }
        )

    return {
        "id": item.id,
        "title": item.title,
        "category": cat,
        "category_id": item.category_id,
        "qty": f"{item.qty:g}",
        "unit": item.unit,
        "qty_kg": float(item.qty_kg),
        "city": city,
        "city_id": item.city_id,
        "address": addr or f"Kota {city}",
        "phone": phone or "-",
        "pickup_before": item.pickup_before.strftime("%d %b %Y, %H:%M WIB"),
        "raw_pickup_before": item.pickup_before,
        "status": ui_status,
        "db_status": item.status,
        "donor": donor,
        "donor_id": item.org_id,
        "tone": f"tone-{tone_index}",
        "views": (item.id * 7 + 13) % 95 + 15,
        "created_at": item.created_at.strftime("%d %b %Y, %H:%M"),
        "notes": item.notes,
        "description": item.notes or "Pangan surplus berkualitas siap diambil oleh komunitas penerima manfaat.",
        "comments": comments_list,
    }


def create_surplus_listing(
    org_id: int,
    category_id: int,
    title: str,
    qty: Decimal,
    unit: str,
    qty_kg: Decimal,
    pickup_before: datetime,
    city_id: int,
    notes: Optional[str] = None,
    actor_user_id: Optional[int] = None,
) -> SurplusListing:
    """Create a new surplus food listing and announce it in real time.

    Args:
        org_id: Organization publishing the listing.
        category_id: Food category id.
        title: Listing title.
        qty: Quantity of food.
        unit: Unit of measure.
        qty_kg: Weight equivalent in kilograms.
        pickup_before: Latest pickup time.
        city_id: City where the food can be collected.
        notes: Optional pickup notes.
        actor_user_id: User that created the listing (excluded from notifications).

    Returns:
        The persisted SurplusListing instance.
    """
    listing = SurplusListing(
        org_id=org_id,
        category_id=category_id,
        title=title.strip(),
        qty=qty,
        unit=unit.strip(),
        qty_kg=qty_kg,
        pickup_before=pickup_before,
        city_id=city_id,
        notes=notes.strip() if notes else None,
        status="available",
    )
    db.session.add(listing)
    db.session.commit()

    announce_listing(listing, actor_user_id=actor_user_id)
    return listing


def announce_listing(listing: SurplusListing, actor_user_id: Optional[int] = None) -> None:
    """Publish the ``surplus_new`` event for a freshly created listing.

    Args:
        listing: Listing that has just been persisted.
        actor_user_id: User that created the listing (excluded from notifications).
    """
    category = db.session.get(FoodCategory, listing.category_id)
    city = db.session.get(City, listing.city_id)
    organization = db.session.get(Organization, listing.org_id)

    realtime.publish_surplus_new(
        listing,
        category_name=category.name if category else "-",
        city_name=city.name if city else "-",
        donor_name=organization.name if organization else "-",
        actor_user_id=actor_user_id,
    )


def get_listing_for_org(listing_id: int, org_id: int) -> SurplusListing:
    """Fetch one surplus listing ensuring it belongs to the owning organization.

    Args:
        listing_id: Primary key of the listing.
        org_id: Organization that must own the listing.

    Returns:
        The SurplusListing instance.

    Raises:
        PermissionError: If the listing belongs to another organization.
        LookupError: If the listing does not exist.
    """
    listing = db.session.get(SurplusListing, listing_id)
    if listing is None:
        raise LookupError("Listing surplus tidak ditemukan.")
    if listing.org_id != org_id:
        raise PermissionError("Anda tidak berhak mengubah surplus milik organisasi lain.")
    return listing


def update_surplus_listing(
    listing_id: int,
    org_id: int,
    category_id: int,
    title: str,
    qty: Decimal,
    unit: str,
    qty_kg: Decimal,
    pickup_before: datetime,
    city_id: int,
    notes: Optional[str] = None,
) -> SurplusListing:
    """Update a surplus listing owned by the given organization.

    Args:
        listing_id: Primary key of the listing to update.
        org_id: Organization that must own the listing.
        category_id: New food category id.
        title: New listing title.
        qty: New quantity.
        unit: New unit of measure.
        qty_kg: New weight equivalent in kilograms.
        pickup_before: New pickup deadline.
        city_id: New city id.
        notes: Optional pickup notes.

    Returns:
        The updated SurplusListing instance.

    Raises:
        PermissionError: If the listing belongs to another organization.
        LookupError: If the listing does not exist.
    """
    listing = get_listing_for_org(listing_id, org_id)
    listing.category_id = category_id
    listing.title = title.strip()
    listing.qty = qty
    listing.unit = unit.strip()
    listing.qty_kg = qty_kg
    listing.pickup_before = pickup_before
    listing.city_id = city_id
    listing.notes = notes.strip() if notes else None
    db.session.commit()
    return listing


def delete_surplus_listing(listing_id: int, org_id: int) -> None:
    """Delete an unclaimed surplus listing owned by the given organization.

    Args:
        listing_id: Primary key of the listing to delete.
        org_id: Organization that must own the listing.

    Raises:
        ValueError: If the listing already has an active claim.
        PermissionError: If the listing belongs to another organization.
        LookupError: If the listing does not exist.
    """
    listing = get_listing_for_org(listing_id, org_id)
    if listing.status in {"claimed", "picked_up"}:
        raise ValueError("Surplus yang sudah diklaim atau diambil tidak dapat dihapus.")
    db.session.delete(listing)
    db.session.commit()


def add_comment(
    listing_id: int,
    user_id: int,
    body: str,
    parent_id: Optional[int] = None,
) -> Comment:
    """Post a comment or reply on a surplus listing."""
    comment = Comment(
        listing_id=listing_id,
        user_id=user_id,
        body=body.strip(),
        parent_id=parent_id,
    )
    db.session.add(comment)
    db.session.commit()
    return comment


def get_category_options() -> list[dict[str, Any]]:
    """Return all food categories as id/label pairs for filter and form selects."""
    rows = db.session.query(FoodCategory.id, FoodCategory.name).order_by(FoodCategory.id.asc()).all()
    return [{"id": cat_id, "name": name} for cat_id, name in rows]


def get_city_options() -> list[dict[str, Any]]:
    """Return cities hosting registered organizations as id/label pairs."""
    rows = (
        db.session.query(City.id, City.name)
        .join(Organization, Organization.city_id == City.id)
        .distinct()
        .order_by(City.name.asc())
        .all()
    )
    return [{"id": city_id, "name": name} for city_id, name in rows]

