"""Authentication routes: login, registration, and logout."""
from __future__ import annotations

from typing import Union

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import limiter
from app.forms.auth import LoginForm, RegisterForm
from app.schemas.payloads import UserLoginSchema, UserRegisterSchema
from app.services import audit_service, auth_service
from app.utils.errors import log_exception
from app.utils.redirects import safe_redirect_target

bp: Blueprint = Blueprint("auth", __name__)

#: Generic copy returned to the client; details are written to the log instead.
INVALID_CREDENTIALS = "Email atau kata sandi tidak valid."
REGISTRATION_FAILED = "Pendaftaran gagal. Silakan periksa kembali data Anda."


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login() -> Union[str, Response]:
    """Authenticate existing users."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()

    # Handle JSON API login request
    if request.is_json:
        try:
            payload = UserLoginSchema(**request.get_json())
        except Exception as err:
            log_exception("Login JSON validation failed", err)
            return {"error": INVALID_CREDENTIALS}, 400

        user = auth_service.authenticate_user(payload.email, payload.password)
        if not user:
            audit_service.log_action("LOGIN_FAILED", "user")
            return {"error": INVALID_CREDENTIALS}, 401

        login_user(user)
        session.permanent = True
        audit_service.log_action("LOGIN_SUCCESS", "user", user.id)
        return {
            "message": "Login berhasil",
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
        }, 200

    # Handle HTML form submission
    if form.validate_on_submit():
        user = auth_service.authenticate_user(form.email.data, form.password.data)
        if user:
            login_user(user, remember=form.remember.data)
            session.permanent = True
            audit_service.log_action("LOGIN_SUCCESS", "user", user.id)
            flash(f"Selamat datang kembali, {user.name}!", "success")
            next_url = safe_redirect_target(request.args.get("next"))
            return redirect(next_url or url_for("main.dashboard"))
        audit_service.log_action("LOGIN_FAILED", "user")
        flash(INVALID_CREDENTIALS, "danger")

    return render_template("auth/login.html", layout="public", form=form)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register() -> Union[str, Response]:
    """Register a new user and organization."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    cities = auth_service.list_city_choices()
    form = RegisterForm()
    form.city_id.choices = [(city["id"], city["name"]) for city in cities]

    # Handle JSON API register request
    if request.is_json:
        try:
            payload = UserRegisterSchema(**request.get_json())
        except Exception as err:
            log_exception("Register JSON validation failed", err)
            return {"error": REGISTRATION_FAILED}, 400

        try:
            user = auth_service.register_user(
                name=payload.name,
                email=payload.email,
                password=payload.password,
                city_id=payload.city_id,
                address=payload.address,
                phone=payload.phone,
            )
        except Exception as err:
            log_exception("Register user failed", err)
            return {"error": REGISTRATION_FAILED}, 400

        login_user(user)
        session.permanent = True
        audit_service.log_action("REGISTER_ORGANIZATION", "user", user.id)
        return {
            "message": "Pendaftaran berhasil",
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
        }, 201

    # Handle HTML form submission
    if form.validate_on_submit():
        try:
            user = auth_service.register_user(
                name=form.name.data,
                email=form.email.data,
                password=form.password.data,
                city_id=form.city_id.data,
                address=form.address.data,
                phone=form.phone.data,
            )
        except ValueError as err:
            log_exception("Register user failed", err)
            flash(str(err), "danger")
        else:
            login_user(user)
            session.permanent = True
            audit_service.log_action("REGISTER_ORGANIZATION", "user", user.id)
            flash("Akun dan organisasi Anda berhasil dibuat! Selamat datang di FoodLoop ID.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template(
        "auth/register.html",
        layout="public",
        form=form,
        cities=cities,
    )


@bp.post("/logout")
@login_required
def logout() -> Response:
    """Log out current user session (POST only, protected by CSRF)."""
    user_id = current_user.id
    logout_user()
    audit_service.log_action("LOGOUT", "user", user_id)
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for("auth.login"))
