"""Blueprints package."""
from app.blueprints.admin import bp as admin_bp
from app.blueprints.auth import bp as auth_bp
from app.blueprints.events import bp as events_bp
from app.blueprints.export import bp as export_bp
from app.blueprints.inventory import bp as inventory_bp
from app.blueprints.main import bp as main_bp
from app.blueprints.notification import bp as notification_bp
from app.blueprints.report import bp as report_bp
from app.blueprints.surplus import bp as surplus_bp
from app.blueprints.waste import bp as waste_bp

__all__ = [
    "main_bp",
    "auth_bp",
    "inventory_bp",
    "surplus_bp",
    "waste_bp",
    "report_bp",
    "export_bp",
    "notification_bp",
    "admin_bp",
    "events_bp",
]
