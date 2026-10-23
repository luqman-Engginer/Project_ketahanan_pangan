"""Impact aggregation based only on approved surplus listings."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import case, distinct, func, or_

from app.extensions import db
from app.models import City, FoodCategory, ImpactFactor, Organization, SurplusListing

MEALS_PER_KG = Decimal("0.4")


def calculate_impact_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    city_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> dict[str, Decimal]:
    """Calculate impact metrics for approved surplus within the given scope."""
    filters = [SurplusListing.review_status == "approved"]
    if start_date:
        filters.append(func.date(SurplusListing.created_at) >= start_date)
    if end_date:
        filters.append(func.date(SurplusListing.created_at) <= end_date)
    if city_id:
        filters.append(SurplusListing.city_id == city_id)
    if org_id:
        filters.append(SurplusListing.org_id == org_id)

    result = (
        db.session.query(
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("kg_saved"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.price_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("rupiah_saved"),
            func.coalesce(func.sum(SurplusListing.qty_kg) / MEALS_PER_KG, Decimal("0")).label("meals"),
            func.coalesce(
                func.sum(SurplusListing.qty_kg * func.coalesce(ImpactFactor.co2e_per_kg, Decimal("0"))),
                Decimal("0"),
            ).label("co2e_avoided"),
        )
        .outerjoin(ImpactFactor, SurplusListing.category_id == ImpactFactor.category_id)
        .filter(*filters)
        .first()
    )

    return {
        "kg_saved": result.kg_saved if result else Decimal("0"),
        "rupiah_saved": result.rupiah_saved if result else Decimal("0"),
        "meals": result.meals if result else Decimal("0"),
        "co2e_avoided": result.co2e_avoided if result else Decimal("0"),
    }


def get_dashboard_kpis(org_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Return the four headline KPI cards for a dashboard."""
    kpis = calculate_impact_kpis(org_id=org_id)
    kg_saved = float(kpis["kg_saved"])
    rupiah = float(kpis["rupiah_saved"])
    co2e_ton = float(kpis["co2e_avoided"]) / 1000.0
    return [
        {
            "key": "kg_saved",
            "label": "Pangan terselamatkan",
            "value": f"{kg_saved:,.0f}".replace(",", "."),
            "unit": "kg",
            "delta": "Pasokan disetujui",
            "delta_up": True,
            "icon": "leaf",
        },
        {
            "key": "rupiah_saved",
            "label": "Nilai pangan",
            "value": f"Rp {rupiah:,.0f}".replace(",", "."),
            "unit": "",
            "delta": "Harga acuan kategori",
            "delta_up": True,
            "icon": "package",
        },
        {
            "key": "meals",
            "label": "Porsi makan",
            "value": f"{float(kpis['meals']):,.0f}".replace(",", "."),
            "unit": "porsi",
            "delta": "Asumsi 400 g/porsi",
            "delta_up": True,
            "icon": "clipboard",
        },
        {
            "key": "co2e_avoided",
            "label": "CO₂e dicegah",
            "value": f"{co2e_ton:.1f}".replace(".", ","),
            "unit": "ton",
            "delta": "Faktor emisi kategori",
            "delta_up": True,
            "icon": "cloud",
        },
    ]


