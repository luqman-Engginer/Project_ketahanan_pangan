"""Export service rendering impact reports to PDF, XLSX, and CSV files."""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from flask import current_app, render_template
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services import report_service

EXPORT_FORMATS = ("pdf", "xlsx", "csv")

MIME_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}

EXTENSIONS = {"pdf": "pdf", "xlsx": "xlsx", "csv": "csv"}

MONTHS_ID = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

_TOKEN_PATTERN = re.compile(r"--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});")


class ExportUnavailableError(RuntimeError):
    """Raised when a file format cannot be produced in the current environment."""


@dataclass(frozen=True)
class ExportKpi:
    """A single report indicator with its raw and display values.

    Attributes:
        key: Stable identifier used by templates and spreadsheets.
        label: Human readable Indonesian label.
        value: Raw numeric value kept for spreadsheet number formats.
        unit: Unit of measure (kg, porsi, klaim, Rp).
        display: Formatted value for PDF and CSV output.
        number_format: Excel number format code for ``value``.
    """

    key: str
    label: str
    value: float
    unit: str
    display: str
    number_format: str = "#,##0.00"


@dataclass(frozen=True)
class ExportDataset:
    """Everything needed to render one report file.

    Attributes:
        start: First day of the reporting window.
        end: Last day of the reporting window.
        scope_label: Description of whose data is included.
        city_label: Description of the city filter applied.
        generated_at: Timestamp of the export.
        kpis: Four headline indicators shown in the report header.
        extra_metrics: Additional PRD Section 5 indicators.
        daily: Daily recap rows.
        categories: Per-category recap rows.
        detail: Transaction level rows of rescued surplus.
    """

    start: date
    end: date
    scope_label: str
    city_label: str
    generated_at: datetime
    kpis: tuple[ExportKpi, ...]
    extra_metrics: tuple[ExportKpi, ...]
    daily: tuple[dict[str, Any], ...]
    categories: tuple[dict[str, Any], ...]
    detail: tuple[dict[str, Any], ...]

    @property
    def period_label(self) -> str:
        """Return the reporting window as a readable Indonesian date range."""
        if self.start == self.end:
            return format_date_id(self.start)
        return f"{format_date_id(self.start)} – {format_date_id(self.end)}"

    @property
    def generated_label(self) -> str:
        """Return the export timestamp as a readable Indonesian string."""
        return f"{format_date_id(self.generated_at.date())} {self.generated_at.strftime('%H:%M')} WIB"


