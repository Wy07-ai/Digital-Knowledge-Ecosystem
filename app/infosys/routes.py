"""Rute modul Information System.

UC-IS-01 Registrasi  : GET/POST /infosys/register
UC-IS-02 Login       : GET/POST /infosys/login   (mendukung ?next=<halaman asal>)
UC-IS-03 Logout      : POST     /infosys/logout  (GET hanya mengarahkan ke Beranda)

Control Panel (sidebar tab, aksen indigo; semua data HANYA milik g.user, lihat panel.py):
UC-IS-07 Ringkasan   : GET      /infosys/
UC-IS-04 Profil      : GET/POST /infosys/profil          (nama, bio, avatar_url)
UC-IS-05 Kata sandi  : POST     /infosys/profil/sandi
UC-IS-06 Log         : GET      /infosys/log?modul=&halaman=
UC-IS-07 Statistik   : GET      /infosys/statistik
UC-IS-08 Keamanan    : GET      /infosys/keamanan?halaman=   (riwayat login)
"""
import sqlite3
import time

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .. import DEFAULT_SETTINGS, MODULE_BY_KEY
from ..db import get_db
from ..utils import csrf_valid, log_activity, login_required, notify, now_iso, safe_next
from . import bp, panel
from .validation import (
    MSG_ACCOUNT_INACTIVE,
    MSG_CURRENT_WRONG,
    MSG_EMAIL_TAKEN,
    MSG_LOGIN_FAILED,
    MSG_PASSWORD_LOCKED,
    normalize_avatar_url,
    normalize_bio,
    normalize_email,
    normalize_name,
    validate_login,
    validate_password_change,
    validate_profile,
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


# --------------------------------------------------------------------------
# Control Panel: kerangka tab (sidebar) dan pembantu
# --------------------------------------------------------------------------
MSG_FORM_INVALID = "Periksa kembali isian yang ditandai."
PW_MAX_FAILS = 5          # percobaan salah kata sandi saat ini sebelum dikunci sementara
PW_LOCK_SECONDS = 300

PANEL_TABS = (
    # (kunci, endpoint, label, ikon)
    ("ringkasan", "infosys.index", "Ringkasan", "infosys"),
    ("profil", "infosys.profile", "Profil", "user"),
    ("log", "infosys.activity", "Log Aktivitas", "list"),
    ("statistik", "infosys.stats", "Statistik Lintas Modul", "chart"),
    ("keamanan", "infosys.security", "Pengaturan Keamanan", "shield"),
)


@bp.app_template_filter("waktu")
def _waktu_filter(value):
    return panel.format_time(value)


@bp.app_template_filter("aksi")
def _aksi_filter(value):
    return panel.action_label(value)


@bp.app_context_processor
def _panel_helpers():
    return {"PANEL_TABS": PANEL_TABS, "initials": panel.initials}


def _uid():
    """Satu-satunya sumber id pengguna untuk data panel: sesi, bukan input permintaan."""
    return g.user["id"]


def _panel(template, tab, title, status=200, **ctx):
    return render_template(template, tab=tab, page_title=title, **ctx), status


def _url_with(endpoint, **params):
    return url_for(endpoint, **{k: v for k, v in params.items() if v not in (None, "", 1)})


def _pagination_ctx(endpoint, info, **params):
    """Tautan halaman sebelumnya/berikutnya + nomor yang ditampilkan (dengan elipsis)."""
    page, pages = info["page"], info["pages"]
    shown = sorted({1, pages, page - 1, page, page + 1} & set(range(1, pages + 1)))
    items, prev = [], 0
    for n in shown:
        if n - prev > 1:
            items.append(None)  # elipsis
        items.append(n)
        prev = n
    return {**info, "numbers": items,
            "url": lambda n: _url_with(endpoint, **params, halaman=n)}


@bp.route("/")
def index():
    if g.user is None:  # Guest: gerbang masuk Control Panel
        return render_template("infosys/index.html", page_title="Information System", tab=None)
    db, uid = get_db(), _uid()
    stats, courses = panel.user_stats(db, uid)
    logins = panel.fetch_logs(db, uid, 2, action="login")
    return _panel("infosys/index.html", "ringkasan", "Ringkasan", stats=stats, courses=courses,
                  recent=panel.fetch_logs(db, uid, 5), total_logs=panel.count_logs(db, uid),
                  previous_login=logins[1]["created_at"] if len(logins) > 1 else None)


# --------------------------------------------------------------------------
# UC-IS-04 Profil dan UC-IS-05 Ubah kata sandi
# --------------------------------------------------------------------------
def _profile_values():
    u = g.user
    return {"name": u["full_name"], "bio": u["bio"] or "", "avatar_url": u["avatar_url"] or ""}


def _render_profile(values=None, pf_errors=None, pw_errors=None, focus=None, status=200):
    return _panel("infosys/profile.html", "profil", "Profil & Pengaturan", status,
                  values=values or _profile_values(), pf_errors=pf_errors or {},
                  pw_errors=pw_errors or {}, focus=focus)


@bp.route("/profil", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "GET":
        return _render_profile()

    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("infosys.profile"))

    values = {"name": normalize_name(request.form.get("name")),
              "bio": normalize_bio(request.form.get("bio")),
              "avatar_url": normalize_avatar_url(request.form.get("avatar_url"))}
    errors = validate_profile(values["name"], values["bio"], values["avatar_url"])
    if errors:
        flash(MSG_FORM_INVALID, "error")
        return _render_profile(values, pf_errors=errors, status=400,
                               focus=_first_error_field(errors, ("name", "bio", "avatar_url")))

    current = _profile_values()
    changed = [label for key, label in (("name", "nama"), ("bio", "bio"), ("avatar_url", "avatar"))
               if values[key] != current[key]]
    if not changed:
        flash("Tidak ada perubahan untuk disimpan.", "info")
        return redirect(url_for("infosys.profile"))

    db = get_db()
    try:
        db.execute("UPDATE users SET full_name = ?, bio = ?, avatar_url = ? WHERE id = ?",
                   (values["name"], values["bio"] or None, values["avatar_url"] or None, _uid()))
        log_activity(MODULE, "update_profile", "Profil diperbarui: " + ", ".join(changed),
                     commit=False)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        flash("Profil belum bisa disimpan. Coba lagi sebentar lagi.", "error")
        return _render_profile(values, status=503)

    flash("Profil berhasil disimpan.", "success")
    return redirect(url_for("infosys.profile"))


def _password_locked():
    return session.get("pw_lock_until", 0) > time.time()


@bp.route("/profil/sandi", methods=["POST"])
@login_required
def change_password():
    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("infosys.profile"))

    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    errors = validate_password_change(current, new, confirm)

    if not errors and _password_locked():
        errors["current_password"] = MSG_PASSWORD_LOCKED
    if not errors and not check_password_hash(g.user["password_hash"], current):
        errors["current_password"] = MSG_CURRENT_WRONG
        fails = session.get("pw_fails", 0) + 1
        session["pw_fails"] = fails
        if fails >= PW_MAX_FAILS:
            session["pw_lock_until"] = time.time() + PW_LOCK_SECONDS
            session["pw_fails"] = 0
        log_activity(MODULE, "password_change_failed", "Kata sandi saat ini salah")

    if errors:
        flash(MSG_PASSWORD_LOCKED if _password_locked() else MSG_FORM_INVALID, "error")
        # Kata sandi tidak pernah dikirim balik ke HTML.
        return _render_profile(pw_errors=errors, status=429 if _password_locked() else 400,
                               focus=_first_error_field(
                                   errors, ("current_password", "new_password", "confirm_password")))

    db = get_db()
    try:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new), _uid()))
        log_activity(MODULE, "change_password", "Kata sandi diubah", commit=False)
        notify(_uid(), "Kata sandi diubah",
               "Jika bukan Anda yang melakukannya, segera ubah kata sandi lagi.",
               link=url_for("infosys.security"), module=MODULE, commit=False)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        flash("Kata sandi belum bisa diubah. Coba lagi sebentar lagi.", "error")
        return _render_profile(status=503)

    session.pop("pw_fails", None)
    session.pop("pw_lock_until", None)
    flash("Kata sandi berhasil diubah.", "success")
    return redirect(url_for("infosys.profile"))


