"""Authentication and user management services."""
from __future__ import annotations

from typing import Optional

from flask_login import login_user, logout_user

from app.extensions import db
from app.models import City, Organization, User


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Verify user credentials against stored Argon2 hash.

    Args:
        email: User email address.
        password: Plaintext password attempt.

    Returns:
        Authenticated User instance, or None if invalid.
    """
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user or not user.is_active:
        return None
    if not user.check_password(password):
        return None
    return user


def register_user(
    name: str,
    role: str,
    email: str,
    password: str,
    city_id: Optional[int] = None,
    address: Optional[str] = None,
    phone: Optional[str] = None,
) -> User:
    """Register a new user and create their corresponding organization.

    Args:
        name: Name of the user or organization.
        role: User role ('donor' or 'receiver').
        email: Unique email address.
        password: Plaintext password to hash with Argon2.
        city_id: City ID (falls back to default city if unspecified).
        address: Optional physical address.
        phone: Optional contact phone number.

    Returns:
        Created User instance.

    Raises:
        ValueError: If email is already registered.
    """
    cleaned_email = email.strip().lower()
    if User.query.filter_by(email=cleaned_email).first():
        raise ValueError("Email sudah terdaftar. Silakan gunakan email lain atau masuk.")

    # Assign fallback city if not provided
    if not city_id:
        default_city = City.query.first()
        city_id = default_city.id if default_city else 3171

    # Create associated organization for donors/receivers
    org = Organization(
        name=name.strip(),
        type=role,
        city_id=city_id,
        address=address.strip() if address else None,
        phone=phone.strip() if phone else None,
    )
    db.session.add(org)
    db.session.flush()

    user = User(
        name=name.strip(),
        email=cleaned_email,
        role=role,
        org_id=org.id,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user

