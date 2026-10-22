"""Food categories, inventory, surplus listings, claims, waste logs, and impact factors."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.activity import Comment
    from app.models.location import City
    from app.models.organization import Organization


class FoodCategory(db.Model):
    """Food classification category with standard metric unit."""

    __tablename__ = "food_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    unit_default: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)

    # Relationships
    inventory_items: Mapped[list[InventoryItem]] = relationship("InventoryItem", back_populates="category")
    surplus_listings: Mapped[list[SurplusListing]] = relationship("SurplusListing", back_populates="category")
    waste_logs: Mapped[list[WasteLog]] = relationship("WasteLog", back_populates="category")
    impact_factor: Mapped[Optional[ImpactFactor]] = relationship(
        "ImpactFactor", back_populates="category", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FoodCategory id={self.id} name={self.name}>"


class InventoryItem(db.Model):
    """Stock item tracked by donor organizations with expiry monitoring."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("ix_inventory_items_org_id_expires_on", "org_id", "expires_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_categories.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="inventory_items")
    category: Mapped[FoodCategory] = relationship("FoodCategory", back_populates="inventory_items")

    def __repr__(self) -> str:
        return f"<InventoryItem id={self.id} name={self.name} expires_on={self.expires_on}>"


class SurplusListing(db.Model):
    """Surplus food post published by donors for claims by receivers."""

    __tablename__ = "surplus_listings"
    __table_args__ = (
        Index("ix_surplus_listings_status_city_pickup", "status", "city_id", "pickup_before"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_categories.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)
    qty_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pickup_before: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("available", "claimed", "picked_up", "expired", "cancelled", name="surplus_status_enum"),
        nullable=False,
        default="available",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="surplus_listings")
    category: Mapped[FoodCategory] = relationship("FoodCategory", back_populates="surplus_listings")
    city: Mapped[City] = relationship("City", back_populates="surplus_listings")
    claims: Mapped[list[Claim]] = relationship("Claim", back_populates="listing", cascade="all, delete-orphan")
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="listing", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SurplusListing id={self.id} title={self.title} status={self.status}>"


class Claim(db.Model):
    """Claim request created by a receiver organisation for a surplus listing."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("surplus_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "picked_up", "cancelled", name="claim_status_enum"),
        nullable=False,
        default="pending",
    )
    claimed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    listing: Mapped[SurplusListing] = relationship("SurplusListing", back_populates="claims")
    receiver_org: Mapped[Organization] = relationship("Organization", back_populates="claims", foreign_keys=[receiver_org_id])

    def __repr__(self) -> str:
        return f"<Claim id={self.id} listing_id={self.listing_id} status={self.status}>"


class WasteLog(db.Model):
    """Record of discarded food for food loss/waste analytics."""

    __tablename__ = "waste_logs"
    __table_args__ = (
        Index("ix_waste_logs_org_id_logged_on", "org_id", "logged_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_categories.id"), nullable=False, index=True
    )
    qty_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="waste_logs")
    category: Mapped[FoodCategory] = relationship("FoodCategory", back_populates="waste_logs")

    def __repr__(self) -> str:
        return f"<WasteLog id={self.id} org_id={self.org_id} qty_kg={self.qty_kg}>"


class ImpactFactor(db.Model):
    """Multiplier factor per food category for financial and carbon impact calculation."""

    __tablename__ = "impact_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_categories.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    co2e_per_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    source_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    category: Mapped[FoodCategory] = relationship("FoodCategory", back_populates="impact_factor")

    def __repr__(self) -> str:
        return f"<ImpactFactor category_id={self.category_id} price={self.price_per_kg} co2e={self.co2e_per_kg}>"

