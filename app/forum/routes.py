"""Forum: daftar thread, buat thread, detail + balasan bersarang, tandai solusi, Thread Saya, pengaturan.

Use case (Blueprint 4.x): UC-FR-01 melihat daftar thread, UC-FR-02 membuat thread (Member), UC-FR-03 melihat
detail thread, UC-FR-04 membalas (Member), UC-FR-05 menandai solusi (pemilik thread).

Aturan penting:
  * SEMUA isi buatan pengguna (judul, isi thread, balasan, nama, bio) dicetak lewat autoescape Jinja. Template
    modul ini tidak boleh memakai |safe, Markup, atau {% autoescape false %} (dijaga oleh tes). JavaScript modul
    ini memasang teks hanya lewat textContent. Tidak ada HTML yang dibangun dari teks pengguna.
  * Hak ubah/hapus balasan hanya milik penulisnya (403 untuk orang lain, termasuk pemilik thread dan admin).
    Menandai solusi hanya milik pemilik thread. Pemeriksaan dilakukan di server pada setiap rute POST, bukan
    hanya dengan menyembunyikan tombol.
  * Setiap POST memeriksa token CSRF. Semua SQL memakai parameter (?). Satu aksi = satu transaksi.
  * Balasan bersarang disimpan lewat posts.parent_post_id (tanpa batas kedalaman di database), tetapi
    DITAMPILKAN maksimal 3 tingkat (logic.MAX_DISPLAY_LEVEL).
  * Menghapus balasan yang punya anak: anak dinaikkan ke induk balasan itu, jadi jawaban orang lain tidak ikut hilang.
  * Balasan membuat notifikasi untuk penulis thread bila ia mengizinkannya (module_settings forum/notify_reply;
    belum diatur = diizinkan) dan penulis balasan bukan penulis thread sendiri.
  * Views bertambah satu per sesi peramban untuk tiap thread (COUNT_ONCE_PER_SESSION).
"""
import sqlite3

from flask import abort, current_app, flash, g, redirect, render_template, request, session, url_for

from ..db import get_db
from ..module_settings import MSG_SAVE_FAILED, get_setting, msg_saved, set_setting
from ..messages import MSG_CHANGE_FAILED
from ..utils import MSG_CSRF, csrf_valid, log_activity, login_required, notify, now_iso
from . import bp
from . import logic as lg

MODULE_KEY = "forum"
PER_PAGE = 8
MY_PER_PAGE = 10

COUNT_ONCE_PER_SESSION = True
VIEWED_KEY = "dke_fm_viewed"
VIEWED_MAX = 100
NEW_POST_KEY = "dke_fm_new_post"   # id balasan yang baru dikirim: dianimasikan slide-up sekali di halaman berikutnya


LIMITS = {
    "title_min": lg.TITLE_MIN, "title_max": lg.TITLE_MAX,
    "thread_min": lg.THREAD_BODY_MIN, "thread_max": lg.THREAD_BODY_MAX,
    "post_min": lg.POST_MIN, "post_max": lg.POST_MAX,
}


# --------------------------------------------------------------------------
# Pembantu data
# --------------------------------------------------------------------------
def get_categories(db):
    return db.execute(
        "SELECT id, name, slug FROM categories WHERE module_key = ? ORDER BY name COLLATE NOCASE", (MODULE_KEY,)
    ).fetchall()


def _thread_select(extra=""):
    """SELECT thread + kategori + penulis + jumlah balasan. Isi fungsi ini hanya konstanta kode."""
    return f"""
    SELECT t.id, t.title, t.is_solved, t.accepted_post_id, t.views, t.created_at, t.user_id{extra},
           c.name AS category_name, c.slug AS category_slug, u.full_name AS author_name,
           (SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id) AS reply_count
      FROM threads t
      LEFT JOIN categories c ON c.id = t.category_id
      JOIN users u ON u.id = t.user_id
    """


def _thread_view(row):
    item = dict(row)
    item["initials"] = lg.initials(item.get("author_name"))
    item["date_label"] = lg.format_date(item["created_at"])
    item["time_label"] = lg.relative_time(item["created_at"])
    item["replies_label"] = lg.plural_replies(item["reply_count"])
    item["is_solved"] = bool(item["is_solved"])
    return item


def _get_setting(db, user_id, key):
    return get_setting(user_id, MODULE_KEY, key, db=db)


