"""Organization model representing a food supplier."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.food import InventoryItem, SurplusListing, WasteLog
    from app.models.location import City
    from app.models.user import User


class Organization(db.Model):
    """Organization entity acting as a food supplier."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("supplier", name="org_type_enum"),
        nullable=False,
        default="supplier",
    )
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    city: Mapped[City] = relationship("City", back_populates="organizations")
    users: Mapped[list[User]] = relationship("User", back_populates="organization")
    inventory_items: Mapped[list[InventoryItem]] = relationship(
        "InventoryItem", back_populates="organization", cascade="all, delete-orphan"
    )
    surplus_listings: Mapped[list[SurplusListing]] = relationship(
        "SurplusListing", back_populates="organization", cascade="all, delete-orphan"
    )
    waste_logs: Mapped[list[WasteLog]] = relationship(
        "WasteLog", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name} type={self.type}>"

