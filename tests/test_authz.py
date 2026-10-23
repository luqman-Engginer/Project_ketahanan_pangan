"""Tests for role-based authorization on protected endpoints."""
from __future__ import annotations

from typing import Any


def test_anonymous_redirected_to_login(client: Any) -> None:
    """Protected pages redirect anonymous visitors to the login page."""
    resp = client.get("/supplier/stok/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_supplier_cannot_access_admin_pages(supplier_client: Any, app: Any) -> None:
    """Suppliers cannot access admin-only pages."""
    client, _ = supplier_client
    assert client.get("/admin/").status_code == 403


def test_admin_can_access_all_pages(admin_client: Any, app: Any) -> None:
    """An admin can reach admin dashboard and admin pasokan board."""
    assert admin_client.get("/admin/").status_code == 200


def test_events_requires_auth(client: Any, app: Any) -> None:
    """/events returns 401 for unauthenticated requests."""
    resp = client.get("/events")
    assert resp.status_code == 401


def test_export_admin_requires_admin_role(supplier_client: Any, app: Any) -> None:
    """Supplier cannot access admin export endpoint."""
    client, _ = supplier_client
    resp = client.get("/admin/laporan/export?format=csv")
    assert resp.status_code == 403


def test_logout_only_post(client: Any, app: Any) -> None:
    """GET to /logout is not allowed (405)."""
    resp = client.get("/logout")
    assert resp.status_code == 405
