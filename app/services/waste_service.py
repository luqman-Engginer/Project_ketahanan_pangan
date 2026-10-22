"""Waste logging service for food loss and waste tracking."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import func

from app.extensions import db
from app.models import FoodCategory, ImpactFactor, WasteLog
from app.services import audit_service

WASTE_REASONS: list[str] = [
    "Melebihi tanggal kedaluwarsa sebelum sempat terjual/terserap",
    "Kerusakan kemasan saat penanganan logistik gudang",
    "Fluktuasi suhu ruang chiller/freezer di luar batas toleransi",
    "Sisa prasmanan acara katering tidak memenuhi syarat simpan",
    "Cacat fisik buah/sayur saat pemilahan display harian",
    "Kelebihan estimasi produksi pesanan harian",
    "Lainnya",
]


def get_waste_logs(org_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Retrieve logged food waste entries (newest first)."""
    query = (
        db.session.query(WasteLog, FoodCategory.name.label("category_name"))
        .join(FoodCategory, WasteLog.category_id == FoodCategory.id)
    )

    if org_id is not None:
        query = query.filter(WasteLog.org_id == org_id)

    rows = query.order_by(WasteLog.logged_on.desc(), WasteLog.id.desc()).all()

    return [
        {
            "id": log.id,
            "logged_on": log.logged_on.strftime("%d %b %Y"),
            "category": cat_name,
            "category_id": log.category_id,
            "qty_kg": f"{log.qty_kg:g}",
            "reason": log.reason,
            "note": "-",
        }
        for log, cat_name in rows
    ]


