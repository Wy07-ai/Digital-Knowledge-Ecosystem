"""Data Beranda (Dashboard Launcher): widget ringkas tiap modul dan tujuan "Lanjutkan".

Semua angka dan judul berasal dari database (bukan data tiruan). Setiap widget:
  * mengembalikan dict {summary, detail, progress, empty, error} yang dipakai _components/module_card.html
  * menangani data kosong dengan pesan yang ramah (empty=True), bukan angka 0 yang membingungkan
  * gagal dengan aman: bila tabel belum ada atau kueri error, kartu tetap tampil
Guest tidak punya data pribadi, jadi widget memakai konten publik (produk, tutorial, artikel, thread).
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
def _w(summary, detail=None, progress=None, empty=False, error=False):
    return {"summary": summary, "detail": detail, "progress": progress, "empty": empty, "error": error}


def _scalar(db, sql, params=()):
    return db.execute(sql, params).fetchone()[0]


def _infosys(db, uid):
    if uid is None:
        return _w("Masuk untuk melihat aktivitas Anda", "Profil, log, dan statistik lintas modul.", empty=True)
    total = _scalar(
        db,
        "SELECT COUNT(*) FROM activity_logs WHERE user_id = ? AND datetime(created_at) >= datetime(?)",
        (uid, _start_of_today_utc()),
    )
    last = friendly_when(g.user["last_login_at"])
    detail = f"Login terakhir: {last}" if last else None
    if total == 0:
        return _w("Belum ada aktivitas hari ini", detail, empty=True)
    return _w(f"{total} aktivitas hari ini", detail)


def _ecommerce(db, uid):
    latest = db.execute(
        "SELECT name FROM products WHERE is_active = 1 ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
    ).fetchone()
    newest = latest["name"] if latest else None
    if uid is None:
        return _w(f"Terbaru: {newest}") if newest else _w("Belum ada produk", empty=True)
    items = _scalar(db, "SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE user_id = ?", (uid,))
    detail = f"Produk terbaru: {newest}" if newest else None
    if items:
        return _w(f"{items} item di keranjang", detail)
    return _w("Keranjang masih kosong", detail, empty=True)


def _elearning(db, uid):
    available = _scalar(db, "SELECT COUNT(*) FROM courses WHERE is_published = 1")
    catalog = f"{available} kelas tersedia" if available else None
    if uid is None:
        if not available:
            return _w("Belum ada kelas", empty=True)
        return _w(catalog, "Masuk untuk melihat progres belajar.")
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
        return _w("Belum mengikuti kelas", catalog, empty=True)
    if not row["total"]:
        return _w(row["title"], "Belum ada materi")
    percent = min(100, round(row["done"] * 100 / row["total"]))
    detail = "Kelas selesai" if row["done"] >= row["total"] else f"{row['done']} dari {row['total']} materi selesai"
    return _w(row["title"], detail, progress=percent)


def _etutorial(db, uid):
    popular = db.execute(
        """
        SELECT t.title FROM tutorials t
          LEFT JOIN tutorial_bookmarks b ON b.tutorial_id = t.id
         GROUP BY t.id
         ORDER BY COUNT(b.user_id) DESC, datetime(t.created_at) DESC, t.id DESC
         LIMIT 1
        """
    ).fetchone()
    name = popular["title"] if popular else None
    if uid is None:
        return _w(f"Populer: {name}") if name else _w("Belum ada tutorial", empty=True)
    saved = _scalar(db, "SELECT COUNT(*) FROM tutorial_bookmarks WHERE user_id = ?", (uid,))
    detail = f"Populer: {name}" if name else None
    if saved:
        return _w(f"{saved} tutorial tersimpan", detail)
    return _w("Belum ada tutorial tersimpan", detail, empty=True)


def _portal(db, uid):
    row = db.execute(
        "SELECT title, read_minutes FROM articles ORDER BY datetime(published_at) DESC, id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return _w("Belum ada artikel", empty=True)
    detail = "Artikel terbaru" + (f" · {row['read_minutes']} menit baca" if row["read_minutes"] else "")
    return _w(row["title"], detail)


def _forum(db, uid):
    row = db.execute(
        "SELECT title FROM threads ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
    ).fetchone()
    newest = row["title"] if row else None
    if uid is None:
        return _w(f"Thread terbaru: {newest}") if newest else _w("Belum ada thread", empty=True)
    unread = _scalar(
        db,
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND module_key = 'forum' AND is_read = 0",
        (uid,),
    )
    detail = f"Thread terbaru: {newest}" if newest else None
    if unread:
        return _w(f"{unread} balasan baru", detail)
    return _w("Tidak ada balasan baru", detail, empty=True)


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
            widgets[module["key"]] = _w("Ringkasan belum tersedia", "Buka modul untuk melihat isinya.", empty=True, error=True)
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
