"""Fungsi bantu yang dipakai lintas modul."""
import re
import unicodedata
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlencode, urlsplit

from flask import flash, g, redirect, request, url_for
from werkzeug.routing import BuildError

from .db import get_db

# Rute login berada di blueprint infosys (dibuat di Prompt 5).
LOGIN_ENDPOINT = "infosys.login"
LOGIN_FALLBACK_PATH = "/infosys/login"


def now_iso():
    """Waktu saat ini (UTC) dalam format ISO-8601, mis. 2026-11-13T03:06:00+00:00."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Redirect aman dan login_required
# --------------------------------------------------------------------------
def is_safe_next(target):
    """True hanya untuk jalur lokal (mis. /forum/thread/3). Mencegah open redirect.

    Menolak URL absolut (https://...), protocol-relative (//evil.com),
    backslash, dan karakter kontrol yang diabaikan sebagian peramban.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    if any(ch in target for ch in "\\\r\n\t"):
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc


def _origin_path():
    """Halaman asal yang akan dituju setelah login, atau None bila tidak ada."""
    if request.method == "GET":
        return request.full_path.rstrip("?")
    # Untuk POST, kembali ke halaman pengirim (hanya bila di situs yang sama).
    if request.referrer:
        ref = urlsplit(request.referrer)
        if ref.netloc == request.host:
            path = ref.path + (f"?{ref.query}" if ref.query else "")
            return path
    return None


def _login_url(next_path):
    params = {"next": next_path} if next_path and is_safe_next(next_path) else {}
    try:
        return url_for(LOGIN_ENDPOINT, **params)
    except BuildError:  # rute login belum dibuat (skeleton Fase 0)
        query = f"?{urlencode(params)}" if params else ""
        return LOGIN_FALLBACK_PATH + query


def login_required(view):
    """Wajibkan login; Guest diarahkan ke /login?next=<halaman asal>."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Silakan masuk terlebih dahulu untuk mengakses halaman ini.", "warning")
            return redirect(_login_url(_origin_path()))
        return view(*args, **kwargs)

    return wrapped


# --------------------------------------------------------------------------
# Log aktivitas dan notifikasi
# (nama kolom sudah disesuaikan dengan schema.sql / Blueprint 3.3)
# --------------------------------------------------------------------------
def log_activity(module, action, detail=None, user_id=None, commit=True):
    """Catat satu baris ke activity_logs untuk pengguna yang sedang login.

    Beri commit=False bila dipanggil di dalam transaksi yang lebih besar
    (mis. checkout) agar ikut COMMIT/ROLLBACK bersama transaksinya.
    """
    if user_id is None and g.get("user") is not None:
        user_id = g.user["id"]
    if user_id is None:  # Guest tidak dicatat
        return
    db = get_db()
    db.execute(
        "INSERT INTO activity_logs (user_id, module_key, action, detail, ip_address, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, module, action, detail, request.remote_addr, now_iso()),
    )
    if commit:
        db.commit()


def notify(user_id, title, body=None, link=None, module=None, commit=True):
    """Buat notifikasi untuk user_id (tampil di lonceng Top-Bar)."""
    # schema.sql (Blueprint 3.3) hanya punya kolom `message` dan `link_url`,
    # jadi judul dan isi digabung menjadi satu pesan.
    message = f"{title}: {body}" if body else title
    db = get_db()
    db.execute(
        "INSERT INTO notifications (user_id, module_key, message, link_url, is_read, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (user_id, module, message, link, now_iso()),
    )
    if commit:
        db.commit()


# --------------------------------------------------------------------------
# Slug
# --------------------------------------------------------------------------
def slugify(text, max_length=80):
    """'Belajar Flask: Dasar-dasar!' -> 'belajar-flask-dasar-dasar'."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length].strip("-")
