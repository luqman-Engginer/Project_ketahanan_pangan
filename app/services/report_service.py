"""Reporting and export aggregation for approved surplus and waste logs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import false, func

from app.extensions import db
from app.models import City, FoodCategory, ImpactFactor, Organization, Province, SurplusListing, WasteLog

MEALS_PER_KG = Decimal("0.4")


@dataclass(frozen=True)
class ReportScope:
    """Describe which records a report request may include."""

    role: str = "admin"
    org_id: Optional[int] = None
    city_id: Optional[int] = None

    @property
    def is_unrestricted(self) -> bool:
        """Return True when every organization is visible."""
        return self.role == "admin"


def build_scope(role: str, org_id: Optional[int], city_id: Optional[int] = None) -> ReportScope:
    """Build a report scope from the authenticated user context."""
    if role == "admin":
        return ReportScope(role="admin", org_id=None, city_id=city_id)
    return ReportScope(role="supplier", org_id=org_id, city_id=city_id)


def _scope_filters(scope: Optional[ReportScope]) -> tuple[list[Any], list[Any]]:
    """Return listing and waste filters enforcing role, org, and city."""
    listing: list[Any] = []
    waste: list[Any] = []
    if scope is not None and scope.role == "supplier":
        if scope.org_id is None:
            listing.append(false())
            waste.append(false())
        else:
            listing.append(SurplusListing.org_id == scope.org_id)
            waste.append(WasteLog.org_id == scope.org_id)
    if scope is not None and scope.city_id is not None:
        listing.append(SurplusListing.city_id == scope.city_id)
        city_orgs = db.session.query(Organization.id).filter(Organization.city_id == scope.city_id)
        waste.append(WasteLog.org_id.in_(city_orgs))
    return listing, waste


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Safely parse a ``YYYY-MM-DD`` string."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def to_date(value: Any) -> Optional[date]:
    """Normalise a grouped SQL date value into a ``date``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_report_range_presets() -> list[dict[str, str]]:
    """Return preset date ranges for the report filter."""
    today = date.today()
    return [
        {"key": "7", "label": "7 hari", "start": (today - timedelta(days=7)).isoformat(), "end": today.isoformat()},
        {"key": "30", "label": "30 hari", "start": (today - timedelta(days=30)).isoformat(), "end": today.isoformat()},
        {"key": "90", "label": "90 hari", "start": (today - timedelta(days=90)).isoformat(), "end": today.isoformat()},
    ]


def get_report_metrics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> dict[str, Decimal]:
    """Return aggregate metrics restricted to the report scope."""
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    listing_filters, waste_filters = _scope_filters(scope)

    saved = (
        db.session.query(
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("kg"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("rupiah"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.co2e_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("co2e"),
            func.count(SurplusListing.id).label("count"),
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *listing_filters,
        )
        .first()
    )
    waste = (
        db.session.query(func.coalesce(func.sum(WasteLog.qty_kg), Decimal("0")))
        .filter(WasteLog.logged_on >= start, WasteLog.logged_on <= end, *waste_filters)
        .scalar()
        or Decimal("0")
    )
    kg_saved = saved.kg if saved else Decimal("0")
    return {
        "kg_saved": kg_saved,
        "kg_waste": waste,
        "approved_count": Decimal(saved.count if saved else 0),
        "rupiah_saved": saved.rupiah if saved else Decimal("0"),
        "meals": kg_saved / MEALS_PER_KG,
        "co2e_avoided": saved.co2e if saved else Decimal("0"),
    }


def get_report_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Build formatted KPI cards for the report page."""
    metrics = get_report_metrics(start_date, end_date, scope)
    rupiah = float(metrics["rupiah_saved"])
    rupiah_str = f"Rp {rupiah / 1_000_000:.1f} jt" if rupiah >= 1_000_000 else f"Rp {int(rupiah):,}".replace(",", ".")
    return [
        {"label": "Pangan terselamatkan", "value": f"{float(metrics['kg_saved']):,.0f}".replace(",", "."), "unit": "kg", "delta": "Pasokan disetujui", "delta_up": True, "icon": "leaf"},
        {"label": "Limbah tercatat", "value": f"{float(metrics['kg_waste']):.1f}".replace(".", ","), "unit": "kg", "delta": "Log supplier", "delta_up": False, "icon": "cloud"},
        {"label": "Pasokan disetujui", "value": str(int(metrics["approved_count"])), "unit": "pasokan", "delta": "Terverifikasi admin", "delta_up": True, "icon": "clipboard"},
        {"label": "Nilai dampak", "value": rupiah_str, "unit": "", "delta": "Harga acuan kategori", "delta_up": True, "icon": "package"},
    ]


def get_report_rekap(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return daily recap rows aggregated through SQL."""
    today = date.today()
    start = start_date or (today - timedelta(days=7))
    end = end_date or today
    listing_filters, waste_filters = _scope_filters(scope)

    saved_rows = (
        db.session.query(
            func.date(SurplusListing.created_at).label("dt"),
            func.sum(SurplusListing.qty_kg).label("kg"),
            func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))).label("rp"),
            func.count(SurplusListing.id).label("cnt"),
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *listing_filters,
        )
        .group_by(func.date(SurplusListing.created_at))
        .all()
    )
    saved_map = {to_date(row.dt): (float(row.kg), float(row.rp), int(row.cnt)) for row in saved_rows if to_date(row.dt)}

    waste_rows = (
        db.session.query(WasteLog.logged_on.label("dt"), func.sum(WasteLog.qty_kg).label("kg"))
        .filter(WasteLog.logged_on >= start, WasteLog.logged_on <= end, *waste_filters)
        .group_by(WasteLog.logged_on)
        .all()
    )
    waste_map = {to_date(row.dt): float(row.kg) for row in waste_rows if to_date(row.dt)}

    rekap: list[dict[str, Any]] = []
    for day in sorted(set(saved_map) | set(waste_map), reverse=True):
        saved_kg, saved_rp, count = saved_map.get(day, (0.0, 0.0, 0))
        wasted_kg = waste_map.get(day, 0.0)
        rekap.append(
            {
                "tanggal": day.strftime("%d %b %Y"),
                "tanggal_iso": day.isoformat(),
                "kg_diselamatkan": f"{saved_kg:,.0f}".replace(",", "."),
                "kg_terbuang": f"{wasted_kg:.1f}".replace(".", ","),
                "pasokan": str(count),
                "rupiah": f"Rp {int(saved_rp):,}".replace(",", "."),
                "saved_kg": round(saved_kg, 2),
                "waste_kg": round(wasted_kg, 2),
                "listing_count": count,
                "rupiah_value": round(saved_rp, 2),
            }
        )
    return rekap


