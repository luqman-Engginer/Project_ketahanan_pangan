"""Password hashing helpers backed by Argon2id."""
from __future__ import annotations

from argon2 import PasswordHasher

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Args:
        password: Plaintext password to hash.

    Returns:
        The Argon2 encoded hash string.
    """
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Args:
        password: Plaintext password supplied by the user.
        password_hash: Stored Argon2 hash.

    Returns:
        ``True`` when the password matches, otherwise ``False``.
    """
    try:
        return _ph.verify(password_hash, password)
    except Exception:
        return False
