"""Pytest fixtures: isolated app, database, factories, and authenticated clients."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterator

import pytest
from flask import g

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import (
    City,
    FoodCategory,
    ImpactFactor,
    InventoryItem,
    Organization,
    Province,
    SurplusListing,
    User,
    WasteLog,
)


@pytest.fixture()
def app() -> Iterator[Any]:
    """Provide a Flask app bound to a fresh in-memory database."""
    application = create_app(TestConfig)

    @application.before_request
    def _reset_login_user_cache() -> None:
        """Drop Flask-Login's cached user so each request resolves its own session.

        The fixture keeps one application context alive for the whole test, and
        Flask reuses it for every request. Flask-Login memoises the loaded user
        on ``g``, so without this reset the second test client would inherit the
        first client's identity.
        """
        g.pop("_login_user", None)

    with application.app_context():
        db.create_all()
        _seed_master_data()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app: Any):
    """Flask test client without authentication."""
    return app.test_client()


def _seed_master_data() -> None:
    """Insert the minimum geography, category, and impact-factor rows."""
    db.session.add(Province(id=32, name="Jawa Barat"))
    db.session.add(City(id=3273, name="Bandung", province_id=32))
    db.session.add(FoodCategory(id=1, name="Makanan Siap Santap", unit_default="porsi"))
    db.session.add(FoodCategory(id=3, name="Produk Roti & Bakery", unit_default="buah"))
    db.session.flush()
    db.session.add(ImpactFactor(category_id=1, price_per_kg=Decimal("35000"), co2e_per_kg=Decimal("2.5")))
    db.session.add(ImpactFactor(category_id=3, price_per_kg=Decimal("28000"), co2e_per_kg=Decimal("1.2")))
    db.session.commit()


def make_org(name: str, org_type: str, city_id: int = 3273, verified: bool = True) -> Organization:
    """Create and persist an organization."""
    org = Organization(
        name=name,
        type=org_type,
        city_id=city_id,
        address="Jl. Uji No. 1",
        phone="08123456789",
        verified_at=datetime.utcnow() if verified else None,
    )
    db.session.add(org)
    db.session.commit()
    return org


def make_user(email: str, role: str, org_id: int | None = None, password: str = "rahasia123") -> User:
    """Create and persist a user with an Argon2-hashed password."""
    user = User(name=f"User {role}", email=email, role=role, org_id=org_id, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def make_listing(org: Organization, status: str = "available", qty_kg: str = "10") -> SurplusListing:
    """Create and persist a surplus listing."""
    listing = SurplusListing(
        org_id=org.id,
        category_id=1,
        title="Surplus uji otomatis",
        qty=Decimal("10"),
        unit="porsi",
        qty_kg=Decimal(qty_kg),
        pickup_before=datetime.utcnow() + timedelta(hours=12),
        city_id=org.city_id,
        notes="Catatan uji",
        status=status,
    )
    db.session.add(listing)
    db.session.commit()
    return listing


def _new_client(app: Any, email: str, role: str, org_name: str, org_type: str):
    """Create an organization, user, and an independently logged-in test client."""
    org = make_org(org_name, org_type)
    make_user(email, role, org.id)
    new_client = app.test_client()
    resp = new_client.post("/login", data={"email": email, "password": "rahasia123"})
    assert resp.status_code == 302, f"login failed for {email}"
    return new_client, org


@pytest.fixture()
def donor_client(app: Any):
    """Return a logged-in donor test client plus its organization."""
    return _new_client(app, "donor@uji.id", "donor", "Donor Uji", "donor")


@pytest.fixture()
def receiver_client(app: Any):
    """Return a logged-in receiver test client plus its organization."""
    return _new_client(app, "receiver@uji.id", "receiver", "Penerima Uji", "receiver")
