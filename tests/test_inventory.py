"""Tests for inventory CRUD with organization isolation."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.extensions import db
from app.models import InventoryItem
from tests.conftest import make_org


def test_supplier_can_create_inventory_item(supplier_client: Any, app: Any) -> None:
    """A supplier records a stock item bound to its own organization."""
    client, org = supplier_client
    resp = client.post(
        "/supplier/stok/",
        data={
            "name": "Beras Premium",
            "category_id": "1",
            "qty": "10",
            "unit": "kg",
            "expires_on": "2030-01-01",
            "cost_per_unit": "15000",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    item = InventoryItem.query.filter_by(name="Beras Premium").first()
    assert item is not None
    assert item.org_id == org.id


def test_inventory_listing_is_org_scoped(supplier_client: Any, app: Any) -> None:
    """A supplier does not see another organization's stock."""
    client, org = supplier_client
    other = make_org("Supplier Lain")
    db.session.add(
        InventoryItem(
            org_id=other.id,
            category_id=1,
            name="Barang Lain",
            qty=5,
            unit="kg",
            expires_on=date(2030, 1, 1),
        )
    )
    db.session.commit()

    resp = client.get("/supplier/stok/")
    assert b"Barang Lain" not in resp.data


def test_update_and_delete_require_ownership(supplier_client: Any, app: Any) -> None:
    """Updating or deleting another org's item does not mutate it."""
    client, org = supplier_client
    other = make_org("Supplier Asing")
    item = InventoryItem(
        org_id=other.id,
        category_id=1,
        name="Milik Lain",
        qty=5,
        unit="kg",
        expires_on=date(2030, 1, 1),
    )
    db.session.add(item)
    db.session.commit()

    client.post(
        f"/supplier/stok/{item.id}/update",
        data={
            "name": "Diretas",
            "category_id": "1",
            "qty": "1",
            "unit": "kg",
            "expires_on": "2030-01-01",
            "cost_per_unit": "1",
        },
        follow_redirects=True,
    )
    client.post(f"/supplier/stok/{item.id}/delete", follow_redirects=True)
    db.session.refresh(item)
    assert item.name == "Milik Lain"
    assert InventoryItem.query.get(item.id) is not None
