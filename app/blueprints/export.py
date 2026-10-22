"""Export blueprint: downloadable PDF, XLSX, and CSV impact reports."""
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


def _resolve_scope(city_id: Optional[int]) -> tuple[report_service.ReportScope, str]:
    """Build the report scope and its human readable label for the current user.

    Administrators may export every organization, while donors and receivers are
    limited to the data of their own organization.

    Args:
        city_id: Optional city restriction applied on top of the role scope.

    Returns:
        A tuple of the scope and the label describing it.

    Raises:
        werkzeug.exceptions.HTTPException: 403 when the account has no organization.
    """
    role = current_user.role
    if role == "admin":
        scope = report_service.build_scope("admin", None, city_id)
        return scope, export_service.build_scope_label("admin", None)

    if not current_user.org_id:
        abort(403, description="Akun Anda belum terhubung dengan organisasi, laporan tidak dapat dibuat.")

    organization = current_user.organization
    org_name = organization.name if organization else None
    scope = report_service.build_scope(role, current_user.org_id, city_id)
    return scope, export_service.build_scope_label(role, org_name)


@bp.get("/laporan/export")
@bp.get("/reports/export")
@login_required
@limiter.limit("20 per minute")
def export_report() -> Response:
    """Export the impact report as PDF, XLSX, or CSV.

    Query parameters:
        format: ``pdf``, ``xlsx``, or ``csv``.
        from: Start date of the window (``start`` is accepted as an alias).
        to: End date of the window (``end`` is accepted as an alias).
        city_id: Optional city restriction.

    Returns:
        The generated file as an attachment download.
    """
    export_format = (request.args.get("format") or "").strip().lower()
    if export_format not in export_service.EXPORT_FORMATS:
        abort(400, description="Format ekspor tidak dikenal. Gunakan pdf, xlsx, atau csv.")

    today = date.today()
    start_date: Optional[date] = report_service.parse_date(
        request.args.get("from") or request.args.get("start")
    )
    end_date: Optional[date] = report_service.parse_date(request.args.get("to") or request.args.get("end"))
    start_date = start_date or (today - timedelta(days=30))
    end_date = end_date or today
    if start_date > end_date:
        abort(400, description="Rentang tanggal tidak valid: tanggal awal lebih besar dari tanggal akhir.")

    city_id: Optional[int] = None
    raw_city = (request.args.get("city_id") or "").strip()
    if raw_city:
        try:
            city_id = int(raw_city)
        except ValueError:
            abort(400, description="Parameter city_id harus berupa angka.")

    scope, scope_label = _resolve_scope(city_id)
    city_label = export_service.build_city_label(report_service.get_city_name(city_id))

    dataset = export_service.collect_dataset(
        scope=scope,
        start_date=start_date,
        end_date=end_date,
        scope_label=scope_label,
        city_label=city_label,
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
                return redirect(
                    url_for(
                        "report.report_page",
                        start=start_date.isoformat(),
                        end=end_date.isoformat(),
                        city_id=city_id,
                    )
                )
            abort(503, description=str(err))

    return send_file(
        BytesIO(payload),
        mimetype=export_service.MIME_TYPES[export_format],
        as_attachment=True,
        download_name=export_service.build_filename(dataset, export_format),
        max_age=0,
    )
