"""Report routes: date filter and aggregated metrics from live database queries."""
from __future__ import annotations

from typing import Optional

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.services import report_service

bp: Blueprint = Blueprint("report", __name__, url_prefix="/laporan")


@bp.get("/")
@login_required
def report_page() -> str:
    """Render the impact report page with live SQL aggregations.

    The page is restricted to the data the requester may see: administrators
    see every organization, donors and receivers only their own.
    """
    start_str = request.args.get("start", "").strip()
    end_str = request.args.get("end", "").strip()
    city_id: Optional[int] = None
    raw_city = (request.args.get("city_id") or "").strip()
    if raw_city:
        try:
            city_id = int(raw_city)
        except ValueError:
            city_id = None

    start_date = report_service.parse_date(start_str)
    end_date = report_service.parse_date(end_str)

    presets = report_service.get_report_range_presets()
    active_key = request.args.get("preset", "30")

    scope = report_service.build_scope(current_user.role, current_user.org_id, city_id)
    cities = report_service.list_cities()

    kpis = report_service.get_report_kpis(start_date=start_date, end_date=end_date, scope=scope)
    rekap = report_service.get_report_rekap(start_date=start_date, end_date=end_date, scope=scope)
    per_kategori = report_service.get_report_kategori(start_date=start_date, end_date=end_date, scope=scope)

    return render_template(
        "report/index.html",
        kpis=kpis,
        rekap=rekap,
        per_kategori=per_kategori,
        presets=presets,
        active_preset=active_key,
        start=start_str,
        end=end_str,
        cities=cities,
        city_id=city_id,
    )
