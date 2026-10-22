"""Inventory management and FEFO tracking services."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func

from app.extensions import db
from app.models import FoodCategory, InventoryItem, Organization, SurplusListing
from app.services import audit_service, realtime, surplus_service


def _map_expiry_status(days_left: int) -> str:
    """Map remaining days to badge category."""
    if days_left < 0:
        return "kedaluwarsa"
    if days_left <= 1:
        return "h1"
    if days_left <= 3:
        return "h3"
    return "aman"


def get_inventory_items(
    org_id: Optional[int] = None,
    status_filter: Optional[str] = "semua",
    search_query: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieve inventory items ordered by FEFO (nearest expiry first).

    Args:
        org_id: Organization ID to restrict items (multi-tenant isolation).
        status_filter: Filter key ('semua', 'h1', 'h3', 'kedaluwarsa').
        search_query: Search term for item name or category.

    Returns:
        List of formatted item dictionaries.
    """
    today = date.today()
    query = (
        db.session.query(InventoryItem, FoodCategory.name.label("category_name"), Organization.name.label("org_name"))
        .join(FoodCategory, InventoryItem.category_id == FoodCategory.id)
        .join(Organization, InventoryItem.org_id == Organization.id)
    )

    if org_id is not None:
        query = query.filter(InventoryItem.org_id == org_id)

    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(
            (InventoryItem.name.ilike(term)) | (FoodCategory.name.ilike(term))
        )

    # Order by FEFO: nearest expiration date first
    items = query.order_by(InventoryItem.expires_on.asc()).all()

    formatted: list[dict[str, Any]] = []
    for item, cat_name, org_name in items:
        days_left = (item.expires_on - today).days
        status = _map_expiry_status(days_left)

        if status_filter and status_filter != "semua" and status != status_filter:
            continue

        days_label = "Lewat" if days_left < 0 else ("Hari ini" if days_left == 0 else f"H-{days_left}")
        formatted.append(
            {
                "id": item.id,
                "name": item.name,
                "category": cat_name,
                "category_id": item.category_id,
                "qty": f"{item.qty:g}",
                "unit": item.unit,
                "expires_on": item.expires_on.strftime("%d %b %Y"),
                "expires_raw": item.expires_on.isoformat(),
                "days_left": days_left,
                "days_label": days_label,
                "status": status,
                "org": org_name,
                "org_id": item.org_id,
                "cost_per_unit": float(item.cost_per_unit),
            }
        )
    return formatted


def get_inventory_item(item_id: int, org_id: int) -> InventoryItem:
    """Fetch one inventory item ensuring it belongs to the owning organization.

    Args:
        item_id: Primary key of the inventory item.
        org_id: Organization that must own the item.

    Returns:
        The InventoryItem instance.

    Raises:
        PermissionError: If the item belongs to another organization.
        LookupError: If the item does not exist.
    """
    item = db.session.get(InventoryItem, item_id)
    if item is None:
        raise LookupError("Item inventory tidak ditemukan.")
    if item.org_id != org_id:
        raise PermissionError("Anda tidak berhak mengubah item milik organisasi lain.")
    return item


def update_inventory_item(
    item_id: int,
    org_id: int,
    name: str,
    category_id: int,
    qty: Decimal,
    unit: str,
    expires_on: date,
    cost_per_unit: Decimal = Decimal("0"),
) -> InventoryItem:
    """Update an inventory item owned by the given organization.

    Args:
        item_id: Primary key of the item to update.
        org_id: Organization that must own the item.
        name: New item name.
        category_id: New food category id.
        qty: New stock quantity.
        unit: New unit of measure.
        expires_on: New expiry date.
        cost_per_unit: New cost per unit.

    Returns:
        The updated InventoryItem instance.

    Raises:
        PermissionError: If the item belongs to another organization.
        LookupError: If the item does not exist.
    """
    item = get_inventory_item(item_id, org_id)
    item.name = name.strip()
    item.category_id = category_id
    item.qty = qty
    item.unit = unit.strip()
    item.expires_on = expires_on
    item.cost_per_unit = cost_per_unit
    db.session.commit()
    audit_service.log_action("UPDATE_INVENTORY_ITEM", "inventory_item", item_id)
    _announce_expiry(item)
    return item


def delete_inventory_item(item_id: int, org_id: int) -> None:
    """Delete an inventory item owned by the given organization.

    Args:
        item_id: Primary key of the item to delete.
        org_id: Organization that must own the item.

    Raises:
        PermissionError: If the item belongs to another organization.
        LookupError: If the item does not exist.
    """
    item = get_inventory_item(item_id, org_id)
    db.session.delete(item)
    db.session.commit()
    audit_service.log_action("DELETE_INVENTORY_ITEM", "inventory_item", item_id)


