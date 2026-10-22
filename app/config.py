"""Environment-driven application configuration."""
from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back on invalid input."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _database_uri() -> str:
    """Return the SQLAlchemy database URI from ``DATABASE_URL``."""
    uri = os.environ.get("DATABASE_URL", "").strip()
    if not uri:
        raise RuntimeError(
            "DATABASE_URL is not set: copy .env.example to .env and fill it in."
        )
    return uri


class Config:
    """Base configuration sourced from environment variables."""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "").strip() or secrets.token_hex(32)
    DEBUG: bool = _env_bool("FLASK_DEBUG")
    TESTING: bool = False

    SQLALCHEMY_DATABASE_URI: str = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, int] = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    # --- Session & cookie hardening -------------------------------------------------
    SESSION_COOKIE_NAME: str = os.environ.get("SESSION_COOKIE_NAME", "foodloop_session")
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = _env_bool("SESSION_COOKIE_SECURE")
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_PATH: str = "/"
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=8)
    REMEMBER_COOKIE_NAME: str = os.environ.get("REMEMBER_COOKIE_NAME", "foodloop_remember")
    REMEMBER_COOKIE_HTTPONLY: bool = True
    REMEMBER_COOKIE_SECURE: bool = _env_bool("SESSION_COOKIE_SECURE")
    REMEMBER_COOKIE_SAMESITE: str = "Lax"
    REMEMBER_COOKIE_DURATION: timedelta = timedelta(days=7)

    MAX_CONTENT_LENGTH: int = _env_int("MAX_CONTENT_LENGTH_MB", 16) * 1024 * 1024
    WTF_CSRF_TIME_LIMIT: int = 3600
    WTF_CSRF_SSL_STRICT: bool = _env_bool("WTF_CSRF_SSL_STRICT")
    RATELIMIT_STORAGE_URI: str = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Upload hardening -----------------------------------------------------------
    UPLOAD_FOLDER: str = os.environ.get("UPLOAD_FOLDER", str(INSTANCE_DIR / "uploads"))
    UPLOAD_MAX_BYTES: int = _env_int("UPLOAD_MAX_BYTES_KB", 2048) * 1024
    UPLOAD_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"png", "jpg", "jpeg", "webp"})

    # --- Security headers (Flask-Talisman) -------------------------------------------
    FORCE_HTTPS: bool = _env_bool("FORCE_HTTPS")
    TALISMAN_CONTENT_SECURITY_POLICY: dict[str, list[str]] = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'self'"],
        "form-action": ["'self'"],
        "script-src": [
            "'self'",
            "'nonce-{nonce}'",
            "https://unpkg.com",
            "https://cdn.jsdelivr.net",
        ],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
        "img-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "worker-src": ["'self'", "blob:"],
        "manifest-src": ["'self'"],
    }
    TALISMAN_NONCE_SECTIONS: list[str] = ["script-src"]
    TALISMAN_REFERRER_POLICY: str = "strict-origin-when-cross-origin"
    TALISMAN_FRAME_OPTIONS: str = "SAMEORIGIN"
    TALISMAN_HSTS_MAX_AGE: int = 31556926


class TestConfig(Config):
    """In-memory SQLite configuration used by the automated test suite."""

    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite://"
    WTF_CSRF_ENABLED: bool = False
    RATELIMIT_ENABLED: bool = False
    FORCE_HTTPS: bool = False
    SECRET_KEY: str = "testing-secret-key"
    UPLOAD_FOLDER: str = str(INSTANCE_DIR / "uploads-test")
