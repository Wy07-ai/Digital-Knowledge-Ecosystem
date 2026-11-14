"""E-Tutorial: daftar tutorial, langkah bernomor (stepper), bookmark, Tersimpan, ukuran font.

Use case (Blueprint 4.x): UC-ET-01 menelusuri daftar tutorial, UC-ET-02 mengikuti langkah
(Step 1, 2, dst.), UC-ET-03 menyalin snippet kode (static/js/copy.js), UC-ET-04 bookmark
(Member), UC-ET-05 ukuran font bacaan.

Aturan penting:
  * Isi tutorial dan kode berasal dari database, jadi SELALU lewat autoescape Jinja. Template
    modul ini tidak boleh memakai |safe, Markup, atau {% autoescape false %} (dijaga oleh tes).
  * Satu langkah = satu URL (/tutorial/<slug>/langkah/<n>), sehingga tombol Kembali browser,
    tautan yang dibagikan, dan Smart Landing (last_path) semuanya membawa ke langkah yang sama.
  * Ukuran font (sm | md | lg) disimpan di module_settings (module_key = 'etutorial',
    setting_key = 'font_size') untuk Member. Guest tidak punya baris di tabel itu (user_id wajib),
    jadi pilihannya disimpan di cookie peramban.
"""
import re
import sqlite3

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from ..db import get_db
from ..utils import csrf_valid, is_safe_next, log_activity, login_required, now_iso
from . import bp

DIFFICULTIES = (("mudah", "Mudah"), ("menengah", "Menengah"), ("sulit", "Sulit"))
DIFFICULTY_LABEL = dict(DIFFICULTIES)

# Ukuran font bacaan: nilai tersimpan -> label. "md" = 16 px (teks dasar Blueprint 5.4).
FONT_CHOICES = (("sm", "Kecil"), ("md", "Sedang"), ("lg", "Besar"))
FONT_LABEL = dict(FONT_CHOICES)
DEFAULT_FONT = "md"
MODULE_KEY = "etutorial"
SETTING_FONT = "font_size"
FONT_COOKIE = "dke_et_font"  # hanya untuk Guest
FONT_COOKIE_MAX_AGE = 60 * 60 * 24 * 365

MSG_CSRF = "Sesi formulir kedaluwarsa. Muat ulang halaman lalu coba lagi."
_LANG_OK = re.compile(r"^[a-z0-9+#.\-]{1,20}$")


# --------------------------------------------------------------------------
# Pembantu data
# --------------------------------------------------------------------------
def _tutorial_query(extra_join="", where=""):
    """SELECT tutorial + kategori + jumlah langkah. Parameter fungsi ini hanya konstanta kode."""
    return f"""
    SELECT t.*, c.name AS category_name, c.slug AS category_slug,
           (SELECT COUNT(*) FROM tutorial_steps s WHERE s.tutorial_id = t.id) AS step_count
      FROM tutorials t
      LEFT JOIN categories c ON c.id = t.category_id{extra_join}
     {where}
    """


def _tutorial_view(row):
    tutorial = dict(row)
    tutorial["difficulty_label"] = DIFFICULTY_LABEL.get(
        tutorial["difficulty"], str(tutorial["difficulty"] or "").title())
    return tutorial


def get_tutorial(slug):
    row = get_db().execute(_tutorial_query(where="WHERE t.slug = ?"), (slug,)).fetchone()
    return _tutorial_view(row) if row else None


def get_steps(tutorial_id):
    return get_db().execute(
        "SELECT id, step_no, title, body, code_snippet, code_language "
        "FROM tutorial_steps WHERE tutorial_id = ? ORDER BY step_no ASC, id ASC",
        (tutorial_id,),
    ).fetchall()


def is_bookmarked(user_id, tutorial_id):
    return get_db().execute(
        "SELECT 1 FROM tutorial_bookmarks WHERE user_id = ? AND tutorial_id = ?",
        (user_id, tutorial_id),
    ).fetchone() is not None


def paragraphs(text):
    """Teks polos -> daftar paragraf (dipisah baris kosong). Tiap paragraf tetap teks biasa
    yang di-escape oleh Jinja; tidak ada HTML yang dibangun di sini."""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", str(text)) if p.strip()]


def clean_language(value):
    """Nama bahasa kode aman untuk atribut kelas dan label; selain itu None."""
    value = (value or "").strip().lower()
    return value if _LANG_OK.match(value) else None


