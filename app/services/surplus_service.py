"""Supplier surplus listings and administrator review workflow."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import or_

from app.extensions import db
from app.models import City, FoodCategory, Organization, SurplusListing
from app.services import audit_service, realtime

REVIEW_LABELS = {"pending": "Menunggu review", "approved": "Disetujui", "rejected": "Ditolak"}
REVIEW_TONES = {"pending": "warning", "approved": "success", "rejected": "danger"}


def get_surplus_listings(
    org_id: Optional[int] = None,
    search_query: Optional[str] = None,
    category_name: Optional[str] = None,
    city_name: Optional[str] = None,
    review_status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieve listings, optionally restricted to one supplier organization."""
    query = (
        db.session.query(
            SurplusListing,
            FoodCategory.name.label("category_name"),
            City.name.label("city_name"),
            Organization.name.label("supplier_name"),
            Organization.address.label("supplier_address"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .join(Organization, SurplusListing.org_id == Organization.id)
        .filter(Organization.type == "supplier")
    )
    if org_id is not None:
        query = query.filter(SurplusListing.org_id == org_id)
    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(or_(SurplusListing.title.ilike(term), SurplusListing.notes.ilike(term)))
    if category_name:
        query = query.filter(FoodCategory.name == category_name.strip())
    if city_name:
        query = query.filter(City.name == city_name.strip())
    if review_status and review_status != "semua":
        if review_status in REVIEW_LABELS:
            query = query.filter(SurplusListing.review_status == review_status)

    rows = query.order_by(SurplusListing.created_at.desc()).all()
    results: list[dict[str, Any]] = []
    for item, category, city, supplier, address in rows:
        results.append(
            {
                "id": item.id,
                "title": item.title,
                "category": category,
                "qty": f"{item.qty:g}",
                "unit": item.unit,
                "qty_kg": float(item.qty_kg),
                "city": city,
                "address": address or f"Kota {city}",
                "pickup_before": item.pickup_before.strftime("%d %b %Y, %H:%M WIB"),
                "status": REVIEW_LABELS.get(item.review_status, item.review_status),
                "review_status": item.review_status,
                "review_label": REVIEW_LABELS.get(item.review_status, item.review_status),
                "review_tone": REVIEW_TONES.get(item.review_status, "neutral"),
                "review_note": item.review_note,
                "supplier": supplier,
                "supplier_id": item.org_id,
                "tone": f"tone-{(item.id % 5) + 1}",
                "created_at": item.created_at.strftime("%d %b %Y, %H:%M"),
                "excerpt": (item.notes[:75] + "...") if item.notes and len(item.notes) > 75 else (item.notes or "Pasokan pangan surplus layak konsumsi."),
                "description": item.notes or "Pasokan pangan surplus dari supplier.",
            }
        )
    return results


def get_surplus_detail(listing_id: int, org_id: Optional[int] = None) -> Optional[dict[str, Any]]:
    """Retrieve one listing; suppliers may only read their own organization."""
    query = (
        db.session.query(
            SurplusListing,
            FoodCategory.name.label("category_name"),
            City.name.label("city_name"),
            Organization.name.label("supplier_name"),
            Organization.address.label("supplier_address"),
            Organization.phone.label("supplier_phone"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .join(Organization, SurplusListing.org_id == Organization.id)
        .filter(SurplusListing.id == listing_id)
    )
    if org_id is not None:
        query = query.filter(SurplusListing.org_id == org_id)
    row = query.first()
    if not row:
        return None

    item, category, city, supplier, address, phone = row
    return {
        "id": item.id,
        "title": item.title,
        "category": category,
        "category_id": item.category_id,
        "qty": f"{item.qty:g}",
        "unit": item.unit,
        "qty_kg": float(item.qty_kg),
        "city": city,
        "city_id": item.city_id,
        "address": address or f"Kota {city}",
        "phone": phone or "-",
        "pickup_before": item.pickup_before.strftime("%d %b %Y, %H:%M WIB"),
        "raw_pickup_before": item.pickup_before,
        "status": REVIEW_LABELS.get(item.review_status, item.review_status),
        "review_status": item.review_status,
        "review_label": REVIEW_LABELS.get(item.review_status, item.review_status),
        "review_tone": REVIEW_TONES.get(item.review_status, "neutral"),
        "review_note": item.review_note,
        "reviewed_at": item.reviewed_at.strftime("%d %b %Y, %H:%M") if item.reviewed_at else None,
        "supplier": supplier,
        "supplier_id": item.org_id,
        "tone": f"tone-{(item.id % 5) + 1}",
        "created_at": item.created_at.strftime("%d %b %Y, %H:%M"),
        "notes": item.notes,
        "description": item.notes or "Pasokan pangan surplus dari supplier.",
        "comments": [],
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
    """Create a pending listing and notify administrators."""
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
        review_status="pending",
    )
    db.session.add(listing)
    db.session.commit()
    audit_service.log_action("CREATE_SURPLUS", "surplus_listing", listing.id)
    announce_listing(listing, actor_user_id=actor_user_id)
    return listing


def announce_listing(listing: SurplusListing, actor_user_id: Optional[int] = None) -> None:
    """Publish the new-listing event for administrators."""
    category = db.session.get(FoodCategory, listing.category_id)
    city = db.session.get(City, listing.city_id)
    organization = db.session.get(Organization, listing.org_id)
    realtime.publish_surplus_new(
        listing,
        category_name=category.name if category else "-",
        city_name=city.name if city else "-",
        supplier_name=organization.name if organization else "-",
        actor_user_id=actor_user_id,
    )


def get_listing_for_org(listing_id: int, org_id: int) -> SurplusListing:
    """Fetch one listing ensuring it belongs to the supplier organization."""
    listing = db.session.get(SurplusListing, listing_id)
    if listing is None:
        raise LookupError("Pasokan tidak ditemukan.")
    if listing.org_id != org_id:
        raise PermissionError("Anda tidak berhak mengubah pasokan milik organisasi lain.")
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
    """Update an owned listing and return it to pending review."""
    listing = get_listing_for_org(listing_id, org_id)
    listing.category_id = category_id
    listing.title = title.strip()
    listing.qty = qty
    listing.unit = unit.strip()
    listing.qty_kg = qty_kg
    listing.pickup_before = pickup_before
    listing.city_id = city_id
    listing.notes = notes.strip() if notes else None
    listing.review_status = "pending"
    listing.reviewed_by = None
    listing.reviewed_at = None
    listing.review_note = None
    db.session.commit()
    audit_service.log_action("UPDATE_SURPLUS", "surplus_listing", listing.id)
    return listing


def delete_surplus_listing(listing_id: int, org_id: int) -> None:
    """Delete an owned listing that is still pending or rejected."""
    listing = get_listing_for_org(listing_id, org_id)
    if listing.review_status == "approved":
        raise ValueError("Pasokan yang sudah disetujui tidak dapat dihapus.")
    db.session.delete(listing)
    db.session.commit()
    audit_service.log_action("DELETE_SURPLUS", "surplus_listing", listing_id)


def review_listing(
    listing_id: int,
    status: str,
    note: Optional[str],
    admin_user_id: int,
    reviewer_name: str,
) -> SurplusListing:
    """Approve or reject a listing and notify its supplier."""
    if status not in {"approved", "rejected"}:
        raise ValueError("Keputusan review harus approved atau rejected.")
    listing = db.session.get(SurplusListing, listing_id)
    if listing is None:
        raise LookupError("Pasokan tidak ditemukan.")
    listing.review_status = status
    listing.reviewed_by = admin_user_id
    listing.reviewed_at = datetime.utcnow()
    listing.review_note = note.strip() if note else None
    db.session.commit()
    audit_service.log_action("REVIEW_SURPLUS", "surplus_listing", listing.id)
    realtime.publish_review_update(listing, reviewer_name=reviewer_name)
    if status == "approved":
        realtime.publish_kpi_update()
    return listing


def get_category_options() -> list[dict[str, Any]]:
    """Return all food categories as id/label pairs."""
    rows = db.session.query(FoodCategory.id, FoodCategory.name).order_by(FoodCategory.id.asc()).all()
    return [{"id": cat_id, "name": name} for cat_id, name in rows]


def get_city_options() -> list[dict[str, Any]]:
    """Return all cities as id/label pairs."""
    rows = db.session.query(City.id, City.name).order_by(City.name.asc()).all()
    return [{"id": city_id, "name": name} for city_id, name in rows]
