# Digital Knowledge Ecosystem (DKE)

Tugas Besar IMK · Teknik Informatika, Universitas Bale Bandung.

Platform web dengan 6 modul independen yang memakai satu database SQLite dan satu sistem
autentikasi: **Information System, E-Commerce, E-Learning, E-Tutorial, Portal, Forum**.

**Stack:** Python 3.10+, Flask (Blueprint), sqlite3, Jinja2, HTML5, Tailwind CDN, JavaScript biasa.

## Menjalankan

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py        # membuat instance/dke.db, 23 tabel, data contoh, dan akun demo
python run.py
```

Buka http://127.0.0.1:5000. Variabel opsional: `DKE_SECRET_KEY`, `FLASK_DEBUG`, `HOST`, `PORT`.

## Database dan data contoh

- `schema.sql` : 23 tabel sesuai Blueprint 3.3 (dapat dijalankan sendiri di SQLite).
- `seed.py`    : membuat database dari awal dan mengisi data contoh berbahasa Indonesia.

```bash
python seed.py            # aman dijalankan ulang: tidak menggandakan data, tidak menimpa kata sandi
python seed.py --reset    # hapus semua tabel lalu bangun ulang dari nol (data lama hilang)
```

Isi seed: kategori per modul, 6 produk (2 bertipe kursus, terhubung ke kursus lewat `course_id`),
3 kursus (15 pelajaran, 3 kuis, 15 soal; 1 kursus gratis), 5 tutorial (22 langkah dengan snippet kode),
10 artikel (2 featured), 5 thread dengan 18 balasan, serta data contoh untuk akun demo.
Seed ditutup dengan pemeriksaan kewajaran data dan jumlah baris setiap tabel.

| Akun  | Email            | Kata sandi bawaan |
|-------|------------------|-------------------|
| Demo  | demo@dke.test    | `Demo12345`       |
| Admin | admin@dke.test   | `Admin12345!`     |

Ubah kata sandi bawaan dengan variabel lingkungan `DKE_DEMO_PASSWORD` / `DKE_ADMIN_PASSWORD`
sebelum seed pertama. Akun budi/citra/dewi/eko@dke.test hanya pelengkap konten forum dan tidak bisa dipakai login.

## Halaman yang tersedia (Fase 0)

| Blueprint   | URL          | Aksen     |
|-------------|--------------|-----------|
| main        | `/`          | -         |
| infosys     | `/infosys/`  | `#4F46E5` |
| ecommerce   | `/ecommerce/`| `#F59E0B` |
| elearning   | `/elearning/`| `#2563EB` |
| etutorial   | `/etutorial/`| `#7C3AED` |
| portal      | `/portal/`   | `#E11D48` |
| forum       | `/forum/`    | `#0D9488` |

## Struktur folder

```
dke/
├── run.py                  # titik masuk
├── requirements.txt
├── instance/               # dke.db dibuat di sini (tidak masuk Git)
└── app/
    ├── __init__.py         # create_app, MODULES, registrasi blueprint, hook, context processor
    ├── db.py               # get_db, close_db, init_app
    ├── utils.py            # login_required, log_activity, notify, slugify
    ├── main/               # Beranda, API pengaturan global (api.py), halaman uji
    ├── infosys/ ecommerce/ elearning/ etutorial/ portal/ forum/
    │   ├── __init__.py     # Blueprint
    │   └── routes.py       # rute modul
    ├── templates/
    │   ├── base.html       # Tailwind CDN, tema anti-kedip, Top-Bar sticky, toast-root
    │   ├── _components/    # topbar, app_switcher, breadcrumb, module_card, empty_state, _icons
    │   ├── main/
    │   └── <modul>/        # layout_<modul>.html + halaman modul
    └── static/
        ├── css/custom.css  # token Light/Dark, keyframes, Mobile View, reduced-motion
        └── js/             # theme.js toast.js switcher.js app.js
```

Aturan: satu blueprint = satu modul = satu folder template = satu `layout_<modul>.html`
yang mewarisi `base.html`.

## Cara kerja inti

- **`before_request`** mengisi `g.user` (dari `session["user_id"]`) dan `g.settings`
  (dari tabel `user_settings`, atau nilai bawaan untuk Guest atau bila DB belum dibuat).
- **`after_request`** menyimpan `last_module` dan `last_path` Member untuk tombol
  "Lanjutkan" dan Smart Landing. Hanya halaman HTML modul (GET, status 200); halaman
  login/register/logout dilewati.
