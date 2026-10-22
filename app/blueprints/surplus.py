"""Surplus board routes: browse, filter, detail views, and discussion comments."""
from __future__ import annotations

from typing import Any, Union

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.forms.activity import CommentForm
from app.forms.surplus import SurplusListingForm
from app.schemas.payloads import CommentCreateSchema, SurplusListingCreateSchema
from app.services import surplus_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("surplus", __name__, url_prefix="/surplus")


def _require_donor_org() -> int:
    """Return the current donor's organization id.

    Returns:
        Organization id bound to the current user.

    Raises:
        PermissionError: If the user has no linked organization.
    """
    if not current_user.org_id:
        raise PermissionError("User tidak terhubung dengan organisasi donor.")
    return current_user.org_id


@bp.get("/")
def surplus_board() -> str:
    """Render the surplus board with server-side search and filter queries."""
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    status = request.args.get("status", "").strip()

    listings = surplus_service.get_surplus_listings(
        search_query=search if search else None,
        category_name=category if category else None,
        city_name=city if city else None,
        status_filter=status if status else None,
    )
    categories = surplus_service.get_category_options()
    cities = surplus_service.get_city_options()

    return render_template(
        "surplus/board.html",
        listings=listings,
        categories=categories,
        cities=cities,
        search_query=search,
        selected_category=category,
        selected_city=city,
        selected_status=status or "semua",
        can_create=current_user.is_authenticated and current_user.role in {"donor", "admin"},
        create_form=SurplusListingForm(),
    )


@bp.get("/<int:listing_id>")
def surplus_detail(listing_id: int) -> str:
    """Render one surplus listing detail page with live discussions."""
    listing = surplus_service.get_surplus_detail(listing_id)
    if listing is None:
        abort(404)

    is_owner = (
        current_user.is_authenticated
        and current_user.org_id is not None
        and current_user.org_id == listing["donor_id"]
    )
    can_manage = current_user.is_authenticated and (is_owner or current_user.role == "admin")

    comment_form = CommentForm()
    edit_form = SurplusListingForm() if can_manage else None
    if edit_form is not None:
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
        comments=listing["comments"],
        comment_form=comment_form,
        can_manage=can_manage,
        edit_form=edit_form,
        categories=surplus_service.get_category_options() if can_manage else [],
        cities=surplus_service.get_city_options() if can_manage else [],
    )


@bp.post("/")
@login_required
@role_required("donor", "admin")
def create_listing() -> Union[Response, tuple[dict[str, Any], int]]:
    """Publish a new surplus food listing."""
    try:
        org_id = _require_donor_org()
    except PermissionError as err:
        return jsonify(error=str(err)), 400

    # Handle JSON API request
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
            return jsonify(message="Listing surplus berhasil dibuat", id=listing.id), 201
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
        flash("Listing surplus berhasil dipublikasikan!", "success")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing.id))

    flash("Gagal mempublikasikan surplus. Silakan periksa formulir.", "danger")
    return redirect(url_for("surplus.surplus_board"))


@bp.post("/<int:listing_id>/update")
@login_required
@role_required("donor", "admin")
def update_listing(listing_id: int) -> Response:
    """Update a surplus listing owned by the current donor organization."""
    try:
        org_id = _require_donor_org()
    except PermissionError as err:
        flash(str(err), "danger")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))

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
            flash("Listing surplus berhasil diperbarui.", "success")
        except (PermissionError, LookupError) as err:
            flash(str(err), "danger")
    else:
        flash("Gagal memperbarui surplus. Silakan periksa formulir.", "danger")

    return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))


@bp.post("/<int:listing_id>/delete")
@login_required
@role_required("donor", "admin")
def delete_listing(listing_id: int) -> Response:
    """Delete a surplus listing owned by the current donor organization."""
    try:
        org_id = _require_donor_org()
        surplus_service.delete_surplus_listing(listing_id=listing_id, org_id=org_id)
        flash("Listing surplus berhasil dihapus.", "success")
        return redirect(url_for("surplus.surplus_board"))
    except (PermissionError, LookupError, ValueError) as err:
        flash(str(err), "danger")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))


@bp.post("/<int:listing_id>/komentar")
@login_required
def post_comment(listing_id: int) -> Union[Response, tuple[dict[str, Any], int]]:
    """Post a discussion comment or Q&A on a surplus listing."""
    # Check if listing exists
    detail = surplus_service.get_surplus_detail(listing_id)
    if not detail:
        abort(404)

    # Handle JSON request
    if request.is_json:
        try:
            payload = CommentCreateSchema(**request.get_json())
            c = surplus_service.add_comment(
                listing_id=listing_id,
                user_id=current_user.id,
                body=payload.body,
                parent_id=payload.parent_id,
            )
            return jsonify(message="Komentar berhasil dikirim", id=c.id), 201
        except Exception as err:
            return jsonify(error=str(err)), 400

    body = (request.form.get("body") or "").strip()
    parent_id_val = request.form.get("parent_id")
    parent_id = int(parent_id_val) if parent_id_val and parent_id_val.isdigit() else None

    if body:
        surplus_service.add_comment(
            listing_id=listing_id,
            user_id=current_user.id,
            body=body,
            parent_id=parent_id,
        )
        flash("Komentar berhasil dikirim!", "success")
    else:
        flash("Isi komentar tidak boleh kosong.", "warning")

    return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))
