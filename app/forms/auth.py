"""Authentication forms for login and registration."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    """User login form."""

    email = StringField(
        "Email",
        validators=[DataRequired(message="Email wajib diisi."), Email(message="Format email tidak valid.")],
    )
    password = PasswordField(
        "Kata Sandi",
        validators=[DataRequired(message="Kata sandi wajib diisi."), Length(min=6, message="Minimal 6 karakter.")],
    )
    remember = BooleanField("Ingat saya")


class RegisterForm(FlaskForm):
    """User and organization registration form."""

    name = StringField(
        "Nama Lengkap / Organisasi",
        validators=[DataRequired(message="Nama wajib diisi."), Length(min=3, max=100)],
    )
    role = SelectField(
        "Saya mendaftar sebagai",
        choices=[("receiver", "Penerima Manfaat"), ("donor", "Donor Pangan")],
        validators=[DataRequired(message="Pilih peran Anda.")],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(message="Email wajib diisi."), Email(message="Format email tidak valid.")],
    )
    password = PasswordField(
        "Kata Sandi",
        validators=[DataRequired(message="Kata sandi wajib diisi."), Length(min=8, message="Minimal 8 karakter.")],
    )
    confirm = PasswordField(
        "Ulangi Kata Sandi",
        validators=[
            DataRequired(message="Konfirmasi sandi wajib diisi."),
            EqualTo("password", message="Kata sandi tidak cocok."),
        ],
    )
    terms = BooleanField("Syarat dan Ketentuan", validators=[DataRequired(message="Wajib menyetujui syarat.")])