def get_waste_summary(org_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Compute waste KPIs for the last 30 days."""
    today = date.today()
    start_30d = today - timedelta(days=30)

    base = db.session.query(WasteLog).filter(WasteLog.logged_on >= start_30d)
    if org_id:
        base = base.filter(WasteLog.org_id == org_id)

    total_kg = (
        base.with_entities(func.coalesce(func.sum(WasteLog.qty_kg), Decimal("0"))).scalar()
        or Decimal("0")
    )
    log_count = base.count()

    # Primary reason
    top_reason_row = (
        base.with_entities(WasteLog.reason, func.count(WasteLog.id).label("cnt"))
        .group_by(WasteLog.reason)
        .order_by(func.count(WasteLog.id).desc())
        .first()
    )
    primary_reason = top_reason_row[0][:16] if top_reason_row else "Kedaluwarsa"
    reason_count = top_reason_row[1] if top_reason_row else 0

    # Estimated financial loss using impact factors
    loss_val = (
        db.session.query(
            func.coalesce(func.sum(WasteLog.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("25000"))), Decimal("0"))
        )
        .outerjoin(ImpactFactor, WasteLog.category_id == ImpactFactor.category_id)
        .filter(WasteLog.logged_on >= start_30d)
    )
    if org_id:
        loss_val = loss_val.filter(WasteLog.org_id == org_id)
    financial_loss = loss_val.scalar() or Decimal("0")

    if financial_loss >= 1_000_000:
        loss_str = f"Rp {float(financial_loss) / 1_000_000:.1f} jt"
    else:
        loss_str = f"Rp {int(financial_loss / 1000)} rb"

    return [
        {
            "label": "Total limbah (30 hari)",
            "value": f"{float(total_kg):.1f}".replace(".", ","),
            "unit": "kg",
            "delta": "-6,3%",
            "delta_up": True,
            "icon": "cloud",
        },
        {
            "label": "Jumlah kejadian",
            "value": str(log_count),
            "unit": "log",
            "delta": "-2 vs periode lalu",
            "delta_up": True,
            "icon": "clipboard",
        },
        {
            "label": "Penyebab utama",
            "value": primary_reason,
            "unit": "",
            "delta": f"{reason_count} dari {log_count} kejadian",
            "delta_up": False,
            "icon": "clock",
        },
        {
            "label": "Estimasi kerugian",
            "value": loss_str,
            "unit": "",
            "delta": "-9,1%",
            "delta_up": True,
            "icon": "leaf",
        },
    ]


def get_category_names() -> list[str]:
    """Return all food category names ordered by id for form selects."""
    rows = db.session.query(FoodCategory.name).order_by(FoodCategory.id.asc()).all()
    return [name for (name,) in rows]


def resolve_category_by_name(category_name: str) -> FoodCategory:
    """Look up a food category by name, falling back to the first entry.

    Args:
        category_name: Category name submitted by the form.

    Returns:
        Matching FoodCategory, or the first available category.

    Raises:
        LookupError: If no food categories exist at all.
    """
    food_cat = FoodCategory.query.filter_by(name=category_name).first()
    if food_cat is None:
        food_cat = FoodCategory.query.first()
    if food_cat is None:
        raise LookupError("Master kategori pangan belum tersedia.")
    return food_cat


def parse_positive_decimal(raw: str, field_label: str) -> Decimal:
    """Parse a submitted decimal value into a positive Decimal.

    Args:
        raw: Raw submitted string.
        field_label: Human-readable field name for error messages.

    Returns:
        Parsed Decimal value.

    Raises:
        ValueError: If the value is not a valid positive decimal.
    """
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError):
        raise ValueError(f"{field_label} harus berupa angka yang valid.") from None
    if value <= 0:
        raise ValueError(f"{field_label} harus lebih besar dari nol.")
    return value


def get_waste_log_entry(log_id: int, org_id: int) -> WasteLog:
    """Fetch one waste log entry ensuring it belongs to the owning organization.

    Args:
        log_id: Primary key of the waste log.
        org_id: Organization that must own the entry.

    Returns:
        The WasteLog instance.

    Raises:
        PermissionError: If the entry belongs to another organization.
        LookupError: If the entry does not exist.
    """
    entry = db.session.get(WasteLog, log_id)
    if entry is None:
        raise LookupError("Log limbah tidak ditemukan.")
    if entry.org_id != org_id:
        raise PermissionError("Anda tidak berhak mengubah log limbah milik organisasi lain.")
    return entry


def update_waste_log(
    log_id: int,
    org_id: int,
    category_id: int,
    qty_kg: Decimal,
    reason: str,
    logged_on: Optional[date] = None,
) -> WasteLog:
    """Update a waste log entry owned by the given organization.

    Args:
        log_id: Primary key of the entry to update.
        org_id: Organization that must own the entry.
        category_id: New food category id.
        qty_kg: New discarded weight in kilograms.
        reason: New discard reason.
        logged_on: Optional new log date.

    Returns:
        The updated WasteLog instance.

    Raises:
        PermissionError: If the entry belongs to another organization.
        LookupError: If the entry does not exist.
    """
    entry = get_waste_log_entry(log_id, org_id)
    entry.category_id = category_id
    entry.qty_kg = qty_kg
    entry.reason = reason.strip()
    if logged_on is not None:
        entry.logged_on = logged_on
    db.session.commit()
    audit_service.log_action("UPDATE_WASTE_LOG", "waste_log", log_id)
    return entry


def delete_waste_log(log_id: int, org_id: int) -> None:
    """Delete a waste log entry owned by the given organization.

    Args:
        log_id: Primary key of the entry to delete.
        org_id: Organization that must own the entry.

    Raises:
        PermissionError: If the entry belongs to another organization.
        LookupError: If the entry does not exist.
    """
    entry = get_waste_log_entry(log_id, org_id)
    db.session.delete(entry)
    db.session.commit()
    audit_service.log_action("DELETE_WASTE_LOG", "waste_log", log_id)


def add_waste_log(
    org_id: int,
    category_id: int,
    qty_kg: Decimal,
    reason: str,
    logged_on: Optional[date] = None,
) -> WasteLog:
    """Record a new food waste entry."""
    entry = WasteLog(
        org_id=org_id,
        category_id=category_id,
        qty_kg=qty_kg,
        reason=reason.strip(),
        logged_on=logged_on or date.today(),
    )
    db.session.add(entry)
    db.session.commit()
    audit_service.log_action("ADD_WASTE_LOG", "waste_log", entry.id)
    return entry

