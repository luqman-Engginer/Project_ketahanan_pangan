"""Authentication and supplier account services."""
from __future__ import annotations

from typing import Optional

from app.extensions import db
from app.models import City, Organization, User


def list_city_choices() -> list[dict[str, object]]:
    """Return city id/name pairs for registration and profile forms."""
    rows = db.session.query(City.id, City.name).order_by(City.name.asc()).all()
    return [{"id": city_id, "name": name} for city_id, name in rows]


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Return the active user matching the credentials, or ``None``."""
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user or not user.is_active or not user.check_password(password):
        return None
    return user


def register_user(
    name: str,
    email: str,
    password: str,
    city_id: Optional[int] = None,
    address: Optional[str] = None,
    phone: Optional[str] = None,
) -> User:
    """Register a supplier account and its organization.

    Public registration always creates a ``supplier``. Administrator accounts
    can only be created through the ``flask create-admin`` command.
    """
    cleaned_email = email.strip().lower()
    if User.query.filter_by(email=cleaned_email).first():
        raise ValueError("Email sudah terdaftar. Silakan gunakan email lain atau masuk.")

    if not city_id:
        default_city = City.query.first()
        city_id = default_city.id if default_city else 3171

    org = Organization(
        name=name.strip(),
        type="supplier",
        city_id=city_id,
        address=address.strip() if address else None,
        phone=phone.strip() if phone else None,
    )
    db.session.add(org)
    db.session.flush()

    user = User(
        name=name.strip(),
        email=cleaned_email,
        role="supplier",
        org_id=org.id,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def create_admin(name: str, email: str, password: str) -> User:
    """Create an administrator account without an organization."""
    cleaned_email = email.strip().lower()
    if User.query.filter_by(email=cleaned_email).first():
        raise ValueError("Email sudah terdaftar.")
    user = User(name=name.strip(), email=cleaned_email, role="admin", org_id=None, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user
