"""E-Learning: daftar kelas, detail, enroll gratis, Kelas Saya, Ruang Belajar, progres, pengaturan.

Use case (Blueprint 4.x): UC-EL-01 daftar kelas, UC-EL-02 enroll kelas gratis, UC-EL-03 materi
teks/video, UC-EL-04 tandai selesai + progres, UC-EL-05 mengerjakan kuis, UC-EL-06 hasil kuis +
pembahasan, UC-EL-07 kecepatan video dan target belajar.

Aturan penting:
  * progress_percent selalu DIHITUNG dari lesson_progress (tidak ada kolom persen yang disimpan).
  * Kursus hasil checkout masuk lewat tabel enrollments (source='order'), jadi otomatis tampil di
    Kelas Saya tanpa kode khusus di sini.
  * Ruang Belajar, API progres, dan kuis hanya untuk Member yang punya baris enrollments untuk kelas itu.
  * Kuis dinilai di server (quiz.grade). Halaman pengerjaan tidak pernah memuat kunci jawaban.
"""
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit

from flask import (abort, current_app, flash, g, jsonify, make_response, redirect, render_template,
                   request, session, url_for)

from ..db import get_db
from ..utils import CSRF_SESSION_KEY, csrf_valid, log_activity, login_required, notify, now_iso
from . import bp, quiz as quizlib

LEVELS = (("pemula", "Pemula"), ("menengah", "Menengah"), ("lanjut", "Lanjut"))
LEVEL_LABEL = dict(LEVELS)

# Pengaturan E-Learning disimpan di module_settings (module_key = 'elearning').
SPEED_CHOICES = ("0.5", "0.75", "1", "1.25", "1.5", "1.75", "2")
DEFAULT_SPEED = "1"
GOAL_MIN, GOAL_MAX, GOAL_STEP = 5, 480, 5
DEFAULT_GOAL = 30
SETTING_SPEED = "playback_speed"
SETTING_GOAL = "daily_goal_min"

# "Hari ini" untuk target belajar dihitung dalam WIB (UTC+7); stempel waktu disimpan dalam UTC.
LOCAL_OFFSET = "+7 hours"

MSG_CSRF = "Sesi formulir kedaluwarsa. Muat ulang halaman lalu coba lagi."


# --------------------------------------------------------------------------
# Pembantu data
# --------------------------------------------------------------------------
def progress_percent(done, total):
    """Persentase progres 0-100 dari jumlah materi selesai / total materi."""
    if not total:
        return 0
    return max(0, min(100, round(done * 100 / total)))


def format_rupiah(value):
    return f"Rp {int(value):,}".replace(",", ".")


def format_minutes(minutes):
    """75 -> '1 j 15 mnt', 40 -> '40 mnt'."""
    minutes = int(minutes or 0)
    if minutes < 60:
        return f"{minutes} mnt"
    hours, rest = divmod(minutes, 60)
    return f"{hours} j {rest} mnt" if rest else f"{hours} j"


def _course_query(extra_select="", extra_join="", order_by=""):
    """SELECT kursus terbit + jumlah materi, total menit, harga, dan slug produk (bila ada).

    Harga diambil dari products.course_id; kursus tanpa produk atau berharga 0 = gratis.
    Tanpa string dari pengguna: semua parameter fungsi ini konstanta dari kode.
    """
    return f"""
    SELECT c.*, cat.name AS category_name{extra_select},
           (SELECT COUNT(*) FROM lessons l WHERE l.course_id = c.id) AS lesson_count,
           (SELECT COALESCE(SUM(l.duration_min), 0) FROM lessons l WHERE l.course_id = c.id) AS total_minutes,
           (SELECT MIN(p.price) FROM products p WHERE p.course_id = c.id) AS price,
           (SELECT p.slug FROM products p WHERE p.course_id = c.id AND p.is_active = 1
             ORDER BY p.price ASC, p.id ASC LIMIT 1) AS product_slug
      FROM courses c
      LEFT JOIN categories cat ON cat.id = c.category_id{extra_join}
     WHERE c.is_published = 1 {{where}}
     {order_by}
    """


def _course_view(row):
    """Baris kursus -> dict dengan penanda gratis/berbayar. Tanpa produk = gratis."""
    course = dict(row)
    course["is_free"] = course["price"] is None or course["price"] <= 0
    course["level_label"] = LEVEL_LABEL.get(course["level"], course["level"].title())
    return course


