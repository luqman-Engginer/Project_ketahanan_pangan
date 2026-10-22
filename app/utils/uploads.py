"""Upload validation helpers: extension, size, and content sniffing."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from flask import current_app
from werkzeug.datastructures import FileStorage


class UploadValidationError(ValueError):
    """Raised when an uploaded file does not satisfy the upload policy."""


#: Leading bytes that identify each allowed image format.
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "webp": (b"RIFF",),
}


def allowed_extensions() -> frozenset[str]:
    """Return the configured whitelist of allowed upload extensions."""
    return frozenset(current_app.config["UPLOAD_ALLOWED_EXTENSIONS"])


def max_upload_bytes() -> int:
    """Return the configured maximum upload size in bytes."""
    return int(current_app.config["UPLOAD_MAX_BYTES"])


def _sniff_extension(head: bytes) -> Optional[str]:
    """Detect the real image format from the file header.

    Args:
        head: First bytes of the uploaded file.

    Returns:
        The detected extension, or ``None`` when the content is not a known image.
    """
    for extension, signatures in _MAGIC_SIGNATURES.items():
        if any(head.startswith(signature) for signature in signatures):
            if extension == "webp":
                return "webp" if head[8:12] == b"WEBP" else None
            return extension
    return None


def validate_upload(file: Optional[FileStorage], field_label: str = "Berkas") -> str:
    """Validate an uploaded file and return a safe random file name.

    The checks cover the declared extension, the real file content, and the file
    size. The returned name is generated randomly so an attacker can never
    control the path used inside the upload directory.

    Args:
        file: The uploaded file object.
        field_label: Human readable name used in error messages.

    Returns:
        A random file name such as ``9f2c1a....png``.

    Raises:
        UploadValidationError: If the file is missing, oversized, or not an
            allowed image type.
    """
    if file is None or not file.filename:
        raise UploadValidationError(f"{field_label} wajib diunggah.")

    allowed = allowed_extensions()
    raw_name = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if raw_name not in allowed:
        raise UploadValidationError(
            f"Format {field_label.lower()} tidak didukung. Gunakan: {', '.join(sorted(allowed))}."
        )

    limit = max_upload_bytes()
    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0:
        raise UploadValidationError(f"{field_label} kosong.")
    if size > limit:
        raise UploadValidationError(
            f"Ukuran {field_label.lower()} melebihi batas {limit // 1024} KB."
        )

    head = file.stream.read(16)
    file.stream.seek(0)
    detected = _sniff_extension(head)
    if detected is None or detected not in allowed:
        raise UploadValidationError(f"Isi {field_label.lower()} bukan gambar yang valid.")
    if detected != raw_name and not (detected == "jpg" and raw_name == "jpeg"):
        raise UploadValidationError(f"Isi {field_label.lower()} tidak cocok dengan format berkas.")

    return f"{secrets.token_hex(16)}.{raw_name}"


def upload_folder() -> Path:
    """Return the upload directory, creating it when missing."""
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_upload(file: FileStorage, filename: str) -> str:
    """Store a validated upload inside the upload directory.

    Args:
        file: The uploaded file object.
        filename: The safe file name returned by :func:`validate_upload`.

    Returns:
        The stored file name.
    """
    file.stream.seek(0)
    file.save(upload_folder() / filename)
    return filename


def delete_upload(filename: Optional[str]) -> None:
    """Remove a previously stored upload, ignoring missing files.

    Args:
        filename: Stored file name to delete.
    """
    if not filename:
        return
    try:
        path = upload_folder() / Path(filename).name
        if path.is_file():
            path.unlink()
    except OSError:
        current_app.logger.warning("Gagal menghapus berkas unggahan: %s", filename)
