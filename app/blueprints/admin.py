"""Administrator dashboard, pasokan review, and read-only monitoring routes."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.schemas.payloads import SurplusReviewSchema
from app.services import admin_service, impact, inventory_service, surplus_service, waste_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@login_required
@role_required("admin")
def index() -> Union[str, Response]:
    """Admin dashboard with the pending review queue and platform KPIs."""
    organizations = admin_service.list_organizations()
    impact_factors = admin_service.get_impact_factors()
    pending = surplus_service.get_surplus_listings(review_status="pending")
    if request.is_json:
        return jsonify(organizations=organizations, impact_factors=impact_factors, pending=pending)
    return render_template(
        "admin/index.html",
        organizations=organizations,
        impact_factors=impact_factors,
        pending=pending[:8],
        kpis=impact.get_dashboard_kpis(),
        review_counts=impact.get_review_counts(),
        trend=impact.get_daily_rescued_trend(days=14),
        kategori=impact.get_category_distribution(),
    )


@bp.get("/pasokan")
@login_required
@role_required("admin")
def pasokan_board() -> str:
    """List all supplier pasokan listings for review."""
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    status = request.args.get("status", "").strip()
    listings = surplus_service.get_surplus_listings(
        org_id=None,
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
        can_create=False,
        create_form=None,
        mode="admin",
    )


@bp.get("/pasokan/<int:listing_id>")
@login_required
@role_required("admin")
def pasokan_detail(listing_id: int) -> str:
    """Render a listing for administrator review."""
    listing = surplus_service.get_surplus_detail(listing_id)
    if listing is None:
        abort(404)
    return render_template("admin/pasokan_detail.html", listing=listing)


@bp.post("/pasokan/<int:listing_id>/review")
@login_required
@role_required("admin")
def review_pasokan(listing_id: int) -> Response:
    """Approve or reject a supplier pasokan listing."""
    if request.is_json:
        try:
            payload = SurplusReviewSchema(**request.get_json())
            status, note = payload.status, payload.note
        except Exception as err:
            return jsonify(error=str(err)), 400
    else:
        status = (request.form.get("status") or "").strip()
        note = (request.form.get("note") or "").strip() or None
        if status not in {"approved", "rejected"}:
            flash("Keputusan review tidak valid.", "danger")
            return redirect(url_for("admin.pasokan_detail", listing_id=listing_id))

    try:
        surplus_service.review_listing(
            listing_id=listing_id,
            status=status,
            note=note,
            admin_user_id=current_user.id,
            reviewer_name=current_user.name,
        )
    except (LookupError, ValueError) as err:
        if request.is_json:
            return jsonify(error=str(err)), 404
        flash(str(err), "danger")
        return redirect(url_for("admin.pasokan_detail", listing_id=listing_id))

    listing = surplus_service.get_surplus_detail(listing_id)
    if request.headers.get("HX-Request") == "true":
        return Response(render_template("admin/_review_row.html", listing=listing, oob=True))
    if request.is_json:
        return jsonify(message="Review pasokan tersimpan.", review_status=listing["review_status"])
    flash(f"Pasokan {listing['title']} berhasil {listing['review_label'].lower()}.", "success")
    return redirect(request.referrer or url_for("admin.pasokan_board"))


@bp.get("/stok")
@login_required
@role_required("admin")
def inventory_monitor() -> str:
    """Show all supplier inventory in read-only mode."""
    items = inventory_service.get_inventory_items(org_id=None)
    return render_template(
        "inventory/index.html",
        items=items,
        kpis=inventory_service.get_inventory_kpis(org_id=None),
        categories=inventory_service.get_category_choices(),
        filters=[],
        active_filter="semua",
        search_query="",
        editing=None,
        read_only=True,
    )


@bp.get("/limbah")
@login_required
@role_required("admin")
def waste_monitor() -> str:
    """Show all supplier waste logs in read-only mode."""
    return render_template(
        "waste/index.html",
        entries=waste_service.get_waste_logs(org_id=None),
        kpis=waste_service.get_waste_summary(org_id=None),
        categories=waste_service.get_category_names(),
        reasons=waste_service.WASTE_REASONS,
        editing=None,
        form=None,
        read_only=True,
    )


@bp.post("/verify/<int:org_id>")
@login_required
@role_required("admin")
def verify_organization(org_id: int) -> Response:
    """Verify a supplier organization."""
    try:
        org = admin_service.verify_organization(org_id, admin_user_id=current_user.id)
        if request.is_json:
            return jsonify(message=f"Organisasi {org.name} berhasil diverifikasi."), 200
        flash(f"Organisasi {org.name} telah diverifikasi.", "success")
    except Exception as err:
        if request.is_json:
            return jsonify(error=str(err)), 400
        flash(f"Gagal verifikasi: {err}", "danger")
    return redirect(request.referrer or url_for("admin.index"))


@bp.post("/impact-factors/<int:category_id>")
@login_required
@role_required("admin")
def update_impact_factor(category_id: int) -> Response:
    """Update price and emission multiplier factors for a category."""
    raw_price = request.form.get("price_per_kg") or (request.get_json(silent=True) or {}).get("price_per_kg")
    raw_co2e = request.form.get("co2e_per_kg") or (request.get_json(silent=True) or {}).get("co2e_per_kg")
    try:
        price = Decimal(str(raw_price))
        co2e = Decimal(str(raw_co2e))
    except (InvalidOperation, TypeError):
        message = "Nilai faktor dampak harus berupa angka yang valid."
        if request.is_json:
            return jsonify(error=message), 400
        flash(message, "danger")
        return redirect(url_for("admin.index"))
    try:
        factor = admin_service.update_impact_factor(
            category_id=category_id,
            price_per_kg=price,
            co2e_per_kg=co2e,
            admin_user_id=current_user.id,
        )
        if request.is_json:
            return jsonify(message="Faktor dampak berhasil diperbarui", factor_id=factor.id), 200
        flash("Faktor dampak berhasil diperbarui.", "success")
    except Exception as err:
        if request.is_json:
            return jsonify(error=str(err)), 400
        flash(f"Gagal memperbarui faktor dampak: {err}", "danger")
    return redirect(url_for("admin.index"))


@bp.get("/audit-logs")
@login_required
@role_required("admin")
def audit_logs() -> Union[str, Response]:
    """List recent administrative audit log entries."""
    logs = admin_service.get_audit_logs()
    if request.is_json:
        return jsonify(logs=logs)
    return render_template("admin/audit_logs.html", logs=logs)