def get_course(course_id):
    row = get_db().execute(_course_query().format(where="AND c.id = ?"), (course_id,)).fetchone()
    return _course_view(row) if row else None


def get_lessons(course_id):
    return get_db().execute(
        "SELECT id, order_no, title, content_type, content_body, video_url, duration_min "
        "FROM lessons WHERE course_id = ? ORDER BY order_no ASC, id ASC",
        (course_id,),
    ).fetchall()


def completed_lesson_ids(user_id, course_id):
    rows = get_db().execute(
        "SELECT lp.lesson_id FROM lesson_progress lp JOIN lessons l ON l.id = lp.lesson_id "
        "WHERE lp.user_id = ? AND l.course_id = ?",
        (user_id, course_id),
    ).fetchall()
    return {r["lesson_id"] for r in rows}


def get_enrollment(user_id, course_id):
    return get_db().execute(
        "SELECT * FROM enrollments WHERE user_id = ? AND course_id = ?", (user_id, course_id)
    ).fetchone()


def course_progress(user_id, course_ids):
    """{course_id: {done, total, percent}} dihitung dari lesson_progress."""
    ids = list(course_ids)
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    rows = get_db().execute(
        f"""
        SELECT l.course_id AS course_id,
               COUNT(*) AS total,
               SUM(CASE WHEN lp.id IS NOT NULL THEN 1 ELSE 0 END) AS done
          FROM lessons l
          LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id = ?
         WHERE l.course_id IN ({marks})
         GROUP BY l.course_id
        """,
        (user_id, *ids),
    ).fetchall()
    result = {cid: {"done": 0, "total": 0, "percent": 0} for cid in ids}
    for r in rows:
        done, total = r["done"] or 0, r["total"] or 0
        result[r["course_id"]] = {"done": done, "total": total, "percent": progress_percent(done, total)}
    return result


def resume_lesson(lessons, done_ids):
    """Materi untuk tombol Lanjutkan: yang belum selesai pertama; semua selesai -> materi pertama."""
    for lesson in lessons:
        if lesson["id"] not in done_ids:
            return lesson
    return lessons[0] if lessons else None


def minutes_studied_today(user_id):
    """Menit belajar hari ini (WIB) = total durasi materi yang ditandai selesai hari ini."""
    row = get_db().execute(
        "SELECT COALESCE(SUM(l.duration_min), 0) AS minutes "
        "FROM lesson_progress lp JOIN lessons l ON l.id = lp.lesson_id "
        "WHERE lp.user_id = ? AND date(lp.completed_at, ?) = date('now', ?)",
        (user_id, LOCAL_OFFSET, LOCAL_OFFSET),
    ).fetchone()
    return int(row["minutes"] or 0)


# --------------------------------------------------------------------------
# Pengaturan modul (kecepatan video, target belajar)
# --------------------------------------------------------------------------
def get_settings(user_id):
    rows = get_db().execute(
        "SELECT setting_key, setting_value FROM module_settings "
        "WHERE user_id = ? AND module_key = 'elearning' AND setting_key IN (?, ?)",
        (user_id, SETTING_SPEED, SETTING_GOAL),
    ).fetchall()
    stored = {r["setting_key"]: r["setting_value"] for r in rows}
    speed = stored.get(SETTING_SPEED)
    if speed not in SPEED_CHOICES:
        speed = DEFAULT_SPEED
    try:
        goal = int(stored.get(SETTING_GOAL) or DEFAULT_GOAL)
    except (TypeError, ValueError):
        goal = DEFAULT_GOAL
    if not GOAL_MIN <= goal <= GOAL_MAX:
        goal = DEFAULT_GOAL
    return {"speed": speed, "goal": goal}


def save_settings(user_id, speed, goal):
    db = get_db()
    db.executemany(
        "INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
        "VALUES (?, 'elearning', ?, ?) "
        "ON CONFLICT(user_id, module_key, setting_key) DO UPDATE SET setting_value = excluded.setting_value",
        ((user_id, SETTING_SPEED, speed), (user_id, SETTING_GOAL, str(goal))),
    )
    db.commit()


def speed_label(speed):
    return "Normal (1×)" if speed == "1" else f"{speed.replace('.', ',')}×"


