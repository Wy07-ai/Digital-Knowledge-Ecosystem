"""Validasi form autentikasi (UC-IS-01 dan UC-IS-02) dan katalog pesannya.

Teks pesan ada di app/messages.py dan mengikuti Blueprint 5.5 (Perancangan Pesan): spesifik,
ramah, menyebutkan solusi, tidak menyalahkan, Bahasa Indonesia sederhana.

Aturan di sini HARUS sama dengan static/js/auth.js (validasi inline di peramban).
Server tetap menjadi penentu akhir: JS hanya mempercepat umpan balik.
"""
import re

# Kalimat pesan ada di app/messages.py (satu sumber). Nama di bawah diimpor ulang di sini
# supaya `from .validation import MSG_...` tetap berfungsi.
from ..messages import (  # noqa: F401
    MSG_ACCOUNT_INACTIVE, MSG_CONFIRM_MISMATCH, MSG_EMAIL_INVALID, MSG_EMAIL_TAKEN,
    MSG_LOGIN_FAILED, MSG_LOGIN_THROTTLED, MSG_NAME_REQUIRED, MSG_NAME_TOO_LONG,
    MSG_PASSWORD_MAX, MSG_PASSWORD_MIN, MSG_PASSWORD_REQUIRED,
)

NAME_MAX = 100
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 128   # batas atas mencegah hashing kata sandi sangat panjang (beban CPU)

# Sengaja sederhana: ada teks, "@", teks, ".", teks; tanpa spasi. Verifikasi sungguhan
# (kotak masuk) di luar cakupan (Blueprint: tanpa verifikasi email).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value):
    """Email dibandingkan dalam huruf kecil dan tanpa spasi tepi."""
    return (value or "").strip().lower()


def normalize_name(value):
    """Rapikan spasi ganda: '  Siti   Aisyah ' -> 'Siti Aisyah'."""
    return " ".join((value or "").split())


def check_email(email):
    """Pesan error untuk email (sudah dinormalisasi), atau None bila valid."""
    if not email or len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        return MSG_EMAIL_INVALID
    return None


def validate_register(name, email, password, confirm):
    """Kembalikan dict {field: pesan}. Kosong berarti semua valid."""
    errors = {}
    if not name:
        errors["name"] = MSG_NAME_REQUIRED
    elif len(name) > NAME_MAX:
        errors["name"] = MSG_NAME_TOO_LONG

    msg = check_email(email)
    if msg:
        errors["email"] = msg

    if len(password) < PASSWORD_MIN:
        errors["password"] = MSG_PASSWORD_MIN
    elif len(password) > PASSWORD_MAX:
        errors["password"] = MSG_PASSWORD_MAX

    if confirm != password:
        errors["confirm"] = MSG_CONFIRM_MISMATCH
    return errors


def validate_login(email, password):
    """Login hanya memeriksa format. Panjang minimum TIDAK dipakai di sini:
    itu aturan membuat kata sandi, bukan aturan masuk."""
    errors = {}
    msg = check_email(email)
    if msg:
        errors["email"] = msg
    if not password:
        errors["password"] = MSG_PASSWORD_REQUIRED
    return errors


# --------------------------------------------------------------------------
# Akun Saya (UC-IS-04 profil, UC-IS-05 ganti kata sandi)
# Aturan di sini HARUS sama dengan static/js/panel.js.
# --------------------------------------------------------------------------
from ..messages import (  # noqa: E402,F401
    MSG_AVATAR_INVALID, MSG_AVATAR_TOO_LONG, MSG_BIO_TOO_LONG, MSG_CURRENT_REQUIRED,
    MSG_CURRENT_WRONG, MSG_NEW_CONFIRM_MISMATCH, MSG_NEW_SAME, MSG_PASSWORD_LOCKED,
)

BIO_MAX = 300
AVATAR_MAX = 500


def normalize_bio(value):
    """Seragamkan baris baru dan buang spasi tepi; baris kosong beruntun diringkas jadi satu."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def normalize_avatar_url(value):
    return (value or "").strip()


def check_avatar_url(url):
    """Pesan error untuk tautan avatar, atau None. Kosong = boleh (memakai inisial nama)."""
    if not url:
        return None
    if len(url) > AVATAR_MAX:
        return MSG_AVATAR_TOO_LONG
    if re.search(r"\s", url) or not re.match(r"^https?://[^/\s?#]+", url, re.I):
        return MSG_AVATAR_INVALID
    return None


def validate_profile(name, bio, avatar_url):
    """Kembalikan dict {field: pesan} untuk form profil (nilai sudah dinormalisasi)."""
    errors = {}
    if not name:
        errors["name"] = MSG_NAME_REQUIRED
    elif len(name) > NAME_MAX:
        errors["name"] = MSG_NAME_TOO_LONG
    if len(bio) > BIO_MAX:
        errors["bio"] = MSG_BIO_TOO_LONG
    msg = check_avatar_url(avatar_url)
    if msg:
        errors["avatar_url"] = msg
    return errors


def validate_password_change(current, new, confirm):
    """Format saja; kecocokan kata sandi saat ini diperiksa di rute (butuh hash dari database)."""
    errors = {}
    if not current:
        errors["current_password"] = MSG_CURRENT_REQUIRED
    if len(new) < PASSWORD_MIN:
        errors["new_password"] = MSG_PASSWORD_MIN
    elif len(new) > PASSWORD_MAX:
        errors["new_password"] = MSG_PASSWORD_MAX
    elif current and new == current:
        errors["new_password"] = MSG_NEW_SAME
    if confirm != new:
        errors["confirm_password"] = MSG_NEW_CONFIRM_MISMATCH
    return errors
