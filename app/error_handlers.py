"""Centralised error handling that keeps internal details out of user responses."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

#: Generic, user-safe copy per HTTP status code.
GENERIC_MESSAGES: dict[int, str] = {
    400: "Permintaan tidak valid. Silakan periksa kembali isian Anda.",
    401: "Anda harus masuk terlebih dahulu untuk mengakses halaman ini.",
    403: "Anda tidak memiliki akses ke sumber daya ini.",
    404: "Halaman atau data yang Anda cari tidak ditemukan.",
    405: "Metode yang digunakan tidak diizinkan pada alamat ini.",
    413: "Ukuran berkas yang diunggah terlalu besar.",
    429: "Terlalu banyak permintaan. Silakan coba lagi beberapa saat lagi.",
    500: "Terjadi kesalahan pada server. Tim kami sudah diberi tahu.",
}

#: Message shown when the CSRF token is missing or expired.
CSRF_MESSAGE = "Sesi formulir tidak valid atau telah kedaluwarsa. Silakan muat ulang halaman dan coba lagi."


def _wants_json() -> bool:
    """Detect whether the current client expects a JSON error payload."""
    if request.is_json:
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def _generic_response(code: int, message: str) -> Any:
    """Return a JSON or HTML response carrying only the safe message."""
    if _wants_json():
        return jsonify(error=message), code
    return render_template("error.html", code=code, message=message), code


def register_error_handlers(app: Flask) -> None:
    """Attach generic error handlers to the application.

    Handlers never expose exception messages for server-side failures; details are
    written to the application log instead.

    Args:
        app: The Flask application to configure.
    """

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError) -> Any:
        """Return a friendly message when the CSRF token is invalid."""
        app.logger.warning("CSRF rejection on %s: %s", request.path, error)
        return _generic_response(400, CSRF_MESSAGE)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException) -> Any:
        """Return curated copy for HTTP errors such as 403 and 404."""
        code = error.code or 500
        message = GENERIC_MESSAGES.get(code, GENERIC_MESSAGES[500])
        if code < 500 and error.description:
            message = error.description
        if code >= 500:
            app.logger.error("HTTP %s on %s", code, request.path)
        return _generic_response(code, message)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Any:
        """Log unexpected exceptions and return a generic response."""
        app.logger.exception("Unhandled error: %s", error)
        return _generic_response(500, GENERIC_MESSAGES[500])
