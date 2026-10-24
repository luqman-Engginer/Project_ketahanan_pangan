# PRD — FoodLoop ID
*Platform manajemen surplus pangan & rantai pasok untuk mengurangi food waste di Indonesia.*

Lomba: Soedirman Technoporia 2026 · Web Development · Sub tema: Food Waste & Supply Chain
(Nama produk bersifat sementara, boleh diganti.)

## 1. Masalah
Indonesia termasuk penghasil sisa pangan terbesar, sementara masih banyak keluarga rawan pangan. Surplus makanan dari restoran, toko, pasar, dan UMKM sering terbuang karena tidak ada sistem yang cepat menghubungkan pemilik surplus dengan penerima, dan pelaku usaha kecil tidak punya alat pantau stok & kedaluwarsa.
> TODO sebelum masuk proposal: verifikasi angka (mis. kajian Bappenas tentang timbulan food loss & waste) dan cantumkan sumbernya.

## 2. Tujuan
- Menghubungkan donor surplus pangan dengan penerima (bank pangan, panti, komunitas) secara cepat.
- Membantu UMKM/warung mencegah pangan kedaluwarsa lewat pemantauan stok.
- Mengukur dampak nyata: kg pangan terselamatkan, rupiah dihemat, porsi makan, CO2e dihindari.

## 3. Pengguna & Role
| Role | Siapa | Kemampuan utama |
|---|---|---|
| Donor | Restoran, toko, katering, pasar, UMKM | Kelola stok, posting surplus, lihat dampak |
| Receiver | Bank pangan, panti, komunitas, relawan | Cari & klaim surplus, konfirmasi pengambilan |
| Admin | Pengelola platform | Verifikasi organisasi, moderasi, lihat semua data |
| Publik | Siapa saja | Lihat dashboard dampak agregat (tanpa login) |

## 4. Fitur MVP (fokus penilaian juri)
1. **Dashboard dampak** — kartu KPI + grafik (tren harian, per kategori, per wilayah). Update real-time.
2. **Surplus Board** — donor posting surplus (kategori, jumlah, satuan, batas ambil, lokasi); receiver filter & klaim. Status: tersedia → diklaim → diambil / kedaluwarsa.
3. **Inventory & Expiry Tracker** — stok per item, tanggal kedaluwarsa, peringatan (H-3, H-1), saran FEFO (First Expired First Out), tombol "jadikan surplus".
4. **Waste Log** — catat pangan terbuang + alasan; dasar analitik penghematan.
5. **Laporan & Ekspor** — PDF (laporan dampak berkop), XLSX (data + ringkasan), CSV. Filter rentang tanggal & wilayah.
6. **Notifikasi real-time** — via SSE: surplus baru di wilayah, klaim masuk, item hampir kedaluwarsa.
7. **Open data** — halaman publik + endpoint JSON agregat `/api/public/impact`.
8. **Pencarian & diskusi** — search bar (surplus, stok) dan kolom komentar/tanya-jawab di Detail Surplus (juri menyebut fitur dasar seperti pencarian dan komentar; wajib berjalan tanpa bug).

Di luar MVP (jangan dikerjakan): pembayaran, aplikasi mobile native, routing kurir, ML/AI prediksi.

## 5. Perhitungan Dampak
- `kg_saved` = jumlah surplus berstatus *diambil* (dikonversi ke kg).
- `rupiah_saved` = kg_saved × harga rata-rata per kategori (tabel `impact_factors`).
- `meals` = kg_saved ÷ 0,4 (asumsi 1 porsi ≈ 400 g; konfigurable).
- `co2e_avoided` = kg_saved × faktor emisi per kategori (tabel `impact_factors`, harus bisa diubah admin; cantumkan sumber faktor di dokumentasi).

## 6. Data Model (MySQL)
- `users` (id, name, email, password_hash, role, org_id, is_active, created_at)
- `organizations` (id, name, type[donor|receiver], city_id, address, phone, verified_at)
- `provinces`, `cities` (id, name, province_id, lat, lng)
- `food_categories` (id, name, unit_default)
- `inventory_items` (id, org_id, category_id, name, qty, unit, expires_on, cost_per_unit, created_at)
- `surplus_listings` (id, org_id, category_id, title, qty, unit, qty_kg, pickup_before, city_id, notes, status, created_at)
- `claims` (id, listing_id, receiver_org_id, status[pending|approved|picked_up|cancelled], claimed_at, picked_up_at)
- `waste_logs` (id, org_id, category_id, qty_kg, reason, logged_on)
- `impact_factors` (id, category_id, price_per_kg, co2e_per_kg, source_note)
- `comments` (id, listing_id, user_id, body, parent_id, created_at)
- `notifications` (id, user_id, type, payload_json, read_at, created_at)
- `audit_logs` (id, user_id, action, entity, entity_id, created_at)
Index: `surplus_listings(status, city_id, pickup_before)`, `inventory_items(org_id, expires_on)`, `waste_logs(org_id, logged_on)`.

## 7. Halaman
Landing · Login/Register · Dashboard · Surplus Board · Detail Surplus · Inventory · Waste Log · Laporan · Notifikasi · Profil Organisasi · Dashboard Publik · Admin (verifikasi, faktor dampak).

## 8. Non-fungsional
- Performa: halaman utama < 2 dtk pada koneksi 4G; query dashboard memakai index & agregasi di SQL.
- Keamanan: lihat `AGENTS.md`. Data pribadi minimal; halaman publik hanya data agregat.
- Ketersediaan: Docker Compose, backup MySQL harian (mysqldump + cron), healthcheck `/health`.
- Dokumentasi: README (setup, env, deploy), ERD, daftar endpoint (docs/API.md), keputusan arsitektur singkat.

## 9. Desain
- Font **Poppins**. Gaya: bersih, modern, banyak ruang putih, card dengan sudut membulat (16px), bayangan halus.
- Token warna:
  - primary-400 `#38BDF8` (aksen, grafik) · primary-600 `#0284C7` · primary-700 `#0369A1` (tombol dengan teks putih, kontras AA)
  - bg `#F0F9FF` · surface `#FFFFFF` · border `#E0F2FE` · ink `#0C4A6E` · ink-muted `#475569`
  - success `#16A34A` (dampak positif) · warning `#F59E0B` (hampir kedaluwarsa) · danger `#DC2626`
- Komponen: KPI card (ikon, angka besar, delta %), chart card, tabel dengan badge status, toast notifikasi, skeleton loader.

## 9b. Keberlanjutan (Sustainability)
Juri menilai bukti keberlanjutan dan dampak nyata. Tampilkan di dashboard publik: tren kg terselamatkan per bulan, jumlah organisasi aktif, rasio surplus diambil vs kedaluwarsa. Model keberlanjutan: gratis untuk komunitas/penerima, langganan ringan untuk donor besar, kolaborasi dengan pemerintah daerah/bank pangan (tuliskan di proposal).

## 10. Kriteria Selesai (selaras dengan penilaian)
- Semua fitur MVP jalan tanpa bug fatal (Kualitas Fungsional 15%).
- Struktur kode berlapis + README + ERD (Source Code 30%).
- UI konsisten, responsif, ada empty/loading state (UI/UX 30%).
- Masalah nyata Indonesia + dampak terukur (Inovasi & Manfaat 25%).
- Seed data realistis (±100 baris) agar demo terlihat hidup.
