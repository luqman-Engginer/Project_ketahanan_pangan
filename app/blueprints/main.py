"""Landing page, health check, and role-based dashboard routing."""
from __future__ import annotations

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.services import impact, surplus_service
from app.utils.decorators import role_required

bp: Blueprint = Blueprint("main", __name__)

LANDING_FEATURES = [
    {"icon": "board", "title": "Pasokan terverifikasi", "body": "Supplier mengirim pasokan pangan surplus dan admin meninjau kelayakannya sebelum tampil."},
    {"icon": "clock", "title": "Stok & kedaluwarsa", "body": "Catat stok, pantau tanggal kedaluwarsa, dan ubah stok berlebih menjadi pasokan."},
    {"icon": "chart", "title": "Laporan dampak", "body": "Pantau pangan terselamatkan, nilai pangan, porsi, dan emisi yang dicegah."},
    {"icon": "leaf", "title": "Jejak karbon", "body": "Setiap kilogram pangan terselamatkan dihitung menggunakan faktor emisi kategori."},
]

LANDING_STEPS = [
    {"number": "1", "title": "Daftar sebagai supplier", "body": "Buat akun supplier untuk organisasi Anda."},
    {"number": "2", "title": "Kirim pasokan", "body": "Catat pangan surplus lengkap dengan kategori, berat, dan batas pengambilan."},
    {"number": "3", "title": "Tinjau dan ukur dampak", "body": "Admin memverifikasi pasokan; dampak dihitung dari pasokan yang disetujui."},
]


@bp.get("/health")
def health() -> Response:
    """Liveness probe used by container health checks."""
    return jsonify(status="ok")


@bp.get("/")
def landing() -> str:
    """Render the public landing page without live database statistics."""
    return render_template("landing.html", layout="public", features=LANDING_FEATURES, steps=LANDING_STEPS)


@bp.get("/dashboard")
@login_required
def dashboard() -> Response:
    """Redirect authenticated users to their role-specific dashboard."""
    if current_user.role == "admin":
        return redirect(url_for("admin.index"))
    if current_user.role == "supplier":
        return redirect(url_for("main.supplier_dashboard"))
    abort(403)


@bp.get("/supplier")
@login_required
@role_required("supplier")
def supplier_dashboard() -> str:
    """Render the supplier dashboard scoped to the user's organization."""
    org_id = current_user.org_id
    if not org_id:
        abort(403, description="Akun Anda belum terhubung dengan organisasi supplier.")
    return render_template(
        "supplier/dashboard.html",
        kpis=impact.get_dashboard_kpis(org_id=org_id),
        trend=impact.get_daily_rescued_trend(days=14, org_id=org_id),
        kategori=impact.get_category_distribution(org_id=org_id),
        review_counts=impact.get_review_counts(org_id=org_id),
        recent_listings=surplus_service.get_surplus_listings(org_id=org_id)[:5],
        organization=current_user.organization,
    )
