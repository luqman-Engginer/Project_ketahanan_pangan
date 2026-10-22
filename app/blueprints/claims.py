"""Claims lifecycle blueprint: claim surplus, update status workflow."""
from __future__ import annotations

from typing import Any, Union

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.schemas.payloads import ClaimStatusUpdateSchema
from app.services import claim_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("claims", __name__, url_prefix="/claims")


@bp.get("/")
@login_required
def list_claims() -> Union[str, Response]:
    """List claims relevant to the current organization role."""
    if not current_user.org_id and current_user.role != "admin":
        if request.is_json:
            return jsonify(claims=[]), 200
        flash("Akun Anda belum terhubung dengan organisasi mana pun.", "warning")
        return redirect(url_for("main.dashboard"))

    claims = claim_service.get_claims_for_user(
        org_id=current_user.org_id,
        role=current_user.role,
    )

    if request.is_json:
        return jsonify(claims=claims), 200

    return render_template("claims/index.html", claims=claims, role=current_user.role)


@bp.post("/")
@login_required
@role_required("receiver", "admin")
def create_claim() -> Union[Response, tuple[dict[str, Any], int]]:
    """Receiver claims an available surplus listing."""
    payload = request.get_json(silent=True) if request.is_json else request.form
    listing_id_val = payload.get("listing_id") if payload else None
    if not listing_id_val:
        return jsonify(error="ID listing surplus wajib diisi."), 400

    try:
        listing_id = int(listing_id_val)
        claim = claim_service.create_claim(
            listing_id=listing_id,
            receiver_org_id=current_user.org_id,
        )
        if request.is_json:
            return jsonify(message="Klaim berhasil dibuat", claim_id=claim.id), 201

        flash("Klaim berhasil dikirim! Menunggu konfirmasi dari donor.", "success")
        return redirect(url_for("claims.list_claims"))
    except (ValueError, PermissionError) as err:
        if request.is_json:
            return jsonify(error=str(err)), 400
        flash(str(err), "danger")
        return redirect(url_for("surplus.surplus_detail", listing_id=listing_id))


@bp.post("/<int:claim_id>/status")
@login_required
def update_status(claim_id: int) -> Union[Response, tuple[dict[str, Any], int]]:
    """Update status of a claim (approved, picked_up, cancelled)."""
    if request.is_json:
        try:
            payload = ClaimStatusUpdateSchema(**request.get_json())
            claim = claim_service.update_claim_status(
                claim_id=claim_id,
                new_status=payload.status,
                user_org_id=current_user.org_id,
                is_admin=(current_user.role == "admin"),
            )
            return jsonify(message="Status klaim berhasil diperbarui", status=claim.status), 200
        except Exception as err:
            return jsonify(error=str(err)), 400

    new_status = request.form.get("status", "").strip()
    try:
        claim_service.update_claim_status(
            claim_id=claim_id,
            new_status=new_status,
            user_org_id=current_user.org_id,
            is_admin=(current_user.role == "admin"),
        )
        flash(f"Status klaim berhasil diubah menjadi {new_status}.", "success")
    except Exception as err:
        flash(str(err), "danger")

    return redirect(url_for("claims.list_claims"))
