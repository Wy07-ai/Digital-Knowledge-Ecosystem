"""Admin minimal (UC-AD-01 kelola konten, UC-AD-02 moderasi; prioritas C, Blueprint 6.5).

Satu halaman: GET /infosys/admin?tab=thread|balasan|akun&halaman=N

  * Thread  : daftar + hapus (halaman konfirmasi, lalu POST ber-CSRF). Balasan thread ikut terhapus (ON DELETE CASCADE).
  * Balasan : daftar + hapus. Anak balasan dinaikkan ke induk balasan itu; bila yang dihapus adalah solusi,
              thread kembali berstatus belum terjawab (aturan sama dengan hapus balasan oleh penulisnya).
  * Akun    : nonaktifkan / aktifkan (users.is_active). Akun nonaktif tidak bisa login dan sesi yang sedang
              berjalan langsung tidak berlaku (lihat load_user_and_settings di app/__init__.py).

Aturan:
  * Semua rute memakai @admin_required: Guest -> login, Member biasa -> 403. Pemeriksaan di server.
  * Setiap POST memeriksa CSRF; SQL memakai parameter (?); satu aksi = satu transaksi.
  * Setiap aksi dicatat di activity_logs (user_id = admin yang bertindak, module_key = 'infosys',
    action = admin_delete_thread | admin_delete_reply | admin_deactivate_user | admin_activate_user).
  * Admin tidak bisa menonaktifkan dirinya sendiri maupun admin lain (tidak ada jalur kunci-keluar).
  * Forum tetap menolak admin mengubah/menghapus balasan orang lain; moderasi hanya lewat halaman ini,
    supaya setiap tindakan moderasi pasti tercatat.
"""
import sqlite3

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from ..db import get_db
from ..messages import MSG_CHANGE_FAILED
from ..utils import MSG_CSRF, admin_required, csrf_valid, log_activity
from . import bp, panel
from .routes import MODULE, _pagination_ctx

ADMIN_PER_PAGE = 10
TABS = (("thread", "Topik"), ("balasan", "Balasan"), ("akun", "Akun"))


def _short(text, limit=80):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _csrf_ok():
    if csrf_valid():
        return True
    flash(MSG_CSRF, "error")
    return False


def _admin_url(tab="thread"):
    return url_for("infosys.admin", tab=tab if tab != "thread" else None)


def _confirm(*, title, lead, subject, notes, action_url, confirm_label, cancel_url, danger=True):
    return render_template(
        "infosys/admin_confirm.html", tab="admin", page_title=title, title=title, lead=lead,
        subject=subject, notes=notes, action_url=action_url, confirm_label=confirm_label,
        cancel_url=cancel_url, danger=danger)


# --------------------------------------------------------------------------
# Daftar (UC-AD-01)
# --------------------------------------------------------------------------
_QUERIES = {
    "thread": (
        "SELECT COUNT(*) FROM threads",
        "SELECT t.id, t.title, t.created_at, u.full_name AS author_name, c.name AS category_name, "
        "(SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id) AS reply_count "
        "FROM threads t JOIN users u ON u.id = t.user_id LEFT JOIN categories c ON c.id = t.category_id "
        "ORDER BY datetime(t.created_at) DESC, t.id DESC LIMIT ? OFFSET ?"),
    "balasan": (
        "SELECT COUNT(*) FROM posts",
        "SELECT p.id, p.body, p.created_at, p.thread_id, t.title AS thread_title, u.full_name AS author_name "
        "FROM posts p JOIN threads t ON t.id = p.thread_id JOIN users u ON u.id = p.user_id "
        "ORDER BY datetime(p.created_at) DESC, p.id DESC LIMIT ? OFFSET ?"),
    "akun": (
        "SELECT COUNT(*) FROM users",
        "SELECT id, full_name, email, role, is_active, created_at, last_login_at FROM users "
        "ORDER BY id LIMIT ? OFFSET ?"),
}


