"""Validasi form autentikasi (UC-IS-01 dan UC-IS-02) dan katalog pesannya.

Teks pesan mengikuti Blueprint 5.5 (Perancangan Pesan). Dua pesan pertama
diambil persis dari tabel Blueprint; sisanya ditulis dengan prinsip yang sama:
spesifik, ramah, menyebutkan solusi, tidak menyalahkan, Bahasa Indonesia.

Aturan di sini HARUS sama dengan static/js/auth.js (validasi inline di peramban).
Server tetap menjadi penentu akhir: JS hanya mempercepat umpan balik.
"""
import re

# --- Blueprint 5.5 (persis) -------------------------------------------------
MSG_EMAIL_INVALID = "Email belum valid. Contoh: nama@email.com"
MSG_PASSWORD_MIN = "Kata sandi minimal 8 karakter."
MSG_LOGIN_FAILED = "Email atau kata sandi salah. Periksa kembali dan coba lagi."  # toast merah

# --- Pesan tambahan, gaya sama --------------------------------------------
MSG_NAME_REQUIRED = "Nama lengkap wajib diisi."
MSG_NAME_TOO_LONG = "Nama lengkap maksimal 100 karakter."
MSG_PASSWORD_MAX = "Kata sandi maksimal 128 karakter."
MSG_CONFIRM_MISMATCH = "Konfirmasi kata sandi belum sama. Ketik ulang kata sandi yang sama."
MSG_PASSWORD_REQUIRED = "Kata sandi wajib diisi."
MSG_EMAIL_TAKEN = "Email ini sudah terdaftar. Silakan masuk atau gunakan email lain."
MSG_ACCOUNT_INACTIVE = "Akun ini dinonaktifkan. Hubungi admin untuk mengaktifkannya kembali."

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
