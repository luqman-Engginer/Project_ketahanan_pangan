"""User and authentication models."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.activity import AuditLog, Comment, Notification
    from app.models.organization import Organization

_hasher = PasswordHasher()


class User(UserMixin, db.Model):
    """User account supporting role-based access control and Argon2 auth."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "supplier", name="user_role_enum"),
        nullable=False,
        default="supplier",
    )
    org_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship("Organization", back_populates="users")
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship("AuditLog", back_populates="user")

    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password using Argon2."""
        self.password_hash = _hasher.hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored Argon2 hash."""
        try:
            return _hasher.verify(self.password_hash, password)
        except (VerifyMismatchError, Exception):
            return False

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"

