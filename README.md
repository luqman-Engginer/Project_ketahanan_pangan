# FoodLoop ID

Platform web untuk mengurangi *food waste* dan memperkuat rantai pasok pangan di Indonesia. Supplier (restoran, toko, katering, UMKM) mencatat pasokan pangan; admin meneliti, menyetujui, dan mengubahnya menjadi data dampak yang terukur.

Dibuat untuk lomba Web Development **Soedirman Technoporia 2026**, tema *Ketahanan Pangan*, sub tema **Food Waste & Supply Chain**.

## Masalah dan solusi
Surplus pangan sering terbuang karena tidak tercatat dan tidak termonitor, terutama di usaha kecil. FoodLoop ID menyediakan pencatatan pasokan dan stok, peringatan kedaluwarsa, alur peninjauan oleh admin, dan laporan dampak (kg terselamatkan, rupiah dihemat, porsi, CO2e).

## Fitur
**Supplier**
- Mencatat Pasokan, stok (dengan saran FEFO dan badge H-1/H-3), dan waste log milik sendiri
- Dashboard pribadi, komentar dan balasan pada Pasokan, pencarian, filter, pagination
- Ekspor data milik sendiri

**Admin**
- Satu-satunya yang melihat data semua supplier
- Antrian review: setujui atau tolak Pasokan dengan catatan
- Dashboard agregat (KPI, tren bulanan, kartu insight otomatis), laporan PDF/XLSX/CSV, audit log
- Mengelola supplier dan faktor dampak

**Publik**: halaman `/publik` dan endpoint `/api/public/impact` menampilkan angka dampak agregat tanpa data pribadi.

**Umum**: notifikasi real-time (SSE), animasi ringan, antarmuka responsif berbahasa Indonesia.

KPI dihitung hanya dari Pasokan berstatus *approved*.

## Teknologi
Python 3.12, Flask 3 (Blueprint), Jinja2, HTMX, Chart.js, Tailwind CSS, MySQL 8, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, Flask-Limiter, Flask-Talisman, Argon2, openpyxl, WeasyPrint.

## Menjalankan di Windows (tanpa Docker)
1. Pasang **Python 3.12** dan **Laragon** (atau XAMPP). Start MySQL, lalu buat database kosong `foodloop`.
2. Di folder proyek (PowerShell):
```powershell
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
3. Edit `.env`:
```
SECRET_KEY=isi-teks-acak-minimal-32-karakter
DATABASE_URL=mysql+pymysql://root:@localhost:3306/foodloop?charset=utf8mb4
```
4. Siapkan aplikasi:
```powershell
python scripts/build_css.py
flask db upgrade
flask seed
flask create-admin
```
5. Jalankan:
```powershell
flask run --debug
```
Buka `http://localhost:5000`.

## Dengan Docker
```bash
cp .env.example .env
docker compose up --build
docker compose exec app python scripts/build_css.py
docker compose exec app flask db upgrade
docker compose exec app flask seed
docker compose exec app flask create-admin
```

## Perintah CLI
| Perintah | Fungsi |
|---|---|
| `flask seed` | Mengisi data master (wilayah, kategori, faktor dampak) |
| `flask create-admin` | Membuat akun admin (password minimal 12 karakter) |
| `flask seed-demo` | Data contoh untuk demo (password acak dicetak sekali) |
| `flask demo-clear` | Menghapus data demo saja |

Supplier mendaftar sendiri lewat halaman Register. Admin hanya bisa dibuat lewat CLI.

## Test
```powershell
$env:DATABASE_URL="sqlite:///:memory:"; $env:SECRET_KEY="test-secret-key-test-secret-key-1"; $env:PYTHONPATH=(Get-Location).Path
python -m pytest -q
```

## Struktur folder
```
app/
  blueprints/   route HTTP (auth, admin, surplus, inventory, waste, report, export, events)
  services/     logika bisnis (impact, insight, export, notifikasi)
  models/       model database
  forms/        validasi form
  templates/    Jinja2
  static/       CSS, JS, vendor
migrations/     migrasi Flask-Migrate
tests/          pytest
docs/           PRD, progres
```
Alur kode: **blueprint -> service -> model**.

## Keamanan
Password Argon2, CSRF pada form dan HTMX, rate limiting, security headers (CSP), otorisasi per role di server, query supplier difilter dari sesi (cegah IDOR), logout lewat POST.

## Lisensi
MIT