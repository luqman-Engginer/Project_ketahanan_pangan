"""Admin operations service for organization verification and master data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from app.extensions import db
from app.models import AuditLog, City, FoodCategory, ImpactFactor, Organization, User
from app.services import realtime


def list_organizations() -> list[dict[str, Any]]:
    """List all organizations with city and verification status."""
    rows = (
        db.session.query(Organization, City.name.label("city_name"))
        .join(City, Organization.city_id == City.id)
        .order_by(Organization.created_at.desc())
        .all()
    )
    return [
        {
            "id": org.id,
            "name": org.name,
            "type": org.type,
            "city": city_name,
            "address": org.address or "-",
            "phone": org.phone or "-",
            "is_verified": org.verified_at is not None,
            "verified_at": org.verified_at.strftime("%d %b %Y") if org.verified_at else None,
        }
        for org, city_name in rows
    ]


def verify_organization(org_id: int, admin_user_id: int) -> Organization:
    """Verify an organization and record an audit log."""
    org = Organization.query.get_or_404(org_id)
    org.verified_at = datetime.utcnow()

    log = AuditLog(
        user_id=admin_user_id,
        action="VERIFY_ORGANIZATION",
        entity="organization",
        entity_id=org.id,
    )
    db.session.add(log)
    db.session.commit()
    return org


def get_impact_factors() -> list[dict[str, Any]]:
    """Get all food category impact factors."""
    rows = (
        db.session.query(ImpactFactor, FoodCategory.name.label("category_name"))
        .join(FoodCategory, ImpactFactor.category_id == FoodCategory.id)
        .order_by(ImpactFactor.category_id.asc())
        .all()
    )
    return [
        {
            "id": factor.id,
            "category_id": factor.category_id,
            "category_name": cat_name,
            "price_per_kg": float(factor.price_per_kg),
            "co2e_per_kg": float(factor.co2e_per_kg),
            "source_note": factor.source_note,
        }
        for factor, cat_name in rows
    ]


def get_audit_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent administrative audit log entries with the acting user name.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of formatted audit log dictionaries.
    """
    rows = (
        db.session.query(AuditLog, User.name.label("user_name"))
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "user": user_name or "-",
            "action": log.action,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "created_at": log.created_at.strftime("%d %b %Y, %H:%M"),
        }
        for log, user_name in rows
    ]


def update_impact_factor(
    category_id: int,
    price_per_kg: Decimal,
    co2e_per_kg: Decimal,
    admin_user_id: int,
) -> ImpactFactor:
    """Update price and emission factors for a category."""
    factor = ImpactFactor.query.filter_by(category_id=category_id).first_or_404()
    factor.price_per_kg = price_per_kg
    factor.co2e_per_kg = co2e_per_kg

    log = AuditLog(
        user_id=admin_user_id,
        action="UPDATE_IMPACT_FACTOR",
        entity="impact_factor",
        entity_id=factor.id,
    )
    db.session.add(log)
    db.session.commit()
    realtime.publish_kpi_update()
    return factor

