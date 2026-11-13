"""Kueri dan pembantu Control Panel Information System (UC-IS-04..08).

ATURAN KEAMANAN: setiap fungsi di sini menerima `user_id` dari sesi (g.user["id"]), tidak pernah
dari query string/form, dan SETIAP kueri memakai `WHERE user_id = ?`. Dengan begitu tidak ada
jalur untuk membaca data milik pengguna lain (IDOR).
"""
from datetime import datetime, timedelta, timezone

PER_PAGE = 10
WIB = timezone(timedelta(hours=7))

# Label tampilan untuk kolom `action` di activity_logs (bahasa Indonesia, ramah).
ACTION_LABELS = {
    "register": "Registrasi akun",
    "login": "Login",
    "logout": "Logout",
    "update_profile": "Ubah profil",
    "change_password": "Ubah kata sandi",
    "password_change_failed": "Gagal ubah kata sandi",
    "enroll": "Ikut kelas",
    "checkout": "Checkout",
    "quiz_passed": "Lulus kuis",
    "quiz_failed": "Kuis belum lulus",
    "create_thread": "Buat thread",
    "reply": "Balas thread",
    "bookmark": "Simpan tutorial",
}


def action_label(action):
    if not action:
        return "-"
    return ACTION_LABELS.get(action) or action.replace("_", " ").capitalize()


def parse_time(value):
    """ISO-8601 (dengan/tanpa zona; tanpa zona dianggap UTC) -> datetime WIB, atau None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)


_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def format_time(value):
    """'13 Nov 2026, 10:05 WIB'; teks asli bila tidak bisa dibaca."""
    dt = parse_time(value)
    if dt is None:
        return value or "-"
    return f"{dt.day} {_BULAN[dt.month - 1]} {dt.year}, {dt:%H:%M} WIB"


def parse_page(raw):
    """Nomor halaman dari query string; nilai buruk jadi 1."""
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def paginate(total, page, per_page=PER_PAGE):
    """Halaman dijepit ke rentang sah, sehingga ?halaman=999 menampilkan halaman terakhir."""
    pages = max(1, -(-total // per_page))
    page = min(max(1, page), pages)
    return {"page": page, "pages": pages, "total": total, "per_page": per_page,
            "offset": (page - 1) * per_page,
            "first": (page - 1) * per_page + 1 if total else 0,
            "last": min(page * per_page, total)}


# --------------------------------------------------------------------------
# Log aktivitas dan riwayat login
# --------------------------------------------------------------------------
def count_logs(db, user_id, module=None, action=None):
    sql, params = "SELECT COUNT(*) FROM activity_logs WHERE user_id = ?", [user_id]
    if module:
        sql += " AND module_key = ?"
        params.append(module)
    if action:
        sql += " AND action = ?"
        params.append(action)
    return db.execute(sql, params).fetchone()[0]


def fetch_logs(db, user_id, limit, offset=0, module=None, action=None):
    sql = ("SELECT id, module_key, action, detail, ip_address, created_at "
           "FROM activity_logs WHERE user_id = ?")
    params = [user_id]
    if module:
        sql += " AND module_key = ?"
        params.append(module)
    if action:
        sql += " AND action = ?"
        params.append(action)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return db.execute(sql, params).fetchall()


def module_counts(db, user_id):
    """Jumlah log per modul milik pengguna (untuk label filter)."""
    rows = db.execute("SELECT module_key, COUNT(*) AS n FROM activity_logs "
                      "WHERE user_id = ? GROUP BY module_key", (user_id,)).fetchall()
    return {r["module_key"]: r["n"] for r in rows}


# --------------------------------------------------------------------------
# Statistik lintas modul
# --------------------------------------------------------------------------
def course_progress(db, user_id):
    """Progres tiap kelas yang diikuti: [{id, title, total, done, percent}]."""
    rows = db.execute(
        "SELECT c.id, c.title, "
        "  (SELECT COUNT(*) FROM lessons l WHERE l.course_id = c.id) AS total, "
        "  (SELECT COUNT(*) FROM lesson_progress lp JOIN lessons l ON l.id = lp.lesson_id "
        "    WHERE lp.user_id = e.user_id AND l.course_id = c.id) AS done "
        "FROM enrollments e JOIN courses c ON c.id = e.course_id "
        "WHERE e.user_id = ? ORDER BY e.enrolled_at DESC, e.id DESC", (user_id,)).fetchall()
    result = []
    for r in rows:
        total, done = r["total"], min(r["done"], r["total"])
        result.append({"id": r["id"], "title": r["title"], "total": total, "done": done,
                       "percent": round(done * 100 / total) if total else None})
    return result


def user_stats(db, user_id):
    """Angka statistik lintas modul milik satu pengguna."""
    orders = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN status = 'paid' THEN total END), 0) AS spent "
        "FROM orders WHERE user_id = ?", (user_id,)).fetchone()
    courses = course_progress(db, user_id)
    measurable = [c["percent"] for c in courses if c["percent"] is not None]
    one = lambda sql: db.execute(sql, (user_id,)).fetchone()[0]  # noqa: E731 (sql tetap, bukan input)
    stats = {
        "orders": orders["n"],
        "spent": orders["spent"],
        "courses": len(courses),
        "avg_progress": round(sum(measurable) / len(measurable)) if measurable else None,
        "bookmarks": one("SELECT COUNT(*) FROM tutorial_bookmarks WHERE user_id = ?"),
        "threads": one("SELECT COUNT(*) FROM threads WHERE user_id = ?"),
        "posts": one("SELECT COUNT(*) FROM posts WHERE user_id = ?"),
    }
    stats["is_empty"] = not any(stats[k] for k in ("orders", "courses", "bookmarks", "threads", "posts"))
    return stats, courses


def initials(name):
    parts = (name or "").split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
