"""Reporting and export aggregation service using SQL queries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import false, func, select

from app.extensions import db
from app.models import (
    City,
    Claim,
    FoodCategory,
    ImpactFactor,
    Organization,
    Province,
    SurplusListing,
    WasteLog,
)

MEALS_PER_KG = Decimal("0.4")


@dataclass(frozen=True)
class ReportScope:
    """Describe which records a report request is allowed to include.

    Attributes:
        role: Role of the requesting user ('admin', 'donor', 'receiver').
        org_id: Organization the user belongs to; ``None`` means every organization.
        city_id: Optional city restriction applied on top of the role scope.
    """

    role: str = "admin"
    org_id: Optional[int] = None
    city_id: Optional[int] = None

    @property
    def is_unrestricted(self) -> bool:
        """Return True when the scope reaches every organization."""
        return self.role == "admin" or self.org_id is None


def build_scope(role: str, org_id: Optional[int], city_id: Optional[int] = None) -> ReportScope:
    """Build a :class:`ReportScope` from the authenticated user context."""
    if role == "admin":
        return ReportScope(role="admin", org_id=None, city_id=city_id)
    return ReportScope(role=role, org_id=org_id, city_id=city_id)


def _scope_filters(scope: Optional[ReportScope]) -> dict[str, list[Any]]:
    """Build SQLAlchemy filter clauses that isolate data per role and city."""
    listing: list[Any] = []
    claims: list[Any] = []
    waste: list[Any] = []

    if scope is not None and scope.role in {"donor", "receiver"}:
        if scope.org_id is None:
            # User has no organization attached: never expose platform-wide data.
            listing.append(false())
            claims.append(false())
            waste.append(false())
        elif scope.role == "donor":
            listing.append(SurplusListing.org_id == scope.org_id)
            claims.append(
                Claim.listing_id.in_(
                    select(SurplusListing.id).where(SurplusListing.org_id == scope.org_id)
                )
            )
        else:
            listing.append(
                SurplusListing.id.in_(
                    select(Claim.listing_id).where(Claim.receiver_org_id == scope.org_id)
                )
            )
            claims.append(Claim.receiver_org_id == scope.org_id)
        waste.append(WasteLog.org_id == scope.org_id)

    if scope is not None and scope.city_id is not None:
        listing.append(SurplusListing.city_id == scope.city_id)
        claims.append(
            Claim.listing_id.in_(
                select(SurplusListing.id).where(SurplusListing.city_id == scope.city_id)
            )
        )
        waste.append(
            WasteLog.org_id.in_(
                select(Organization.id).where(Organization.city_id == scope.city_id)
            )
        )

    return {"listing": listing, "claims": claims, "waste": waste}


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Safely parse YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def to_date(value: Any) -> Optional[date]:
    """Normalise a grouped SQL date value into a ``date``.

    ``func.date()`` returns a ``date`` on MySQL but a string on SQLite, so the
    grouping keys are converted before they are sorted or formatted.
    """
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
    """Preset date ranges for the report filter."""
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
    """Return raw aggregate metrics for the selected range, restricted to ``scope``.

    The formulas follow PRD Section 5: ``kg_saved`` from picked-up surplus,
    ``rupiah_saved`` and ``co2e_avoided`` from the per-category impact factors,
    and ``meals`` from ``kg_saved / 0.4``.

    Args:
        start_date: Inclusive start of the reporting window.
        end_date: Inclusive end of the reporting window.
        scope: Role/organization/city restriction of the request.

    Returns:
        Mapping of metric name to its raw numeric value.
    """
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    filters = _scope_filters(scope)

    kg_saved = (
        db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .scalar()
        or Decimal("0")
    )

    kg_waste = (
        db.session.query(func.coalesce(func.sum(WasteLog.qty_kg), Decimal("0")))
        .filter(
            WasteLog.logged_on >= start,
            WasteLog.logged_on <= end,
            *filters["waste"],
        )
        .scalar()
        or Decimal("0")
    )

    claims_resolved = (
        db.session.query(func.count(Claim.id))
        .filter(
            Claim.status == "picked_up",
            func.date(Claim.claimed_at) >= start,
            func.date(Claim.claimed_at) <= end,
            *filters["claims"],
        )
        .scalar()
        or 0
    )

    rupiah_saved = (
        db.session.query(
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))),
                Decimal("0"),
            )
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .scalar()
        or Decimal("0")
    )

    co2e_avoided = (
        db.session.query(
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.co2e_per_kg, Decimal("0"))),
                Decimal("0"),
            )
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .scalar()
        or Decimal("0")
    )

    return {
        "kg_saved": kg_saved,
        "kg_waste": kg_waste,
        "claims_resolved": Decimal(claims_resolved),
        "rupiah_saved": rupiah_saved,
        "meals": kg_saved / MEALS_PER_KG,
        "co2e_avoided": co2e_avoided,
    }


def get_report_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Calculate aggregate KPIs for the selected report range using SQL."""
    metrics = get_report_metrics(start_date=start_date, end_date=end_date, scope=scope)

    kg_saved = metrics["kg_saved"]
    kg_waste = metrics["kg_waste"]
    claims_resolved = metrics["claims_resolved"]
    rupiah_saved = metrics["rupiah_saved"]

    rupiah_val = float(rupiah_saved)
    if rupiah_val >= 1_000_000:
        rupiah_str = f"Rp {rupiah_val / 1_000_000:.1f} jt"
    else:
        rupiah_str = f"Rp {int(rupiah_val):,}".replace(",", ".")

    return [
        {
            "label": "Pangan terselamatkan",
            "value": f"{float(kg_saved):,.0f}".replace(",", "."),
            "unit": "kg",
            "delta": "+14,7%",
            "delta_up": True,
            "icon": "leaf",
        },
        {
            "label": "Limbah tercatat",
            "value": f"{float(kg_waste):.1f}".replace(".", ","),
            "unit": "kg",
            "delta": "-6,3%",
            "delta_up": True,
            "icon": "cloud",
        },
        {
            "label": "Klaim diselesaikan",
            "value": str(int(claims_resolved)),
            "unit": "klaim",
            "delta": "+11,2%",
            "delta_up": True,
            "icon": "clipboard",
        },
        {
            "label": "Nilai dampak",
            "value": rupiah_str,
            "unit": "",
            "delta": "+16,0%",
            "delta_up": True,
            "icon": "package",
        },
    ]