def get_category_choices() -> list[dict[str, Any]]:
    """Return all food categories as id/label pairs for form selects."""
    rows = db.session.query(FoodCategory.id, FoodCategory.name).order_by(FoodCategory.id.asc()).all()
    return [{"id": cat_id, "name": name} for cat_id, name in rows]


def get_inventory_kpis(org_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Calculate summary KPIs for inventory stock."""
    today = date.today()
    h3_date = today + timedelta(days=3)

    base_query = db.session.query(InventoryItem)
    if org_id:
        base_query = base_query.filter(InventoryItem.org_id == org_id)

    total_items = base_query.count()

    hampir_exp = base_query.filter(
        InventoryItem.expires_on >= today,
        InventoryItem.expires_on <= h3_date,
    ).count()

    sudah_exp = base_query.filter(InventoryItem.expires_on < today).count()

    # Sum of stock for items with unit 'kg'
    total_stok = (
        base_query.filter(InventoryItem.unit == "kg")
        .with_entities(func.coalesce(func.sum(InventoryItem.qty), Decimal("0")))
        .scalar()
        or Decimal("0")
    )

    return [
        {
            "label": "Item terpantau",
            "value": str(total_items),
            "unit": "item",
            "delta": "+2 minggu ini",
            "delta_up": True,
            "icon": "package",
        },
        {
            "label": "Hampir kedaluwarsa",
            "value": str(hampir_exp),
            "unit": "item",
            "delta": "Perlu prioritas FEFO",
            "delta_up": False,
            "icon": "clipboard",
        },
        {
            "label": "Sudah kedaluwarsa",
            "value": str(sudah_exp),
            "unit": "item",
            "delta": "Catat ke Waste Log",
            "delta_up": False,
            "icon": "cloud",
        },
        {
            "label": "Total stok",
            "value": f"{float(total_stok):g}",
            "unit": "kg",
            "delta": "+8,5%",
            "delta_up": True,
            "icon": "leaf",
        },
    ]


def create_inventory_item(
    org_id: int,
    name: str,
    category_id: int,
    qty: Decimal,
    unit: str,
    expires_on: date,
    cost_per_unit: Decimal = Decimal("0"),
) -> InventoryItem:
    """Create a new inventory item for an organization."""
    item = InventoryItem(
        org_id=org_id,
        category_id=category_id,
        name=name.strip(),
        qty=qty,
        unit=unit.strip(),
        expires_on=expires_on,
        cost_per_unit=cost_per_unit,
    )
    db.session.add(item)
    db.session.commit()
    audit_service.log_action("CREATE_INVENTORY_ITEM", "inventory_item", item.id)
    _announce_expiry(item)
    return item


def _announce_expiry(item: InventoryItem) -> None:
    """Emit an ``expiry_alert`` event when a stock item enters the alert window.

    Args:
        item: The persisted inventory item.
    """
    category = db.session.get(FoodCategory, item.category_id)
    organization = db.session.get(Organization, item.org_id)
    realtime.alert_expiring_item(
        item,
        category_name=category.name if category else "-",
        org_name=organization.name if organization else "-",
    )


def convert_inventory_to_surplus(
    item_id: int,
    org_id: int,
    pickup_before: datetime,
    notes: Optional[str] = None,
) -> SurplusListing:
    """Convert an expiring inventory item directly into a surplus food listing."""
    item = InventoryItem.query.filter_by(id=item_id, org_id=org_id).first_or_404()
    org = Organization.query.get_or_404(org_id)

    qty_kg = item.qty if item.unit == "kg" else item.qty * Decimal("0.4")

    listing = SurplusListing(
        org_id=org_id,
        category_id=item.category_id,
        title=f"Surplus: {item.name}",
        qty=item.qty,
        unit=item.unit,
        qty_kg=qty_kg,
        pickup_before=pickup_before,
        city_id=org.city_id,
        notes=notes or f"Dialihkan dari stok gudang menjelang batas kedaluwarsa ({item.expires_on}).",
        status="available",
    )
    db.session.add(listing)
    # Remove from inventory or deduct
    db.session.delete(item)
    db.session.commit()
    audit_service.log_action("CONVERT_TO_SURPLUS", "surplus_listing", listing.id)

    surplus_service.announce_listing(listing)
    return listing