- **`login_required`** mengarahkan Guest ke `/infosys/login?next=<halaman asal>`;
  `is_safe_next()` disediakan untuk mencegah open redirect.
- **`context_processor`** menyediakan `MODULES`, `current_module`, `accent`,
  `current_user`, dan `settings` ke semua template.

## Catatan skema

Nama kolom `activity_logs` dan `notifications` di `app/utils.py` sudah disesuaikan dengan `schema.sql`
(`module_key`, `message`, `link_url`). `notify()` menggabungkan `title` dan `body` menjadi satu `message`,
karena Blueprint hanya mendefinisikan kolom `message`.

## Fondasi tampilan (Fase 1, Prompt 4)

- **Tema** Light/Dark/Sistem dan **tampilan** Desktop/Mobile: Guest -> `localStorage`
  (`dke-theme`, `dke-view`); Member -> `POST /api/settings/global` (tabel `user_settings`),
  dan nilai dari database dipakai saat halaman dimuat. Skrip anti-kedip di `<head>` `base.html`.
- **Toast** menggantikan `alert()`: `toast(pesan, 'success|error|info|warning', ms)`.
  Pesan `flash()` Flask otomatis tampil sebagai toast (kategori `danger` -> error, tanpa kategori -> info).
- **Mobile View paksa**: beri kelas `launcher-grid` / `product-grid` / `card-grid` pada grid,
  `stack-mobile` pada tumpukan flex, `dke-hide-mobile` pada elemen yang disembunyikan di mobile.
  Kelas responsif Tailwind (`md:`, `lg:`) mengikuti lebar jendela sungguhan, jadi untuk elemen
  baru yang harus patuh pada Mobile View gunakan kelas-kelas tersebut.
- **Komponen** (`{% from "_components/xxx.html" import xxx %}`): `breadcrumb()`, `back_link()`,
  `module_card()`, `empty_state()`; `topbar` dan `app_switcher` di-include oleh `base.html`.
- **Token warna Tailwind**: `bg-page bg-surface text-ink text-muted border-line bg-primary text-on-primary bg-header text-success`.
  Nilainya di `custom.css`, sehingga satu kelas berlaku untuk Light dan Dark.
- **Halaman uji**: http://127.0.0.1:5000/dev/ui-test (semua jenis toast, flash() dari server, status tema).
  Matikan di produksi dengan `DKE_UI_TEST=0`.
- Tailwind dimuat dari CDN (`cdn.tailwindcss.com/3.4.17`) dan font Inter dari Google Fonts, jadi
  perlu internet saat demo; tanpa internet tampilan jatuh ke `system-ui` dan tanpa gaya Tailwind.

## Autentikasi (Fase 1, UC-IS-01..03)

| URL | Metode | Fungsi |
|-----|--------|--------|
| `/infosys/register` | GET, POST | Registrasi: membuat `users` + `user_settings` + log `register` dalam satu transaksi |
| `/infosys/login`    | GET, POST | Login; mendukung `?next=<halaman asal>`; mencatat `activity_logs` dan `last_login_at` |
| `/infosys/logout`   | POST      | Logout (mencatat `activity_logs`); GET hanya mengarahkan ke Beranda |
| `/infosys/profil`   | GET       | Penampung halaman terlindungi (`@login_required`), diisi pada UC-IS-04 |

- Validasi inline (Blueprint 5.5) ada di `app/infosys/validation.py` (server) dan `static/js/auth.js` (peramban); aturannya harus sama.
- Kata sandi: `werkzeug.security.generate_password_hash`; kredensial salah memberi pesan sama untuk email tak dikenal dan kata sandi salah.
- `next` hanya diterima bila jalur lokal (`utils.safe_next` memakai `is_safe_next`, menolak URL absolut, `//`, backslash, karakter kontrol, dan halaman login/register/logout).
- Form dilindungi token CSRF per sesi (`utils.csrf_token` / `csrf_valid`); tombol Keluar memakai POST.
- Tes otomatis: `python -m unittest discover -s tests -v`. Skenario uji manual: `docs/UJI_MANUAL_AUTH.md`.

## Roadmap

Fase 0 skeleton (selesai) → schema.sql + seed.py (selesai) → Fase 1 fondasi tampilan (selesai) dan autentikasi →
Fase 2-5 modul → Fase 6 QA dan laporan.
