# Digital Knowledge Ecosystem (DKE)

Tugas Besar IMK · Teknik Informatika, Universitas Bale Bandung.

Platform web dengan 6 aplikasi independen yang memakai satu database SQLite dan satu sistem
autentikasi. Seluruh aset (Tailwind CSS, font Inter) dilayani dari berkas sendiri, jadi aplikasi
berjalan **tanpa CDN dan tanpa internet**.

## Daftar isi

- [Aplikasi](#aplikasi)
- [Tech stack](#tech-stack)
- [Quick Start (Menjalankan)](#quick-start-menjalankan)
- [Environment variables](#environment-variables)
- [Menjalankan tes](#menjalankan-tes)
- [Struktur folder](#struktur-folder)
- [Dokumentasi](#dokumentasi)
- [Kontribusi, lisensi, dan kode etik](#kontribusi-lisensi-dan-kode-etik)
- [Roadmap](#roadmap)

## Aplikasi

Untuk pengguna, tiap bagian DKE disebut **aplikasi** (bukan "modul"). Di kode tetap `module_key`, `MODULES`,
dan sejenisnya. Istilah baku ada di [`docs/GLOSARIUM_TEKS.md`](docs/GLOSARIUM_TEKS.md).

| Aplikasi | URL | Aksen | Fungsi singkat |
|----------|-----|-------|----------------|
| Information System | `/infosys/` | `#4F46E5` | Akun Saya: login, profil, log aktivitas, statistik, keamanan, admin minimal |
| E-Commerce | `/ecommerce/` | `#F59E0B` | Katalog, keranjang, checkout simulasi, riwayat pesanan |
| E-Learning | `/elearning/` | `#2563EB` | Kelas, Ruang Belajar, progres, kuis dinilai di server |
| E-Tutorial | `/etutorial/` | `#7C3AED` | Tutorial langkah demi langkah, blok kode, bookmark |
| Portal | `/portal/` | `#E11D48` | Artikel, kategori, preferensi kategori favorit |
| Forum | `/forum/` | `#0D9488` | Thread, balasan bersarang, tandai solusi, notifikasi |

Beranda ada di `/` (blueprint `main`). Setelah server berjalan, buka http://127.0.0.1:5000.
Rincian fitur dan rute: [`docs/PANDUAN_FITUR_APLIKASI.md`](docs/PANDUAN_FITUR_APLIKASI.md).

## Tech stack

Python 3.10+, Flask (Blueprint), sqlite3, Jinja2, HTML5, Tailwind CSS (hasil build statis, tanpa CDN),
JavaScript biasa. Node.js hanya dibutuhkan untuk membangun ulang CSS.

## Quick Start (Menjalankan)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py        # membuat instance/dke.db, 23 tabel, data contoh, akun demo + admin (catat kata sandi admin yang dicetak)
export DKE_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python run.py
```

Windows PowerShell:

```powershell
$env:DKE_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python run.py
```

Buka http://127.0.0.1:5000.

- `DKE_SECRET_KEY` **wajib** saat mode debug mati (bawaan); tanpa itu `python run.py` berhenti dengan pesan penjelasan.
- Untuk pengembangan lokal: `FLASK_DEBUG=1 python run.py` (PowerShell: `$env:FLASK_DEBUG="1"; python run.py`).
  Jangan menyalakan debug pada aplikasi yang terjangkau jaringan.
- Akun demo: `demo@dke.test` / `Demo12345` (**hanya untuk lokal**). Akun admin: `admin@dke.test`, kata sandi dari
  `DKE_ADMIN_PASSWORD` atau acak dan dicetak sekali oleh `seed.py`. Rincian:
  [Database dan akun seed](docs/PANDUAN_FITUR_APLIKASI.md#database-dan-data-contoh).
- Reset database dari nol: `python seed.py --reset` (data lama hilang).
- Memperbarui database lama tanpa kehilangan data: `python seed.py --migrate`. Versi skema disimpan di
  `PRAGMA user_version`, dan langkah migrasinya ada di folder `migrations/`. Bila `seed.py` berhenti dengan pesan
  "versi skema tertinggal", jalankan perintah itu (salin berkas database lebih dulu sebagai cadangan). Menjalankannya
  berulang aman. Database lama tanpa nomor versi yang bentuknya cocok hanya ditandai versi 1, datanya tidak diubah.
  `--reset` hanya diperlukan bila datanya memang boleh hilang. Cara menambah migrasi: lihat
  [`CONTRIBUTING.md`](CONTRIBUTING.md#mengubah-skema-database-migrasi).

## Environment variables

| Variabel | Bawaan | Fungsi |
|----------|--------|--------|
| `DKE_SECRET_KEY` | (tidak ada) | Kunci sesi. Wajib saat debug mati; hasilkan dengan `secrets.token_hex(32)` |
| `FLASK_DEBUG` | `0` | `1` menyalakan mode debug (hanya untuk komputer sendiri) |
| `HOST`, `PORT` | `127.0.0.1`, `5000` | Alamat dan port server pengembangan |
| `DKE_HTTPS` | `0` | `1` menambahkan atribut `Secure` pada cookie; nyalakan hanya bila dilayani lewat `https://` |
| `DKE_BEHIND_PROXY` | `0` | `1` memasang `ProxyFix` untuk IP klien di belakang reverse proxy |
| `DKE_PROXY_HOPS` | `1` | Jumlah proxy tepercaya (bersama `DKE_BEHIND_PROXY=1`) |
| `DKE_ADMIN_PASSWORD` | (acak) | Kata sandi admin saat `seed.py` membuat akunnya |
| `DKE_DEMO_PASSWORD` | `Demo12345` | Kata sandi akun demo saat `seed.py` membuat akunnya |
| `DKE_UI_TEST` | `1` | `0` mematikan halaman uji `/dev/ui-test` di produksi |

Nilai aktif untuk variabel bertanda `1`: `1`, `true`, `yes`, atau `on`. Penjelasan lengkap setiap variabel:
[`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md#konfigurasi-lingkungan).

## Menjalankan tes

```bash
python -m unittest discover -s tests          # semua tes (tambahkan -v untuk rinci)
python -m unittest tests.test_security        # satu berkas tes
```

Tes tidak membutuhkan `DKE_SECRET_KEY` karena tiap tes memberi `SECRET_KEY` sendiri lewat `create_app(test_config)`.
Skenario uji manual ada di [`docs/`](docs/) (berkas `UJI_MANUAL_*.md`).

## Struktur folder

```
.
├── run.py                  # titik masuk aplikasi
├── seed.py, schema.sql     # database (23 tabel) dan data contoh
├── requirements.txt
├── package.json, tailwind.config.js, scripts/   # hanya untuk build CSS dan alat bantu teks
├── app/
│   ├── __init__.py         # create_app, registrasi blueprint, hook, context processor
│   ├── security.py, errors.py, messages.py, navigation.py, utils.py, db.py
│   ├── main/               # Beranda dan API pengaturan global
│   ├── infosys/ ecommerce/ elearning/ etutorial/ portal/ forum/
│   ├── templates/          # base.html, _components/, satu folder per aplikasi
│   └── static/             # css (tailwind.css hasil build), fonts, js, img
├── tests/                  # unit test (unittest)
└── docs/                   # dokumentasi detail
```

Struktur lengkap beserta fungsi tiap berkas:
[`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md#struktur-folder-lengkap).

## Dokumentasi

| Dokumen | Isi |
|---------|-----|
| [`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md) | Cara kerja inti, konfigurasi lingkungan, cookie sesi dan header keamanan (CSP), pembatas login, halaman galat, fondasi tampilan, build Tailwind offline |
| [`docs/PANDUAN_FITUR_APLIKASI.md`](docs/PANDUAN_FITUR_APLIKASI.md) | Fitur dan rute tiap aplikasi, navigasi 3 level, integrasi lintas modul, admin minimal, database dan akun seed |
| [`docs/GLOSARIUM_TEKS.md`](docs/GLOSARIUM_TEKS.md) | Panduan gaya teks antarmuka, istilah baku dan istilah terlarang, katalog pesan |
| [`docs/PERANCANGAN_ANTARMUKA.md`](docs/PERANCANGAN_ANTARMUKA.md) | Perancangan antarmuka (micro-interactions, token visual) |
| [`docs/PERUBAHAN_INTEGRASI.md`](docs/PERUBAHAN_INTEGRASI.md) | Rincian perubahan integrasi lintas modul |
| [`docs/TEKS_SEBELUM_SESUDAH.md`](docs/TEKS_SEBELUM_SESUDAH.md) | Perbandingan teks antarmuka sebelum dan sesudah penulisan ulang (Issue 5.5) |
| [`docs/INVENTARIS_TEKS.csv`](docs/INVENTARIS_TEKS.csv) | Inventaris seluruh teks tampilan (dibuat oleh `scripts/inventaris_teks.py`) |

Panduan uji manual: [Auth](docs/UJI_MANUAL_AUTH.md) ·
[Panel](docs/UJI_MANUAL_PANEL.md) · [Admin](docs/UJI_MANUAL_ADMIN.md) ·
[E-Learning](docs/UJI_MANUAL_ELEARNING.md) · [Kuis](docs/UJI_MANUAL_KUIS.md) ·
[E-Tutorial](docs/UJI_MANUAL_ETUTORIAL.md) · [Portal](docs/UJI_MANUAL_PORTAL.md) ·
[Forum](docs/UJI_MANUAL_FORUM.md) · [Integrasi](docs/UJI_MANUAL_INTEGRASI.md) ·
[Tema](docs/UJI_MANUAL_TEMA.md) · [Offline](docs/UJI_MANUAL_OFFLINE.md) ·
[Pencarian](docs/UJI_MANUAL_PENCARIAN.md) ·
[Navigasi mobile](docs/UJI_MANUAL_NAV_MOBILE.md)

Untuk meninjau semua teks tampilan: `python scripts/inventaris_teks.py --cari "kata"` atau
`python scripts/inventaris_teks.py --csv docs/INVENTARIS_TEKS.csv`.

## Kontribusi, lisensi, dan kode etik

- Panduan kontribusi: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Kode etik: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- Lisensi: [MIT](LICENSE) © 2026 Wyo Nugraha

## Roadmap

Fase 0 skeleton (selesai) → `schema.sql` + `seed.py` (selesai) → Fase 1 fondasi tampilan dan autentikasi (selesai) →
Fase 2: Akun Saya Information System (selesai) → E-Commerce, E-Learning, E-Tutorial, Portal, Forum (selesai) →
Tailwind statis/offline dan Admin minimal (selesai) → Fase 6 QA dan laporan.
