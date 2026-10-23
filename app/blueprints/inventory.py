"""Inventory tracker routes: FEFO ordering, expiry badges, and stock monitoring."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Union

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.forms.inventory import InventoryItemForm
from app.schemas.payloads import InventoryItemCreateSchema
from app.services import inventory_service, realtime
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("inventory", __name__, url_prefix="/supplier/stok")

_STATUS_FILTERS: dict[str, str] = {
    "semua": "Semua status",
    "h3": "H-3",
    "h1": "H-1",
    "kedaluwarsa": "Kedaluwarsa",
}


def _require_supplier_org() -> int:
    """Return the current supplier's organization id, or abort with 403.

    Returns:
        Organization id bound to the current user.

    Raises:
        PermissionError: If the user has no linked organization.
    """
    if not current_user.org_id:
        raise PermissionError("User tidak terhubung dengan organisasi supplier.")
    return current_user.org_id


@bp.get("/")
@login_required
@role_required("supplier")
def inventory_page() -> str:
    """Render the inventory table filtered by expiry status and search query."""
    active = request.args.get("status", "semua")
    search = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", "1") or 1))

    if active not in _STATUS_FILTERS:
        active = "semua"

    # Multi-tenant isolation: suppliers only see their own organization's stock
    org_id = current_user.org_id if current_user.role != "admin" else None

    items, pagination = inventory_service.get_inventory_items_paginated(
        org_id=org_id,
        status_filter=active,
        search_query=search if search else None,
        page=page,
        per_page=8,
    )
    kpis = inventory_service.get_inventory_kpis(org_id=org_id)
    categories = inventory_service.get_category_choices()
    realtime.scan_expiry_alerts()

    return render_template(
        "inventory/index.html",
        items=items,
        kpis=kpis,
        categories=categories,
        filters=[{"key": k, "label": v} for k, v in _STATUS_FILTERS.items()],
        active_filter=active,
        search_query=search,
        editing=request.args.get("edit"),
        pagination=pagination,
    )


@bp.post("/")
@login_required
@role_required("supplier")
def create_item() -> Union[Response, tuple[dict[str, Any], int]]:
    """Record a new inventory stock item."""
    try:
        org_id = _require_supplier_org()
    except PermissionError as err:
        return jsonify(error=str(err)), 400

    # Support JSON API payload
    if request.is_json:
        try:
            payload = InventoryItemCreateSchema(**request.get_json())
            item = inventory_service.create_inventory_item(
                org_id=org_id,
                name=payload.name,
                category_id=payload.category_id,
                qty=payload.qty,
                unit=payload.unit,
                expires_on=payload.expires_on,
                cost_per_unit=payload.cost_per_unit,
            )
            return jsonify(message="Item berhasil ditambahkan", id=item.id), 201
        except Exception as err:
            return jsonify(error=str(err)), 400

    form = InventoryItemForm()
    if form.validate_on_submit():
        try:
            inventory_service.create_inventory_item(
                org_id=org_id,
                name=form.name.data,
                category_id=form.category_id.data,
                qty=form.qty.data,
                unit=form.unit.data,
                expires_on=form.expires_on.data,
                cost_per_unit=form.cost_per_unit.data or Decimal("0"),
            )
            flash("Item berhasil dicatat ke stok inventory.", "success")
        except Exception as err:
            flash(f"Gagal menambahkan item: {err}", "danger")
    else:
        flash("Gagal menambahkan item. Periksa input formulir Anda.", "danger")

    return redirect(url_for("inventory.inventory_page"))


@bp.post("/<int:item_id>/update")
@login_required
@role_required("supplier")
def update_item(item_id: int) -> Response:
    """Update an inventory item owned by the current supplier organization."""
    try:
        org_id = _require_supplier_org()
    except PermissionError as err:
        flash(str(err), "danger")
        return redirect(url_for("inventory.inventory_page"))

    form = InventoryItemForm()
    if form.validate_on_submit():
        try:
            inventory_service.update_inventory_item(
                item_id=item_id,
                org_id=org_id,
                name=form.name.data,
                category_id=form.category_id.data,
                qty=form.qty.data,
                unit=form.unit.data,
                expires_on=form.expires_on.data,
                cost_per_unit=form.cost_per_unit.data or Decimal("0"),
            )
            flash("Item inventory berhasil diperbarui.", "success")
        except (PermissionError, LookupError) as err:
            flash(str(err), "danger")
    else:
        flash("Gagal memperbarui item. Periksa input formulir Anda.", "danger")

    return redirect(url_for("inventory.inventory_page"))


@bp.post("/<int:item_id>/delete")
@login_required
@role_required("supplier")
def delete_item(item_id: int) -> Response:
    """Delete an inventory item owned by the current supplier organization."""
    try:
        org_id = _require_supplier_org()
        inventory_service.delete_inventory_item(item_id=item_id, org_id=org_id)
        flash("Item inventory berhasil dihapus.", "success")
    except (PermissionError, LookupError) as err:
        flash(str(err), "danger")

    return redirect(url_for("inventory.inventory_page"))


@bp.post("/<int:item_id>/convert-surplus")
@login_required
@role_required("supplier")
def convert_to_surplus(item_id: int) -> Response:
    """Convert an expiring inventory stock item directly into a surplus food listing."""
    try:
        org_id = _require_supplier_org()
    except PermissionError as err:
        flash(str(err), "danger")
        return redirect(url_for("inventory.inventory_page"))

    pickup_before = datetime.utcnow() + timedelta(hours=24)

    try:
        listing = inventory_service.convert_inventory_to_surplus(
            item_id=item_id,
            org_id=org_id,
            pickup_before=pickup_before,
        )
        flash(f"Item berhasil dialihkan menjadi listing surplus #{listing.id}!", "success")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing.id))
    except Exception as e:
        flash(f"Gagal mengalihkan item ke surplus: {e}", "danger")
        return redirect(url_for("inventory.inventory_page"))

