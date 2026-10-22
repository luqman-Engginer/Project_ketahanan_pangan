"""Tests for impact KPI aggregation (PRD Section 5) and the public JSON API."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models import SurplusListing
from app.services import impact
from tests.conftest import make_org
from app.models import City, ImpactFactor, Organization


def _make_picked_listing(org, category_id: int, qty_kg: str, created: datetime) -> SurplusListing:
    """Insert a picked-up listing with an explicit creation timestamp."""
    listing = SurplusListing(
        org_id=org.id,
        category_id=category_id,
        title="Listing dampak",
        qty=Decimal("10"),
        unit="porsi",
        qty_kg=Decimal(qty_kg),
        pickup_before=created + timedelta(hours=6),
        city_id=org.city_id,
        status="picked_up",
        created_at=created,
    )
    db.session.add(listing)
    db.session.commit()
    return listing


def test_kpis_computed_via_sql(app: Any) -> None:
    """kg, rupiah, meals, and CO2e follow the PRD formulas."""
    org = make_org("Donor KPI", "donor")
    _make_picked_listing(org, 1, "10", datetime.utcnow())
    _make_picked_listing(org, 3, "5", datetime.utcnow())

    kpis = impact.calculate_impact_kpis()
    # 10*35000 + 5*28000 = 490000
    assert float(kpis["kg_saved"]) == 15.0
    assert float(kpis["rupiah_saved"]) == 490000.0
    assert float(kpis["meals"]) == 15.0 / 0.4
    # 10*2.5 + 5*1.2 = 31
    assert float(kpis["co2e_avoided"]) == 31.0


def test_impact_only_counts_picked_up(app: Any) -> None:
    """Available or claimed listings do not count toward impact."""
    org = make_org("Donor Status", "donor")
    _make_picked_listing(org, 1, "10", datetime.utcnow())
    from tests.conftest import make_listing

    make_listing(org, status="available", qty_kg="99")
    make_listing(org, status="claimed", qty_kg="99")

    kpis = impact.calculate_impact_kpis()
    assert float(kpis["kg_saved"]) == 10.0


def test_kpis_respect_date_and_org_filters(app: Any) -> None:
    """Date range and org filters scope the aggregation."""
    org = make_org("Donor Filter KPI", "donor")
    old = datetime.utcnow() - timedelta(days=60)
    _make_picked_listing(org, 1, "10", datetime.utcnow())
    _make_picked_listing(org, 1, "7", old)

    recent = impact.calculate_impact_kpis(start_date=date.today() - timedelta(days=7))
    assert float(recent["kg_saved"]) == 10.0

    total = impact.calculate_impact_kpis(org_id=org.id)
    assert float(total["kg_saved"]) == 17.0


def test_monthly_trend_aggregates_in_sql(app: Any) -> None:
    """Monthly trend groups picked-up kilograms by month."""
    org = make_org("Donor Trend", "donor")
    _make_picked_listing(org, 1, "8", datetime.utcnow())
    trend = impact.get_monthly_rescued_trend(months=6)
    assert len(trend["labels"]) == 6
    assert trend["values"][-1] == 8.0


def test_public_impact_api_returns_aggregates(client: Any, app: Any) -> None:
    """The open-data endpoint returns the aggregated JSON payload."""
    org = make_org("Donor API", "donor")
    _make_picked_listing(org, 1, "20", datetime.utcnow())

    resp = client.get("/api/public/impact")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_rescued_kg"] == 20.0
    assert data["organization_count"] == 1
    assert data["meals_provided"] == int(20.0 / 0.4)
    assert "monthly_rescued_kg" in data
    assert "regional_breakdown" in data
    assert "rupiah_saved" in data


def test_public_pages_render_without_login(client: Any, app: Any) -> None:
    """Landing, public dashboard, and API are reachable anonymously."""
    assert client.get("/").status_code == 200
    assert client.get("/publik").status_code == 200
    assert client.get("/api/public/impact").status_code == 200
