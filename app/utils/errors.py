"""Helpers for logging internal details while keeping user messages generic."""
from __future__ import annotations

from flask import current_app


def log_exception(context: str, error: BaseException) -> None:
    """Write the full exception detail to the application log.

    User-facing responses must only contain a generic message; the technical
    detail is kept server side for debugging.

    Args:
        context: Short description of the operation that failed.
        error: The exception that was raised.
    """
    current_app.logger.exception("%s | %s: %s", context, type(error).__name__, error)


def log_event(context: str, detail: str) -> None:
    """Record a notable server-side event without raising to the user.

    Args:
        context: Short description of the operation.
        detail: Additional context such as identifiers or IPs.
    """
    current_app.logger.info("%s | %s", context, detail)
