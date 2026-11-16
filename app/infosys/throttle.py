"""Pembatas percobaan login dan ganti kata sandi, dihitung dari `activity_logs`.

Tanpa tabel baru (skema tetap 23 tabel): kegagalan dicatat sebagai baris `activity_logs`, lalu
dihitung dalam jendela waktu geser. Karena hitungan ada di database (bukan cookie sesi), membuang
cookie atau membuka peramban lain tidak mengosongkan hitungan.

Dua kunci dihitung terpisah, dan salah satunya cukup untuk menolak:
  - per akun : `login_failed` per email (disimpan sebagai hash HMAC di kolom `detail`, jadi email
               tak dikenal tidak tersimpan mentah) atau `password_change_failed` per user_id;
  - per IP   : alamat `request.remote_addr`. Sengaja tidak membaca X-Forwarded-For karena header itu
               bisa dipalsukan klien. Di belakang reverse proxy, nyalakan DKE_BEHIND_PROXY=1 (ProxyFix, lihat
               app/security.py) agar remote_addr berisi IP klien, bukan IP proxy.

Batas per IP lebih longgar daripada per akun supaya satu jaringan bersama (kampus, kantor) tidak
terkunci hanya karena satu orang salah ketik. Semua nilai dapat diganti lewat `app.config`.
"""
import hashlib
import hmac
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import current_app, request

from ..db import get_db
from ..utils import now_iso

MODULE = "infosys"
ACTION_LOGIN_FAILED = "login_failed"
ACTION_PASSWORD_FAILED = "password_change_failed"   # sudah dicatat oleh form ganti kata sandi

# Nilai bawaan; ganti lewat app.config (mis. di test_config).
DEFAULT_MAX_FAILS = 5            # LOGIN_MAX_FAILS         : kegagalan per akun dalam jendela waktu
DEFAULT_MAX_FAILS_PER_IP = 20    # LOGIN_MAX_FAILS_PER_IP  : kegagalan per IP dalam jendela waktu
DEFAULT_WINDOW_SECONDS = 600     # LOGIN_FAIL_WINDOW_SECONDS: 10 menit


def _limits():
    cfg = current_app.config
    return (cfg.get("LOGIN_MAX_FAILS", DEFAULT_MAX_FAILS),
            cfg.get("LOGIN_MAX_FAILS_PER_IP", DEFAULT_MAX_FAILS_PER_IP),
            cfg.get("LOGIN_FAIL_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS))


def _window_start(window_seconds):
    """Batas awal jendela dalam format yang sama dengan `now_iso()` (UTC, urut secara leksikal)."""
    start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    return start.isoformat(timespec="seconds")


def _count(action, since, *, ip=None, user_id=None, detail=None):
    sql, params = "SELECT COUNT(*) FROM activity_logs WHERE action = ? AND created_at >= ?", [action, since]
    for column, value in (("ip_address", ip), ("user_id", user_id), ("detail", detail)):
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(value)
    return get_db().execute(sql, params).fetchone()[0]


def _blocked(action, *, user_id=None, detail=None):
    max_account, max_ip, window = _limits()
    since = _window_start(window)
    if _count(action, since, user_id=user_id, detail=detail) >= max_account:
        return True
    ip = request.remote_addr
    return ip is not None and _count(action, since, ip=ip) >= max_ip


# --------------------------------------------------------------------------
# Login (kunci akun = email)
# --------------------------------------------------------------------------
def _login_detail(email):
    """Teks `detail` baris login_failed. Email diubah jadi hash HMAC (kunci = SECRET_KEY)."""
    key = str(current_app.config["SECRET_KEY"]).encode()
    ref = hmac.new(key, email.encode(), hashlib.sha256).hexdigest()[:24]
    return f"Percobaan login gagal (ref {ref})"


def login_blocked(email):
    """True bila email (sudah dinormalisasi) atau IP ini sudah terlalu sering gagal login.

    Berlaku sama untuk email terdaftar maupun tidak, jadi status 429 tidak membocorkan akun mana
    yang ada.
    """
    return _blocked(ACTION_LOGIN_FAILED, detail=_login_detail(email))


def record_login_failure(email, user_id=None):
    """Catat satu kegagalan login. `user_id` None untuk email tak dikenal (kolom boleh NULL)."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO activity_logs (user_id, module_key, action, detail, ip_address, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, MODULE, ACTION_LOGIN_FAILED, _login_detail(email), request.remote_addr, now_iso()),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.warning("Gagal mencatat login_failed", exc_info=True)


# --------------------------------------------------------------------------
# Ganti kata sandi (kunci akun = user_id; barisnya sudah dicatat oleh form itu sendiri)
# --------------------------------------------------------------------------
def password_change_blocked(user_id):
    return _blocked(ACTION_PASSWORD_FAILED, user_id=user_id)
