"""Claim lifecycle and workflow service (pending -> approved -> picked_up / cancelled)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.extensions import db
from app.models import City, Claim, Organization, SurplusListing
from app.services import realtime


def create_claim(listing_id: int, receiver_org_id: int) -> Claim:
    """Create a new claim for an available surplus listing.

    Args:
        listing_id: Target surplus listing.
        receiver_org_id: Claiming receiver organization.

    Returns:
        Created Claim instance.

    Raises:
        ValueError: If listing is unavailable or already claimed.
    """
    listing = SurplusListing.query.get_or_404(listing_id)
    if listing.status != "available":
        raise ValueError("Surplus ini sudah tidak tersedia untuk diklaim.")

    if listing.org_id == receiver_org_id:
        raise ValueError("Organisasi donor tidak dapat mengklaim surplusnya sendiri.")

    claim = Claim(
        listing_id=listing.id,
        receiver_org_id=receiver_org_id,
        status="pending",
        claimed_at=datetime.utcnow(),
    )
    listing.status = "claimed"
    db.session.add(claim)
    db.session.commit()

    _announce_claim(claim, listing, notify_donor=True)
    return claim


def update_claim_status(
    claim_id: int,
    new_status: str,
    user_org_id: int,
    is_admin: bool = False,
) -> Claim:
    """Update claim status adhering to role permissions.

    - Donor or Admin can approve ('approved') or mark picked up ('picked_up').
    - Receiver, Donor, or Admin can cancel ('cancelled').
    """
    claim = Claim.query.get_or_404(claim_id)
    listing = SurplusListing.query.get_or_404(claim.listing_id)

    # Authorization verification
    if not is_admin and user_org_id not in (claim.receiver_org_id, listing.org_id):
        raise PermissionError("Anda tidak berhak memperbarui klaim ini.")

    if new_status == "approved":
        if not is_admin and user_org_id != listing.org_id:
            raise PermissionError("Hanya donor pemilik surplus yang dapat menyetujui klaim.")
        claim.status = "approved"

    elif new_status == "picked_up":
        claim.status = "picked_up"
        claim.picked_up_at = datetime.utcnow()
        listing.status = "picked_up"

    elif new_status == "cancelled":
        claim.status = "cancelled"
        listing.status = "available"

    else:
        claim.status = new_status

    db.session.commit()

    _announce_claim(claim, listing, notify_receiver=(new_status != "cancelled"))
    if new_status == "picked_up":
        realtime.publish_kpi_update()
    return claim


def _announce_claim(
    claim: Claim,
    listing: SurplusListing,
    notify_donor: bool = False,
    notify_receiver: bool = False,
) -> None:
    """Publish the ``claim_update`` event and notify the counterparty.

    Args:
        claim: The persisted claim.
        listing: Surplus listing referenced by the claim.
        notify_donor: Notify the donor organisation about the new claim.
        notify_receiver: Notify the receiver organisation about the status change.
    """
    receiver = db.session.get(Organization, claim.receiver_org_id)
    city = db.session.get(City, listing.city_id)

    notify_user_ids: list[int] = []
    if notify_donor:
        notify_user_ids.extend(realtime.users_of_org(listing.org_id))
    if notify_receiver:
        notify_user_ids.extend(realtime.users_of_org(claim.receiver_org_id))

    realtime.publish_claim_update(
        claim,
        listing_title=listing.title,
        receiver_name=receiver.name if receiver else "-",
        city_name=city.name if city else "-",
        notify_user_ids=notify_user_ids,
    )


def get_claims_for_user(org_id: int, role: str) -> list[dict[str, Any]]:
    """Get claims visible to a specific organization role."""
    query = (
        db.session.query(
            Claim,
            SurplusListing.title.label("listing_title"),
            Organization.name.label("receiver_name"),
            City.name.label("city_name"),
        )
        .join(SurplusListing, Claim.listing_id == SurplusListing.id)
        .join(Organization, Claim.receiver_org_id == Organization.id)
        .join(City, SurplusListing.city_id == City.id)
    )

    if role == "receiver":
        query = query.filter(Claim.receiver_org_id == org_id)
    elif role == "donor":
        query = query.filter(SurplusListing.org_id == org_id)

    rows = query.order_by(Claim.claimed_at.desc()).all()

    return [
        {
            "id": c.id,
            "listing_id": c.listing_id,
            "listing": title,
            "receiver": rec_name,
            "city": city,
            "status": c.status,
            "claimed_at": c.claimed_at.strftime("%d %b, %H:%M"),
            "time": c.claimed_at.strftime("%d %b, %H:%M"),
            "picked_up_at": c.picked_up_at.strftime("%d %b, %H:%M") if c.picked_up_at else "-",
        }
        for c, title, rec_name, city in rows
    ]


def get_recent_claims(limit: int = 5) -> list[dict[str, str]]:
    """Return latest claims across the platform for the dashboard table."""
    rows = (
        db.session.query(
            Claim,
            SurplusListing.title.label("listing_title"),
            Organization.name.label("receiver_name"),
            City.name.label("city_name"),
        )
        .join(SurplusListing, Claim.listing_id == SurplusListing.id)
        .join(Organization, Claim.receiver_org_id == Organization.id)
        .join(City, SurplusListing.city_id == City.id)
        .order_by(Claim.claimed_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "receiver": rec_name,
            "listing": title,
            "city": city,
            "status": c.status,
            "time": c.claimed_at.strftime("%d %b, %H:%M"),
        }
        for c, title, rec_name, city in rows
    ]

