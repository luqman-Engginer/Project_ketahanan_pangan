"""Role-separated impact report routes."""
from __future__ import annotations

from typing import Optional

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import report_service

bp: Blueprint = Blueprint("report", __name__)


def _render_report(role: str) -> str:
    """Render a report restricted to the authenticated role."""
    if current_user.role != role:
        abort(403)
    if role == "supplier" and not current_user.org_id:
        abort(403, description="Akun Anda belum terhubung dengan organisasi supplier.")

    raw_city = (request.args.get("city_id") or "").strip()
    try:
        city_id: Optional[int] = int(raw_city) if raw_city else None
    except ValueError:
        city_id = None

    start_str = request.args.get("start", "").strip()
    end_str = request.args.get("end", "").strip()
    start_date = report_service.parse_date(start_str)
    end_date = report_service.parse_date(end_str)
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    scope = report_service.build_scope(role, current_user.org_id, city_id)
    return render_template(
        "report/index.html",
        kpis=report_service.get_report_kpis(start_date, end_date, scope),
        rekap=report_service.get_report_rekap(start_date, end_date, scope),
        per_kategori=report_service.get_report_kategori(start_date, end_date, scope),
        presets=report_service.get_report_range_presets(),
        active_preset=request.args.get("preset", "30"),
        start=start_str,
        end=end_str,
        cities=report_service.list_cities(),
        city_id=city_id,
        role=role,
        export_endpoint="export.export_supplier" if role == "supplier" else "export.export_admin",
    )


@bp.get("/supplier/laporan")
@login_required
def supplier_report() -> str:
    """Render the supplier's own impact report."""
    return _render_report("supplier")


@bp.get("/admin/laporan")
@login_required
def admin_report() -> str:
    """Render the platform-wide impact report for administrators."""
    return _render_report("admin")
