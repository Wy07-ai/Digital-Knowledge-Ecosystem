"""Rute modul Information System.

UC-IS-01 Registrasi  : GET/POST /infosys/register
UC-IS-02 Login       : GET/POST /infosys/login   (mendukung ?next=<halaman asal>)
UC-IS-03 Logout      : POST     /infosys/logout  (GET hanya mengarahkan ke Beranda)
"""
import sqlite3

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .. import DEFAULT_SETTINGS
from ..db import get_db
from ..utils import csrf_valid, log_activity, login_required, now_iso, safe_next
from . import bp
from .validation import (
    MSG_ACCOUNT_INACTIVE,
    MSG_EMAIL_TAKEN,
    MSG_LOGIN_FAILED,
    normalize_email,
    normalize_name,
    validate_login,
    validate_register,
)

MODULE = "infosys"
MSG_CSRF = "Formulir sudah kedaluwarsa. Muat ulang halaman, lalu coba lagi."

# Hash tiruan: dipakai saat email tidak ditemukan agar waktu respons login tidak
# membocorkan apakah email itu terdaftar.
_DUMMY_HASH = generate_password_hash("dke-dummy-password")

# Tema/tampilan Guest (localStorage) dibawa ke akun baru bila nilainya sah.
_THEMES = ("light", "dark", "system")
_VIEWS = ("desktop", "mobile")


def _next_url():
    """Tujuan setelah login: dari query (GET) atau field tersembunyi (POST), hanya bila aman."""
    return safe_next(request.values.get("next"))


def _first_error_field(errors, order):
    return next((f for f in order if f in errors), None)


def _find_user_by_email(email):
    return get_db().execute(
        "SELECT * FROM users WHERE lower(email) = ?", (email,)
    ).fetchone()


@bp.route("/")
def index():
    return render_template("infosys/index.html", page_title="Information System")


@bp.route("/profil")
@login_required
def profile():
    """Penampung halaman terlindungi; isi sebenarnya dibangun di UC-IS-04."""
    return render_template("infosys/profile.html", page_title="Profil & Pengaturan")


# --------------------------------------------------------------------------
# UC-IS-01 Registrasi
# --------------------------------------------------------------------------
@bp.route("/register", methods=["GET", "POST"])
def register():
    next_url = _next_url()
    if g.user is not None:
        return redirect(next_url or url_for("main.index"))

    if request.method == "GET":
        return render_template("infosys/register.html", page_title="Daftar",
                               next_url=next_url, values={}, errors={}, focus="name")

    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("infosys.register", next=next_url) if next_url
                        else url_for("infosys.register"))

    name = normalize_name(request.form.get("name"))
    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    errors = validate_register(name, email, password, confirm)
    status = 400
    if not errors and _find_user_by_email(email) is not None:
        errors["email"] = MSG_EMAIL_TAKEN
        status = 409

    if errors:
        focus = _first_error_field(errors, ("name", "email", "password", "confirm"))
        # Kata sandi tidak pernah dikirim balik ke HTML.
        return render_template("infosys/register.html", page_title="Daftar", next_url=next_url,
                               values={"name": name, "email": email}, errors=errors,
                               focus=focus), status

    theme = request.form.get("pref_theme")
    view = request.form.get("pref_view")
    theme = theme if theme in _THEMES else DEFAULT_SETTINGS["theme"]
    view = view if view in _VIEWS else DEFAULT_SETTINGS["view_mode"]

    db = get_db()
    try:
        # users + user_settings + activity_logs dalam SATU transaksi: gagal satu, batal semua.
        cur = db.execute(
            "INSERT INTO users (full_name, email, password_hash, role, is_active, created_at) "
            "VALUES (?, ?, ?, 'member', 1, ?)",
            (name, email, generate_password_hash(password), now_iso()),
        )
        user_id = cur.lastrowid
        db.execute(
            "INSERT INTO user_settings (user_id, theme, view_mode, landing_mode, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, theme, view, DEFAULT_SETTINGS["landing_mode"], now_iso()),
        )
        log_activity(MODULE, "register", "Akun baru dibuat", user_id=user_id, commit=False)
        db.commit()
    except sqlite3.IntegrityError:
        # Dua pendaftaran email yang sama bersamaan: UNIQUE(email) di database menang.
        db.rollback()
        return render_template("infosys/register.html", page_title="Daftar", next_url=next_url,
                               values={"name": name, "email": email},
                               errors={"email": MSG_EMAIL_TAKEN}, focus="email"), 409
    except sqlite3.Error:
        db.rollback()
        flash("Akun belum bisa dibuat. Coba lagi sebentar lagi.", "error")
        return render_template("infosys/register.html", page_title="Daftar", next_url=next_url,
                               values={"name": name, "email": email}, errors={},
                               focus="name"), 503

    # Alur Blueprint: Registrasi, lalu login. Email diisikan otomatis di halaman login.
    session["login_prefill_email"] = email
    flash("Akun berhasil dibuat. Silakan masuk dengan email dan kata sandi Anda.", "success")
    return redirect(url_for("infosys.login", next=next_url) if next_url
                    else url_for("infosys.login"))