def format_number(value: float, decimals: int = 0) -> str:
    """Format a number using Indonesian conventions (dot thousands, comma decimals)."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_rupiah(value: float) -> str:
    """Format a monetary value as Indonesian rupiah."""
    return f"Rp {format_number(value, 0)}"


def format_date_id(value: date) -> str:
    """Format a date as ``DD Mon YYYY`` in Indonesian."""
    return f"{value.day:02d} {MONTHS_ID[value.month - 1]} {value.year}"


@lru_cache(maxsize=1)
def load_tokens() -> dict[str, str]:
    """Return the design tokens declared in ``static/css/tokens.css``."""
    path = Path(current_app.root_path) / "static" / "css" / "tokens.css"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    return {match.group(1): match.group(2) for match in _TOKEN_PATTERN.finditer(content)}


def token_color(name: str, fallback: str) -> str:
    """Return the hex colour of a design token with a safe fallback."""
    return load_tokens().get(name, fallback)


def collect_dataset(
    scope: report_service.ReportScope,
    start_date: date,
    end_date: date,
    scope_label: str,
    city_label: str,
) -> ExportDataset:
    """Gather every figure needed for an export file.

    Args:
        scope: Role/organization/city restriction applied to the queries.
        start_date: First day of the reporting window.
        end_date: Last day of the reporting window.
        scope_label: Human readable description of the data scope.
        city_label: Human readable description of the city filter.

    Returns:
        A populated :class:`ExportDataset`.
    """
    metrics = report_service.get_report_metrics(start_date=start_date, end_date=end_date, scope=scope)
    daily = report_service.get_report_rekap(start_date=start_date, end_date=end_date, scope=scope)
    categories = report_service.get_report_kategori(start_date=start_date, end_date=end_date, scope=scope)
    detail = report_service.get_report_detail(start_date=start_date, end_date=end_date, scope=scope)

    kg_saved = float(metrics["kg_saved"])
    kg_waste = float(metrics["kg_waste"])
    claims = int(metrics["claims_resolved"])
    rupiah = float(metrics["rupiah_saved"])

    kpis = (
        ExportKpi(
            key="kg_saved",
            label="Pangan terselamatkan",
            value=round(kg_saved, 2),
            unit="kg",
            display=f"{format_number(kg_saved, 1)} kg",
        ),
        ExportKpi(
            key="kg_waste",
            label="Limbah tercatat",
            value=round(kg_waste, 2),
            unit="kg",
            display=f"{format_number(kg_waste, 1)} kg",
        ),
        ExportKpi(
            key="claims",
            label="Klaim diselesaikan",
            value=claims,
            unit="klaim",
            display=f"{format_number(claims)} klaim",
            number_format="#,##0",
        ),
        ExportKpi(
            key="rupiah",
            label="Nilai dampak",
            value=round(rupiah, 2),
            unit="Rp",
            display=format_rupiah(rupiah),
            number_format='"Rp" #,##0',
        ),
    )

    extra_metrics = (
        ExportKpi(
            key="meals",
            label="Porsi makan tercukupi",
            value=round(float(metrics["meals"]), 2),
            unit="porsi",
            display=f"{format_number(float(metrics['meals']), 0)} porsi",
            number_format="#,##0",
        ),
        ExportKpi(
            key="co2e",
            label="CO₂e dicegah",
            value=round(float(metrics["co2e_avoided"]), 2),
            unit="kg CO₂e",
            display=f"{format_number(float(metrics['co2e_avoided']), 1)} kg CO₂e",
        ),
    )

    return ExportDataset(
        start=start_date,
        end=end_date,
        scope_label=scope_label,
        city_label=city_label,
        generated_at=datetime.now(),
        kpis=kpis,
        extra_metrics=extra_metrics,
        daily=tuple(daily),
        categories=tuple(categories),
        detail=tuple(detail),
    )


def build_daily_chart_svg(daily: list[dict[str, Any]], max_points: int = 30) -> str:
    """Build a self-contained SVG bar chart of the daily recap.

    The chart is rendered as inline SVG so the PDF engine can draw it without
    any external image dependency.

    Args:
        daily: Daily recap rows as returned by the report service.
        max_points: Maximum number of days drawn on the chart.

    Returns:
        SVG markup, or an empty string when there is no data to plot.
    """
    points = sorted(daily, key=lambda row: row["tanggal_iso"])[-max_points:]
    if not points:
        return ""

    width, height = 680, 224
    pad_left, pad_right, pad_top, pad_bottom = 48, 14, 16, 36
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    saved_color = token_color("primary-400", "#38bdf8")
    waste_color = token_color("warning", "#f59e0b")
    ink_color = token_color("ink", "#0c4a6e")
    muted_color = token_color("ink-muted", "#475569")
    grid_color = token_color("border", "#e0f2fe")
    surface_color = token_color("surface", "#ffffff")

    peak = max(
        [float(row.get("saved_kg", 0)) for row in points]
        + [float(row.get("waste_kg", 0)) for row in points]
        + [1.0]
    )
    step = _nice_step(peak / 4)
    grid_max = step * max(1, math.ceil(peak / step))

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        'aria-label="Grafik tren harian pangan terselamatkan dan terbuang">',
        "<title>Tren harian pangan terselamatkan dan terbuang</title>",
        f'<rect width="{width}" height="{height}" fill="{surface_color}" />',
    ]

    for index in range(5):
        value = grid_max * index / 4
        y = pad_top + plot_h - (value / grid_max * plot_h)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" '
            f'stroke="{grid_color}" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{pad_left - 6}" y="{y + 3:.1f}" text-anchor="end" font-size="8" '
            f'font-family="Poppins, sans-serif" fill="{muted_color}">{format_number(value, 0)}</text>'
        )

    slot = plot_w / len(points)
    bar_w = min(max(2.5, slot * 0.32), 26)
    gap = max(1.0, bar_w * 0.18)
    label_step = max(1, math.ceil(len(points) / 8))

    for index, row in enumerate(points):
        center = pad_left + slot * (index + 0.5)
        for value, offset, color in (
            (float(row.get("saved_kg", 0)), -(bar_w + gap) / 2, saved_color),
            (float(row.get("waste_kg", 0)), gap / 2, waste_color),
        ):
            bar_h = max(0.0, value / grid_max * plot_h)
            x = center + offset
            y = pad_top + plot_h - bar_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="2" fill="{color}" />'
            )
        if index % label_step == 0:
            label = str(row["tanggal_iso"])[8:10]
            parts.append(
                f'<text x="{center:.1f}" y="{height - 14}" text-anchor="middle" font-size="7.5" '
                f'font-family="Poppins, sans-serif" fill="{muted_color}">{label}</text>'
            )

    parts.append(
        f'<line x1="{pad_left}" y1="{pad_top + plot_h}" x2="{width - pad_right}" '
        f'y2="{pad_top + plot_h}" stroke="{ink_color}" stroke-width="1" />'
    )
    legend_y = height - 2
    swatch_y = height - 10
    legend_items = ((saved_color, "Terselamatkan"), (waste_color, "Terbuang"))
    legend_x = pad_left
    for color, label in legend_items:
        parts.append(
            f'<rect x="{legend_x}" y="{swatch_y}" width="6" height="6" rx="1" fill="{color}" />'
        )
        parts.append(
            f'<text x="{legend_x + 10}" y="{legend_y}" font-size="8" font-family="Poppins, sans-serif" '
            f'fill="{ink_color}">{label}</text>'
        )
        legend_x += 96
    parts.append("</svg>")
    return "".join(parts)


def _nice_step(raw: float) -> float:
    """Round a raw axis step up to a human friendly value."""
    if raw <= 0:
        return 1.0
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10**exponent)
    if fraction <= 1:
        nice = 1.0
    elif fraction <= 2:
        nice = 2.0
    elif fraction <= 2.5:
        nice = 2.5
    elif fraction <= 5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10**exponent)


def build_xlsx(dataset: ExportDataset) -> bytes:
    """Render the dataset as an XLSX workbook with a summary and a data sheet.

    Args:
        dataset: Figures to write into the workbook.

    Returns:
        The workbook bytes.
    """
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Ringkasan"
    data_sheet = workbook.create_sheet("Data")
    detail_sheet = workbook.create_sheet("Detail")

    header_fill = PatternFill("solid", fgColor="E0F2FE")
    accent_fill = PatternFill("solid", fgColor="BAE6FD")
    header_font = Font(bold=True, color="0C4A6E")
    title_font = Font(bold=True, size=14, color="0C4A6E")
    label_font = Font(bold=True, color="0C4A6E")
    thin = Side(style="thin", color="BAE6FD")
    header_border = Border(bottom=Side(style="medium", color="38BDF8"))

    summary["A1"] = "LAPORAN DAMPAK — FOODLOOP ID"
    summary["A1"].font = title_font
    summary["A2"] = "Ringkasan dampak pangan platform FoodLoop ID"
    summary["A2"].font = Font(color="475569", size=10)

    meta_rows = [
        ("Periode", dataset.period_label),
        ("Cakupan data", dataset.scope_label),
        ("Wilayah", dataset.city_label),
        ("Dicetak pada", dataset.generated_label),
    ]
    for offset, (label, value) in enumerate(meta_rows, start=4):
        summary.cell(row=offset, column=1, value=label).font = label_font
        summary.cell(row=offset, column=2, value=value)

    header_row = 9
    for column, title in enumerate(("Indikator", "Nilai", "Satuan"), start=1):
        cell = summary.cell(row=header_row, column=column, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = header_border

    row_cursor = header_row + 1
    for kpi in dataset.kpis + dataset.extra_metrics:
        summary.cell(row=row_cursor, column=1, value=kpi.label)
        value_cell = summary.cell(row=row_cursor, column=2, value=kpi.value)
        value_cell.number_format = kpi.number_format
        summary.cell(row=row_cursor, column=3, value=kpi.unit)
        row_cursor += 1

    category_title_row = row_cursor + 1
    summary.cell(row=category_title_row, column=1, value="KONTRIBUSI PER KATEGORI").font = title_font
    category_header_row = category_title_row + 1
    category_headers = ("Kategori", "Terselamatkan (kg)", "Terbuang (kg)", "Kontribusi")
    for column, title in enumerate(category_headers, start=1):
        cell = summary.cell(row=category_header_row, column=column, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = header_border

    row_cursor = category_header_row + 1
    for row in dataset.categories:
        summary.cell(row=row_cursor, column=1, value=row["kategori"])
        saved_cell = summary.cell(row=row_cursor, column=2, value=row["saved_kg"])
        saved_cell.number_format = "#,##0.00"
        waste_cell = summary.cell(row=row_cursor, column=3, value=row["waste_kg"])
        waste_cell.number_format = "#,##0.00"
        pct_cell = summary.cell(row=row_cursor, column=4, value=row["contribution_pct"])
        pct_cell.number_format = '0.0"%"'
        row_cursor += 1

    summary.column_dimensions["A"].width = 32
    summary.column_dimensions["B"].width = 22
    summary.column_dimensions["C"].width = 14
    summary.column_dimensions["D"].width = 16
    summary.freeze_panes = "A10"

    daily_headers = (
        "Tanggal",
        "Tanggal (ISO)",
        "Terselamatkan (kg)",
        "Terbuang (kg)",
        "Klaim",
        "Nilai dampak (Rp)",
    )
    _write_table(
        data_sheet,
        daily_headers,
        [
            (
                row["tanggal"],
                row["tanggal_iso"],
                row["saved_kg"],
                row["waste_kg"],
                row["claim_count"],
                row["rupiah_value"],
            )
            for row in dataset.daily
        ],
        number_formats=(None, None, "#,##0.00", "#,##0.00", "#,##0", '"Rp" #,##0'),
        header_fill=header_fill,
        header_font=header_font,
        header_border=header_border,
        thin=thin,
    )

    detail_headers = (
        "Tanggal",
        "Organisasi",
        "Kategori",
        "Nama surplus",
        "Kota",
        "Kuantitas",
        "Satuan",
        "Berat (kg)",
        "Nilai dampak (Rp)",
    )
    _write_table(
        detail_sheet,
        detail_headers,
        [
            (
                row["tanggal"],
                row["organisasi"],
                row["kategori"],
                row["judul"],
                row["kota"],
                row["qty"],
                row["unit"],
                row["qty_kg"],
                row["rupiah"],
            )
            for row in dataset.detail
        ],
        number_formats=(None, None, None, None, None, "#,##0.00", None, "#,##0.00", '"Rp" #,##0'),
        header_fill=header_fill,
        header_font=header_font,
        header_border=header_border,
        thin=thin,
    )

    workbook.properties.title = "Laporan Dampak FoodLoop ID"
    workbook.properties.creator = "FoodLoop ID"
    workbook.properties.subject = dataset.period_label

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_table(
    sheet: Any,
    headers: tuple[str, ...],
    rows: list[tuple[Any, ...]],
    number_formats: tuple[Optional[str], ...],
    header_fill: PatternFill,
    header_font: Font,
    header_border: Border,
    thin: Side,
) -> None:
    """Write a header row plus data rows into a worksheet with styling.

    Args:
        sheet: Target worksheet.
        headers: Column titles.
        rows: Data rows, each matching the header count.
        number_formats: Excel number format per column, ``None`` for text.
        header_fill: Fill style of the header row.
        header_font: Font style of the header row.
        header_border: Border style of the header row.
        thin: Border style used under data rows.
    """
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=column, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = header_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_index, values in enumerate(rows, start=2):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=value)
            cell.border = Border(bottom=thin)
            if column - 1 < len(number_formats) and number_formats[column - 1]:
                cell.number_format = number_formats[column - 1]

    widths = []
    for column in range(1, len(headers) + 1):
        longest = len(headers[column - 1])
        for values in rows:
            longest = max(longest, len(str(values[column - 1])))
        widths.append(min(max(longest + 3, 12), 42))

    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width

    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"


def build_csv(dataset: ExportDataset) -> bytes:
    """Render the daily recap as a CSV file encoded in UTF-8 with BOM.

    The byte order mark makes Microsoft Excel detect the UTF-8 encoding so the
    Indonesian characters are displayed correctly.

    Args:
        dataset: Figures to write into the file.

    Returns:
        The CSV bytes prefixed with a UTF-8 BOM.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(
        ("Tanggal", "Tanggal (ISO)", "Terselamatkan (kg)", "Terbuang (kg)", "Klaim", "Nilai dampak (Rp)")
    )
    for row in dataset.daily:
        writer.writerow(
            (
                row["tanggal"],
                row["tanggal_iso"],
                f"{row['saved_kg']:.2f}",
                f"{row['waste_kg']:.2f}",
                row["claim_count"],
                f"{row['rupiah_value']:.2f}",
            )
        )
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def build_pdf(dataset: ExportDataset) -> bytes:
    """Render the dataset as a PDF report using WeasyPrint.

    Args:
        dataset: Figures to write into the report.

    Returns:
        The PDF bytes.

    Raises:
        ExportUnavailableError: When WeasyPrint or its native libraries are
            unavailable on the host.
    """
    try:
        from weasyprint import HTML  # noqa: PLC0415
    except Exception as err:  # pragma: no cover - depends on host libraries
        raise ExportUnavailableError(
            "Ekspor PDF tidak tersedia: pustaka sistem WeasyPrint (libpango) belum terpasang. "
            "Jalankan aplikasi melalui Docker atau pasang libpango-1.0-0."
        ) from err

    chart_svg = build_daily_chart_svg(list(dataset.daily))
    tokens_css = _load_tokens_css()
    html = render_template(
        "report/export_pdf.html",
        dataset=dataset,
        kpis=dataset.kpis,
        extra_metrics=dataset.extra_metrics,
        daily=dataset.daily,
        categories=dataset.categories,
        chart_svg=chart_svg,
        tokens_css=tokens_css,
        period_label=dataset.period_label,
        scope_label=dataset.scope_label,
        city_label=dataset.city_label,
        generated_label=dataset.generated_label,
    )
    return HTML(string=html, base_url=current_app.static_folder or ".").write_pdf()


def _load_tokens_css() -> str:
    """Return the content of ``tokens.css`` so the PDF reuses the design tokens."""
    path = Path(current_app.root_path) / "static" / "css" / "tokens.css"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - tokens file is shipped with the app
        return ""


def build_filename(dataset: ExportDataset, export_format: str) -> str:
    """Return the download filename for an export file."""
    extension = EXTENSIONS.get(export_format, export_format)
    return f"laporan-dampak-foodloop-{dataset.start.isoformat()}-{dataset.end.isoformat()}.{extension}"


def build_scope_label(role: str, org_name: Optional[str]) -> str:
    """Return a human readable description of whose data an export contains."""
    if role == "admin":
        return "Seluruh organisasi (akun admin)"
    if not org_name:
        return "Data organisasi sendiri"
    if role == "receiver":
        return f"Klaim dan surplus diterima oleh {org_name}"
    return f"Surplus dan limbah organisasi {org_name}"


def build_city_label(city_name: Optional[str]) -> str:
    """Return a human readable description of the applied city filter."""
    return f"Kota {city_name}" if city_name else "Semua kota"
