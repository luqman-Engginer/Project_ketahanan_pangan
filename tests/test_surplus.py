"""Tests for surplus listing CRUD, search/filter, and discussion comments."""
from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import Comment, SurplusListing
from app.services import surplus_service
from tests.conftest import make_listing, make_user


def test_donor_can_create_listing(donor_client: Any, app: Any) -> None:
    """A donor can publish a surplus listing through the form."""
    client, org = donor_client
    resp = client.post(
        "/surplus/",
        data={
            "category_id": "1",
            "title": "Nasi Kotak Uji",
            "qty": "10",
            "unit": "porsi",
            "qty_kg": "4",
            "pickup_before": "2030-01-01T10:00",
            "city_id": "3273",
            "notes": "Layak konsumsi",
        },
    )
    assert resp.status_code == 302
    listing = SurplusListing.query.filter_by(title="Nasi Kotak Uji").first()
    assert listing is not None
    assert listing.org_id == org.id
    assert listing.status == "available"


def test_donor_cannot_update_other_org_listing(donor_client: Any, app: Any) -> None:
    """A donor may not modify a listing owned by another organization."""
    client, org = donor_client
    other_org = make_org_other()
    other_listing = make_listing(other_org)

    resp = client.post(
        f"/surplus/{other_listing.id}/update",
        data={
            "category_id": "1",
            "title": "Dibajak",
            "qty": "5",
            "unit": "porsi",
            "qty_kg": "2",
            "pickup_before": "2030-01-01T10:00",
            "city_id": "3273",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(other_listing)
    assert other_listing.title == "Surplus uji otomatis"


def test_search_filters_by_title(app: Any) -> None:
    """Search query filters listings by title or notes."""
    from tests.conftest import make_org

    org = make_org("Donor Search", "donor")
    make_listing(org)
    result = surplus_service.get_surplus_listings(search_query="otomatis")
    assert len(result) == 1
    assert surplus_service.get_surplus_listings(search_query="tidakada") == []


def test_search_filters_by_category_and_city(app: Any) -> None:
    """Category and city filters narrow the result set."""
    from tests.conftest import make_org

    org = make_org("Donor Filter", "donor")
    make_listing(org)
    assert len(surplus_service.get_surplus_listings(category_name="Makanan Siap Santap")) == 1
    assert len(surplus_service.get_surplus_listings(city_name="Bandung")) == 1
    assert surplus_service.get_surplus_listings(category_name="Produk Roti & Bakery") == []


def test_comment_requires_login_and_persists(client: Any, app: Any) -> None:
    """Comments require authentication and are stored on the listing."""
    from tests.conftest import make_org

    org = make_org("Donor Comment", "donor")
    listing = make_listing(org)
    assert client.post(f"/surplus/{listing.id}/komentar", data={"body": "anon"}).status_code == 302

    user = make_user("commenter@uji.id", "receiver", org.id)
    client.post("/login", data={"email": "commenter@uji.id", "password": "rahasia123"})
    resp = client.post(f"/surplus/{listing.id}/komentar", data={"body": "Bisa diambil sore?"})
    assert resp.status_code == 302

    comment = Comment.query.filter_by(listing_id=listing.id).first()
    assert comment is not None
    assert comment.body == "Bisa diambil sore?"
    assert comment.user_id == user.id


def make_org_other():
    """Helper creating a distinct organization for isolation checks."""
    from tests.conftest import make_org

    return make_org("Org Lain", "donor")
