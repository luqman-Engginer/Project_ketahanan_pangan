"""Authorization and utility decorators."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user


def role_required(*roles: str) -> Callable[..., Any]:
    """Ensure the user is logged in and possesses one of the authorized roles.

    Args:
        *roles: One or more role names ('admin', 'donor', 'receiver').

    Returns:
        Decorated view function.
    """

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                flash("Silakan masuk terlebih dahulu untuk mengakses halaman ini.", "warning")
                return redirect(url_for("auth.login", next=request.url))
            if current_user.role not in roles and current_user.role != "admin":
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator

