"""Inventory item form for donor stock tracking."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange


class InventoryItemForm(FlaskForm):
    """Form to record or update an inventory stock item."""

    name = StringField("Nama Item", validators=[DataRequired(), Length(max=150)])
    category_id = IntegerField("Kategori Pangan", validators=[DataRequired()])
    qty = DecimalField("Jumlah Stok", validators=[DataRequired(), NumberRange(min=0.01)])
    unit = StringField("Satuan", validators=[DataRequired(), Length(max=20)], default="kg")
    expires_on = DateField("Tanggal Kedaluwarsa", validators=[DataRequired()])
    cost_per_unit = DecimalField("Biaya per Satuan (Rp)", validators=[NumberRange(min=0)], default=0.0)

