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
python run.py
```

Buka http://127.0.0.1:5000. Variabel opsional: `DKE_SECRET_KEY`, `FLASK_DEBUG`, `HOST`, `PORT`.

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
    ├── main/               # Beranda
    ├── infosys/ ecommerce/ elearning/ etutorial/ portal/ forum/
    │   ├── __init__.py     # Blueprint
    │   └── routes.py       # rute modul
    ├── templates/
    │   ├── base.html       # kerangka sementara (final di Prompt 4)
    │   ├── _components/    # topbar, app_switcher, breadcrumb, ... (Prompt 4)
    │   ├── main/
    │   └── <modul>/        # layout_<modul>.html + halaman modul
    └── static/{css,js,img}
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

## Catatan asumsi

Dokumen Blueprint tidak ikut terlampir saat skeleton dibuat, sehingga struktur folder dan nama
kolom (`users`, `user_settings`, `activity_logs`, `notifications`) disusun dari Blok Konteks.
Cocokkan dengan Blueprint 6.1 dan `schema.sql` (Prompt 2) bila ada perbedaan.

## Roadmap

Fase 0 skeleton (selesai) → schema.sql + seed.py → Fase 1 fondasi tampilan dan autentikasi →
Fase 2-5 modul → Fase 6 QA dan laporan.
