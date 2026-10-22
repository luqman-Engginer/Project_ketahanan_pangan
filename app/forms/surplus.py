"""Surplus listing form for donor food posting."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, DecimalField, IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class SurplusListingForm(FlaskForm):
    """Form to publish a new surplus food listing."""

    title = StringField("Judul Surplus", validators=[DataRequired(), Length(max=200)])
    category_id = IntegerField("Kategori Pangan", validators=[DataRequired()])
    qty = DecimalField("Jumlah", validators=[DataRequired(), NumberRange(min=0.01)])
    unit = StringField("Satuan", validators=[DataRequired(), Length(max=20)], default="kg")
    qty_kg = DecimalField("Berat Setara (kg)", validators=[DataRequired(), NumberRange(min=0.01)])
    pickup_before = DateTimeLocalField("Batas Waktu Pengambilan", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    city_id = IntegerField("Kota Lokasi", validators=[DataRequired()])
    notes = TextAreaField("Catatan & Petunjuk Pengambilan", validators=[Optional(), Length(max=1000)])

