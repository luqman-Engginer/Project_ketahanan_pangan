"""Geographical administrative division models (provinces and cities)."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.food import SurplusListing
    from app.models.organization import Organization


class Province(db.Model):
    """Indonesian province administrative division."""

    __tablename__ = "provinces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Relationships
    cities: Mapped[list[City]] = relationship("City", back_populates="province", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Province id={self.id} name={self.name}>"


class City(db.Model):
    """Regency or city (Kabupaten/Kota) within a province."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    province_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("provinces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)

    # Relationships
    province: Mapped[Province] = relationship("Province", back_populates="cities")
    organizations: Mapped[list[Organization]] = relationship("Organization", back_populates="city")
    surplus_listings: Mapped[list[SurplusListing]] = relationship("SurplusListing", back_populates="city")

    def __repr__(self) -> str:
        return f"<City id={self.id} name={self.name}>"

