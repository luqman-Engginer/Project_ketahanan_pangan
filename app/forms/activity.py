"""Forms for waste logging, claims, and surplus discussion."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DecimalField, HiddenField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class WasteLogForm(FlaskForm):
    """Form to record discarded food waste."""

    category_id = IntegerField("Kategori Pangan", validators=[DataRequired()])
    qty_kg = DecimalField("Jumlah (kg)", validators=[DataRequired(), NumberRange(min=0.01)])
    reason = StringField("Penyebab Limbah", validators=[DataRequired(), Length(max=255)])
    note = TextAreaField("Catatan Tambahan", validators=[Optional(), Length(max=500)])


class ClaimStatusForm(FlaskForm):
    """Form to transition claim workflow status."""

    status = SelectField(
        "Status Klaim",
        choices=[
            ("pending", "Menunggu"),
            ("approved", "Disetujui"),
            ("picked_up", "Diambil"),
            ("cancelled", "Dibatalkan"),
        ],
        validators=[DataRequired()],
    )


class CommentForm(FlaskForm):
    """Form to post a discussion comment on a surplus listing."""

    body = TextAreaField("Komentar", validators=[DataRequired(), Length(min=2, max=1000)])
    parent_id = IntegerField("Balasan ke", validators=[Optional()])

