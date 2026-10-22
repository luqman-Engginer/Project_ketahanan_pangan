"""Admin blueprint for organization verification and master impact factor management."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Union

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import admin_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@login_required
@role_required("admin")
def index() -> Union[str, Response]:
    """Admin dashboard: organization verification and impact factor management."""
    organizations = admin_service.list_organizations()
    impact_factors = admin_service.get_impact_factors()

    if request.is_json:
        return jsonify(
            organizations=organizations,
            impact_factors=impact_factors,
        )

    return render_template(
        "admin/index.html",
        organizations=organizations,
        impact_factors=impact_factors,
    )


@bp.post("/verify/<int:org_id>")
@login_required
@role_required("admin")
def verify_organization(org_id: int) -> Response:
    """Verify an organization to grant verified donor/receiver badge."""
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
        err_msg = "Nilai faktor dampak harus berupa angka yang valid."
        if request.is_json:
            return jsonify(error=err_msg), 400
        flash(err_msg, "danger")
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