def format_minutes(minutes):
    """20 -> '20 menit', 75 -> '1 jam 15 menit', None -> ''."""
    if not minutes:
        return ""
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} menit"
    hours, rest = divmod(minutes, 60)
    return f"{hours} jam {rest} menit" if rest else f"{hours} jam"


# --------------------------------------------------------------------------
# Pengaturan ukuran font (UC-ET-05)
# --------------------------------------------------------------------------
def get_font_size():
    """Ukuran font aktif: Member dari module_settings, Guest dari cookie, selain itu 'md'."""
    if g.get("user") is not None:
        row = get_db().execute(
            "SELECT setting_value FROM module_settings "
            "WHERE user_id = ? AND module_key = ? AND setting_key = ?",
            (g.user["id"], MODULE_KEY, SETTING_FONT),
        ).fetchone()
        value = row["setting_value"] if row else None
    else:
        value = request.cookies.get(FONT_COOKIE)
    return value if value in FONT_LABEL else DEFAULT_FONT


def save_font_size(user_id, font):
    db = get_db()
    db.execute(
        "INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, module_key, setting_key) DO UPDATE SET setting_value = excluded.setting_value",
        (user_id, MODULE_KEY, SETTING_FONT, font),
    )
    db.commit()


# --------------------------------------------------------------------------
# Daftar tutorial (UC-ET-01)
# --------------------------------------------------------------------------
@bp.route("/")
def index():
    db = get_db()
    rows = db.execute(
        _tutorial_query() + " ORDER BY datetime(t.created_at) DESC, t.id DESC"
    ).fetchall()
    everything = [_tutorial_view(r) for r in rows]

    categories = db.execute(
        "SELECT name, slug FROM categories WHERE module_key = ? ORDER BY name COLLATE NOCASE",
        (MODULE_KEY,),
    ).fetchall()
    category_slugs = {c["slug"] for c in categories}

    req_cat = (request.args.get("kategori") or "").strip().lower()
    req_diff = (request.args.get("tingkat") or "").strip().lower()
    category = req_cat if req_cat in category_slugs else None
    difficulty = req_diff if req_diff in DIFFICULTY_LABEL else None
    unknown_filter = (bool(req_cat) and category is None) or (bool(req_diff) and difficulty is None)

    def matches(t, cat, diff):
        return (cat is None or t["category_slug"] == cat) and (diff is None or t["difficulty"] == diff)

    # Angka di tiap tombol filter = hasil bila tombol itu dipilih bersama filter lain yang aktif.
    cat_counts = {c["slug"]: sum(1 for t in everything if matches(t, c["slug"], difficulty)) for c in categories}
    diff_counts = {key: sum(1 for t in everything if matches(t, category, key)) for key, _ in DIFFICULTIES}
    tutorials = [t for t in everything if matches(t, category, difficulty)]

    saved_ids = set()
    if g.user is not None:
        saved_ids = {
            r["tutorial_id"] for r in db.execute(
                "SELECT tutorial_id FROM tutorial_bookmarks WHERE user_id = ?", (g.user["id"],))
        }
    return render_template(
        "etutorial/index.html",
        page_title="Daftar Tutorial",
        tutorials=tutorials,
        total_count=len(everything),
        categories=categories,
        difficulties=DIFFICULTIES,
        category=category,
        difficulty=difficulty,
        unknown_filter=unknown_filter,
        cat_counts=cat_counts,
        diff_counts=diff_counts,
        all_cat_count=sum(1 for t in everything if matches(t, None, difficulty)),
        all_diff_count=sum(1 for t in everything if matches(t, category, None)),
        saved_ids=saved_ids,
        format_minutes=format_minutes,
    )


# --------------------------------------------------------------------------
# Halaman tutorial: satu kolom, satu langkah per halaman (UC-ET-02, UC-ET-03)
# --------------------------------------------------------------------------
def _bookmarked(tut):
    return g.user is not None and is_bookmarked(g.user["id"], tut["id"])


@bp.route("/tutorial/<slug>", defaults={"step_no": 1})
@bp.route("/tutorial/<slug>/langkah/<int:step_no>")
def tutorial(slug, step_no):
    tut = get_tutorial(slug)
    if tut is None:
        abort(404)
    steps = get_steps(tut["id"])
    total = len(steps)

    if total == 0:
        return render_template(
            "etutorial/tutorial.html", page_title=tut["title"], tutorial=tut, steps=[], step=None,
            total=0, current=0, percent=0, bookmarked=_bookmarked(tut), font=get_font_size(),
            format_minutes=format_minutes,
        )
    if step_no < 1 or step_no > total:  # langkah di luar rentang -> langkah terdekat yang ada
        return redirect(url_for("etutorial.tutorial", slug=slug, step_no=max(1, min(step_no, total))))

    step = dict(steps[step_no - 1])
    step["paragraphs"] = paragraphs(step["body"])
    step["language"] = clean_language(step["code_language"])
    return render_template(
        "etutorial/tutorial.html",
        page_title=f"{tut['title']} · Step {step_no}",
        tutorial=tut,
        steps=steps,
        step=step,
        total=total,
        current=step_no,
        percent=round(step_no * 100 / total),
        bookmarked=_bookmarked(tut),
        font=get_font_size(),
        format_minutes=format_minutes,
    )


