"""Public impact dashboard: aggregate sustainability numbers without authentication."""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, render_template

from app.extensions import limiter
from app.services import impact

bp: Blueprint = Blueprint("public", __name__)


@bp.get("/publik")
@bp.get("/publik/")
def public_dashboard() -> str:
    """Render the public sustainability dashboard backed by live SQL data."""
    data = impact.get_public_impact_data()
    return render_template(
        "public/dashboard.html",
        layout="public",
        kpis=data["kpis"],
        trend=data["trend"],
        ratio=data["ratio"],
        wilayah=data["wilayah"],
    )


@bp.get("/api/public/impact")
@bp.get("/publik/api/impact")
@limiter.limit("60 per minute")
def public_impact_api() -> Response:
    """Aggregate impact numbers as JSON (open data endpoint per PRD Section 4 & 5)."""
    data = impact.get_public_impact_data()
    return jsonify(
        organization_count=data["organization_count"],
        cities_covered=data["cities_covered"],
        total_rescued_kg=data["total_rescued_kg"],
        co2e_prevented_ton=data["co2e_prevented_ton"],
        rupiah_saved=data["rupiah_saved"],
        meals_provided=data["meals_provided"],
        monthly_rescued_kg=data["trend"],
        taken_vs_expired_pct=data["ratio"],
        regional_breakdown=data["wilayah"],
    )