@bp.route("/admin")
@admin_required
def admin():
    tab = (request.args.get("tab") or "thread").strip().lower()
    if tab not in _QUERIES:
        tab = "thread"
    db = get_db()
    count_sql, list_sql = _QUERIES[tab]
    total = db.execute(count_sql).fetchone()[0]
    info = panel.paginate(total, panel.parse_page(request.args.get("halaman")), ADMIN_PER_PAGE)
    rows = [dict(r) for r in db.execute(list_sql, (info["per_page"], info["offset"])).fetchall()] if total else []
    for r in rows:
        if "body" in r:
            r["excerpt"] = _short(r["body"], 100)
    return render_template(
        "infosys/admin.html", tab="admin", page_title="Admin", admin_tab=tab, admin_tabs=TABS, rows=rows,
        pager=_pagination_ctx("infosys.admin", info, tab=tab if tab != "thread" else None),
        noun={"thread": "topik", "balasan": "balasan", "akun": "akun"}[tab])


# --------------------------------------------------------------------------
# Hapus thread (UC-AD-02)
# --------------------------------------------------------------------------
def _thread_or_404(db, thread_id):
    row = db.execute(
        "SELECT t.id, t.title, u.full_name AS author_name, "
        "(SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id) AS reply_count "
        "FROM threads t JOIN users u ON u.id = t.user_id WHERE t.id = ?", (thread_id,)).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/admin/thread/<int:thread_id>/hapus", methods=["GET", "POST"])
@admin_required
def admin_delete_thread(thread_id):
    db = get_db()
    thread = _thread_or_404(db, thread_id)
    back = _admin_url("thread")
    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for("infosys.admin_delete_thread", thread_id=thread_id))
        try:
            db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))  # posts ikut terhapus (CASCADE)
            log_activity(MODULE, "admin_delete_thread",
                         f"Topik #{thread_id} \"{_short(thread['title'], 100)}\" oleh {thread['author_name']} "
                         f"({thread['reply_count']} balasan ikut terhapus)", commit=False)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Admin gagal menghapus thread id=%s", thread_id)
            flash(MSG_CHANGE_FAILED, "error")
            return redirect(back)
        flash("Topik dihapus.", "success")
        return redirect(back)
    notes = ["Topik yang dihapus tidak bisa dikembalikan."]
    if thread["reply_count"]:
        notes.append(f"{thread['reply_count']} balasan di topik ini ikut terhapus.")
    return _confirm(
        title="Hapus topik ini?", lead="Topik oleh " + thread["author_name"] + ":", subject=thread["title"],
        notes=notes, action_url=url_for("infosys.admin_delete_thread", thread_id=thread_id),
        confirm_label="Ya, hapus topik", cancel_url=back)


# --------------------------------------------------------------------------
# Hapus balasan (UC-AD-02)
# --------------------------------------------------------------------------
def _post_or_404(db, post_id):
    row = db.execute(
        "SELECT p.id, p.thread_id, p.parent_post_id, p.body, t.title AS thread_title, t.accepted_post_id, "
        "u.full_name AS author_name FROM posts p JOIN threads t ON t.id = p.thread_id "
        "JOIN users u ON u.id = p.user_id WHERE p.id = ?", (post_id,)).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/admin/balasan/<int:post_id>/hapus", methods=["GET", "POST"])
