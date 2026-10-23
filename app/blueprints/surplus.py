"""Supplier surplus listing routes."""
from __future__ import annotations

from typing import Any, Union

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.forms.surplus import SurplusListingForm
from app.schemas.payloads import SurplusListingCreateSchema
from app.services import surplus_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("surplus", __name__, url_prefix="/supplier/pasokan")


def _require_supplier_org() -> int:
    """Return the current supplier's organization id or abort with 403."""
    if not current_user.org_id:
        abort(403, description="Akun Anda belum terhubung dengan organisasi supplier.")
    return current_user.org_id


@bp.get("/")
@login_required
@role_required("supplier")
def surplus_board() -> str:
    """Render the supplier's own pasokan list."""
    org_id = _require_supplier_org()
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    status = request.args.get("status", "").strip()
    listings = surplus_service.get_surplus_listings(
        org_id=org_id,
        search_query=search or None,
        category_name=category or None,
        city_name=city or None,
        review_status=status or None,
    )
    return render_template(
        "surplus/board.html",
        listings=listings,
        categories=surplus_service.get_category_options(),
        cities=surplus_service.get_city_options(),
        search_query=search,
        selected_category=category,
        selected_city=city,
        selected_status=status or "semua",
        can_create=True,
        create_form=SurplusListingForm(),
        mode="supplier",
    )


@bp.get("/<int:listing_id>")
@login_required
@role_required("supplier")
def surplus_detail(listing_id: int) -> str:
    """Render one of the supplier's own listings."""
    org_id = _require_supplier_org()
    listing = surplus_service.get_surplus_detail(listing_id, org_id=org_id)
    if listing is None:
        abort(404)
    edit_form = SurplusListingForm()
    edit_form.title.data = listing["title"]
    edit_form.qty.data = listing["qty"]
    edit_form.unit.data = listing["unit"]
    edit_form.qty_kg.data = listing["qty_kg"]
    edit_form.pickup_before.data = listing["raw_pickup_before"]
    edit_form.city_id.data = listing["city_id"]
    edit_form.category_id.data = listing["category_id"]
    edit_form.notes.data = listing["notes"]
    return render_template(
        "surplus/detail.html",
        listing=listing,
        can_manage=True,
        edit_form=edit_form,
        categories=surplus_service.get_category_options(),
        cities=surplus_service.get_city_options(),
        mode="supplier",
    )


@bp.post("/")
@login_required
@role_required("supplier")
def create_listing() -> Union[Response, tuple[dict[str, Any], int]]:
    """Publish a new pending pasokan listing."""
    org_id = _require_supplier_org()
    if request.is_json:
        try:
            payload = SurplusListingCreateSchema(**request.get_json())
            listing = surplus_service.create_surplus_listing(
                org_id=org_id,
                category_id=payload.category_id,
                title=payload.title,
                qty=payload.qty,
                unit=payload.unit,
                qty_kg=payload.qty_kg,
                pickup_before=payload.pickup_before,
                city_id=payload.city_id,
                notes=payload.notes,
                actor_user_id=current_user.id,
            )
            return jsonify(message="Pasokan berhasil dikirim untuk review", id=listing.id, review_status=listing.review_status), 201
        except Exception as err:
            return jsonify(error=str(err)), 400

    form = SurplusListingForm()
    if form.validate_on_submit():
        listing = surplus_service.create_surplus_listing(
            org_id=org_id,
            category_id=form.category_id.data,
            title=form.title.data,
            qty=form.qty.data,
            unit=form.unit.data,
            qty_kg=form.qty_kg.data,
            pickup_before=form.pickup_before.data,
            city_id=form.city_id.data,
            notes=form.notes.data,
            actor_user_id=current_user.id,
        )
        flash("Pasokan berhasil dikirim dan menunggu review admin.", "success")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing.id))

    flash("Gagal mengirim pasokan. Silakan periksa formulir.", "danger")
    return redirect(url_for("surplus.surplus_board"))


@bp.post("/<int:listing_id>/update")
@login_required
@role_required("supplier")
def update_listing(listing_id: int) -> Response:
    """Update an owned listing and reset its review status to pending."""
    org_id = _require_supplier_org()
    form = SurplusListingForm()
    if form.validate_on_submit():
        try:
            surplus_service.update_surplus_listing(
                listing_id=listing_id,
                org_id=org_id,
                category_id=form.category_id.data,
                title=form.title.data,
                qty=form.qty.data,
                unit=form.unit.data,
                qty_kg=form.qty_kg.data,
                pickup_before=form.pickup_before.data,
                city_id=form.city_id.data,
                notes=form.notes.data,
            )
        except (PermissionError, LookupError) as err:
            flash(str(err), "danger")
            return redirect(url_for("surplus.surplus_board"))
    else:
        flash("Gagal memperbarui pasokan. Periksa formulir.", "danger")
    return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))


@bp.post("/<int:listing_id>/delete")
@login_required
@role_required("supplier")
def delete_listing(listing_id: int) -> Response:
    """Delete an owned listing that has not been approved."""
    org_id = _require_supplier_org()
    try:
        surplus_service.delete_surplus_listing(listing_id=listing_id, org_id=org_id)
        flash("Pasokan berhasil dihapus.", "success")
        return redirect(url_for("surplus.surplus_board"))
    except (PermissionError, LookupError, ValueError) as err:
        flash(str(err), "danger")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))
