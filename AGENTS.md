# AGENTS.md — FoodLoop ID (aturan wajib untuk AI agent)

Baca file ini di awal setiap sesi. Untuk konteks produk baca `docs/PRD.md` HANYA bagian yang relevan dengan tugas.

## Stack (jangan diganti tanpa izin)
- Python 3.12, Flask 3 (application factory + Blueprints), Jinja2 templates, HTMX, Chart.js
- MySQL 8 (Flask-SQLAlchemy + Flask-Migrate/Alembic, driver PyMySQL)
- Auth & keamanan: Flask-Login, Flask-WTF (form + CSRF), Flask-Limiter, Flask-Talisman, argon2-cffi
- Tailwind CSS (standalone CLI, bukan CDN di production)
- Export: openpyxl (XLSX), csv (stdlib), WeasyPrint (PDF)
- Real-time: Server-Sent Events (SSE) lewat Response(mimetype='text/event-stream'), bukan WebSocket
- Server: gunicorn (worker gevent, 1 worker karena broadcaster SSE in-memory)
- Deploy: Docker Compose (app + mysql + caddy)

## Struktur folder
wsgi.py · app/{__init__.py (create_app), config.py, extensions.py, models/, schemas/, blueprints/, services/, templates/, static/}
migrations/ · tests/ · docs/ · docker-compose.yml · Dockerfile · Caddyfile · .env.example

## Aturan kerja (hemat token)
1. Kerjakan SATU tugas per prompt. Jangan menyentuh fitur di luar tugas.
2. Sebelum coding: tulis rencana maksimal 8 baris, lalu langsung kerjakan.
3. Jangan membaca ulang seluruh repo. Buka hanya file yang relevan.
4. Jangan membuat file dokumentasi/README/test baru kecuali diminta.
5. Setelah selesai: tampilkan ringkasan perubahan maksimal 6 baris (file apa saja + cara menjalankan). Jangan menempelkan ulang kode.
6. Jangan menambah library baru tanpa menyebut alasannya.

## Kualitas kode (dinilai juri: Source Code 30%)
- Pisahkan: blueprint/route (HTTP) → service (logika bisnis) → model (DB). Route tidak berisi query.
- Type hints + docstring singkat untuk fungsi publik. Nama dalam bahasa Inggris.
- Tidak ada secret/hardcoded password. Semua konfigurasi lewat `.env` (class Config di app/config.py).
- Semua perubahan skema DB lewat Flask-Migrate (`flask db migrate/upgrade`).

## Keamanan (wajib)
- Password: argon2. Session: cookie HttpOnly + Secure + SameSite=Lax. Flask-Login untuk sesi.
- Validasi input: WTForms (form) dan Pydantic (payload JSON). Query hanya lewat SQLAlchemy (tanpa string SQL manual).
- CSRF lewat Flask-WTF (CSRFProtect global), rate limiting Flask-Limiter di login & API publik.
- Security headers via Flask-Talisman: CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS.
- Cek otorisasi per role di setiap endpoint (admin / donor / receiver). Upload file: batasi tipe & ukuran.

## Desain (dinilai juri: UI/UX 30%)
- Font: Poppins (400/500/600/700). Bahasa antarmuka: Bahasa Indonesia.
- Token warna ada di `app/static/css/tokens.css`. Jangan hardcode warna di template.
- Konsisten: komponen card, tombol, tabel, badge, dan empty state dipakai ulang.
- Responsif mobile-first. Ada loading, empty, dan error state di setiap halaman data.
- Aksesibilitas dasar: kontras AA, label form, fokus terlihat.
