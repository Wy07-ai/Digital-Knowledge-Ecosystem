"""Akses database SQLite (instance/dke.db).

Pola standar Flask: satu koneksi per permintaan, disimpan di `g`, dan
ditutup otomatis saat permintaan selesai.
"""
import sqlite3

from flask import current_app, g


# Batas tunggu (ms) bila database dikunci penulis lain. Bisa diubah lewat config DATABASE_BUSY_TIMEOUT_MS.
DEFAULT_BUSY_TIMEOUT_MS = 5000


def get_db():
    """Kembalikan koneksi SQLite untuk permintaan saat ini (dibuat bila belum ada).

    Mode journal WAL membuat pembaca tidak terblokir oleh penulis. Catatan: WAL membuat berkas
    `-wal` dan `-shm` di samping database dan tidak aman di sebagian filesystem jaringan (NFS/SMB).
    """
    if "db" not in g:
        busy_ms = int(current_app.config.get("DATABASE_BUSY_TIMEOUT_MS", DEFAULT_BUSY_TIMEOUT_MS))
        conn = sqlite3.connect(current_app.config["DATABASE"], timeout=busy_ms / 1000)
        conn.row_factory = sqlite3.Row            # akses kolom lewat nama: row["email"]
        conn.execute(f"PRAGMA busy_timeout = {busy_ms}")  # eksplisit, bukan hanya bawaan sqlite3
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite mematikannya secara bawaan
        try:
            # Tersimpan di berkas database: no-op bila sudah WAL. Gagal (mis. database sedang
            # dikunci) tidak fatal; koneksi ini tetap berfungsi dan WAL dicoba lagi di permintaan berikutnya.
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        g.db = conn
    return g.db


def set_busy_timeout(ms):
    """Ubah batas tunggu kunci pada koneksi permintaan saat ini."""
    get_db().execute(f"PRAGMA busy_timeout = {int(ms)}")


def close_db(exception=None):
    """Tutup koneksi bila ada. Didaftarkan sebagai teardown_appcontext."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Daftarkan fungsi database ke aplikasi."""
    app.teardown_appcontext(close_db)