def get_report_rekap(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return daily recap rows aggregated through SQL.

    Each row carries human-readable strings for the UI plus raw numeric values
    (``saved_kg``, ``waste_kg``, ``claim_count``, ``rupiah_value``) used by the
    export writers so spreadsheets keep sortable numbers.
    """
    today = date.today()
    start = start_date or (today - timedelta(days=7))
    end = end_date or today
    filters = _scope_filters(scope)

    # Saved per day
    saved_rows = (
        db.session.query(
            func.date(SurplusListing.created_at).label("dt"),
            func.sum(SurplusListing.qty_kg).label("kg"),
            func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))).label("rp"),
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .group_by(func.date(SurplusListing.created_at))
        .all()
    )
    saved_map: dict[date, tuple[float, float]] = {}
    for row in saved_rows:
        key = to_date(row.dt)
        if key is not None:
            saved_map[key] = (float(row.kg), float(row.rp))

    # Wasted per day
    waste_rows = (
        db.session.query(
            WasteLog.logged_on.label("dt"),
            func.sum(WasteLog.qty_kg).label("kg"),
        )
        .filter(
            WasteLog.logged_on >= start,
            WasteLog.logged_on <= end,
            *filters["waste"],
        )
        .group_by(WasteLog.logged_on)
        .all()
    )
    waste_map: dict[date, float] = {}
    for row in waste_rows:
        key = to_date(row.dt)
        if key is not None:
            waste_map[key] = float(row.kg)

    # Claims per day
    claim_rows = (
        db.session.query(
            func.date(Claim.claimed_at).label("dt"),
            func.count(Claim.id).label("cnt"),
        )
        .filter(
            Claim.status == "picked_up",
            func.date(Claim.claimed_at) >= start,
            func.date(Claim.claimed_at) <= end,
            *filters["claims"],
        )
        .group_by(func.date(Claim.claimed_at))
        .all()
    )
    claim_map: dict[date, int] = {}
    for row in claim_rows:
        key = to_date(row.dt)
        if key is not None:
            claim_map[key] = row.cnt

    # Union of all dates
    all_dates = sorted(set(list(saved_map.keys()) + list(waste_map.keys()) + list(claim_map.keys())), reverse=True)

    rekap: list[dict[str, Any]] = []
    for d in all_dates:
        saved_kg, saved_rp = saved_map.get(d, (0.0, 0.0))
        wasted_kg = waste_map.get(d, 0.0)
        claims = claim_map.get(d, 0)
        rekap.append(
            {
                "tanggal": d.strftime("%d %b %Y"),
                "tanggal_iso": d.isoformat(),
                "kg_diselamatkan": f"{saved_kg:,.0f}".replace(",", "."),
                "kg_terbuang": f"{wasted_kg:.1f}".replace(".", ","),
                "klaim": str(claims),
                "rupiah": f"Rp {int(saved_rp):,}".replace(",", "."),
                "saved_kg": round(saved_kg, 2),
                "waste_kg": round(wasted_kg, 2),
                "claim_count": int(claims),
                "rupiah_value": round(saved_rp, 2),
            }
        )
    return rekap


def get_report_kategori(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return per-category recap aggregated through SQL.

    Rows include raw numeric fields (``saved_kg``, ``waste_kg``,
    ``contribution_pct``) alongside the formatted strings used by the UI.
    """
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    filters = _scope_filters(scope)

    total_saved = (
        db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("1")))
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .scalar()
        or Decimal("1")
    )

    saved_cat = (
        db.session.query(
            FoodCategory.name.label("name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("saved_kg"),
        )
        .join(SurplusListing, SurplusListing.category_id == FoodCategory.id)
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .group_by(FoodCategory.id, FoodCategory.name)
        .all()
    )
    saved_map = {r.name: float(r.saved_kg) for r in saved_cat}

    waste_cat = (
        db.session.query(
            FoodCategory.name.label("name"),
            func.coalesce(func.sum(WasteLog.qty_kg), Decimal("0")).label("waste_kg"),
        )
        .join(WasteLog, WasteLog.category_id == FoodCategory.id)
        .filter(
            WasteLog.logged_on >= start,
            WasteLog.logged_on <= end,
            *filters["waste"],
        )
        .group_by(FoodCategory.id, FoodCategory.name)
        .all()
    )
    waste_map = {r.name: float(r.waste_kg) for r in waste_cat}

    all_cats = db.session.query(FoodCategory.name).order_by(FoodCategory.id).all()
    results: list[dict[str, Any]] = []

    for c in all_cats:
        c_name = c[0]
        s_kg = saved_map.get(c_name, 0.0)
        w_kg = waste_map.get(c_name, 0.0)
        pct = (s_kg / float(total_saved) * 100) if float(total_saved) > 0 else 0.0
        results.append(
            {
                "kategori": c_name,
                "kg_diselamatkan": f"{s_kg:,.0f}".replace(",", "."),
                "kg_terbuang": f"{w_kg:.1f}".replace(".", ","),
                "kontribusi": f"{pct:.1f}%".replace(".", ","),
                "saved_kg": round(s_kg, 2),
                "waste_kg": round(w_kg, 2),
                "contribution_pct": round(pct, 2),
            }
        )
    return results


def get_report_detail(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope: Optional[ReportScope] = None,
) -> list[dict[str, Any]]:
    """Return transaction-level rows of rescued surplus for the given range.

    Each row describes one picked-up surplus listing together with its
    organisation, category, city, quantity, and monetary impact.

    Args:
        start_date: Inclusive start of the reporting window.
        end_date: Inclusive end of the reporting window.
        scope: Role/organization/city restriction of the request.

    Returns:
        List of detail rows ordered from newest to oldest.
    """
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    filters = _scope_filters(scope)

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
            func.coalesce(
                SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0")),
                Decimal("0"),
            ).label("rupiah"),
        )
        .join(Organization, SurplusListing.org_id == Organization.id)
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .join(City, SurplusListing.city_id == City.id)
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= end,
            *filters["listing"],
        )
        .order_by(SurplusListing.created_at.desc())
        .all()
    )

    detail: list[dict[str, Any]] = []
    for row in rows:
        tanggal = to_date(row.tanggal)
        detail.append(
            {
                "tanggal": tanggal.strftime("%d %b %Y") if tanggal else "-",
                "tanggal_iso": tanggal.isoformat() if tanggal else "",
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
    """Return the list of cities usable as a report filter."""
    rows = (
        db.session.query(City.id, City.name, Province.name)
        .join(Province, City.province_id == Province.id)
        .order_by(Province.name, City.name)
        .all()
    )
    return [{"id": r.id, "name": r.name, "province": r[2]} for r in rows]


def get_city_name(city_id: Optional[int]) -> Optional[str]:
    """Return the display name of a city, or ``None`` when the id is unknown."""
    if city_id is None:
        return None
    return db.session.query(City.name).filter(City.id == city_id).scalar()