# --------------------------------------------------------------------------
# Konten materi: teks -> blok, video -> embed aman
# --------------------------------------------------------------------------
def text_blocks(text):
    """Isi materi (teks biasa) -> [{'type': 'p'|'code', 'text': ...}].

    Paragraf dipisah baris kosong; baris yang menjorok 4 spasi/tab menjadi blok kode.
    Output tetap teks mentah: Jinja yang meng-escape, jadi aman dari XSS.
    """
    blocks, para, code = [], [], []

    def flush_para():
        if para:
            blocks.append({"type": "p", "text": " ".join(s.strip() for s in para)})
            para.clear()

    def flush_code():
        while code and not code[-1].strip():
            code.pop()
        if code:
            blocks.append({"type": "code", "text": "\n".join(code)})
        code.clear()

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        if raw.startswith(("    ", "\t")) and raw.strip():
            flush_para()
            code.append(raw[4:] if raw.startswith("    ") else raw[1:])
        elif not raw.strip():
            if code:
                code.append("")      # baris kosong di dalam kode, dibuang bila berada di ujung
            else:
                flush_para()
        else:
            flush_code()
            para.append(raw)
    flush_para()
    flush_code()
    return blocks


_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIMEO_ID = re.compile(r"^\d{6,12}$")
_FILE_EXT = (".mp4", ".webm", ".ogg")


def video_embed(url):
    """Tautan video -> {'kind', 'src'} untuk iframe/<video>, atau None bila tidak didukung.

    Hanya https dan hanya YouTube, Vimeo, atau berkas langsung (.mp4/.webm/.ogg).
    Tautan lain ditolak agar tidak ada iframe ke situs sembarang.
    """
    if not url:
        return None
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.hostname:
        return None
    host = parts.hostname.lower()
    segments = [s for s in parts.path.split("/") if s]

    video_id = None
    if host in ("youtu.be", "www.youtu.be") and segments:
        video_id = segments[0]
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"):
        if segments[:1] == ["watch"]:
            video_id = (parse_qs(parts.query).get("v") or [""])[0]
        elif segments[:1] in (["embed"], ["shorts"], ["live"]) and len(segments) > 1:
            video_id = segments[1]
    if video_id and _YT_ID.match(video_id):
        return {"kind": "youtube",
                "src": f"https://www.youtube-nocookie.com/embed/{video_id}?enablejsapi=1&rel=0&playsinline=1"}

    candidate = None
    if host in ("vimeo.com", "www.vimeo.com") and segments:
        candidate = segments[0]
    elif host == "player.vimeo.com" and segments[:1] == ["video"] and len(segments) > 1:
        candidate = segments[1]
    if candidate and _VIMEO_ID.match(candidate):
        return {"kind": "vimeo", "src": f"https://player.vimeo.com/video/{candidate}"}

    if parts.path.lower().endswith(_FILE_EXT):
        return {"kind": "file", "src": url.strip()}
    return None


# --------------------------------------------------------------------------
# Daftar kelas (UC-EL-01) dan detail kelas
# --------------------------------------------------------------------------
@bp.route("/")
def index():
    db = get_db()
    requested = (request.args.get("level") or "").strip().lower()
    level = requested if requested in LEVEL_LABEL else None
    unknown_level = bool(requested) and level is None

    rows = db.execute(
        _course_query(order_by="ORDER BY c.created_at DESC, c.id DESC").format(where="")
    ).fetchall()
    all_courses = [_course_view(r) for r in rows]
    counts = {key: 0 for key, _ in LEVELS}
    for c in all_courses:
        counts[c["level"]] = counts.get(c["level"], 0) + 1
    courses = [c for c in all_courses if level is None or c["level"] == level]

    progress, enrolled_ids = {}, set()
    if g.user is not None:
        progress = course_progress(g.user["id"], [c["id"] for c in courses])
        enrolled_ids = {
            r["course_id"] for r in db.execute(
                "SELECT course_id FROM enrollments WHERE user_id = ?", (g.user["id"],))
        }
    return render_template(
        "elearning/index.html",
        page_title="Daftar Kelas",
        courses=courses,
        levels=LEVELS,
        level=level,
        unknown_level=unknown_level,
        counts=counts,
        total_count=len(all_courses),
        progress=progress,
        enrolled_ids=enrolled_ids,
        format_rupiah=format_rupiah,
        format_minutes=format_minutes,
    )


