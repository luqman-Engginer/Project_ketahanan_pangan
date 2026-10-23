"""Master-data seeding and administrator creation commands."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import City, FoodCategory, ImpactFactor, Province
from app.services import auth_service

PROVINCES_DATA: list[tuple[int, str]] = [
    (11, "Aceh"), (12, "Sumatera Utara"), (13, "Sumatera Barat"), (14, "Riau"),
    (15, "Jambi"), (16, "Sumatera Selatan"), (17, "Bengkulu"), (18, "Lampung"),
    (19, "Kepulauan Bangka Belitung"), (21, "Kepulauan Riau"), (31, "DKI Jakarta"),
    (32, "Jawa Barat"), (33, "Jawa Tengah"), (34, "DI Yogyakarta"), (35, "Jawa Timur"),
    (36, "Banten"), (51, "Bali"), (52, "Nusa Tenggara Barat"), (53, "Nusa Tenggara Timur"),
    (61, "Kalimantan Barat"), (62, "Kalimantan Tengah"), (63, "Kalimantan Selatan"),
    (64, "Kalimantan Timur"), (65, "Kalimantan Utara"), (71, "Sulawesi Utara"),
    (72, "Sulawesi Tengah"), (73, "Sulawesi Selatan"), (74, "Sulawesi Tenggara"),
    (75, "Gorontalo"), (76, "Sulawesi Barat"), (81, "Maluku"), (82, "Maluku Utara"),
    (91, "Papua Barat"), (94, "Papua"),
]

CITIES_DATA: list[tuple[int, str, int, Decimal, Decimal]] = [
    (3171, "Jakarta Pusat", 31, Decimal("-6.1805113"), Decimal("106.8283831")),
    (3174, "Jakarta Selatan", 31, Decimal("-6.2614930"), Decimal("106.8105998")),
    (3273, "Bandung", 32, Decimal("-6.9174639"), Decimal("107.6191228")),
    (3275, "Kota Bekasi", 32, Decimal("-6.2382700"), Decimal("106.9755730")),
    (3271, "Kota Bogor", 32, Decimal("-6.5971470"), Decimal("106.8060390")),
    (3374, "Semarang", 33, Decimal("-6.9666670"), Decimal("110.4166640")),
    (3372, "Surakarta", 33, Decimal("-7.5754890"), Decimal("110.8243260")),
    (3302, "Banyumas (Purwokerto)", 33, Decimal("-7.4244240"), Decimal("109.2302320")),
    (3471, "Yogyakarta", 34, Decimal("-7.7955798"), Decimal("110.3694896")),
    (3578, "Surabaya", 35, Decimal("-7.2574719"), Decimal("112.7520883")),
    (3573, "Malang", 35, Decimal("-7.9666204"), Decimal("112.6326321")),
    (1271, "Medan", 12, Decimal("3.5951956"), Decimal("98.6722227")),
    (1671, "Palembang", 16, Decimal("-2.9760735"), Decimal("104.7754307")),
    (5171, "Denpasar", 51, Decimal("-8.6704582"), Decimal("115.2126293")),
    (7371, "Makassar", 73, Decimal("-5.1476650"), Decimal("119.4327310")),
    (6471, "Balikpapan", 64, Decimal("-1.2379260"), Decimal("116.8528530")),
]

CATEGORIES_DATA: list[dict[str, Any]] = [
    {"id": 1, "name": "Makanan Siap Santap", "unit": "porsi", "price": "35000", "co2e": "2.500", "source": "Bappenas & FAO 2021"},
    {"id": 2, "name": "Sayuran & Buah Segar", "unit": "kg", "price": "20000", "co2e": "0.850", "source": "UNEP Food Waste Index 2024"},
    {"id": 3, "name": "Produk Roti & Bakery", "unit": "buah", "price": "28000", "co2e": "1.200", "source": "WRAP UK & Bappenas 2021"},
    {"id": 4, "name": "Daging, Ikan & Unggas", "unit": "kg", "price": "85000", "co2e": "6.800", "source": "FAO 2022"},
    {"id": 5, "name": "Produk Olahan Susu & Telur", "unit": "kg", "price": "45000", "co2e": "3.200", "source": "Poore & Nemecek 2018"},
    {"id": 6, "name": "Makanan Pokok & Sembako", "unit": "kg", "price": "16000", "co2e": "1.400", "source": "IRRI & Bappenas 2021"},
    {"id": 7, "name": "Makanan Kemasan & Kaleng", "unit": "kotak", "price": "32000", "co2e": "1.900", "source": "KLHK 2022"},
    {"id": 8, "name": "Minuman & Sari Buah", "unit": "liter", "price": "18000", "co2e": "0.950", "source": "Water Footprint Network 2020"},
]


@click.command("seed")
@with_appcontext
def seed_command() -> None:
    """Seed geography, food categories, and impact factors only."""
    for province_id, name in PROVINCES_DATA:
        if not db.session.get(Province, province_id):
            db.session.add(Province(id=province_id, name=name))
    db.session.flush()

    for city_id, name, province_id, lat, lng in CITIES_DATA:
        if not db.session.get(City, city_id):
            db.session.add(City(id=city_id, name=name, province_id=province_id, lat=lat, lng=lng))
    db.session.flush()

    for item in CATEGORIES_DATA:
        category = db.session.get(FoodCategory, item["id"])
        if not category:
            category = FoodCategory(id=item["id"], name=item["name"], unit_default=item["unit"])
            db.session.add(category)
            db.session.flush()
        factor = ImpactFactor.query.filter_by(category_id=item["id"]).first()
        if not factor:
            db.session.add(
                ImpactFactor(
                    category_id=item["id"],
                    price_per_kg=Decimal(item["price"]),
                    co2e_per_kg=Decimal(item["co2e"]),
                    source_note=item["source"],
                )
            )

    db.session.commit()
    click.secho("Master data FoodLoop ID berhasil dimuat.", fg="green")


@click.command("create-admin")
@click.option("--name", prompt=True, help="Nama administrator.")
@click.option("--email", prompt=True, help="Email administrator.")
@click.password_option(confirmation_prompt=True, help="Kata sandi minimal 12 karakter.")
@with_appcontext
def create_admin_command(name: str, email: str, password: str) -> None:
    """Create an administrator account through an interactive prompt."""
    if len(password) < 12:
        raise click.ClickException("Kata sandi administrator minimal 12 karakter.")
    try:
        user = auth_service.create_admin(name=name, email=email, password=password)
    except ValueError as err:
        raise click.ClickException(str(err)) from err
    click.secho(f"Admin {user.email} berhasil dibuat.", fg="green")