# --------------------------------------------------------------------------
# UC-IS-06 Log aktivitas (filter modul + paginasi)
# --------------------------------------------------------------------------
@bp.route("/log")
@login_required
def activity():
    db, uid = get_db(), _uid()
    raw = (request.args.get("modul") or "").strip()
    module = raw if raw in MODULE_BY_KEY else None      # nilai tak dikenal = tanpa filter
    info = panel.paginate(panel.count_logs(db, uid, module), panel.parse_page(request.args.get("halaman")))
    rows = panel.fetch_logs(db, uid, info["per_page"], info["offset"], module)
    return _panel("infosys/activity.html", "log", "Log Aktivitas", rows=rows, module=module,
                  invalid_filter=bool(raw) and module is None,
                  all_total=panel.count_logs(db, uid), counts=panel.module_counts(db, uid),
                  pager=_pagination_ctx("infosys.activity", info, modul=module))


# --------------------------------------------------------------------------
# UC-IS-07 Statistik lintas modul
# --------------------------------------------------------------------------
@bp.route("/statistik")
@login_required
def stats():
    stats_, courses = panel.user_stats(get_db(), _uid())
    return _panel("infosys/stats.html", "statistik", "Statistik Lintas Modul",
                  stats=stats_, courses=courses)


# --------------------------------------------------------------------------
# UC-IS-08 Pengaturan keamanan (riwayat login)
# --------------------------------------------------------------------------
@bp.route("/keamanan")
@login_required
def security():
    db, uid = get_db(), _uid()
    total = panel.count_logs(db, uid, action="login")
    info = panel.paginate(total, panel.parse_page(request.args.get("halaman")))
    rows = panel.fetch_logs(db, uid, info["per_page"], info["offset"], action="login")
    ips = {r["ip_address"] for r in rows if r["ip_address"]}
    return _panel("infosys/security.html", "keamanan", "Pengaturan Keamanan", rows=rows,
                  total=total, many_ips=len(ips) > 1,
                  pager=_pagination_ctx("infosys.security", info))


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