def get_report_kategori(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return per-category recap rows aggregated through SQL."""
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    listing_filters, waste_filters = _scope_filters(scope)

    saved_cat = (
        db.session.query(FoodCategory.name.label("name"), func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("saved_kg"))
        .join(SurplusListing, SurplusListing.category_id == FoodCategory.id)
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *listing_filters,
        )
        .group_by(FoodCategory.id, FoodCategory.name)
        .all()
    )
    saved_map = {row.name: float(row.saved_kg) for row in saved_cat}
    total_saved = sum(saved_map.values()) or 1.0

    waste_cat = (
        db.session.query(FoodCategory.name.label("name"), func.coalesce(func.sum(WasteLog.qty_kg), Decimal("0")).label("waste_kg"))
        .join(WasteLog, WasteLog.category_id == FoodCategory.id)
        .filter(WasteLog.logged_on >= start, WasteLog.logged_on <= end, *waste_filters)
        .group_by(FoodCategory.id, FoodCategory.name)
        .all()
    )
    waste_map = {row.name: float(row.waste_kg) for row in waste_cat}

    results: list[dict[str, Any]] = []
    for (category_name,) in db.session.query(FoodCategory.name).order_by(FoodCategory.id).all():
        saved_kg = saved_map.get(category_name, 0.0)
        waste_kg = waste_map.get(category_name, 0.0)
        pct = saved_kg / total_saved * 100
        results.append(
            {
                "kategori": category_name,
                "kg_diselamatkan": f"{saved_kg:,.0f}".replace(",", "."),
                "kg_terbuang": f"{waste_kg:.1f}".replace(".", ","),
                "kontribusi": f"{pct:.1f}%".replace(".", ","),
                "saved_kg": round(saved_kg, 2),
                "waste_kg": round(waste_kg, 2),
                "contribution_pct": round(pct, 2),
            }
        )
    return results


def get_report_detail(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return transaction-level rows of approved surplus for the range."""
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    listing_filters, _ = _scope_filters(scope)
    rows = (
        db.session.query(
            func.date(SurplusListing.created_at).label("tanggal"),
            Organization.name.label("organisasi"),
            FoodCategory.name.label("kategori"),
            SurplusListing.title.label("judul"),
            City.name.label("kota"),
            SurplusListing.qty.label("qty"),
            SurplusListing.unit.label("unit"),
            SurplusListing.qty_kg.label("qty_kg"),
            func.coalesce(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0")), Decimal("0")).label("rupiah"),
        )
        .join(Organization, SurplusListing.org_id == Organization.id)
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *listing_filters,
        )
        .order_by(SurplusListing.created_at.desc())
        .all()
    )
    detail: list[dict[str, Any]] = []
    for row in rows:
        day = to_date(row.tanggal)
        detail.append(
            {
                "tanggal": day.strftime("%d %b %Y") if day else "-",
                "tanggal_iso": day.isoformat() if day else "",
                "organisasi": row.organisasi,
                "kategori": row.kategori,
                "judul": row.judul,
                "kota": row.kota,
                "qty": float(row.qty),
                "unit": row.unit,
                "qty_kg": float(row.qty_kg),
                "rupiah": float(row.rupiah),
            }
        )
    return detail


def list_cities() -> list[dict[str, Any]]:
    """Return cities usable as a report filter."""
    rows = (
        db.session.query(City.id, City.name, Province.name)
        .join(Province, City.province_id == Province.id)
        .order_by(Province.name, City.name)
        .all()
    )
    return [{"id": row.id, "name": row.name, "province": row[2]} for row in rows]


def get_city_name(city_id: Optional[int]) -> Optional[str]:
    """Return the display name of a city, or ``None`` when unknown."""
    if city_id is None:
        return None
    return db.session.query(City.name).filter(City.id == city_id).scalar()