@bp.route("/kelas/<int:course_id>")
def course_detail(course_id):
    course = get_course(course_id)
    if course is None:
        abort(404)
    lessons = get_lessons(course_id)
    enrolled, done_ids, progress, resume, quiz = False, set(), None, None, None
    if g.user is not None:
        enrolled = get_enrollment(g.user["id"], course_id) is not None
        if enrolled:
            done_ids = completed_lesson_ids(g.user["id"], course_id)
            progress = course_progress(g.user["id"], [course_id])[course_id]
            resume = resume_lesson(lessons, done_ids)
            quiz = quizlib.quiz_summary(get_db(), g.user["id"], course_id)
    return render_template(
        "elearning/course_detail.html",
        page_title=course["title"],
        course=course,
        lessons=lessons,
        enrolled=enrolled,
        done_ids=done_ids,
        progress=progress,
        resume=resume,
        quiz=quiz,
        format_rupiah=format_rupiah,
        format_minutes=format_minutes,
    )


# --------------------------------------------------------------------------
# Enroll kelas gratis (UC-EL-02)
# --------------------------------------------------------------------------
@bp.post("/kelas/<int:course_id>/daftar")
@login_required
def enroll(course_id):
    course = get_course(course_id)
    if course is None:
        abort(404)
    detail = url_for("elearning.course_detail", course_id=course_id)
    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(detail)

    user_id = g.user["id"]
    lessons = get_lessons(course_id)
    if get_enrollment(user_id, course_id) is not None:
        flash("Anda sudah terdaftar di kelas ini. Lanjutkan belajar!", "info")
        target = resume_lesson(lessons, completed_lesson_ids(user_id, course_id))
        return redirect(_lesson_url(course_id, target) if target else detail)

    if not course["is_free"]:
        flash("Kelas ini berbayar. Beli kelas lewat E-Commerce, lalu kelas otomatis muncul di Kelas Saya.", "warning")
        return redirect(detail)
    if not lessons:
        flash("Kelas ini belum memiliki materi, jadi belum bisa diikuti.", "warning")
        return redirect(detail)

    db = get_db()
    try:
        db.execute(
            "INSERT INTO enrollments (user_id, course_id, source, enrolled_at) VALUES (?, ?, 'free', ?)",
            (user_id, course_id, now_iso()),
        )
        log_activity("elearning", "enroll", f"Mendaftar kelas gratis: {course['slug']}", commit=False)
        notify(user_id, "Pendaftaran kelas berhasil",
               f"Anda terdaftar di {course['title']}. Selamat belajar!",
               link=url_for("elearning.my_courses"), module="elearning", commit=False)
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()  # permintaan ganda bersamaan: pendaftaran pertama sudah tersimpan
        flash("Anda sudah terdaftar di kelas ini. Lanjutkan belajar!", "info")
        return redirect(detail)
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal enroll user_id=%s course_id=%s", user_id, course_id)
        flash("Pendaftaran belum bisa disimpan. Coba lagi sebentar lagi.", "error")
        return redirect(detail)

    flash(f"Berhasil mengikuti kelas {course['title']}. Selamat belajar!", "success")
    return redirect(_lesson_url(course_id, lessons[0]))


def _lesson_url(course_id, lesson):
    return url_for("elearning.lesson", course_id=course_id, order_no=lesson["order_no"])


# --------------------------------------------------------------------------
# Kelas Saya
# --------------------------------------------------------------------------
@bp.route("/kelas-saya")
@login_required
def my_courses():
    db = get_db()
    user_id = g.user["id"]
    rows = db.execute(
        _course_query(
            extra_select=", e.source AS enroll_source, e.enrolled_at AS enrolled_at, e.completed_at AS completed_at",
            extra_join=" JOIN enrollments e ON e.course_id = c.id AND e.user_id = ?",
            order_by="""ORDER BY COALESCE(
                (SELECT MAX(datetime(lp.completed_at)) FROM lesson_progress lp
                   JOIN lessons l ON l.id = lp.lesson_id
                  WHERE lp.user_id = e.user_id AND l.course_id = c.id),
                datetime(e.enrolled_at)) DESC, e.id DESC""",
        ).format(where=""),
        (user_id,),
    ).fetchall()
    courses = [_course_view(r) for r in rows]
    progress = course_progress(user_id, [c["id"] for c in courses])

    resume_urls = {}
    for c in courses:
        lessons = get_lessons(c["id"])
        target = resume_lesson(lessons, completed_lesson_ids(user_id, c["id"]))
        resume_urls[c["id"]] = _lesson_url(c["id"], target) if target else None

    settings = get_settings(user_id)
    studied = minutes_studied_today(user_id)
    return render_template(
        "elearning/my_courses.html",
        page_title="Kelas Saya",
        courses=courses,
        progress=progress,
        resume_urls=resume_urls,
        goal=settings["goal"],
        studied=studied,
        goal_percent=progress_percent(studied, settings["goal"]),
        format_rupiah=format_rupiah,
        format_minutes=format_minutes,
    )


