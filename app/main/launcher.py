"""Data Beranda (Dashboard Launcher): widget ringkas tiap modul dan tujuan "Lanjutkan".

Semua angka dan judul berasal dari database (bukan data tiruan). Setiap widget:
  * mengembalikan dict {value, label, progress, empty, error, cta} (satu baris metrik) yang dipakai _components/module_card.html
  * menangani data kosong dengan pesan yang ramah (empty=True), bukan angka 0 yang membingungkan
  * gagal dengan aman: bila tabel belum ada atau kueri error, kartu tetap tampil
Guest tidak punya data pribadi, jadi tiap kartu hanya berisi satu ajakan pendek ("Lihat kelas", "Baca artikel").
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import current_app, g

from .. import MODULE_BY_KEY, MODULES
from ..db import get_db
from ..navigation import describe_path
from ..utils import safe_next

BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


# --------------------------------------------------------------------------
# Waktu: database menyimpan UTC (ISO-8601), tampilan memakai zona pengguna
# --------------------------------------------------------------------------
def _tz():
    """Zona tampilan. Atur dengan DKE_TZ; bila tzdata tidak ada (Windows) pakai UTC+7."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(os.environ.get("DKE_TZ", "Asia/Jakarta"))
    except Exception:  # ZoneInfoNotFoundError, ImportError
        return timezone(timedelta(hours=7))


def _parse(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_tz())


def friendly_when(value, now=None):
    """'hari ini 10.05', 'kemarin 09.30', '3 hari lalu', atau '5 Nov 2026'."""
    dt = _parse(value)
    if dt is None:
        return None
    now = now or datetime.now(_tz())
    days = (now.date() - dt.date()).days
    clock = dt.strftime("%H.%M")
    if days <= 0:
        return f"hari ini {clock}"
    if days == 1:
        return f"kemarin {clock}"
    if days < 7:
        return f"{days} hari lalu"
    return f"{dt.day} {BULAN[dt.month - 1]} {dt.year}"


