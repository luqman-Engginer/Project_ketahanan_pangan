"""Helpers for building safe redirect targets."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import request


def safe_redirect_target(target: str | None) -> str | None:
    """Return the target only when it points back to this application.

    Absolute URLs, protocol-relative URLs (``//evil.example``) and backslash
    variants are rejected to prevent open-redirect abuse.

    Args:
        target: Raw ``next`` value coming from the request.

    Returns:
        The relative path when it is safe, otherwise ``None``.
    """
    if not target:
        return None
    candidate = target.strip()
    if not candidate.startswith("/") or candidate.startswith("//") or candidate.startswith("/\\"):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    return candidate


def default_next_target() -> str:
    """Return the current request path as a safe default redirect target."""
    return request.path
