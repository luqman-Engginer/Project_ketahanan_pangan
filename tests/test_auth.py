"""Tests for authentication: registration, login, logout, and password hashing."""
from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import User
from tests.conftest import make_org, make_user


def test_register_creates_user_and_organization(client: Any) -> None:
    """A valid registration creates an org and an Argon2-hashed user."""
    resp = client.post(
        "/register",
        data={
            "name": "Donor Baru",
            "role": "donor",
            "email": "baru@uji.id",
            "password": "rahasia123",
            "confirm": "rahasia123",
            "terms": "y",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    user = User.query.filter_by(email="baru@uji.id").first()
    assert user is not None
    assert user.role == "donor"
    assert user.org_id is not None
    assert user.password_hash.startswith("$argon2")


def test_register_rejects_duplicate_email(client: Any, app: Any) -> None:
    """Registering an existing email must not create a second user."""
    org = make_org("Donor Lama", "donor")
    make_user("dup@uji.id", "donor", org.id)

    client.post(
        "/register",
        data={
            "name": "Donor Lain",
            "role": "donor",
            "email": "dup@uji.id",
            "password": "rahasia123",
            "confirm": "rahasia123",
            "terms": "y",
        },
        follow_redirects=True,
    )
    assert User.query.filter_by(email="dup@uji.id").count() == 1


def test_login_valid_credentials(client: Any, app: Any) -> None:
    """Login with correct credentials redirects to the dashboard."""
    org = make_org("Donor Login", "donor")
    make_user("login@uji.id", "donor", org.id)

    resp = client.post("/login", data={"email": "login@uji.id", "password": "rahasia123"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_login_invalid_password(client: Any, app: Any) -> None:
    """Login with a wrong password keeps the user unauthenticated."""
    org = make_org("Donor Salah", "donor")
    make_user("salah@uji.id", "donor", org.id)

    resp = client.post("/login", data={"email": "salah@uji.id", "password": "salahsekali"})
    assert resp.status_code == 200
    assert b"/dashboard" not in resp.data


def test_logout_clears_session(client: Any, app: Any) -> None:
    """Logout redirects away and protects the dashboard afterwards."""
    org = make_org("Donor Logout", "donor")
    make_user("logout@uji.id", "donor", org.id)
    client.post("/login", data={"email": "logout@uji.id", "password": "rahasia123"})

    assert client.get("/dashboard").status_code == 200
    client.get("/logout")
    assert client.get("/dashboard").status_code == 302


def test_password_is_argon2_hashed(app: Any) -> None:
    """Passwords are never stored in plaintext and verify correctly."""
    org = make_org("Donor Hash", "donor")
    user = make_user("hash@uji.id", "donor", org.id, password="rahasia123")
    assert user.password_hash != "rahasia123"
    assert user.check_password("rahasia123") is True
    assert user.check_password("salah") is False