@admin_required
def admin_delete_post(post_id):
    db = get_db()
    post = _post_or_404(db, post_id)
    back = _admin_url("balasan")
    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for("infosys.admin_delete_post", post_id=post_id))
        try:
            # Anak langsung dinaikkan ke induk balasan ini agar jawaban orang lain tetap ada.
            db.execute("UPDATE posts SET parent_post_id = ? WHERE parent_post_id = ?", (post["parent_post_id"], post_id))
            if post["accepted_post_id"] == post_id:  # solusi dihapus -> thread kembali belum terjawab
                db.execute("UPDATE threads SET is_solved = 0, accepted_post_id = NULL WHERE id = ?", (post["thread_id"],))
            db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            log_activity(MODULE, "admin_delete_reply",
                         f"Balasan #{post_id} oleh {post['author_name']} di topik #{post['thread_id']} "
                         f"\"{_short(post['thread_title'], 100)}\"", commit=False)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Admin gagal menghapus balasan id=%s", post_id)
            flash(MSG_CHANGE_FAILED, "error")
            return redirect(back)
        flash("Balasan dihapus.", "success")
        return redirect(back)
    child_count = db.execute("SELECT COUNT(*) FROM posts WHERE parent_post_id = ?", (post_id,)).fetchone()[0]
    notes = ["Balasan yang dihapus tidak bisa dikembalikan."]
    if child_count:
        notes.append(f"{child_count} balasan lain yang menanggapinya tetap ada dan naik satu tingkat.")
    if post["accepted_post_id"] == post_id:
        notes.append("Balasan ini ditandai sebagai solusi, jadi topik kembali berstatus belum terjawab.")
    return _confirm(
        title="Hapus balasan ini?", lead=f"Balasan oleh {post['author_name']} di topik \"{_short(post['thread_title'], 80)}\":",
        subject=_short(post["body"], 200), notes=notes,
        action_url=url_for("infosys.admin_delete_post", post_id=post_id),
        confirm_label="Ya, hapus balasan", cancel_url=back)


# --------------------------------------------------------------------------
# Nonaktifkan / aktifkan akun (UC-AD-02)
# --------------------------------------------------------------------------
def _set_user_status(user_id, make_active):
    db = get_db()
    user = db.execute("SELECT id, full_name, email, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)
    back = _admin_url("akun")
    endpoint = "infosys.admin_activate_user" if make_active else "infosys.admin_deactivate_user"
    verb = "aktifkan" if make_active else "nonaktifkan"

    # Penjaga: tak ada jalur kunci-keluar. Dicek di GET maupun POST.
    if not make_active and user["id"] == g.user["id"]:
        flash("Anda tidak bisa menonaktifkan akun Anda sendiri.", "error")
        return redirect(back)
    if not make_active and user["role"] == "admin":
        flash("Akun admin tidak bisa dinonaktifkan lewat halaman ini.", "error")
        return redirect(back)
    if bool(user["is_active"]) == make_active:
        flash(f"Akun {user['full_name']} sudah {'aktif' if make_active else 'nonaktif'}.", "info")
        return redirect(back)

    if request.method == "POST":
        if not _csrf_ok():
            return redirect(url_for(endpoint, user_id=user_id))
        try:
            db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if make_active else 0, user_id))
            log_activity(MODULE, "admin_activate_user" if make_active else "admin_deactivate_user",
                         f"Akun #{user_id} {user['full_name']} ({user['email']})", commit=False)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Admin gagal mengubah status akun id=%s", user_id)
            flash(MSG_CHANGE_FAILED, "error")
            return redirect(back)
        flash(f"Akun {user['full_name']} di{verb}.", "success")
        return redirect(back)

    if make_active:
        notes = ["Pengguna bisa masuk lagi dengan kata sandinya."]
    else:
        notes = ["Pengguna tidak bisa masuk, dan sesi yang sedang berjalan langsung berakhir.",
                 "Topik dan balasannya tetap ada. Akun bisa diaktifkan kembali kapan saja."]
    return _confirm(
        title=f"{verb.capitalize()} akun ini?", lead="Akun:", subject=f"{user['full_name']} ({user['email']})",
        notes=notes, action_url=url_for(endpoint, user_id=user_id),
        confirm_label=f"Ya, {verb} akun", cancel_url=back, danger=not make_active)


@bp.route("/admin/akun/<int:user_id>/nonaktifkan", methods=["GET", "POST"])
@admin_required
def admin_deactivate_user(user_id):
    return _set_user_status(user_id, make_active=False)


@bp.route("/admin/akun/<int:user_id>/aktifkan", methods=["GET", "POST"])
@admin_required
def admin_activate_user(user_id):
    return _set_user_status(user_id, make_active=True)