def _start_of_today_utc():
    now = datetime.now(_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Widget per modul
# --------------------------------------------------------------------------
# Setiap widget hanya satu baris metrik (maks. ~40 karakter), tanpa deskripsi dan tanpa baris detail:
#   value : angka/kata pendek yang ditonjolkan (opsional), mis. "2"
#   label : sisa kalimat, mis. "di keranjang"
#   cta   : True bila ini ajakan untuk Guest ("Lihat kelas"), bukan data
#   empty : True bila datanya kosong (tampil redup)
def _w(label, value=None, progress=None, empty=False, error=False, cta=False):
    return {"value": value, "label": label, "progress": progress, "empty": empty, "error": error, "cta": cta}


def _cta(label):
    return _w(label, cta=True)


def _scalar(db, sql, params=()):
    return db.execute(sql, params).fetchone()[0]


def _infosys(db, uid):
    if uid is None:
        return _cta("Masuk ke akun")
    total = _scalar(
        db,
        "SELECT COUNT(*) FROM activity_logs WHERE user_id = ? AND datetime(created_at) >= datetime(?)",
        (uid, _start_of_today_utc()),
    )
    if total == 0:
        return _w("Belum ada aktivitas hari ini", empty=True)
    return _w("aktivitas hari ini", value=total)


def _ecommerce(db, uid):
    if uid is None:
        has_products = _scalar(db, "SELECT COUNT(*) FROM products WHERE is_active = 1")
        return _cta("Lihat produk") if has_products else _w("Belum ada produk", empty=True)
    items = _scalar(db, "SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE user_id = ?", (uid,))
    if items:
        return _w("di keranjang", value=items)
    return _w("Keranjang masih kosong", empty=True)


def _elearning(db, uid):
    if uid is None:
        available = _scalar(db, "SELECT COUNT(*) FROM courses WHERE is_published = 1")
        return _cta("Lihat kelas") if available else _w("Belum ada kelas", empty=True)
    row = db.execute(
        """
        SELECT c.title,
               (SELECT COUNT(*) FROM lessons l WHERE l.course_id = c.id) AS total,
               (SELECT COUNT(*) FROM lesson_progress lp JOIN lessons l ON l.id = lp.lesson_id
                 WHERE lp.user_id = e.user_id AND l.course_id = c.id) AS done,
               COALESCE((SELECT MAX(datetime(lp.completed_at)) FROM lesson_progress lp
                          JOIN lessons l ON l.id = lp.lesson_id
                          WHERE lp.user_id = e.user_id AND l.course_id = c.id),
                        datetime(e.enrolled_at)) AS last_activity
          FROM enrollments e JOIN courses c ON c.id = e.course_id
         WHERE e.user_id = ?
         ORDER BY last_activity DESC, e.id DESC
         LIMIT 1
        """,
        (uid,),
    ).fetchone()
    if row is None:
        return _w("Belum mengikuti kelas", empty=True)
    if not row["total"]:
        return _w(row["title"])
    percent = min(100, round(row["done"] * 100 / row["total"]))
    return _w(row["title"], progress=percent)


def _etutorial(db, uid):
    if uid is None:
        has_tutorials = _scalar(db, "SELECT COUNT(*) FROM tutorials")
        return _cta("Lihat tutorial") if has_tutorials else _w("Belum ada tutorial", empty=True)
    saved = _scalar(db, "SELECT COUNT(*) FROM tutorial_bookmarks WHERE user_id = ?", (uid,))
    if saved:
        return _w("tersimpan", value=saved)
    return _w("Belum ada tutorial tersimpan", empty=True)


def _portal(db, uid):
    total = _scalar(db, "SELECT COUNT(*) FROM articles")
    if total == 0:
        return _w("Belum ada artikel", empty=True)
    if uid is None:
        return _cta("Baca artikel")
    recent = _scalar(db, "SELECT COUNT(*) FROM articles WHERE datetime(published_at) >= datetime('now', '-7 days')")
    if recent:
        return _w("artikel baru minggu ini", value=recent)
    return _w("Belum ada artikel baru", empty=True)


def _forum(db, uid):
    if uid is None:
        has_threads = _scalar(db, "SELECT COUNT(*) FROM threads")
        return _cta("Lihat diskusi") if has_threads else _w("Belum ada diskusi", empty=True)
    unread = _scalar(
        db,
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND module_key = 'forum' AND is_read = 0",
        (uid,),
    )
    if unread:
        return _w("balasan baru", value=unread)
    return _w("Tidak ada balasan baru", empty=True)


_BUILDERS = {
    "infosys": _infosys,
    "ecommerce": _ecommerce,
    "elearning": _elearning,
    "etutorial": _etutorial,
    "portal": _portal,
    "forum": _forum,
}


def build_widgets():
    """{module_key: widget} untuk keenam modul. Kegagalan satu widget tidak merusak halaman."""
    uid = g.user["id"] if g.get("user") is not None else None
    widgets = {}
    for module in MODULES:
        try:
            widgets[module["key"]] = _BUILDERS[module["key"]](get_db(), uid)
        except sqlite3.Error:
            current_app.logger.warning("Widget %s gagal dimuat", module["key"], exc_info=True)
            widgets[module["key"]] = _w("Ringkasan belum tersedia", empty=True, error=True)
    return widgets


# --------------------------------------------------------------------------
# Lanjutkan (Smart Landing)
# --------------------------------------------------------------------------
def resume_target():
    """Tujuan tombol "Lanjutkan" untuk Member, atau None bila tidak ada yang bisa dilanjutkan.

    Sumber: user_settings.last_module dan last_path. Tujuan divalidasi ulang setiap kali:
    jalurnya harus lokal dan aman, masih cocok dengan rute yang ada, dan berada di modul yang
    tersimpan. Bila tidak, tombol disembunyikan (bukan mengarah ke halaman rusak).
    Hasil: {"module": dict modul, "url": jalur, "labels": ["E-Learning", "Python Dasar", ...]}
    """
    if g.get("user") is None:
        return None
    key = g.settings.get("last_module")
    path = g.settings.get("last_path")
    module = MODULE_BY_KEY.get(key)
    if module is None:
        return None
    if not path:
        return {"module": module, "url": module["prefix"] + "/", "labels": [module["name"]]}
    if safe_next(path) is None:
        return None
    described = describe_path(path)
    if described is None:
        return None
    endpoint, labels = described
    if endpoint.split(".", 1)[0] != key:
        return None
    if not labels:  # rute ada tetapi belum punya hierarki: tampilkan modulnya saja
        labels = [module["name"], "Halaman terakhir"]
    return {"module": module, "url": path, "labels": labels}
