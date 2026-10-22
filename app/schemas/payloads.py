"""Pydantic validation schemas for JSON API payloads."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterSchema(BaseModel):
    """Payload schema for user and organisation self-registration."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=3, max_length=100)
    role: str = Field(..., pattern="^(donor|receiver)$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    city_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class UserLoginSchema(BaseModel):
    """Payload schema for JSON login requests."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=1)


class InventoryItemCreateSchema(BaseModel):
    """Payload schema to create an inventory item."""

    category_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    qty: Decimal = Field(..., gt=0)
    unit: str = Field(default="kg", max_length=20)
    expires_on: date
    cost_per_unit: Decimal = Field(default=Decimal("0.0"), ge=0)


class SurplusListingCreateSchema(BaseModel):
    """Payload schema to publish surplus food."""

    category_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=3, max_length=200)
    qty: Decimal = Field(..., gt=0)
    unit: str = Field(default="kg", max_length=20)
    qty_kg: Decimal = Field(..., gt=0)
    pickup_before: datetime
    city_id: int = Field(..., gt=0)
    notes: Optional[str] = None


class ClaimStatusUpdateSchema(BaseModel):
    """Payload schema to update claim workflow status."""

    status: str = Field(..., pattern="^(pending|approved|picked_up|cancelled)$")


class WasteLogCreateSchema(BaseModel):
    """Payload schema to record discarded food."""

    category_id: int = Field(..., gt=0)
    qty_kg: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=2, max_length=255)
    logged_on: Optional[date] = None


class CommentCreateSchema(BaseModel):
    """Payload schema to post a discussion comment."""

    body: str = Field(..., min_length=2, max_length=1000)
    parent_id: Optional[int] = None

