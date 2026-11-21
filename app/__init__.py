"""Application factory Digital Knowledge Ecosystem (DKE)."""
import os
import sqlite3
from importlib import import_module

from flask import Flask, abort, g, request, session

from . import db
from .errors import register_error_handlers
from .navigation import build_nav
from .security import default_security_config, init_security
from .utils import csrf_token, current_login_url, notification_summary, safe_url_for

# Kunci bawaan HANYA untuk pengembangan lokal (mode debug). Nilainya tertulis di repositori, jadi siapa pun
# bisa memalsukan cookie sesi bila kunci ini dipakai di server yang terjangkau jaringan.
DEV_SECRET_KEY = "dev-only-ganti-di-produksi"

SECRET_KEY_HELP = """\
SECRET_KEY belum aman: DKE_SECRET_KEY tidak diisi (atau masih nilai bawaan) padahal mode debug mati.
Kunci ini menandatangani cookie sesi; siapa pun yang mengetahuinya bisa login sebagai pengguna mana pun.

Buat kunci acak, lalu isi sebelum menjalankan aplikasi:
    python -c "import secrets; print(secrets.token_hex(32))"
    export DKE_SECRET_KEY=<hasil perintah di atas>      # PowerShell: $env:DKE_SECRET_KEY="<hasil>"
    python run.py

Hanya untuk pengembangan di komputer sendiri (kunci bawaan boleh, debugger aktif):
    FLASK_DEBUG=1 python run.py                         # PowerShell: $env:FLASK_DEBUG="1"; python run.py"""


class ConfigError(RuntimeError):
    """Konfigurasi tidak aman atau tidak lengkap; aplikasi menolak start."""


# Daftar 6 modul. Satu modul = satu Blueprint = satu folder template.
# "key" sama dengan nama paket Python (app/<key>/) dan nama Blueprint.
MODULES = [
    {"key": "infosys",   "name": "Information System", "prefix": "/infosys",   "accent": "#4F46E5", "desc": "Profil, log aktivitas, dan statistik dari semua aplikasi."},
    {"key": "ecommerce", "name": "E-Commerce",         "prefix": "/ecommerce", "accent": "#F59E0B", "desc": "Katalog produk, keranjang, dan pembayaran."},
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

# Pelacakan halaman terakhir bersifat best-effort: UPDATE-nya hanya menunggu kunci sebentar (ms), lalu dilewati.
LAST_PAGE_BUSY_TIMEOUT_MS = 100

# Halaman yang tidak boleh dicatat sebagai "halaman terakhir".
NO_TRACK_ENDPOINTS = {"infosys.login", "infosys.register", "infosys.logout"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Wajib diisi lewat DKE_SECRET_KEY kecuali mode debug (lihat _check_secret_key).
        SECRET_KEY=os.environ.get("DKE_SECRET_KEY", "").strip() or DEV_SECRET_KEY,
        DATABASE=os.path.join(app.instance_path, "dke.db"),
        # Halaman uji komponen (/dev/ui-test). Matikan di produksi: DKE_UI_TEST=0
        UI_TEST_PAGE=os.environ.get("DKE_UI_TEST", "1") == "1",
        # Cookie sesi, ProxyFix, dan header keamanan (lihat app/security.py): DKE_HTTPS, DKE_BEHIND_PROXY, DKE_PROXY_HOPS
        **default_security_config(os.environ),
    )
    if test_config:
        app.config.update(test_config)
    _check_secret_key(app)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    _register_blueprints(app)
    _register_hooks(app)
    register_error_handlers(app)
    init_security(app)
    return app


def _check_secret_key(app):
    """Tolak start bila mode debug mati dan SECRET_KEY kosong atau masih kunci bawaan.

    Mode debug = app.debug (dari FLASK_DEBUG atau config DEBUG). Tes boleh memberi kunci sendiri
    lewat test_config (mis. SECRET_KEY="test"), yang lolos karena bukan kunci bawaan.
    """
    key = app.config.get("SECRET_KEY")
    if key and key != DEV_SECRET_KEY:
        return
    if not app.debug:
        raise ConfigError(SECRET_KEY_HELP)
    app.logger.warning(
        "Mode debug memakai SECRET_KEY bawaan. Jangan jalankan begini di jaringan yang bisa dijangkau orang lain.")
    if not key:
        app.config["SECRET_KEY"] = DEV_SECRET_KEY


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
            if not user["is_active"]:  # akun dinonaktifkan admin -> sesi tidak lagi berlaku (anggap Guest)
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
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                # Tabel belum ada (database belum di-seed): perlakukan sebagai Guest.
                g.user = None
                return
            # "database is locked" dan galat lain: BUKAN Guest. Sesi dibiarkan utuh, minta coba lagi.
            app.logger.warning("Database tidak bisa dibaca saat memuat pengguna", exc_info=True)
            g.user = None
            abort(503)

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
        conn = None
        try:
            conn = db.get_db()
            db.set_busy_timeout(LAST_PAGE_BUSY_TIMEOUT_MS)  # best-effort: jangan menahan respons
            conn.execute(
                "UPDATE user_settings SET last_module = ?, last_path = ? WHERE user_id = ?",
                (module_key, path, g.user["id"]),
            )
            conn.commit()
        except sqlite3.Error:
            app.logger.warning("Gagal menyimpan last_module/last_path", exc_info=True)
            try:
                conn.rollback()
            except (sqlite3.Error, AttributeError):
                pass
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
