"""API pengaturan global Member: POST /api/settings/global.

Dipanggil oleh static/js/theme.js saat Member mengganti tema atau tampilan.
Guest tidak memakai endpoint ini (disimpan di localStorage).
Body JSON (sebagian atau semua kolom):
    {"theme": "light|dark|system", "view_mode": "desktop|mobile",
     "landing_mode": "launcher|last_module"}
"""
import sqlite3

from flask import g, jsonify, request

from .. import db
from ..utils import now_iso
from . import bp

# Daftar putih kolom -> nilai yang diizinkan. Nama kolom TIDAK pernah berasal dari input.
ALLOWED = {
    "theme": ("light", "dark", "system"),
    "view_mode": ("desktop", "mobile"),
    "landing_mode": ("launcher", "last_module"),
}


def _json_error(message, status):
    resp = jsonify(ok=False, error=message)
    resp.status_code = status
    return resp


@bp.post("/api/settings/global")
def update_global_settings():
    if g.get("user") is None:
        return _json_error("Silakan masuk terlebih dahulu.", 401)

    # Perlindungan CSRF ringan tanpa token: hanya JSON same-origin. Browser tidak bisa
    # mengirim Content-Type application/json lintas situs tanpa preflight CORS (yang
    # tidak kita aktifkan); Sec-Fetch-Site menolak permintaan lintas situs secara eksplisit.
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return _json_error("Permintaan ditolak.", 403)
    if not request.is_json:
        return _json_error("Gunakan Content-Type application/json.", 415)

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return _json_error("Data pengaturan tidak valid.", 400)

    unknown = sorted(set(data) - set(ALLOWED))
    if unknown:
        return _json_error(f"Pengaturan tidak dikenal: {', '.join(unknown)}.", 400)
    for key, value in data.items():
        if value not in ALLOWED[key]:
            return _json_error(f"Nilai {key} tidak valid. Pilihan: {', '.join(ALLOWED[key])}.", 400)

    columns = list(data)                                   # sudah lolos daftar putih
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c} = excluded.{c}" for c in columns + ["updated_at"])
    try:
        conn = db.get_db()
        conn.execute(
            f"INSERT INTO user_settings (user_id, {', '.join(columns)}, updated_at) "
            f"VALUES (?, {placeholders}, ?) "
            f"ON CONFLICT(user_id) DO UPDATE SET {updates}",
            [g.user["id"], *[data[c] for c in columns], now_iso()],
        )
        conn.commit()
    except sqlite3.Error:
        return _json_error("Pengaturan belum bisa disimpan. Coba lagi sebentar lagi.", 503)

    resp = jsonify(ok=True, saved=data)
    resp.headers["Cache-Control"] = "no-store"
    return resp