# --------------------------------------------------------------------------
# Ruang Belajar (UC-EL-03) dan tandai selesai (UC-EL-04)
# --------------------------------------------------------------------------
@bp.route("/kelas/<int:course_id>/materi/<int:order_no>")
@login_required
def lesson(course_id, order_no):
    course = get_course(course_id)
    if course is None:
        abort(404)
    user_id = g.user["id"]

    # Tolak akses bila belum terdaftar: kembali ke detail kelas dengan penjelasan.
    if get_enrollment(user_id, course_id) is None:
        flash("Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu untuk membuka ruang belajar.", "error")
        return redirect(url_for("elearning.course_detail", course_id=course_id))

    lessons = get_lessons(course_id)
    index_of = next((i for i, l in enumerate(lessons) if l["order_no"] == order_no), None)
    if index_of is None:
        abort(404)
    current = lessons[index_of]
    done_ids = completed_lesson_ids(user_id, course_id)
    progress = course_progress(user_id, [course_id])[course_id]

    embed = video_embed(current["video_url"]) if current["content_type"] == "video" else None
    return render_template(
        "elearning/lesson.html",
        page_title=current["title"],
        course=course,
        lessons=lessons,
        current=current,
        prev_lesson=lessons[index_of - 1] if index_of > 0 else None,
        next_lesson=lessons[index_of + 1] if index_of + 1 < len(lessons) else None,
        position=index_of + 1,
        done_ids=done_ids,
        progress=progress,
        blocks=text_blocks(current["content_body"]),
        embed=embed,
        el_settings=get_settings(user_id),
        quiz=quizlib.quiz_summary(get_db(), user_id, course_id),
        format_minutes=format_minutes,
        speed_label=speed_label,
    )


def _json_error(message, status):
    resp = jsonify(ok=False, error=message)
    resp.status_code = status
    return resp


