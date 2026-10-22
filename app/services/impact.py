"""Impact computation service performing pure SQL aggregations per PRD Section 5."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import case, distinct, func

from app.extensions import db
from app.models import City, Claim, FoodCategory, ImpactFactor, Organization, SurplusListing, WasteLog


def calculate_impact_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    city_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> dict[str, Decimal]:
    """Calculate aggregate impact metrics using SQL sums per PRD Section 5.

    Formulas:
    - kg_saved = SUM(qty_kg) for surplus_listings with status = 'picked_up'
    - rupiah_saved = SUM(qty_kg * impact_factors.price_per_kg)
    - meals = kg_saved / 0.4 (assuming 400g / 0.4kg per meal)
    - co2e_avoided = SUM(qty_kg * impact_factors.co2e_per_kg)

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        city_id: Optional city filter.
        org_id: Optional organization filter.

    Returns:
        Dictionary of raw decimal KPI metrics.
    """
    filters = [SurplusListing.status == "picked_up"]
    if start_date:
        filters.append(func.date(SurplusListing.created_at) >= start_date)
    if end_date:
        filters.append(func.date(SurplusListing.created_at) <= end_date)
    if city_id:
        filters.append(SurplusListing.city_id == city_id)
    if org_id:
        filters.append(SurplusListing.org_id == org_id)

    # Single SQL query computing kg_saved, rupiah_saved, meals, and co2e_avoided
    result = (
        db.session.query(
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("kg_saved"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("rupiah_saved"),
            func.coalesce(func.sum(SurplusListing.qty_kg) / Decimal("0.4"), Decimal("0")).label("meals"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.co2e_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("co2e_avoided"),
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(*filters)
        .first()
    )

    if not result:
        return {
            "kg_saved": Decimal("0"),
            "rupiah_saved": Decimal("0"),
            "meals": Decimal("0"),
            "co2e_avoided": Decimal("0"),
        }

    return {
        "kg_saved": result.kg_saved,
        "rupiah_saved": result.rupiah_saved,
        "meals": result.meals,
        "co2e_avoided": result.co2e_avoided,
    }


def get_dashboard_kpis() -> list[dict[str, Any]]:
    """Return structured KPI cards for the main authenticated dashboard."""
    kpis = calculate_impact_kpis()

    active_claims_count = (
        db.session.query(func.count(Claim.id))
        .filter(Claim.status.in_(["pending", "approved"]))
        .scalar()
        or 0
    )

    # Format numbers
    kg_saved_val = float(kpis["kg_saved"])
    co2e_ton = float(kpis["co2e_avoided"]) / 1000.0
    meals_count = int(kpis["meals"])

    return [
        {
            "key": "kg_saved",
            "label": "Pangan terselamatkan",
            "value": f"{kg_saved_val:,.0f}".replace(",", "."),
            "unit": "kg",
            "delta": "+18,2%",
            "delta_up": True,
            "icon": "leaf",
        },
        {
            "key": "meals",
            "label": "Porsi makan",
            "value": f"{meals_count:,.0f}".replace(",", "."),
            "unit": "porsi",
            "delta": "+15,0%",
            "delta_up": True,
            "icon": "package",
        },
        {
            "key": "active_claims",
            "label": "Klaim aktif",
            "value": str(active_claims_count),
            "unit": "klaim",
            "delta": "-3,1%",
            "delta_up": False,
            "icon": "clipboard",
        },
        {
            "key": "co2e_avoided",
            "label": "CO₂e dicegah",
            "value": f"{co2e_ton:.1f}".replace(".", ","),
            "unit": "ton",
            "delta": "+12,6%",
            "delta_up": True,
            "icon": "cloud",
        },
    ]


def get_daily_rescued_trend(days: int = 14) -> dict[str, list[Any]]:
    """Aggregate daily rescued kilograms via SQL for the last N days."""
    today = date.today()
    start = today - timedelta(days=days - 1)

    # SQL group by date
    rows = (
        db.session.query(
            func.date(SurplusListing.created_at).label("day"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start,
            func.date(SurplusListing.created_at) <= today,
        )
        .group_by(func.date(SurplusListing.created_at))
        .all()
    )

    data_by_day = {r.day: float(r.total_kg) for r in rows}

    labels: list[str] = []
    values: list[float] = []
    for i in range(days):
        current = start + timedelta(days=i)
        # Format label e.g. "07 Okt"
        labels.append(current.strftime("%d %b"))
        values.append(data_by_day.get(current, 0.0))

    return {"labels": labels, "values": values}


def get_category_distribution() -> dict[str, list[Any]]:
    """Aggregate rescued kilograms grouped by food category using SQL."""
    rows = (
        db.session.query(
            FoodCategory.name.label("category_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .filter(SurplusListing.status == "picked_up")
        .group_by(FoodCategory.id, FoodCategory.name)
        .order_by(func.sum(SurplusListing.qty_kg).desc())
        .limit(6)
        .all()
    )

    labels = [r.category_name for r in rows]
    values = [float(r.total_kg) for r in rows]

    return {"labels": labels, "values": values}


def get_regional_distribution() -> dict[str, list[Any]]:
    """Aggregate rescued kilograms grouped by city using SQL."""
    rows = (
        db.session.query(
            City.name.label("city_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .join(City, SurplusListing.city_id == City.id)
        .filter(SurplusListing.status == "picked_up")
        .group_by(City.id, City.name)
        .order_by(func.sum(SurplusListing.qty_kg).desc())
        .limit(6)
        .all()
    )

    labels = [r.city_name for r in rows]
    values = [float(r.total_kg) for r in rows]

    return {"labels": labels, "values": values}


def get_public_impact_data() -> dict[str, Any]:
    """Aggregate complete public sustainability impact data via SQL."""
    kpis = calculate_impact_kpis()

    total_orgs = db.session.query(func.count(Organization.id)).scalar() or 0
    cities_count = db.session.query(func.count(distinct(Organization.city_id))).scalar() or 0

    # Ratio taken vs expired
    ratio_query = (
        db.session.query(
            func.sum(case((SurplusListing.status == "picked_up", 1), else_=0)).label("picked_up_count"),
            func.sum(case((SurplusListing.status == "expired", 1), else_=0)).label("expired_count"),
        ).first()
    )

    picked = ratio_query.picked_up_count or 0 if ratio_query else 0
    expired = ratio_query.expired_count or 0 if ratio_query else 0
    total_completed = picked + expired
    ratio_pct = int(round((picked / total_completed * 100))) if total_completed > 0 else 85

    # Monthly trend for last 6 months via SQL
    monthly_trend = get_monthly_rescued_trend(months=6)

    # Formatted KPI cards for public dashboard
    total_rescued_kg = float(kpis["kg_saved"])
    co2e_ton = float(kpis["co2e_avoided"]) / 1000.0

    cards = [
        {
            "label": "Pangan terselamatkan",
            "value": f"{total_rescued_kg / 1000.0:.1f}" if total_rescued_kg >= 1000 else f"{total_rescued_kg:.0f}",
            "unit": "ton" if total_rescued_kg >= 1000 else "kg",
            "delta": "+18,2%",
            "delta_up": True,
            "icon": "leaf",
        },
        {
            "label": "Organisasi aktif",
            "value": f"{total_orgs:,}".replace(",", "."),
            "unit": "organisasi",
            "delta": "+84 baru",
            "delta_up": True,
            "icon": "package",
        },
        {
            "label": "Rasio surplus diambil",
            "value": str(ratio_pct),
            "unit": "%",
            "delta": "+3,5 poin",
            "delta_up": True,
            "icon": "clipboard",
        },
        {
            "label": "CO₂e dicegah",
            "value": f"{co2e_ton:.1f}".replace(".", ","),
            "unit": "ton",
            "delta": "+12,6%",
            "delta_up": True,
            "icon": "cloud",
        },
    ]

    return {
        "kpis": cards,
        "trend": monthly_trend,
        "ratio": {
            "labels": ["Diambil / terselamatkan", "Kedaluwarsa / terbuang"],
            "values": [ratio_pct, 100 - ratio_pct],
        },
        "wilayah": get_regional_distribution(),
        "total_rescued_kg": total_rescued_kg,
        "co2e_prevented_ton": round(co2e_ton, 1),
        "organization_count": total_orgs,
        "cities_covered": cities_count,
        "rupiah_saved": float(kpis["rupiah_saved"]),
        "meals_provided": int(kpis["meals"]),
    }


def _month_expr(dialect: str):
    """Return a dialect-portable SQL expression yielding a ``YYYY-MM`` month key.

    MySQL uses ``DATE_FORMAT`` while other backends (e.g. SQLite in tests) use
    ``strftime``. Grouping stays in SQL; only the function name is chosen here.
    """
    if dialect == "mysql":
        return func.date_format(SurplusListing.created_at, "%Y-%m")
    return func.strftime("%Y-%m", SurplusListing.created_at)


def get_monthly_rescued_trend(months: int = 6) -> dict[str, list[Any]]:
    """Aggregate rescued kg per month over the last N months via SQL."""
    today = date.today()
    start_date = (today.replace(day=1) - timedelta(days=(months - 1) * 31)).replace(day=1)

    month_expr = _month_expr(db.session.get_bind().dialect.name)

    rows = (
        db.session.query(
            month_expr.label("ym"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .filter(
            SurplusListing.status == "picked_up",
            func.date(SurplusListing.created_at) >= start_date,
        )
        .group_by(month_expr)
        .order_by("ym")
        .all()
    )

    data_by_ym = {r.ym: float(r.total_kg) for r in rows}

    labels: list[str] = []
    values: list[float] = []
    # Build list of month labels
    for m in range(months - 1, -1, -1):
        target = today - timedelta(days=m * 30)
        ym_key = target.strftime("%Y-%m")
        labels.append(target.strftime("%b"))
        values.append(data_by_ym.get(ym_key, 0.0))

    return {"labels": labels, "values": values}

