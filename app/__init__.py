"""Application factory Digital Knowledge Ecosystem (DKE)."""
import os
import sqlite3
from importlib import import_module

from flask import Flask, g, request, session

from . import db
from .navigation import build_nav
from .utils import csrf_token, current_login_url, notification_summary, safe_url_for

# Daftar 6 modul. Satu modul = satu Blueprint = satu folder template.
# "key" sama dengan nama paket Python (app/<key>/) dan nama Blueprint.
MODULES = [
    {"key": "infosys",   "name": "Information System", "prefix": "/infosys",   "accent": "#4F46E5", "desc": "Profil, log aktivitas, dan statistik lintas modul."},
    {"key": "ecommerce", "name": "E-Commerce",         "prefix": "/ecommerce", "accent": "#F59E0B", "desc": "Katalog produk, keranjang, dan checkout."},
    {"key": "elearning", "name": "E-Learning",         "prefix": "/elearning", "accent": "#2563EB", "desc": "Kelas, materi, kuis, dan progres belajar."},
    {"key": "etutorial", "name": "E-Tutorial",         "prefix": "/etutorial", "accent": "#7C3AED", "desc": "Tutorial langkah demi langkah dengan contoh kode."},
    {"key": "portal",    "name": "Portal",             "prefix": "/portal",    "accent": "#E11D48", "desc": "Artikel dan berita pilihan per kategori."},
    {"key": "forum",     "name": "Forum",              "prefix": "/forum",     "accent": "#0D9488", "desc": "Diskusi, tanya jawab, dan balasan komunitas."},
]
MODULE_BY_KEY = {m["key"]: m for m in MODULES}

# Pengaturan bawaan untuk Guest atau bila baris user_settings belum ada.
DEFAULT_SETTINGS = {
    "theme": "system",         # light | dark | system
    "view_mode": "desktop",    # desktop | mobile
    "landing_mode": "launcher",  # launcher | last_module (Smart Landing)
    "last_module": None,
    "last_path": None,
}

# Penanda sesi: Member sudah "mendarat" (sudah membuka halaman apa pun) di sesi ini. Dipakai Beranda
# agar landing_mode = last_module hanya mengalihkan pada kedatangan pertama (lihat main/routes.py).
LANDED_KEY = "dke_landed"

# Halaman yang tidak boleh dicatat sebagai "halaman terakhir".
NO_TRACK_ENDPOINTS = {"infosys.login", "infosys.register", "infosys.logout"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Ganti lewat variabel lingkungan DKE_SECRET_KEY saat dipakai sungguhan.
        SECRET_KEY=os.environ.get("DKE_SECRET_KEY", "dev-only-ganti-di-produksi"),
        DATABASE=os.path.join(app.instance_path, "dke.db"),
        # Halaman uji komponen (/dev/ui-test). Matikan di produksi: DKE_UI_TEST=0
        UI_TEST_PAGE=os.environ.get("DKE_UI_TEST", "1") == "1",
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    _register_blueprints(app)
    _register_hooks(app)
    return app


def _register_blueprints(app):
    """Daftarkan 7 blueprint: Beranda (main) + 6 modul dengan url_prefix masing-masing."""
    from .main import bp as main_bp

    app.register_blueprint(main_bp)  # Beranda di "/"
    for module in MODULES:
        bp = import_module(f"app.{module['key']}").bp
        app.register_blueprint(bp, url_prefix=module["prefix"])


def _register_hooks(app):
    @app.before_request
    def load_user_and_settings():
        """Isi g.user dan g.settings untuk setiap permintaan."""
        g.user = None
        g.settings = dict(DEFAULT_SETTINGS)
        if request.endpoint == "static":
            return
        user_id = session.get("user_id")
        if user_id is None:  # Guest: cukup pengaturan bawaan
            return
        try:
            conn = db.get_db()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:  # akun sudah tidak ada -> anggap Guest
                session.pop("user_id", None)
                return
            g.user = user
            if request.endpoint != "main.index" and not session.get(LANDED_KEY):
                session[LANDED_KEY] = True  # Member membuka halaman lain dulu: Beranda tidak dialihkan lagi
            row = conn.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is not None:
                g.settings.update({k: row[k] for k in row.keys() if row[k] is not None})
        except sqlite3.OperationalError:
            # Tabel belum ada (database belum di-seed): perlakukan sebagai Guest.
            g.user = None

    @app.after_request
    def remember_last_page(response):
        """Simpan modul dan halaman terakhir yang dibuka Member (untuk Smart Landing)."""
        if (
            g.get("user") is None
            or request.method != "GET"
            or response.status_code != 200
            or response.mimetype != "text/html"
            or request.blueprint not in MODULE_BY_KEY
            or request.endpoint in NO_TRACK_ENDPOINTS
        ):
            return response
        module_key = request.blueprint
        path = request.full_path.rstrip("?")
        if g.settings.get("last_module") == module_key and g.settings.get("last_path") == path:
            return response  # tidak berubah, hemat satu UPDATE
        try:
            conn = db.get_db()
            conn.execute(
                "UPDATE user_settings SET last_module = ?, last_path = ? WHERE user_id = ?",
                (module_key, path, g.user["id"]),
            )
            conn.commit()
        except sqlite3.Error:
            app.logger.warning("Gagal menyimpan last_module/last_path", exc_info=True)
        return response

    @app.context_processor
    def inject_globals():
        """Variabel yang tersedia di semua template."""
        current = MODULE_BY_KEY.get(request.blueprint)
        return {
            "MODULES": MODULES,
            "current_module": current,
            "accent": current["accent"] if current else "#475569",
            "current_user": g.get("user"),
            "settings": g.get("settings", DEFAULT_SETTINGS),
            # Navigasi 3 level: breadcrumb + tombol Kembali dari hierarki (app/navigation.py)
            "nav": _current_nav(),
            # Helper untuk Top-Bar (lihat app/utils.py)
            "safe_url": safe_url_for,
            "login_url": current_login_url,
            "notification_summary": notification_summary,
            "csrf_token": csrf_token,
        }


def _current_nav():
    """build_nav() sekali per permintaan (hasilnya di-cache di g)."""
    if "_nav" not in g:
        g._nav = build_nav()
    return g._nav