# --------------------------------------------------------------------------
# Bookmark (UC-ET-04) dan halaman Tersimpan
# --------------------------------------------------------------------------
@bp.route("/tutorial/<slug>/simpan", methods=["POST"])
@login_required
def bookmark(slug):
    tut = get_tutorial(slug)
    if tut is None:
        abort(404)
    back = request.form.get("next", "")
    target = back if is_safe_next(back) else url_for("etutorial.tutorial", slug=slug)
    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(target)

    action = request.form.get("action", "add")
    if action not in ("add", "remove"):
        abort(400)
    user_id = g.user["id"]
    db = get_db()
    try:
        if action == "add":
            cur = db.execute(
                "INSERT OR IGNORE INTO tutorial_bookmarks (user_id, tutorial_id, created_at) VALUES (?, ?, ?)",
                (user_id, tut["id"], now_iso()),
            )
            changed = cur.rowcount == 1
            if changed:
                log_activity(MODULE_KEY, "bookmark", tut["title"], commit=False)
            db.commit()
            flash("Tutorial disimpan ke Tersimpan." if changed else "Tutorial ini sudah ada di Tersimpan.",
                  "success" if changed else "info")
        else:
            cur = db.execute(
                "DELETE FROM tutorial_bookmarks WHERE user_id = ? AND tutorial_id = ?", (user_id, tut["id"]))
            changed = cur.rowcount == 1
            if changed:
                log_activity(MODULE_KEY, "unbookmark", tut["title"], commit=False)
            db.commit()
            flash("Tutorial dihapus dari Tersimpan." if changed else "Tutorial ini memang belum disimpan.",
                  "success" if changed else "info")
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal mengubah bookmark user_id=%s tutorial=%s", user_id, tut["id"])
        flash("Perubahan belum bisa disimpan. Coba lagi sebentar lagi.", "error")
    return redirect(target)


@bp.route("/tersimpan")
@login_required
def saved():
    rows = get_db().execute(
        _tutorial_query(
            extra_join=" JOIN tutorial_bookmarks b ON b.tutorial_id = t.id",
            where="WHERE b.user_id = ?",
        ) + " ORDER BY datetime(b.created_at) DESC, t.id DESC",
        (g.user["id"],),
    ).fetchall()
    return render_template(
        "etutorial/saved.html", page_title="Tersimpan",
        tutorials=[_tutorial_view(r) for r in rows], format_minutes=format_minutes,
    )


# --------------------------------------------------------------------------
# Pengaturan: ukuran font bacaan (UC-ET-05)
# --------------------------------------------------------------------------
@bp.route("/pengaturan", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        if not csrf_valid():
            flash(MSG_CSRF, "error")
            return redirect(url_for("etutorial.settings"))
        font = request.form.get("font_size", "").strip()
        if font not in FONT_LABEL:
            return render_template(
                "etutorial/settings.html", page_title="Pengaturan E-Tutorial",
                font=get_font_size(), choices=FONT_CHOICES,
                error="Pilih salah satu ukuran font yang tersedia.",
            ), 400
        response = redirect(url_for("etutorial.settings"))
        if g.user is not None:
            try:
                save_font_size(g.user["id"], font)
            except sqlite3.Error:
                get_db().rollback()
                current_app.logger.exception("Gagal menyimpan font_size user_id=%s", g.user["id"])
                flash("Pengaturan belum bisa disimpan. Coba lagi sebentar lagi.", "error")
                return response
        else:
            response.set_cookie(FONT_COOKIE, font, max_age=FONT_COOKIE_MAX_AGE, samesite="Lax", httponly=True)
        flash(f"Ukuran font {FONT_LABEL[font].lower()} disimpan.", "success")
        return response

    return render_template(
        "etutorial/settings.html", page_title="Pengaturan E-Tutorial",
        font=get_font_size(), choices=FONT_CHOICES, error=None,
    )
