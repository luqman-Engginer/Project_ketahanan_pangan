"""Tests for the claim lifecycle workflow and receiver data isolation."""
from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import Claim, SurplusListing
from app.services import claim_service
from tests.conftest import make_listing


def test_receiver_can_claim_available_listing(receiver_client: Any, app: Any, donor_client: Any) -> None:
    """A receiver claims an available listing, flipping it to claimed."""
    donor_org = donor_client[1]
    listing = make_listing(donor_org, status="available")

    client, recv_org = receiver_client
    resp = client.post("/claims/", data={"listing_id": listing.id}, follow_redirects=True)
    assert resp.status_code == 200

    claim = Claim.query.filter_by(listing_id=listing.id).first()
    assert claim is not None
    assert claim.receiver_org_id == recv_org.id
    assert claim.status == "pending"
    db.session.refresh(listing)
    assert listing.status == "claimed"


def test_cannot_claim_unavailable_listing(receiver_client: Any, app: Any, donor_client: Any) -> None:
    """A listing already claimed cannot be claimed again."""
    donor_org = donor_client[1]
    listing = make_listing(donor_org, status="claimed")

    client, _ = receiver_client
    client.post("/claims/", data={"listing_id": listing.id}, follow_redirects=True)
    assert Claim.query.filter_by(listing_id=listing.id).count() == 0


def test_claim_status_workflow_approved_then_picked_up(receiver_client: Any, app: Any, donor_client: Any) -> None:
    """Donor approves then marks picked up; listing becomes picked_up."""
    donor_org = donor_client[1]
    listing = make_listing(donor_org)

    recv_client, recv_org = receiver_client
    recv_client.post("/claims/", data={"listing_id": listing.id})
    claim = Claim.query.filter_by(listing_id=listing.id).first()

    donor_client[0].post(f"/claims/{claim.id}/status", data={"status": "approved"})
    db.session.expire_all()
    claim = db.session.get(Claim, claim.id)
    assert claim.status == "approved"

    donor_client[0].post(f"/claims/{claim.id}/status", data={"status": "picked_up"})
    db.session.expire_all()
    claim = db.session.get(Claim, claim.id)
    listing = db.session.get(SurplusListing, listing.id)
    assert claim.status == "picked_up"
    assert claim.picked_up_at is not None
    assert listing.status == "picked_up"


def test_receiver_only_sees_own_claims(receiver_client: Any, app: Any, donor_client: Any) -> None:
    """get_claims_for_user isolates receiver claims by organization."""
    donor_org = donor_client[1]
    listing = make_listing(donor_org)
    other_recv_org = make_other_receiver()

    claim = Claim(listing_id=listing.id, receiver_org_id=other_recv_org.id, status="pending")
    db.session.add(claim)
    db.session.commit()

    client, recv_org = receiver_client
    rows = claim_service.get_claims_for_user(org_id=recv_org.id, role="receiver")
    assert rows == []

    rows_other = claim_service.get_claims_for_user(org_id=other_recv_org.id, role="receiver")
    assert len(rows_other) == 1


def make_other_receiver():
    """Helper creating a second receiver organization."""
    from tests.conftest import make_org

    return make_org("Penerima Lain", "receiver")