def _save_setting(db, user_id, key, value):
    """Upsert tanpa commit (dipanggil di dalam transaksi pemanggil)."""
    set_setting(user_id, MODULE_KEY, key, value, db=db, commit=False)


def _get_thread_or_404(db, thread_id, extra=""):
    row = db.execute(_thread_select(extra) + " WHERE t.id = ?", (thread_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def _get_post_or_404(db, post_id):
    row = db.execute(
        "SELECT p.id, p.thread_id, p.user_id, p.parent_post_id, p.body, p.created_at, "
        "t.title AS thread_title, t.user_id AS thread_owner_id, t.accepted_post_id "
        "FROM posts p JOIN threads t ON t.id = p.thread_id WHERE p.id = ?",
        (post_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return row


def _owned_post_or_403(db, post_id):
    """Balasan milik pengguna yang sedang login; selain itu 404 (tak ada) atau 403 (milik orang lain)."""
    post = _get_post_or_404(db, post_id)
    if post["user_id"] != g.user["id"]:
        abort(403)
    return post


def _csrf_ok():
    """True bila token sah. Bila tidak, siapkan flash galat dan kembalikan False agar pemanggil me-redirect."""
    if csrf_valid():
        return True
    flash(MSG_CSRF, "error")
    return False


def _parse_int(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _short(text, limit=80):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _count_view(db, thread_id):
    """Tambah views thread (UPDATE atomik). HEAD tidak dihitung; kegagalan DB tidak merusak halaman."""
    if request.method != "GET":
        return False
    seen = list(session.get(VIEWED_KEY, []))
    if COUNT_ONCE_PER_SESSION and thread_id in seen:
        return False
    try:
        db.execute("UPDATE threads SET views = views + 1 WHERE id = ?", (thread_id,))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.warning("Gagal menambah views thread id=%s", thread_id, exc_info=True)
        return False
    if COUNT_ONCE_PER_SESSION:
        seen.append(thread_id)
        session[VIEWED_KEY] = seen[-VIEWED_MAX:]
    return True


def _pager(info, endpoint, **fixed):
    page, pages = info["page"], info["pages"]
    shown = sorted({1, pages, page - 1, page, page + 1} & set(range(1, pages + 1)))
    numbers, prev = [], 0
    for n in shown:
        if n - prev > 1:
            numbers.append(None)
        numbers.append(n)
        prev = n
    return {**info, "numbers": numbers,
            "url": lambda n: url_for(endpoint, **fixed, halaman=n if n > 1 else None)}


# --------------------------------------------------------------------------
# Daftar thread (UC-FR-01)
# --------------------------------------------------------------------------
@bp.route("/")
def index():
    db = get_db()
    categories = get_categories(db)
    by_slug = {c["slug"]: c for c in categories}

    req_cat = (request.args.get("kategori") or "").strip().lower()
    category = req_cat if req_cat in by_slug else None
    unknown_filter = bool(req_cat) and category is None

    req_sort = (request.args.get("urut") or "").strip().lower()
    sort = req_sort if req_sort in lg.SORT_CHOICES else "terbaru"
    unknown_sort = bool(req_sort) and req_sort not in lg.SORT_CHOICES

    # "Belum terjawab" = thread yang belum punya jawaban yang ditandai solusi; yang paling sedikit
    # balasannya tampil lebih dulu (paling butuh bantuan), lalu yang terbaru.
    sort_where = "t.is_solved = 0" if sort == "belum-terjawab" else ""

    counts = {row["category_id"]: row["n"] for row in db.execute(
        "SELECT t.category_id AS category_id, COUNT(*) AS n FROM threads t"
        + (" WHERE " + sort_where if sort_where else "") + " GROUP BY t.category_id")}
    all_total = sum(counts.values())
    chips = [{"slug": c["slug"], "name": c["name"], "count": counts.get(c["id"], 0)} for c in categories]

    clauses, params = [], []
    if sort_where:
        clauses.append(sort_where)
    if category:
        clauses.append("c.slug = ?")
        params.append(category)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    total = all_total if not category else counts.get(by_slug[category]["id"], 0)

    info = lg.paginate(total, lg.parse_page(request.args.get("halaman")), PER_PAGE)
    order = ("reply_count ASC, datetime(t.created_at) DESC, t.id DESC" if sort == "belum-terjawab"
             else "datetime(t.created_at) DESC, t.id DESC")
    rows = db.execute(_thread_select() + where + f" ORDER BY {order} LIMIT ? OFFSET ?",
                      params + [info["per_page"], info["offset"]]).fetchall() if total else []

    return render_template(
        "forum/index.html",
        page_title="Forum",
        threads=[_thread_view(r) for r in rows],
        chips=chips,
        all_total=all_total,
        category=category,
        category_name=by_slug[category]["name"] if category else None,
        sort=sort,
        unknown_filter=unknown_filter,
        unknown_sort=unknown_sort,
        pager=_pager(info, "forum.index", kategori=category, urut=sort if sort != "terbaru" else None),
    )


# --------------------------------------------------------------------------
# Buat thread (UC-FR-02)
# --------------------------------------------------------------------------
def _render_new_thread(categories, values, errors, status=200):
    return render_template(
        "forum/new_thread.html", page_title="Buat Topik", categories=categories,
        values=values, errors=errors, limits=LIMITS), status


@bp.route("/buat", methods=["GET", "POST"])
@login_required
def new_thread():
    db = get_db()
    categories = get_categories(db)
    valid_ids = {c["id"] for c in categories}

    if request.method == "GET":
        preset = next((c["id"] for c in categories if c["slug"] == (request.args.get("kategori") or "").lower()), None)
        return _render_new_thread(categories, {"title": "", "body": "", "category_id": preset}, {})

    if not _csrf_ok():
        return redirect(url_for("forum.new_thread"))
    values, errors = lg.validate_thread(
        request.form.get("title"), request.form.get("body"), request.form.get("category_id"), valid_ids)
    if errors:
        # Isian dipertahankan; kategori yang tidak sah dikosongkan agar pengguna memilih ulang.
        return _render_new_thread(categories, values, errors, status=422)

    try:
        now = now_iso()
        cur = db.execute(
            "INSERT INTO threads (category_id, user_id, title, body, is_solved, views, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (values["category_id"], g.user["id"], values["title"], values["body"], now, now))
        thread_id = cur.lastrowid
        log_activity(MODULE_KEY, "create_thread", _short(values["title"], 120), commit=False)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal membuat thread user_id=%s", g.user["id"])
        flash(MSG_CHANGE_FAILED, "error")
        return _render_new_thread(categories, values, {}, status=500)

    flash("Topik berhasil dibuat. Tunggu balasan dari anggota lain.", "success")
    return redirect(url_for("forum.thread", thread_id=thread_id))


# --------------------------------------------------------------------------
# Detail thread + balasan bersarang (UC-FR-03)
# --------------------------------------------------------------------------
def _post_rows(db, thread_id):
    return db.execute(
        "SELECT p.id, p.parent_post_id, p.user_id, p.body, p.created_at, u.full_name AS author_name "
        "FROM posts p JOIN users u ON u.id = p.user_id WHERE p.thread_id = ?", (thread_id,)).fetchall()


def _render_thread(db, thread, *, reply_error=None, reply_body="", reply_parent_id=None, status=200,
                   pop_new=True):
    """Halaman detail. Dipakai GET dan POST balasan yang gagal validasi (isian dipertahankan)."""
    uid = g.user["id"] if g.get("user") is not None else None
    is_owner = uid is not None and uid == thread["user_id"]
    flat = lg.flatten_posts(_post_rows(db, thread["id"]))
    by_id = {p["id"]: p for p in flat}

    new_id = session.pop(NEW_POST_KEY, None) if pop_new else None
    for p in flat:
        p["initials"] = lg.initials(p["author_name"])
        p["paragraphs"] = lg.paragraphs(p["body"])
        p["time_label"] = lg.relative_time(p["created_at"])
        p["datetime_label"] = lg.format_datetime(p["created_at"])
        p["is_mine"] = uid is not None and p["user_id"] == uid
        p["is_solution"] = thread["accepted_post_id"] == p["id"]
        p["is_new"] = new_id == p["id"]
        p["excerpt"] = _short(p["body"], 120)

    reply_parent = by_id.get(reply_parent_id) if reply_parent_id is not None else None
    detail = _thread_view(thread)
    detail["body"] = thread["body"]
    detail["paragraphs"] = lg.paragraphs(thread["body"])
    detail["datetime_label"] = lg.format_datetime(thread["created_at"])
    detail["solution_id"] = thread["accepted_post_id"] if thread["accepted_post_id"] in by_id else None

    return render_template(
        "forum/thread.html",
        page_title=detail["title"],
        thread=detail,
        posts=flat,
        is_owner=is_owner,
        reply_parent=reply_parent,
        reply_error=reply_error,
        reply_body=reply_body,
        max_level=lg.MAX_DISPLAY_LEVEL,
        limits=LIMITS,
    ), status


@bp.route("/thread/<int:thread_id>")
def thread(thread_id):
    db = get_db()
    row = _get_thread_or_404(db, thread_id, ", t.body AS body")
    if _count_view(db, thread_id):
        row = _get_thread_or_404(db, thread_id, ", t.body AS body")
    # ?balas=<id> menyiapkan formulir untuk membalas balasan tertentu (berfungsi tanpa JavaScript).
    return _render_thread(db, row, reply_parent_id=_parse_int(request.args.get("balas")))


@bp.route("/thread/<int:thread_id>/balas", methods=["POST"])
@login_required
def reply(thread_id):
    """Kirim balasan (UC-FR-04). Membuat notifikasi untuk penulis thread bila diizinkan."""
    db = get_db()
    row = _get_thread_or_404(db, thread_id, ", t.body AS body")
    if not _csrf_ok():
        return redirect(url_for("forum.thread", thread_id=thread_id))

    body, error = lg.validate_post(request.form.get("body"))
    raw_parent = (request.form.get("parent_post_id") or "").strip()
    parent_id = _parse_int(raw_parent) if raw_parent else None
    if raw_parent:
        parent = db.execute("SELECT id, thread_id FROM posts WHERE id = ?", (parent_id,)).fetchone() \
            if parent_id is not None else None
        # Induk harus balasan di thread YANG SAMA; kalau tidak, tolak (bukan diam-diam dijadikan tingkat atas).
        if parent is None or parent["thread_id"] != thread_id:
            error = error or "Balasan yang dituju tidak ditemukan. Muat ulang halaman lalu coba lagi."
            parent_id = None
    if error:
        return _render_thread(db, row, reply_error=error, reply_body=body, reply_parent_id=parent_id,
                              status=422, pop_new=False)

    try:
        now = now_iso()
        cur = db.execute(
            "INSERT INTO posts (thread_id, user_id, parent_post_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, g.user["id"], parent_id, body, now))
        post_id = cur.lastrowid
        db.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        if row["user_id"] != g.user["id"] and lg.notify_enabled(_get_setting(db, row["user_id"], lg.SETTING_NOTIFY)):
            notify(row["user_id"], f"{g.user['full_name']} membalas topik Anda", row["title"],
                   link=url_for("forum.thread", thread_id=thread_id) + f"#balasan-{post_id}",
                   module=MODULE_KEY, commit=False)
        log_activity(MODULE_KEY, "reply", _short(row["title"], 120), commit=False)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal menyimpan balasan thread_id=%s", thread_id)
        flash(MSG_CHANGE_FAILED, "error")
        return _render_thread(db, row, reply_error=MSG_CHANGE_FAILED, reply_body=body, reply_parent_id=parent_id,
                              status=500, pop_new=False)

    session[NEW_POST_KEY] = post_id
    flash("Balasan terkirim.", "success")
    return redirect(url_for("forum.thread", thread_id=thread_id) + f"#balasan-{post_id}")


# --------------------------------------------------------------------------
# Tandai solusi (UC-FR-05): hanya pemilik thread
# --------------------------------------------------------------------------
@bp.route("/thread/<int:thread_id>/solusi", methods=["POST"])
@login_required
def mark_solution(thread_id):
    db = get_db()
    row = _get_thread_or_404(db, thread_id)
    if row["user_id"] != g.user["id"]:
        abort(403)  # hanya pemilik thread; tombolnya juga tidak ditampilkan untuk orang lain
    if not _csrf_ok():
        return redirect(url_for("forum.thread", thread_id=thread_id))

    action = request.form.get("action", "mark")
    if action not in ("mark", "unmark"):
        abort(400)
    post_id = None
    try:
        if action == "unmark":
            db.execute("UPDATE threads SET is_solved = 0, accepted_post_id = NULL, updated_at = ? WHERE id = ?",
                       (now_iso(), thread_id))
            log_activity(MODULE_KEY, "unmark_solution", _short(row["title"], 120), commit=False)
            message = "Tanda solusi dibatalkan. Topik kembali berstatus belum terjawab."
        else:
            post_id = _parse_int(request.form.get("post_id"))
            post = db.execute("SELECT id FROM posts WHERE id = ? AND thread_id = ?", (post_id, thread_id)).fetchone() \
                if post_id is not None else None
            if post is None:
                flash("Balasan yang dipilih tidak ditemukan di topik ini.", "error")
                return redirect(url_for("forum.thread", thread_id=thread_id))
            db.execute("UPDATE threads SET is_solved = 1, accepted_post_id = ?, updated_at = ? WHERE id = ?",
                       (post_id, now_iso(), thread_id))
            log_activity(MODULE_KEY, "mark_solution", _short(row["title"], 120), commit=False)
            message = "Balasan ditandai sebagai solusi. Topik kini berlabel Terjawab."
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal mengubah status solusi thread_id=%s", thread_id)
        flash(MSG_CHANGE_FAILED, "error")
        return redirect(url_for("forum.thread", thread_id=thread_id))

    flash(message, "success")
    anchor = f"#balasan-{post_id}" if post_id else ""
    return redirect(url_for("forum.thread", thread_id=thread_id) + anchor)


# --------------------------------------------------------------------------
# Ubah dan hapus balasan: hanya penulis balasan
# --------------------------------------------------------------------------
@bp.route("/balasan/<int:post_id>/ubah", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    db = get_db()
    post = _owned_post_or_403(db, post_id)
    body, error = post["body"], None
    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for("forum.edit_post", post_id=post_id))
        body, error = lg.validate_post(request.form.get("body"))
        if error is None:
            try:
                db.execute("UPDATE posts SET body = ? WHERE id = ? AND user_id = ?", (body, post_id, g.user["id"]))
                log_activity(MODULE_KEY, "edit_reply", _short(post["thread_title"], 120), commit=False)
                db.commit()
            except sqlite3.Error:
                db.rollback()
                current_app.logger.exception("Gagal mengubah balasan id=%s", post_id)
                flash(MSG_CHANGE_FAILED, "error")
                return redirect(url_for("forum.edit_post", post_id=post_id))
            flash("Balasan diperbarui.", "success")
            return redirect(url_for("forum.thread", thread_id=post["thread_id"]) + f"#balasan-{post_id}")
    return render_template("forum/edit_post.html", page_title="Ubah Balasan", post=post, body=body,
                           error=error, limits=LIMITS), (422 if error else 200)


@bp.route("/balasan/<int:post_id>/hapus", methods=["GET", "POST"])
@login_required
def delete_post(post_id):
    db = get_db()
    post = _owned_post_or_403(db, post_id)
    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for("forum.delete_post", post_id=post_id))
        try:
            # Anak langsung dinaikkan ke induk balasan ini (atau jadi tingkat atas) agar jawaban orang lain tetap ada.
            db.execute("UPDATE posts SET parent_post_id = ? WHERE parent_post_id = ?", (post["parent_post_id"], post_id))
            if post["accepted_post_id"] == post_id:  # solusi dihapus -> thread kembali belum terjawab
                db.execute("UPDATE threads SET is_solved = 0, accepted_post_id = NULL WHERE id = ?", (post["thread_id"],))
            db.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, g.user["id"]))
            log_activity(MODULE_KEY, "delete_reply", _short(post["thread_title"], 120), commit=False)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Gagal menghapus balasan id=%s", post_id)
            flash(MSG_CHANGE_FAILED, "error")
            return redirect(url_for("forum.thread", thread_id=post["thread_id"]))
        flash("Balasan dihapus.", "success")
        return redirect(url_for("forum.thread", thread_id=post["thread_id"]))
    child_count = db.execute("SELECT COUNT(*) FROM posts WHERE parent_post_id = ?", (post_id,)).fetchone()[0]
    return render_template("forum/delete_post.html", page_title="Hapus Balasan", post=post,
                           child_count=child_count, excerpt=_short(post["body"], 200))


# --------------------------------------------------------------------------
# Thread Saya
# --------------------------------------------------------------------------
@bp.route("/saya")
@login_required
def my_threads():
    db = get_db()
    uid = g.user["id"]
    total = db.execute("SELECT COUNT(*) FROM threads WHERE user_id = ?", (uid,)).fetchone()[0]
    solved = db.execute("SELECT COUNT(*) FROM threads WHERE user_id = ? AND is_solved = 1", (uid,)).fetchone()[0]
    info = lg.paginate(total, lg.parse_page(request.args.get("halaman")), MY_PER_PAGE)
    rows = db.execute(
        _thread_select() + " WHERE t.user_id = ? ORDER BY datetime(t.created_at) DESC, t.id DESC LIMIT ? OFFSET ?",
        (uid, info["per_page"], info["offset"])).fetchall() if total else []
    return render_template(
        "forum/my_threads.html", page_title="Topik Saya", threads=[_thread_view(r) for r in rows],
        total=total, solved=solved, pager=_pager(info, "forum.my_threads"))


# --------------------------------------------------------------------------
# Pengaturan: privasi profil + notifikasi balasan
# --------------------------------------------------------------------------
@bp.route("/pengaturan", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    uid = g.user["id"]
    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for("forum.settings"))
        privacy = (request.form.get("profile_privacy") or "").strip().lower()
        notify_value = (request.form.get("notify_reply") or "").strip()
        if privacy not in lg.PRIVACY_CHOICES or notify_value not in ("1", "0"):
            flash("Pilihan tidak dikenali. Pilih salah satu opsi yang tersedia.", "error")
            return redirect(url_for("forum.settings"))
        try:
            _save_setting(db, uid, lg.SETTING_PRIVACY, privacy)
            _save_setting(db, uid, lg.SETTING_NOTIFY, notify_value)
            log_activity(MODULE_KEY, "forum_settings",
                         f"Privasi profil: {privacy}; notifikasi balasan: {'aktif' if notify_value == '1' else 'nonaktif'}",
                         commit=False)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Gagal menyimpan pengaturan Forum user_id=%s", uid)
            flash(MSG_SAVE_FAILED, "error")
            return redirect(url_for("forum.settings"))
        flash(msg_saved("Forum"), "success")
        return redirect(url_for("forum.settings"))

    return render_template(
        "forum/settings.html", page_title="Pengaturan Forum",
        privacy=lg.normalize_privacy(_get_setting(db, uid, lg.SETTING_PRIVACY)),
        notify_on=lg.notify_enabled(_get_setting(db, uid, lg.SETTING_NOTIFY)),
        privacy_choices=[(key, *lg.PRIVACY_LABELS[key]) for key in lg.PRIVACY_CHOICES])


# --------------------------------------------------------------------------
# Profil Forum seorang anggota (menghormati pengaturan privasi)
# --------------------------------------------------------------------------
@bp.route("/pengguna/<int:user_id>")
def profile(user_id):
    db = get_db()
    owner = db.execute(
        "SELECT id, full_name, bio, created_at FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    if owner is None:
        abort(404)
    viewer_id = g.user["id"] if g.get("user") is not None else None
    privacy = lg.normalize_privacy(_get_setting(db, user_id, lg.SETTING_PRIVACY))
    allowed = lg.can_view_profile(privacy, viewer_id, user_id)

    ctx = {"name": owner["full_name"], "initials": lg.initials(owner["full_name"]), "allowed": allowed,
           "privacy": privacy, "is_self": viewer_id == user_id, "viewer_is_guest": viewer_id is None}
    if allowed:  # data profil tidak diambil sama sekali bila tidak boleh dilihat
        ctx.update(
            bio=owner["bio"], joined=lg.format_date(owner["created_at"]),
            thread_count=db.execute("SELECT COUNT(*) FROM threads WHERE user_id = ?", (user_id,)).fetchone()[0],
            reply_count=db.execute("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user_id,)).fetchone()[0],
            solved_count=db.execute("SELECT COUNT(*) FROM threads WHERE user_id = ? AND is_solved = 1",
                                    (user_id,)).fetchone()[0],
            recent=[_thread_view(r) for r in db.execute(
                _thread_select() + " WHERE t.user_id = ? ORDER BY datetime(t.created_at) DESC, t.id DESC LIMIT 5",
                (user_id,)).fetchall()])
    return render_template("forum/profile.html", page_title=owner["full_name"], p=ctx)
