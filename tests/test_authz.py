"""Tests for role-based authorization on protected endpoints."""
from __future__ import annotations

from typing import Any

from tests.conftest import make_listing


def test_anonymous_redirected_to_login(client: Any) -> None:
    """Protected pages redirect anonymous visitors to the login page."""
    resp = client.get("/inventory/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_receiver_forbidden_from_donor_pages(receiver_client: Any, app: Any) -> None:
    """Receivers cannot access donor-only inventory and waste pages."""
    client, _ = receiver_client
    assert client.get("/inventory/").status_code == 403
    assert client.get("/waste").status_code == 403


def test_donor_forbidden_from_claim_creation_page_scope(donor_client: Any, app: Any) -> None:
    """A donor cannot create a claim (receiver-only action)."""
    client, org = donor_client
    listing = make_listing(org)
    resp = client.post("/claims/", data={"listing_id": listing.id})
    assert resp.status_code == 403


def test_admin_can_access_all_pages(client: Any, app: Any) -> None:
    """An admin can reach donor and admin pages."""
    from tests.conftest import make_user

    make_user("admin@uji.id", "admin", None)
    client.post("/login", data={"email": "admin@uji.id", "password": "rahasia123"})
    assert client.get("/admin/").status_code == 200
    assert client.get("/inventory/").status_code == 200
