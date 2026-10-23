"""Waste log routes: capture form + table of wasted food using real database entries."""
from __future__ import annotations

from typing import Any, Union

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.schemas.payloads import WasteLogCreateSchema
from app.services import waste_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("waste", __name__, url_prefix="/supplier/limbah")


@bp.route("", methods=["GET", "POST"])
@login_required
@role_required("supplier")
def waste_page() -> Union[str, Response, tuple[dict[str, Any], int]]:
    """Render waste log table; POST records or updates a waste entry."""
    org_id = current_user.org_id
    is_admin = current_user.role == "admin"
    scope_org_id = None if is_admin else org_id

    # Handle JSON API create request
    if request.is_json and request.method == "POST":
        try:
            payload = WasteLogCreateSchema(**request.get_json())
            entry = waste_service.add_waste_log(
                org_id=org_id,
                category_id=payload.category_id,
                qty_kg=payload.qty_kg,
                reason=payload.reason,
                logged_on=payload.logged_on,
            )
            return jsonify(message="Log limbah berhasil dicatat", id=entry.id), 201
        except Exception as err:
            return jsonify(error=str(err)), 400

    if request.method == "POST":
        action = request.form.get("action", "create")
        cat_name = (request.form.get("category") or "").strip()
        qty_kg_str = (request.form.get("qty_kg") or "").strip()
        reason = (request.form.get("reason") or "").strip()

        try:
            if action == "update":
                log_id = int(request.form.get("log_id", "0"))
                entry = waste_service.update_waste_log(
                    log_id=log_id,
                    org_id=org_id,
                    category_id=waste_service.resolve_category_by_name(cat_name).id,
                    qty_kg=waste_service.parse_positive_decimal(qty_kg_str, "Jumlah"),
                    reason=reason,
                )
                flash(f"Log limbah #{entry.id} berhasil diperbarui.", "success")
            elif action == "delete":
                log_id = int(request.form.get("log_id", "0"))
                waste_service.delete_waste_log(log_id=log_id, org_id=org_id)
                flash("Log limbah berhasil dihapus.", "success")
            elif cat_name and qty_kg_str and reason:
                waste_service.add_waste_log(
                    org_id=org_id,
                    category_id=waste_service.resolve_category_by_name(cat_name).id,
                    qty_kg=waste_service.parse_positive_decimal(qty_kg_str, "Jumlah"),
                    reason=reason,
                )
                flash("Log limbah berhasil dicatat ke database.", "success")
        except (ValueError, PermissionError, LookupError) as err:
            flash(f"Gagal memproses log limbah: {err}", "danger")

    categories = waste_service.get_category_names()
    entries = waste_service.get_waste_logs(org_id=scope_org_id)
    kpis = waste_service.get_waste_summary(org_id=scope_org_id)
    editing_id = request.args.get("edit")

    return render_template(
        "waste/index.html",
        entries=entries,
        kpis=kpis,
        categories=categories,
        reasons=waste_service.WASTE_REASONS,
        editing=editing_id,
        form=request.form if request.method == "POST" else None,
    )


@bp.post("/<int:log_id>/delete")
@login_required
@role_required("supplier")
def delete_log(log_id: int) -> Response:
    """Delete a waste log entry owned by the current supplier organization."""
    try:
        waste_service.delete_waste_log(log_id=log_id, org_id=current_user.org_id)
        flash("Log limbah berhasil dihapus.", "success")
    except (PermissionError, LookupError) as err:
        flash(str(err), "danger")

    return redirect(url_for("waste.waste_page"))

