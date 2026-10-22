"""Main application routes: landing page, health check, and authenticated impact dashboard."""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models import City, Organization
from app.services import claim_service, impact

bp: Blueprint = Blueprint("main", __name__)

LANDING_FEATURES = [
    {
        "icon": "board",
        "title": "Papan Surplus",
        "body": "Donor menayangkan kelebihan pangan, penerima menyaring per kota dan status lalu mengklaim.",
    },
    {
        "icon": "clock",
        "title": "Pelacakan Kedaluwarsa",
        "body": "Peringatan H-3 dan H-1 beserta saran FEFO agar stok terpakai sebelum dibuang.",
    },
    {
        "icon": "chart",
        "title": "Laporan Dampak",
        "body": "Grafik tren harian, kontribusi per kategori, dan sebaran wilayah dalam satu dasbor.",
    },
    {
        "icon": "leaf",
        "title": "Jejak Karbon",
        "body": "Setiap paket yang terselamatkan dihitung CO₂e yang dicegah berdasar faktor emisi.",
    },
]

LANDING_STEPS = [
    {"number": "1", "title": "Daftar organisasi", "body": "Donor atau penerima mendaftar dan memilih peran."},
    {"number": "2", "title": "Sebar atau klaim surplus", "body": "Posting pangan berlebih atau klaim yang sesuai kebutuhan."},
    {"number": "3", "title": "Ambil dan catat dampak", "body": "Barang diambil, dampak terhitung otomatis di dasbor."},
]


@bp.get("/health")
def health() -> Response:
    """Liveness probe used by container health checks."""
    return jsonify(status="ok")


@bp.get("/")
def landing() -> str:
    """Render the public landing page with live statistics."""
    kpis = impact.calculate_impact_kpis()
    kg_saved = float(kpis["kg_saved"])
    ton_saved = kg_saved / 1000.0 if kg_saved >= 1000 else kg_saved

    org_count = Organization.query.count()
    city_count = db.session.query(db.func.count(db.func.distinct(Organization.city_id))).scalar() or 0

    stats = [
        {"value": f"{ton_saved:.0f} ton" if kg_saved >= 1000 else f"{kg_saved:.0f} kg", "label": "Pangan terselamatkan"},
        {"value": f"{org_count:,}".replace(",", "."), "label": "Organisasi aktif"},
        {"value": f"{city_count} kota", "label": "Jangkauan layanan"},
    ]

    return render_template(
        "landing.html",
        layout="public",
        stats=stats,
        features=LANDING_FEATURES,
        steps=LANDING_STEPS,
    )


@bp.get("/dashboard")
@login_required
def dashboard() -> str:
    """Render the authenticated impact dashboard with live KPI cards and Chart.js charts."""
    kpis = impact.get_dashboard_kpis()
    trend = impact.get_daily_rescued_trend(days=14)
    kategori = impact.get_category_distribution()
    wilayah = impact.get_regional_distribution()
    recent_claims = claim_service.get_recent_claims(limit=5)

    return render_template(
        "dashboard.html",
        kpis=kpis,
        trend=trend,
        kategori=kategori,
        wilayah=wilayah,
        claims=recent_claims,
    )
