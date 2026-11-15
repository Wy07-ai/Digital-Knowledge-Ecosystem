"""Pengaturan per modul (Blueprint 5.4): satu pola untuk semua tab Pengaturan.

Semua modul menyimpan pengaturan pribadinya di tabel `module_settings` (key-value, UNIQUE
user_id + module_key + setting_key). Modul TIDAK menulis SQL sendiri; cukup:

    from ..module_settings import get_setting, set_setting

    speed = get_setting(user_id, "elearning", "playback_speed", default="1")
    set_setting(user_id, "elearning", "playback_speed", "1.5")

Aturan bersama:
  * Nilai disimpan sebagai teks. Validasi nilai tetap tugas modul pemanggil.
  * set_setting(..., None) menghapus baris (kembali ke nilai bawaan).
  * commit=True (bawaan) langsung COMMIT; beri commit=False bila dipanggil di dalam transaksi
    yang lebih besar (mis. menyimpan beberapa pengaturan + log_activity sekaligus), lalu
    pemanggil yang melakukan db.commit() atau db.rollback().
  * module_key dan setting_key selalu lewat parameter SQL, tidak pernah dirangkai ke teks SQL.
"""
from .db import get_db

# Kalimat bersama untuk semua tab Pengaturan (Blueprint 5.5: spesifik, ramah, ada jalan keluar).
MSG_SAVE_FAILED = "Pengaturan belum bisa disimpan. Coba lagi sebentar lagi."


def msg_saved(module_name, detail=None):
    """'Pengaturan E-Learning berhasil disimpan.' (+ rincian singkat bila ada)."""
    return f"Pengaturan {module_name} berhasil disimpan." + (f" {detail}" if detail else "")


def get_setting(user_id, module_key, setting_key, default=None, db=None):
    """Nilai pengaturan (teks) milik user_id, atau `default` bila belum pernah disimpan/kosong."""
    db = db or get_db()
    row = db.execute(
        "SELECT setting_value FROM module_settings "
        "WHERE user_id = ? AND module_key = ? AND setting_key = ?",
        (user_id, module_key, setting_key),
    ).fetchone()
    if row is None or row["setting_value"] is None:
        return default
    return row["setting_value"]


def set_setting(user_id, module_key, setting_key, value, db=None, commit=True):
    """Simpan (upsert) satu pengaturan; `value=None` menghapusnya."""
    db = db or get_db()
    if value is None:
        db.execute(
            "DELETE FROM module_settings WHERE user_id = ? AND module_key = ? AND setting_key = ?",
            (user_id, module_key, setting_key),
        )
    else:
        db.execute(
            "INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, module_key, setting_key) "
            "DO UPDATE SET setting_value = excluded.setting_value",
            (user_id, module_key, setting_key, str(value)),
        )
    if commit:
        db.commit()
