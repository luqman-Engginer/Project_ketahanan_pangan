"""Role-separated report exports to PDF, XLSX, and CSV."""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Optional

from flask import Blueprint, Response, abort, flash, redirect, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.services import export as export_service
from app.services import report_service

bp: Blueprint = Blueprint("export", __name__)


def _resolve_scope(role: str, city_id: Optional[int]) -> tuple[report_service.ReportScope, str]:
    """Build a role-bound report scope and its display label."""
    if current_user.role != role:
        abort(403)
    if role == "admin":
        return report_service.build_scope("admin", None, city_id), export_service.build_scope_label("admin", None)
    if not current_user.org_id:
        abort(403, description="Akun Anda belum terhubung dengan organisasi supplier.")
    organization = current_user.organization
    org_name = organization.name if organization else None
    return report_service.build_scope("supplier", current_user.org_id, city_id), export_service.build_scope_label("supplier", org_name)


def _run_export(role: str) -> Response:
    """Generate an export for the given authenticated role."""
    export_format = (request.args.get("format") or "").strip().lower()
    if export_format not in export_service.EXPORT_FORMATS:
        abort(400, description="Format ekspor tidak dikenal. Gunakan pdf, xlsx, atau csv.")

    today = date.today()
    start_date = report_service.parse_date(request.args.get("from") or request.args.get("start"))
    end_date = report_service.parse_date(request.args.get("to") or request.args.get("end"))
    start_date = start_date or (today - timedelta(days=30))
    end_date = end_date or today
    if start_date > end_date:
        abort(400, description="Rentang tanggal tidak valid: tanggal awal lebih besar dari tanggal akhir.")

    raw_city = (request.args.get("city_id") or "").strip()
    try:
        city_id: Optional[int] = int(raw_city) if raw_city else None
    except ValueError:
        abort(400, description="Parameter city_id harus berupa angka.")

    scope, scope_label = _resolve_scope(role, city_id)
    dataset = export_service.collect_dataset(
        scope=scope,
        start_date=start_date,
        end_date=end_date,
        scope_label=scope_label,
        city_label=export_service.build_city_label(report_service.get_city_name(city_id)),
    )

    if export_format == "xlsx":
        payload = export_service.build_xlsx(dataset)
    elif export_format == "csv":
        payload = export_service.build_csv(dataset)
    else:
        try:
            payload = export_service.build_pdf(dataset)
        except export_service.ExportUnavailableError as err:
            if "text/html" in request.headers.get("Accept", ""):
                flash(str(err), "danger")
                endpoint = "report.supplier_report" if role == "supplier" else "report.admin_report"
                return redirect(url_for(endpoint, start=start_date.isoformat(), end=end_date.isoformat(), city_id=city_id))
            abort(503, description=str(err))

    return send_file(
        BytesIO(payload),
        mimetype=export_service.MIME_TYPES[export_format],
        as_attachment=True,
        download_name=export_service.build_filename(dataset, export_format),
        max_age=0,
    )


@bp.get("/supplier/laporan/export")
@login_required
@limiter.limit("20 per minute")
def export_supplier() -> Response:
    """Export the supplier's own report."""
    return _run_export("supplier")


@bp.get("/admin/laporan/export")
@login_required
@limiter.limit("20 per minute")
def export_admin() -> Response:
    """Export the platform-wide report."""
    return _run_export("admin")