# --------------------------------------------------------------------------
# UC-IS-02 Login
# --------------------------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = _next_url()
    if g.user is not None:
        return redirect(next_url or url_for("main.index"))

    if request.method == "GET":
        email = session.pop("login_prefill_email", "")
        return render_template("infosys/login.html", page_title="Masuk", next_url=next_url,
                               values={"email": email}, errors={},
                               focus="password" if email else "email")

    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("infosys.login", next=next_url) if next_url
                        else url_for("infosys.login"))

    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")

    # 3) Validasi format. 3a) Format salah: pesan di bawah kolom.
    errors = validate_login(email, password)
    if errors:
        focus = _first_error_field(errors, ("email", "password"))
        return render_template("infosys/login.html", page_title="Masuk", next_url=next_url,
                               values={"email": email}, errors=errors, focus=focus), 400

    # 4) Cocokkan hash. Selalu jalankan satu pemeriksaan hash (waktu respons seragam).
    user = _find_user_by_email(email)
    password_ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)

    if user is None or not password_ok:
        # 4a) Toast error + fokus kembali ke kolom kata sandi. Pesan sama untuk email
        # tak dikenal dan kata sandi salah (tidak membocorkan akun mana yang ada).
        flash(MSG_LOGIN_FAILED, "error")
        return render_template("infosys/login.html", page_title="Masuk", next_url=next_url,
                               values={"email": email}, errors={}, focus="password"), 401

    if not user["is_active"]:  # dicek setelah kata sandi benar agar status akun tidak bocor
        flash(MSG_ACCOUNT_INACTIVE, "error")
        return render_template("infosys/login.html", page_title="Masuk", next_url=next_url,
                               values={"email": email}, errors={}, focus="email"), 403

    # 5) Buat sesi baru (session.clear() membuang data sesi lama, termasuk token CSRF lama)
    # dan catat activity_logs.
    session.clear()
    session["user_id"] = user["id"]
    db = get_db()
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), user["id"]))
    log_activity(MODULE, "login", "Login berhasil", user_id=user["id"], commit=False)
    db.commit()

    flash(f"Selamat datang kembali, {user['full_name'].split()[0]}.", "success")
    # 5a) Dikembalikan ke halaman asal; selain itu ke Beranda 6 kotak.
    return redirect(next_url or url_for("main.index"))


# --------------------------------------------------------------------------
# UC-IS-03 Logout
# --------------------------------------------------------------------------
@bp.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "GET":
        # Membuka URL ini langsung TIDAK mengeluarkan siapa pun (cegah logout lewat tautan/gambar
        # dari situs lain). Tombol "Keluar" di Top-Bar memakai POST.
        return redirect(url_for("main.index"))

    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("main.index"))

    if g.user is not None:
        log_activity(MODULE, "logout", "Logout", commit=True)   # sebelum sesi dihapus
        session.clear()
        flash("Anda sudah keluar. Sampai jumpa lagi.", "success")
    return redirect(url_for("main.index"))