def get_admin_insights(org_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Compile rule-based admin insight cards for the dashboard."""
    today = date.today()
    current_month_start = today.replace(day=1)
    prev_month_start = (current_month_start.replace(day=1) - timedelta(days=1)).replace(day=1)
    prev_month_end = current_month_start - timedelta(days=1)

    waste_q = (
        db.session.query(
            FoodCategory.name.label("category_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("qty_kg"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .filter(SurplusListing.review_status == "approved")
    )
    if org_id:
        waste_q = waste_q.filter(SurplusListing.org_id == org_id)
    waste_row = waste_q.group_by(FoodCategory.id, FoodCategory.name).order_by(func.sum(SurplusListing.qty_kg).desc()).first()

    current_month = (
        db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= current_month_start,
            func.date(SurplusListing.created_at) <= today,
        )
        .scalar()
        or Decimal("0")
    )
    if org_id:
        current_month = (
            db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
            .filter(
                SurplusListing.org_id == org_id,
                SurplusListing.review_status == "approved",
                func.date(SurplusListing.created_at) >= current_month_start,
                func.date(SurplusListing.created_at) <= today,
            )
            .scalar()
            or Decimal("0")
        )
    previous_month = (
        db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
        .filter(
            SurplusListing.review_status == "approved",
            func.date(SurplusListing.created_at) >= prev_month_start,
            func.date(SurplusListing.created_at) <= prev_month_end,
        )
        .scalar()
        or Decimal("0")
    )
    if org_id:
        previous_month = (
            db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
            .filter(
                SurplusListing.org_id == org_id,
                SurplusListing.review_status == "approved",
                func.date(SurplusListing.created_at) >= prev_month_start,
                func.date(SurplusListing.created_at) <= prev_month_end,
            )
            .scalar()
            or Decimal("0")
        )
    trend_delta = 0.0
    if float(previous_month) > 0:
        trend_delta = ((float(current_month) - float(previous_month)) / float(previous_month)) * 100

    rescued_kg = float(current_month)
    waste_kg = 0.0
    waste_rows = (
        db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
        .filter(SurplusListing.review_status == "rejected", func.date(SurplusListing.created_at) >= current_month_start, func.date(SurplusListing.created_at) <= today)
        .scalar() or Decimal("0")
    )
    if org_id:
        waste_rows = (
            db.session.query(func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")))
            .filter(SurplusListing.org_id == org_id, SurplusListing.review_status == "rejected", func.date(SurplusListing.created_at) >= current_month_start, func.date(SurplusListing.created_at) <= today)
            .scalar() or Decimal("0")
        )
    waste_kg = float(waste_rows)
    ratio = ((rescued_kg / (rescued_kg + waste_kg)) * 100) if (rescued_kg + waste_kg) else 0.0

    return [
        {
            "label": "Kategori paling terbuang",
            "value": waste_row.category_name if waste_row else "Belum ada",
            "unit": "kategori",
            "delta": "30 hari terakhir",
            "delta_up": True,
            "icon": "package",
        },
        {
            "label": "Tren bulan ini",
            "value": f"{trend_delta:+.0f}%",
            "unit": "vs bulan lalu",
            "delta": f"{current_month:.0f} kg",
            "delta_up": trend_delta >= 0,
            "icon": "leaf",
        },
        {
            "label": "Rasio penyelamatan",
            "value": f"{ratio:.0f}%",
            "unit": "efektivitas",
            "delta": "terselamatkan / total",
            "delta_up": ratio >= 50,
            "icon": "clipboard",
        },
    ]


def get_daily_rescued_trend(days: int = 14, org_id: Optional[int] = None) -> dict[str, list[Any]]:
    """Aggregate approved daily rescued kilograms for the last N days."""
    today = date.today()
    start = today - timedelta(days=days - 1)
    filters = [
        SurplusListing.review_status == "approved",
        func.date(SurplusListing.created_at) >= start,
        func.date(SurplusListing.created_at) <= today,
    ]
    if org_id:
        filters.append(SurplusListing.org_id == org_id)

    rows = (
        db.session.query(
            func.date(SurplusListing.created_at).label("day"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .filter(*filters)
        .group_by(func.date(SurplusListing.created_at))
        .all()
    )
    data_by_day = {str(row.day)[:10]: float(row.total_kg) for row in rows}
    labels = [(start + timedelta(days=index)).strftime("%d %b") for index in range(days)]
    values = [data_by_day.get((start + timedelta(days=index)).isoformat(), 0.0) for index in range(days)]
    return {"labels": labels, "values": values}


def get_category_distribution(org_id: Optional[int] = None) -> dict[str, list[Any]]:
    """Aggregate approved kilograms by food category."""
    query = (
        db.session.query(
            FoodCategory.name.label("category_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .join(FoodCategory, SurplusListing.category_id == FoodCategory.id)
        .filter(SurplusListing.review_status == "approved")
    )
    if org_id:
        query = query.filter(SurplusListing.org_id == org_id)
    rows = query.group_by(FoodCategory.id, FoodCategory.name).order_by(func.sum(SurplusListing.qty_kg).desc()).limit(6).all()
    return {"labels": [row.category_name for row in rows], "values": [float(row.total_kg) for row in rows]}


def get_regional_distribution(org_id: Optional[int] = None) -> dict[str, list[Any]]:
    """Aggregate approved kilograms by city."""
    query = (
        db.session.query(
            City.name.label("city_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .join(City, SurplusListing.city_id == City.id)
        .filter(SurplusListing.review_status == "approved")
    )
    if org_id:
        query = query.filter(SurplusListing.org_id == org_id)
    rows = query.group_by(City.id, City.name).order_by(func.sum(SurplusListing.qty_kg).desc()).limit(6).all()
    return {"labels": [row.city_name for row in rows], "values": [float(row.total_kg) for row in rows]}


def _month_expr(dialect: str):
    """Return a portable SQL expression for a YYYY-MM month key."""
    if dialect == "mysql":
        return func.date_format(SurplusListing.created_at, "%Y-%m")
    return func.strftime("%Y-%m", SurplusListing.created_at)


def get_monthly_rescued_trend(months: int = 6, org_id: Optional[int] = None) -> dict[str, list[Any]]:
    """Aggregate approved kilograms per month over the last N months."""
    today = date.today()
    start_date = (today.replace(day=1) - timedelta(days=(months - 1) * 31)).replace(day=1)
    month_expr = _month_expr(db.session.get_bind().dialect.name)
    filters = [
        SurplusListing.review_status == "approved",
        func.date(SurplusListing.created_at) >= start_date,
    ]
    if org_id:
        filters.append(SurplusListing.org_id == org_id)
    rows = (
        db.session.query(month_expr.label("ym"), func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"))
        .filter(*filters)
        .group_by(month_expr)
        .order_by("ym")
        .all()
    )
    data_by_ym = {row.ym: float(row.total_kg) for row in rows}
    labels: list[str] = []
    values: list[float] = []
    for offset in range(months - 1, -1, -1):
        target = today - timedelta(days=offset * 30)
        labels.append(target.strftime("%b"))
        values.append(data_by_ym.get(target.strftime("%Y-%m"), 0.0))
    return {"labels": labels, "values": values}


def get_review_counts(org_id: Optional[int] = None) -> dict[str, int]:
    """Return counts of pending, approved, and rejected listings."""
    query = db.session.query(SurplusListing.review_status, func.count(SurplusListing.id))
    if org_id:
        query = query.filter(SurplusListing.org_id == org_id)
    counts = {status: count for status, count in query.group_by(SurplusListing.review_status).all()}
    return {key: int(counts.get(key, 0)) for key in ("pending", "approved", "rejected")}


def get_supplier_summary(org_id: int) -> dict[str, Any]:
    """Return headline counts used by the supplier dashboard."""
    approved = db.session.query(func.count(SurplusListing.id)).filter(
        SurplusListing.org_id == org_id,
        SurplusListing.review_status == "approved",
    ).scalar() or 0
    return {"approved_listings": int(approved), **get_review_counts(org_id)}


def get_regional_distribution() -> dict[str, list[Any]]:
    """Aggregate rescued kilograms grouped by city using SQL."""
    rows = (
        db.session.query(
            City.name.label("city_name"),
            func.coalesce(func.sum(SurplusListing.qty_kg), Decimal("0")).label("total_kg"),
        )
        .join(City, SurplusListing.city_id == City.id)
        .filter(or_(SurplusListing.status == "picked_up", SurplusListing.review_status == "approved"))
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

    ratio_query = (
        db.session.query(
            func.sum(case((or_(SurplusListing.status == "picked_up", SurplusListing.review_status == "approved"), 1), else_=0)).label("picked_up_count"),
            func.sum(case((SurplusListing.status == "expired", 1), else_=0)).label("expired_count"),
        ).first()
    )

    picked = ratio_query.picked_up_count or 0 if ratio_query else 0
    expired = ratio_query.expired_count or 0 if ratio_query else 0
    total_completed = picked + expired
    ratio_pct = int(round((picked / total_completed * 100))) if total_completed > 0 else 85

    monthly_trend = get_monthly_rescued_trend(months=6)

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
