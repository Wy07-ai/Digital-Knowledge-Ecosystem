"""Akses database SQLite (instance/dke.db).

Pola standar Flask: satu koneksi per permintaan, disimpan di `g`, dan
ditutup otomatis saat permintaan selesai.
"""
import sqlite3

from flask import current_app, g


def get_db():
    """Kembalikan koneksi SQLite untuk permintaan saat ini (dibuat bila belum ada)."""
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row            # akses kolom lewat nama: row["email"]
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite mematikannya secara bawaan
        g.db = conn
    return g.db


def close_db(exception=None):
    """Tutup koneksi bila ada. Didaftarkan sebagai teardown_appcontext."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Daftarkan fungsi database ke aplikasi."""
    app.teardown_appcontext(close_db)
