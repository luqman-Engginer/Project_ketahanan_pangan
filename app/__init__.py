"""FoodLoop ID application factory."""
from __future__ import annotations

import secrets
from typing import Any

from flask import Flask, request

from app.blueprints import (
    admin_bp,
    auth_bp,
    events_bp,
    export_bp,
    inventory_bp,
    main_bp,
    notification_bp,
    public_bp,
    report_bp,
    surplus_bp,
    waste_bp,
)
from app.config import Config
from app.error_handlers import register_error_handlers
from app.extensions import csrf, db, limiter, login_manager, migrate, talisman
import app.models  # noqa: F401


@login_manager.user_loader
def _load_user(user_id: str):
    """Load user by primary key for Flask-Login."""
    from app.models.user import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def _register_extensions(app: Flask) -> None:
    """Initialise shared Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan masuk terlebih dahulu untuk mengakses halaman ini."
    login_manager.login_message_category = "warning"
    csrf.init_app(app)
    limiter.init_app(app)
    _register_security_headers(app)


def _register_security_headers(app: Flask) -> None:
    """Apply security headers (CSP with nonce, HSTS, frame and referrer policies).

    The Content Security Policy allows the CDNs used by HTMX and Chart.js while
    inline scripts must carry the per-request nonce exposed as ``csp_nonce()``.

    Args:
        app: The Flask application to harden.
    """
    talisman.init_app(
        app,
        content_security_policy=app.config["TALISMAN_CONTENT_SECURITY_POLICY"],
        content_security_policy_nonce_in=app.config["TALISMAN_NONCE_SECTIONS"],
        force_https=app.config["FORCE_HTTPS"],
        frame_options=app.config["TALISMAN_FRAME_OPTIONS"],
        referrer_policy=app.config["TALISMAN_REFERRER_POLICY"],
        session_cookie_secure=app.config["SESSION_COOKIE_SECURE"],
        session_cookie_http_only=True,
        session_cookie_samesite="Lax",
        strict_transport_security=True,
        strict_transport_security_max_age=app.config["TALISMAN_HSTS_MAX_AGE"],
        x_content_type_options=True,
        x_xss_protection=False,
    )


def _register_blueprints(app: Flask) -> None:
    """Register HTTP blueprints."""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(surplus_bp)
    app.register_blueprint(waste_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(public_bp)


def _register_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""
    from app.scripts.seed import create_admin_command, demo_clear_command, seed_command, seed_demo_command

    app.cli.add_command(seed_command)
    app.cli.add_command(seed_demo_command)
    app.cli.add_command(demo_clear_command)
    app.cli.add_command(create_admin_command)


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_class: Configuration class loaded via ``app.config.from_object``.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    if not app.config.get("SECRET_KEY"):
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        else:
            raise RuntimeError("SECRET_KEY wajib diisi melalui environment pada mode production.")
    if not app.config.get("DEBUG") and not app.config.get("TESTING"):
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("Production menolak start bila SECRET_KEY kosong.")
    _register_extensions(app)
    _register_blueprints(app)
    _register_commands(app)
    register_error_handlers(app)

    @app.after_request
    def prevent_authenticated_caching(response):
        """Prevent browsers from caching authenticated and auth pages."""
        from flask_login import current_user

        if response.mimetype == "text/html" and (
            current_user.is_authenticated or request.endpoint in {"auth.login", "auth.register"}
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        """Expose current user notification badge count to all templates."""
        from flask_login import current_user
        from app.services import notification_service

        unread = notification_service.get_unread_count(current_user.id) if current_user.is_authenticated else 0
        return {"unread_count": unread}

    return app
