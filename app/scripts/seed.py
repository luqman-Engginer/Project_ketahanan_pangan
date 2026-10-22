"""Database seeding command for FoodLoop ID."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import (
    AuditLog,
    City,
    Claim,
    Comment,
    FoodCategory,
    ImpactFactor,
    InventoryItem,
    Notification,
    Organization,
    Province,
    SurplusListing,
    User,
    WasteLog,
)


# 34 Provinces in Indonesia (official BPS codes)
PROVINCES_DATA: list[tuple[int, str]] = [
    (11, "Aceh"),
    (12, "Sumatera Utara"),
    (13, "Sumatera Barat"),
    (14, "Riau"),
    (15, "Jambi"),
    (16, "Sumatera Selatan"),
    (17, "Bengkulu"),
    (18, "Lampung"),
    (19, "Kepulauan Bangka Belitung"),
    (21, "Kepulauan Riau"),
    (31, "DKI Jakarta"),
    (32, "Jawa Barat"),
    (33, "Jawa Tengah"),
    (34, "DI Yogyakarta"),
    (35, "Jawa Timur"),
    (36, "Banten"),
    (51, "Bali"),
    (52, "Nusa Tenggara Barat"),
    (53, "Nusa Tenggara Timur"),
    (61, "Kalimantan Barat"),
    (62, "Kalimantan Tengah"),
    (63, "Kalimantan Selatan"),
    (64, "Kalimantan Timur"),
    (65, "Kalimantan Utara"),
    (71, "Sulawesi Utara"),
    (72, "Sulawesi Tengah"),
    (73, "Sulawesi Selatan"),
    (74, "Sulawesi Tenggara"),
    (75, "Gorontalo"),
    (76, "Sulawesi Barat"),
    (81, "Maluku"),
    (82, "Maluku Utara"),
    (91, "Papua Barat"),
    (94, "Papua"),
]

# Major Indonesian cities with coordinates
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

# 8 Food Categories with standard unit & impact parameters
CATEGORIES_DATA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "Makanan Siap Santap",
        "unit": "porsi",
        "price_per_kg": Decimal("35000.00"),
        "co2e_per_kg": Decimal("2.500"),
        "source": "Bappenas & FAO Food Wastage Footprint 2021",
    },
    {
        "id": 2,
        "name": "Sayuran & Buah Segar",
        "unit": "kg",
        "price_per_kg": Decimal("20000.00"),
        "co2e_per_kg": Decimal("0.850"),
        "source": "UNEP Food Waste Index Report 2024",
    },
    {
        "id": 3,
        "name": "Produk Roti & Bakery",
        "unit": "buah",
        "price_per_kg": Decimal("28000.00"),
        "co2e_per_kg": Decimal("1.200"),
        "source": "WRAP UK & Kajian Bappenas FLW 2021",
    },
    {
        "id": 4,
        "name": "Daging, Ikan & Unggas",
        "unit": "kg",
        "price_per_kg": Decimal("85000.00"),
        "co2e_per_kg": Decimal("6.800"),
        "source": "FAO Greenhouse Gas Emissions in Agriculture 2022",
    },
    {
        "id": 5,
        "name": "Produk Olahan Susu & Telur",
        "unit": "kg",
        "price_per_kg": Decimal("45000.00"),
        "co2e_per_kg": Decimal("3.200"),
        "source": "Poore & Nemecek Science 2018",
    },
    {
        "id": 6,
        "name": "Makanan Pokok & Sembako",
        "unit": "kg",
        "price_per_kg": Decimal("16000.00"),
        "co2e_per_kg": Decimal("1.400"),
        "source": "IRRI & Bappenas Kajian FLW Indonesia 2021",
    },
    {
        "id": 7,
        "name": "Makanan Kemasan & Kaleng",
        "unit": "kotak",
        "price_per_kg": Decimal("32000.00"),
        "co2e_per_kg": Decimal("1.900"),
        "source": "Kementerian Lingkungan Hidup & Kehutanan 2022",
    },
    {
        "id": 8,
        "name": "Minuman & Sari Buah",
        "unit": "liter",
        "price_per_kg": Decimal("18000.00"),
        "co2e_per_kg": Decimal("0.950"),
        "source": "Water Footprint Network & FAO 2020",
    },
]


def _seed_geography() -> None:
    """Seed 34 Indonesian provinces and major cities."""
    for prov_id, prov_name in PROVINCES_DATA:
        if not db.session.get(Province, prov_id):
            db.session.add(Province(id=prov_id, name=prov_name))
    db.session.flush()

    for city_id, city_name, prov_id, lat, lng in CITIES_DATA:
        if not db.session.get(City, city_id):
            db.session.add(City(id=city_id, name=city_name, province_id=prov_id, lat=lat, lng=lng))
    db.session.flush()


def _seed_categories_and_impact() -> None:
    """Seed 8 food categories and corresponding realistic impact factors."""
    for cat in CATEGORIES_DATA:
        food_cat = db.session.get(FoodCategory, cat["id"])
        if not food_cat:
            food_cat = FoodCategory(id=cat["id"], name=cat["name"], unit_default=cat["unit"])
            db.session.add(food_cat)
            db.session.flush()

        factor = ImpactFactor.query.filter_by(category_id=cat["id"]).first()
        if not factor:
            factor = ImpactFactor(
                category_id=cat["id"],
                price_per_kg=cat["price_per_kg"],
                co2e_per_kg=cat["co2e_per_kg"],
                source_note=cat["source"],
            )
            db.session.add(factor)
    db.session.flush()


def _seed_organizations_and_users(now: datetime) -> dict[str, Any]:
    """Seed 3 donor organizations, 3 receiver organizations, and associated user accounts."""
    orgs_data = [
        # Donors
        {
            "name": "PT Berkah Katering Nusantara",
            "type": "donor",
            "city_id": 3273,  # Bandung
            "address": "Jl. LLRE Martadinata (Riau) No. 45, Bandung",
            "phone": "081223344550",
            "user_email": "budi@berkahkatering.id",
            "user_name": "Chef Budi Santoso",
            "password": "donor123",
            "role": "donor",
        },
        {
            "name": "Supermarket Segar Makmur",
            "type": "donor",
            "city_id": 3174,  # Jakarta Selatan
            "address": "Jl. RS Fatmawati Raya No. 88, Cilandak, Jakarta Selatan",
            "phone": "081234567890",
            "user_email": "hendra@segarmakmur.id",
            "user_name": "Hendra Wijaya (Store Mgr)",
            "password": "donor123",
            "role": "donor",
        },
        {
            "name": "Bakery Aroma Manis Banyumas",
            "type": "donor",
            "city_id": 3302,  # Banyumas / Purwokerto
            "address": "Jl. Jenderal Soedirman No. 120, Purwokerto",
            "phone": "081398765432",
            "user_email": "siti@aromamanis.id",
            "user_name": "Siti Rahma (Owner)",
            "password": "donor123",
            "role": "donor",
        },
        # Receivers
        {
            "name": "Yayasan Food Bank Indonesia",
            "type": "receiver",
            "city_id": 3174,  # Jakarta Selatan
            "address": "Jl. Tebet Barat Dalam Raya No. 15, Jakarta Selatan",
            "phone": "08119876543",
            "user_email": "rian@foodbank.id",
            "user_name": "Rian Prasetya (Koordinator)",
            "password": "receiver123",
            "role": "receiver",
        },
        {
            "name": "Panti Asuhan Kasih Mandiri",
            "type": "receiver",
            "city_id": 3273,  # Bandung
            "address": "Jl. Cihampelas No. 102, Coblong, Bandung",
            "phone": "081233445566",
            "user_email": "maria@kasihmandiri.id",
            "user_name": "Suster Maria",
            "password": "receiver123",
            "role": "receiver",
        },
        {
            "name": "Dapur Komunitas Banyumas Berbagi",
            "type": "receiver",
            "city_id": 3302,  # Banyumas / Purwokerto
            "address": "Jl. Dr. Angka No. 7, Purwokerto Lor",
            "phone": "081566778899",
            "user_email": "eko@banyumasberbagi.id",
            "user_name": "Eko Supriyanto (Relawan)",
            "password": "receiver123",
            "role": "receiver",
        },
    ]

    donor_orgs: list[Organization] = []
    receiver_orgs: list[Organization] = []
    created_users: list[User] = []

    for item in orgs_data:
        org = Organization.query.filter_by(name=item["name"]).first()
        if not org:
            org = Organization(
                name=item["name"],
                type=item["type"],
                city_id=item["city_id"],
                address=item["address"],
                phone=item["phone"],
                verified_at=now - timedelta(days=90),
                created_at=now - timedelta(days=95),
            )
            db.session.add(org)
            db.session.flush()

        if item["type"] == "donor":
            donor_orgs.append(org)
        else:
            receiver_orgs.append(org)

        user = User.query.filter_by(email=item["user_email"]).first()
        if not user:
            user = User(
                name=item["user_name"],
                email=item["user_email"],
                role=item["role"],
                org_id=org.id,
                is_active=True,
                created_at=now - timedelta(days=90),
            )
            user.set_password(item["password"])
            db.session.add(user)
            db.session.flush()
        created_users.append(user)

    # Super Admin user
    admin_user = User.query.filter_by(email="admin@foodloop.id").first()
    if not admin_user:
        admin_user = User(
            name="Admin FoodLoop ID",
            email="admin@foodloop.id",
            role="admin",
            org_id=None,
            is_active=True,
            created_at=now - timedelta(days=95),
        )
        admin_user.set_password("admin123")
        db.session.add(admin_user)
        db.session.flush()

    return {
        "donors": donor_orgs,
        "receivers": receiver_orgs,
        "users": created_users,
        "admin": admin_user,
    }


def _seed_activity_data(
    now: datetime,
    donors: list[Organization],
    receivers: list[Organization],
    users: list[User],
) -> None:
    """Generate ~105 records across surplus listings, inventory items, and waste logs spread across 90 days."""
    random.seed(42)  # Deterministic seed for reproducible testing

    # 1. Seed ~40 Surplus Listings over the last 90 days
    surplus_catalog = [
        (1, "Nasi Kotak Ayam Bakar Komplit (Sisa Katering Seminar)", 35, "porsi", Decimal("14.0")),
        (1, "Prasmanan Rendang Daging & Gulai Sayur", 50, "porsi", Decimal("22.5")),
        (1, "Nasi Goreng Spesial & Ayam Geprek", 40, "porsi", Decimal("16.0")),
        (1, "Paket Nasi Uduk & Lauk Pauk Pagi", 30, "porsi", Decimal("12.0")),
        (2, "Sayur Sawi Hijau & Bayam Segar Curah", 25, "kg", Decimal("25.0")),
        (2, "Tomat Buah Grade B Siap Olah", 30, "kg", Decimal("30.0")),
        (2, "Pisang Cavendish Matang Sempurna", 40, "kg", Decimal("40.0")),
        (2, "Wortel Manis Berastagi Segar", 20, "kg", Decimal("20.0")),
        (3, "Roti Tawar Gandum Utuh (Expiry Hari Ini)", 30, "bungkus", Decimal("15.0")),
        (3, "Aneka Roti Manis Isi Cokelat & Keju", 45, "buah", Decimal("13.5")),
        (3, "Baguette & Roti Sourdough Artisan", 25, "buah", Decimal("10.0")),
        (4, "Potongan Daging Ayam Broiler Segar Chilled", 25, "kg", Decimal("25.0")),
        (4, "Ikan Nila & Gurame Segar Hasil Kolam", 30, "kg", Decimal("30.0")),
        (5, "Telur Ayam Ras Grade Konsumsi", 50, "kg", Decimal("50.0")),
        (5, "Susu Pasteurisasi Segar Kemasan 1 Liter", 20, "liter", Decimal("20.0")),
        (6, "Beras Premium IR 64 Karung 5kg", 10, "karung", Decimal("50.0")),
        (6, "Mi Telur Kering & Bihun Jagung", 30, "pack", Decimal("15.0")),
        (7, "Sarden Kaleng Bumbu Balado (Mendekati ED)", 40, "kaleng", Decimal("18.0")),
        (8, "Jus Buah Jeruk & Mangga Kemasan Botol", 25, "botol", Decimal("25.0")),
    ]

    receiver_by_city = {r.city_id: r for r in receivers}

    # Generate 40 surplus posts spread over 90 days (days 88 down to 0)
    days_offsets = sorted([random.randint(0, 88) for _ in range(40)], reverse=True)
    created_listings: list[SurplusListing] = []

    for idx, day_offset in enumerate(days_offsets):
        donor = donors[idx % len(donors)]
        template = surplus_catalog[idx % len(surplus_catalog)]
        cat_id, title, qty, unit, qty_kg = template

        created_dt = now - timedelta(days=day_offset, hours=random.randint(1, 10))
        pickup_before = created_dt + timedelta(hours=random.randint(8, 24))

        # Assign status based on age
        if day_offset > 3:
            # Older than 3 days: 85% picked up, 15% expired
            status = "picked_up" if (idx % 7 != 0) else "expired"
        elif day_offset >= 1:
            # 1-3 days old: mixture of claimed, picked_up, or available
            status = random.choice(["available", "claimed", "picked_up"])
        else:
            # Within 24h: active surplus board
            status = "available"

        listing = SurplusListing(
            org_id=donor.id,
            category_id=cat_id,
            title=title,
            qty=Decimal(qty),
            unit=unit,
            qty_kg=qty_kg,
            pickup_before=pickup_before,
            city_id=donor.city_id,
            notes=f"Kondisi higienis layak konsumsi. Siap diambil sebelum batas waktu oleh mitra bank pangan.",
            status=status,
            created_at=created_dt,
        )
        db.session.add(listing)
        db.session.flush()
        created_listings.append(listing)

        # Create claim record if claimed or picked up
        if status in {"claimed", "picked_up"}:
            receiver = receiver_by_city.get(donor.city_id, receivers[0])
            claim_dt = created_dt + timedelta(hours=random.randint(1, 4))
            picked_dt = (created_dt + timedelta(hours=random.randint(4, 7))) if status == "picked_up" else None

            claim = Claim(
                listing_id=listing.id,
                receiver_org_id=receiver.id,
                status="picked_up" if status == "picked_up" else "approved",
                claimed_at=claim_dt,
                picked_up_at=picked_dt,
            )
            db.session.add(claim)

    # 2. Seed ~35 Inventory Items with diverse expiry dates (FEFO testing)
    inventory_catalog = [
        # (cat_id, name, unit, cost_per_unit, days_to_expire, qty)
        (1, "Nasi Box Ayam Bakar Bumbu Rujak", "porsi", Decimal("22000"), 1, Decimal("25")),
        (1, "Sop Buntut Sapi Porsi Katering", "porsi", Decimal("35000"), 2, Decimal("15")),
        (1, "Tumis Buncis Daging Cincang", "porsi", Decimal("12000"), 1, Decimal("20")),
        (2, "Sayur Kangkung Segar Ikatan", "kg", Decimal("8000"), 2, Decimal("18")),
        (2, "Tomat Merah Segar Curah", "kg", Decimal("14000"), 3, Decimal("35")),
        (2, "Pisang Raja Matang", "kg", Decimal("18000"), 2, Decimal("24")),
        (2, "Wortel Impor Segar", "kg", Decimal("15000"), 12, Decimal("40")),
        (2, "Kentang Granola Dieng", "kg", Decimal("16000"), 25, Decimal("60")),
        (2, "Bawang Merah Brebes", "kg", Decimal("32000"), 20, Decimal("30")),
        (2, "Bawang Putih Kating", "kg", Decimal("35000"), 35, Decimal("25")),
        (3, "Roti Gandum Toast Loaf", "buah", Decimal("22000"), 1, Decimal("16")),
        (3, "Croissant Mentega Perancis", "buah", Decimal("15000"), 2, Decimal("30")),
        (3, "Roti Sobek Cokelat Lumer", "buah", Decimal("18000"), 3, Decimal("20")),
        (3, "Donat Gula Halus Klasik", "buah", Decimal("6000"), -1, Decimal("15")),  # Expired yesterday
        (3, "Muffin Cokelat Chocochip", "buah", Decimal("12000"), -2, Decimal("10")),  # Expired
        (4, "Daging Sapi Gandik Segar", "kg", Decimal("130000"), 4, Decimal("15")),
        (4, "Fillet Dada Ayam Tanpa Tulang", "kg", Decimal("48000"), 3, Decimal("40")),
        (4, "Udang Vaname Segar Tambak", "kg", Decimal("75000"), 2, Decimal("20")),
        (4, "Ikan Kembung Banjar Segar", "kg", Decimal("38000"), 1, Decimal("18")),
        (4, "Daging Cincang Sapi Australia", "kg", Decimal("110000"), -1, Decimal("8")),  # Expired
        (5, "Susu Segar Pasteurisasi Greenfields 1L", "liter", Decimal("26000"), 3, Decimal("30")),
        (5, "Keju Cheddar Olahan Blok 2kg", "blok", Decimal("115000"), 40, Decimal("10")),
        (5, "Telur Ayam Ras Omega-3", "tray", Decimal("55000"), 8, Decimal("25")),
        (5, "Yogurt Greek Natural 500g", "pot", Decimal("38000"), 5, Decimal("18")),
        (6, "Beras Pandan Wangi Premium 25kg", "karung", Decimal("360000"), 60, Decimal("8")),
        (6, "Minyak Goreng Kelapa Sawit 2L", "pouch", Decimal("33000"), 90, Decimal("45")),
        (6, "Gula Pasir Kristal Putih 1kg", "kg", Decimal("17500"), 120, Decimal("50")),
        (6, "Tepung Terigu Protein Sedang 1kg", "kg", Decimal("12000"), 45, Decimal("60")),
        (6, "Bihun Beras Instan Pack", "pack", Decimal("8000"), 75, Decimal("40")),
        (7, "Sarden Saus Tomat Kaleng 425g", "kaleng", Decimal("22000"), 45, Decimal("35")),
        (7, "Kornet Daging Sapi Kaleng 340g", "kaleng", Decimal("31000"), 60, Decimal("25")),
        (7, "Kacang Polong Kaleng Import", "kaleng", Decimal("18000"), -3, Decimal("12")),  # Expired
        (8, "Jus Jeruk Segar Tanpa Pengawet", "liter", Decimal("22000"), 2, Decimal("25")),
        (8, "Sari Buah Apel Malang Botol", "liter", Decimal("20000"), 4, Decimal("20")),
        (8, "Susu Kedelai Murni Tanpa Gula", "liter", Decimal("15000"), 1, Decimal("15")),
    ]

    for idx, item in enumerate(inventory_catalog):
        cat_id, name, unit, cost, offset_days, qty = item
        donor = donors[idx % len(donors)]
        item_exp = now.date() + timedelta(days=offset_days)
        item_created = now - timedelta(days=random.randint(5, 30))

        inv = InventoryItem(
            org_id=donor.id,
            category_id=cat_id,
            name=name,
            qty=qty,
            unit=unit,
            expires_on=item_exp,
            cost_per_unit=cost,
            created_at=item_created,
        )
        db.session.add(inv)

    # 3. Seed ~30 Waste Logs distributed over 90 days
    waste_reasons = [
        "Melebihi tanggal kedaluwarsa sebelum sempat terjual/terserap",
        "Kerusakan kemasan saat penanganan logistik gudang",
        "Fluktuasi suhu ruang chiller/freezer di luar batas toleransi",
        "Sisa prasmanan acara katering tidak memenuhi syarat simpan",
        "Cacat fisik buah/sayur saat pemilahan display harian",
        "Kelebihan estimasi produksi pesanan harian",
    ]

    waste_days = sorted([random.randint(1, 89) for _ in range(30)], reverse=True)
    for idx, day_offset in enumerate(waste_days):
        donor = donors[idx % len(donors)]
        cat_id = (idx % 8) + 1
        qty_kg = Decimal(str(round(random.uniform(4.0, 26.5), 1)))
        logged_date = (now - timedelta(days=day_offset)).date()

        waste = WasteLog(
            org_id=donor.id,
            category_id=cat_id,
            qty_kg=qty_kg,
            reason=waste_reasons[idx % len(waste_reasons)],
            logged_on=logged_date,
            created_at=datetime.combine(logged_date, datetime.min.time()) + timedelta(hours=17),
        )
        db.session.add(waste)

    # 4. Add discussions and sample notifications
    sample_comments = [
        "Apakah surplus ini bisa kami ambil sekitar pukul 15.00 WIB sore?",
        "Bisa kak, silakan datang membawa wadah higienis mandiri ya.",
        "Terima kasih donasi pangannya, sudah tersalurkan ke warga lansia sekitar.",
    ]
    if created_listings:
        target_listing = created_listings[0]
        c1 = Comment(
            listing_id=target_listing.id,
            user_id=users[3].id,  # Receiver user
            body=sample_comments[0],
            created_at=target_listing.created_at + timedelta(minutes=30),
        )
        db.session.add(c1)
        db.session.flush()

        c2 = Comment(
            listing_id=target_listing.id,
            user_id=users[0].id,  # Donor user
            body=sample_comments[1],
            parent_id=c1.id,
            created_at=c1.created_at + timedelta(minutes=15),
        )
        db.session.add(c2)

    # Sample notifications for users
    for user in users[:4]:
        notif = Notification(
            user_id=user.id,
            type="surplus_posted",
            payload_json={
                "title": "Surplus Pangan Tersedia",
                "message": "Mitra donor di wilayah Anda baru saja membagikan surplus pangan.",
            },
            created_at=now - timedelta(hours=random.randint(1, 24)),
        )
        db.session.add(notif)

    # Sample audit log
    db.session.add(
        AuditLog(
            user_id=users[0].id,
            action="SEED_DATABASE",
            entity="system",
            entity_id=None,
            created_at=now,
        )
    )

    db.session.commit()


@click.command("seed")
@with_appcontext
def seed_command() -> None:
    """Populate database with initial master data and 90-day realistic activity."""
    click.echo("Seeding FoodLoop ID database...")

    now = datetime.utcnow()

    # 1. Master Geography (34 Provinces + Major Cities)
    click.echo("-> Seeding 34 provinces and major cities...")
    _seed_geography()

    # 2. Food Categories & Impact Factors
    click.echo("-> Seeding 8 food categories and impact factors...")
    _seed_categories_and_impact()

    # 3. Organizations and Users
    click.echo("-> Seeding donor and receiver organizations & users...")
    org_user_data = _seed_organizations_and_users(now)

    # 4. Activity: Listings, Claims, Inventory, Waste Logs (spread over 90 days)
    click.echo("-> Seeding ~105 records across surplus, inventory, and waste logs...")
    _seed_activity_data(
        now=now,
        donors=org_user_data["donors"],
        receivers=org_user_data["receivers"],
        users=org_user_data["users"],
    )

    click.secho("FoodLoop ID database seeded successfully!", fg="green", bold=True)