@bp.post("/api/materi/<int:lesson_id>/selesai")
def api_lesson_complete(lesson_id):
    """Tandai (atau batalkan) materi selesai. Body JSON: {"completed": true|false}.

    Respons memuat hitungan terbaru sehingga halaman memperbarui progress bar tanpa reload.
    """
    if g.get("user") is None:
        return _json_error("Silakan masuk terlebih dahulu.", 401)
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return _json_error("Permintaan ditolak.", 403)
    if not request.is_json:
        return _json_error("Gunakan Content-Type application/json.", 415)
    expected = session.get(CSRF_SESSION_KEY)
    sent = request.headers.get("X-CSRF-Token", "")
    if not expected or sent != expected:
        return _json_error("Sesi kedaluwarsa. Muat ulang halaman lalu coba lagi.", 403)

    data = request.get_json(silent=True)
    completed = data.get("completed", True) if isinstance(data, dict) else None
    if not isinstance(completed, bool):
        return _json_error("Data tidak valid.", 400)

    db = get_db()
    user_id = g.user["id"]
    row = db.execute(
        "SELECT l.id, l.course_id, l.order_no, l.title FROM lessons l "
        "JOIN courses c ON c.id = l.course_id WHERE l.id = ? AND c.is_published = 1",
        (lesson_id,),
    ).fetchone()
    if row is None:
        return _json_error("Materi tidak ditemukan.", 404)
    if get_enrollment(user_id, row["course_id"]) is None:
        return _json_error("Anda belum terdaftar di kelas ini.", 403)

    try:
        if completed:
            cur = db.execute(
                "INSERT OR IGNORE INTO lesson_progress (user_id, lesson_id, completed_at) VALUES (?, ?, ?)",
                (user_id, lesson_id, now_iso()),
            )
            if cur.rowcount:
                log_activity("elearning", "lesson_complete",
                             f"Materi {row['order_no']} selesai: {row['title']}", commit=False)
        else:
            db.execute("DELETE FROM lesson_progress WHERE user_id = ? AND lesson_id = ?", (user_id, lesson_id))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal menyimpan progres user_id=%s lesson_id=%s", user_id, lesson_id)
        return _json_error("Progres belum bisa disimpan. Coba lagi sebentar lagi.", 503)

    stats = course_progress(user_id, [row["course_id"]])[row["course_id"]]
    resp = jsonify(
        ok=True,
        lesson_id=lesson_id,
        completed=completed,
        done=stats["done"],
        total=stats["total"],
        progress_percent=stats["percent"],
        course_completed=stats["total"] > 0 and stats["done"] >= stats["total"],
        studied_today=minutes_studied_today(user_id),
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------
# Kuis: kerjakan (UC-EL-05), kumpulkan + nilai di server, hasil dan pembahasan (UC-EL-06)
# --------------------------------------------------------------------------
def _quiz_storage_key(user_id, quiz_id):
    """Kunci penyimpanan jawaban sementara di browser; memuat id pengguna agar akun tidak saling timpa."""
    return f"dke:quiz:{user_id}:{quiz_id}"


def _quiz_context(course_id):
    """Prasyarat semua halaman kuis: (course, quiz, None) atau (None, None, respons_redirect).

    404 untuk kelas yang tidak ada; Member yang belum terdaftar dan kelas tanpa soal dialihkan ke
    detail kelas dengan penjelasan.
    """
    course = get_course(course_id)
    if course is None:
        abort(404)
    detail = redirect(url_for("elearning.course_detail", course_id=course_id))
    if get_enrollment(g.user["id"], course_id) is None:
        flash("Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu untuk mengerjakan kuis.", "error")
        return None, None, detail
    quiz = quizlib.get_quiz(get_db(), course_id)
    if quiz is None or not quizlib.get_public_questions(get_db(), quiz["id"]):
        flash("Kelas ini belum memiliki kuis.", "info")
        return None, None, detail
    return course, quiz, None


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/kelas/<int:course_id>/kuis")
@login_required
def quiz(course_id):
    course, quiz_row, denied = _quiz_context(course_id)
    if denied is not None:
        return denied
    # Hanya kolom soal dan opsi: tanpa correct_option dan explanation (lihat quizlib.get_public_questions).
    questions = [
        {"id": q["id"], "question": q["question"], "options": quizlib.question_options(q)}
        for q in quizlib.get_public_questions(get_db(), quiz_row["id"])
    ]
    return _no_store(make_response(render_template(
        "elearning/quiz.html",
        page_title=quiz_row["title"],
        course=course,
        quiz=quiz_row,
        questions=questions,
        storage_key=_quiz_storage_key(g.user["id"], quiz_row["id"]),
        summary=quizlib.quiz_summary(get_db(), g.user["id"], course_id),
    )))


@bp.post("/kelas/<int:course_id>/kuis/kumpul")
@login_required
def quiz_submit(course_id):
    """Terima jawaban, nilai di server, simpan percobaan, lalu redirect ke hasil (Post/Redirect/Get).

    Field yang dibaca hanya q_<id soal> = a|b|c|d. Field lain (mis. score, passed) diabaikan.
    """
    quiz_url = url_for("elearning.quiz", course_id=course_id)
    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(quiz_url)
    course, quiz_row, denied = _quiz_context(course_id)
    if denied is not None:
        return denied

    db = get_db()
    user_id = g.user["id"]
    questions = quizlib.get_full_questions(db, quiz_row["id"])
    answers = {q["id"]: request.form.get(f"q_{q['id']}", "") for q in questions}
    result = quizlib.grade(questions, answers, quiz_row["pass_score"])

    taken_at = now_iso()
    try:
        attempt_id = quizlib.save_attempt(db, user_id, quiz_row["id"], result, taken_at)
        detail = f"{quiz_row['title']}: skor {result['score']}"
        if result["passed"]:
            newly_completed = quizlib.complete_course(db, user_id, course_id, taken_at)
            log_activity("elearning", "quiz_passed", detail, commit=False)
            if newly_completed:
                notify(user_id, "Kelas selesai",
                       f"Anda lulus kuis dan menyelesaikan kelas {course['title']}.",
                       link=url_for("elearning.course_detail", course_id=course_id),
                       module="elearning", commit=False)
        else:
            log_activity("elearning", "quiz_failed", detail, commit=False)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Gagal menyimpan kuis user_id=%s course_id=%s", user_id, course_id)
        flash("Jawaban belum bisa disimpan. Coba kumpulkan lagi; jawaban Anda masih tersimpan di browser.", "error")
        return redirect(quiz_url)
    return redirect(url_for("elearning.quiz_result", course_id=course_id, attempt_id=attempt_id))


@bp.route("/kelas/<int:course_id>/kuis/hasil/<int:attempt_id>")
@login_required
def quiz_result(course_id, attempt_id):
    course, quiz_row, denied = _quiz_context(course_id)
    if denied is not None:
        return denied
    db = get_db()
    attempt = quizlib.get_attempt(db, g.user["id"], course_id, attempt_id)
    if attempt is None:  # tidak ada, atau milik pengguna lain: sama-sama 404
        abort(404)

    questions = quizlib.get_full_questions(db, attempt["quiz_id"])
    graded = quizlib.grade(questions, quizlib.answers_from_json(attempt["answers_json"]), attempt["pass_score"])
    by_id = {q["id"]: q for q in questions}
    review = []
    for number, item in enumerate(graded["results"], start=1):
        q = by_id[item["question_id"]]
        review.append({
            "number": number,
            "question": q["question"],
            "options": quizlib.question_options(q),
            "chosen": item["chosen"],
            "correct_option": item["correct_option"],
            "is_correct": item["is_correct"],
            "answered": item["answered"],
            "explanation": q["explanation"],
        })
    return _no_store(make_response(render_template(
        "elearning/quiz_result.html",
        page_title=f"Hasil {attempt['quiz_title']}",
        course=course,
        attempt=attempt,
        passed=bool(attempt["passed"]),
        correct=graded["correct"],
        total=graded["total"],
        review=review,
        storage_key=_quiz_storage_key(g.user["id"], attempt["quiz_id"]),
        taken_at=attempt["taken_at"],
    )))


# --------------------------------------------------------------------------
# Pengaturan: kecepatan video dan target belajar (UC-EL-07)
# --------------------------------------------------------------------------
@bp.route("/pengaturan", methods=["GET", "POST"])
@login_required
def settings():
    user_id = g.user["id"]
    values = get_settings(user_id)
    errors = {}
    if request.method == "POST":
        if not csrf_valid():
            flash(MSG_CSRF, "error")
            return redirect(url_for("elearning.settings"))
        speed = request.form.get("playback_speed", "").strip()
        goal_raw = request.form.get("daily_goal_min", "").strip()
        if speed not in SPEED_CHOICES:
            errors["playback_speed"] = "Pilih salah satu kecepatan yang tersedia."
        goal = None
        if not goal_raw.isdigit():
            errors["daily_goal_min"] = f"Isi target dengan angka bulat, {GOAL_MIN}–{GOAL_MAX} menit."
        else:
            goal = int(goal_raw)
            if not GOAL_MIN <= goal <= GOAL_MAX:
                errors["daily_goal_min"] = f"Target belajar harus antara {GOAL_MIN} dan {GOAL_MAX} menit per hari."
        if errors:
            return render_template(
                "elearning/settings.html", page_title="Pengaturan E-Learning",
                values={"speed": speed, "goal": goal_raw}, errors=errors,
                speeds=SPEED_CHOICES, speed_label=speed_label,
                goal_min=GOAL_MIN, goal_max=GOAL_MAX, goal_step=GOAL_STEP,
            ), 400
        try:
            save_settings(user_id, speed, goal)
        except sqlite3.Error:
            get_db().rollback()
            current_app.logger.exception("Gagal menyimpan pengaturan E-Learning user_id=%s", user_id)
            flash("Pengaturan belum bisa disimpan. Coba lagi sebentar lagi.", "error")
            return redirect(url_for("elearning.settings"))
        flash("Pengaturan E-Learning berhasil disimpan.", "success")
        return redirect(url_for("elearning.settings"))

    return render_template(
        "elearning/settings.html", page_title="Pengaturan E-Learning",
        values=values, errors=errors, speeds=SPEED_CHOICES, speed_label=speed_label,
        goal_min=GOAL_MIN, goal_max=GOAL_MAX, goal_step=GOAL_STEP,
    )
