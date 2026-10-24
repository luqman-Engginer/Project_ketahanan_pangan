# Arsitektur FoodLoop ID

## Lapisan kode
```
Request -> blueprint (route + form) -> service (logika bisnis) -> model (SQLAlchemy) -> MySQL
```
- **Blueprint** (`app/blueprints/`): hanya menangani HTTP, validasi form, dan otorisasi (`role_required`). Tidak berisi query.
- **Service** (`app/services/`): logika bisnis, yaitu perhitungan KPI, insight, ekspor, notifikasi.
- **Model** (`app/models/`): tabel dan relasi. Skema diubah lewat Flask-Migrate.

## Alur review Pasokan
1. Supplier membuat Pasokan, statusnya `pending`.
2. Admin menerima notifikasi, lalu menyetujui atau menolak dengan catatan.
3. Supplier menerima notifikasi hasil review.
4. KPI (kg, rupiah, porsi, CO2e) dihitung hanya dari Pasokan `approved`, dengan agregasi SQL.

## Akses
- Dua role: `admin` dan `supplier`. Admin dibuat lewat `flask create-admin`, bukan lewat Register.
- Query supplier selalu difilter dari organisasi di sesi, bukan dari parameter request (cegah IDOR).

## Real-time
Notifikasi memakai Server-Sent Events (`/events`, wajib login). Broadcaster berada di memori, jadi production memakai satu worker gunicorn bergaya gevent.

## Keamanan
Password Argon2, CSRF pada form dan HTMX, rate limiting, security headers (CSP, tanpa CDN), cookie HttpOnly dan SameSite, production menolak start bila `SECRET_KEY` kosong.