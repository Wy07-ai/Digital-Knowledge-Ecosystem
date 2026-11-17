from flask import abort, current_app, flash, g, redirect, render_template, request, session, url_for

from .. import LANDED_KEY, MODULES
from ..db import get_db
from ..search import KIND_BY_KEY, KINDS, MIN_QUERY_CHARS, normalize_query, search_all
from . import bp
from .launcher import HERO_INTERVAL_MS, build_widgets, hero_slides, resume_target


@bp.route("/")
def index():
    resume = resume_target()

    # Smart Landing: landing_mode = last_module membawa Member langsung ke halaman terakhirnya,
    # tetapi HANYA pada kedatangan pertama di sesi ini. Tanpa batas ini, tombol DKE (Beranda) di
    # Top-Bar akan memantul kembali ke modul dan Member tidak pernah bisa melihat Beranda.
    # Penanda sesi (LANDED_KEY) dipasang oleh hook before_request pada halaman mana pun, dan
    # dihapus saat login/logout karena session.clear().
    if (
        resume is not None
        and g.settings.get("landing_mode") == "last_module"
        and not session.get(LANDED_KEY)
    ):
        session[LANDED_KEY] = True
        flash(
            "Melanjutkan: " + " › ".join(resume["labels"]) + ". Pilih DKE di bilah atas untuk kembali ke Beranda.",
            "info",
        )
        return redirect(resume["url"])

    if g.get("user") is not None:
        session[LANDED_KEY] = True

    user = g.get("user")
    return render_template(
        "main/index.html",
        page_title="Beranda",
        widgets=build_widgets(),
        hero_slides=hero_slides(),
        hero_interval=HERO_INTERVAL_MS,
        resume=resume,
        first_name=user["full_name"].split()[0] if user else None,
    )


# --------------------------------------------------------------------------
# Pencarian terpadu: GET /cari?q=&jenis= (logika kueri ada di app/search.py)
# --------------------------------------------------------------------------
@bp.route("/cari")
def search():
    q = normalize_query(request.args.get("q"))
    requested = (request.args.get("jenis") or "").strip().lower()
    kind = requested if requested in KIND_BY_KEY else None
    unknown_kind = bool(requested) and kind is None

    state, groups, total = "kosong", [], 0
    if q:
        state = "hasil" if len(q) >= MIN_QUERY_CHARS else "pendek"
    if state == "hasil":
        groups = search_all(get_db(), q, kind)
        total = sum(group["total"] for group in groups)
        if total == 0:
            state = "nihil"

    return render_template(
        "main/search.html",
        page_title="Pencarian",
        q=q,
        kind=kind,
        kind_label=KIND_BY_KEY[kind]["label"] if kind else None,
        unknown_kind=unknown_kind,
        kinds=KINDS,
        state=state,
        groups=groups,
        total=total,
        search_query=q,                    # mengisi kolom pencarian di bilah atas
        search_autofocus=(state == "kosong"),
    )


# --------------------------------------------------------------------------
# Halaman uji komponen (hanya bila config UI_TEST_PAGE aktif; env DKE_UI_TEST=0 mematikannya)
# --------------------------------------------------------------------------
def _require_test_page():
    if not current_app.config.get("UI_TEST_PAGE"):
        abort(404)


@bp.route("/dev/ui-test")
def ui_test():
    _require_test_page()
    return render_template("main/ui_test.html", page_title="Uji Komponen", modules=MODULES)


@bp.route("/dev/ui-test/flash")
def ui_test_flash():
    """Memicu flash() Flask dari sisi server, lalu kembali ke halaman uji (pola PRG)."""
    _require_test_page()
    flash(MSG_ADDED_TO_CART, "success")
    flash(MSG_LOGIN_FAILED, "error")
    flash(MSG_PROGRESS_AUTOSAVED, "info")
    flash(MSG_SLOW_CONNECTION, "warning")
    flash("Pesan tanpa kategori (bawaan Flask) tampil sebagai toast info.")
    return redirect(url_for("main.ui_test"))


# --------------------------------------------------------------------------
# Contoh halaman bersarang untuk breadcrumb dan tombol Kembali (hierarki ada di app/navigation.py)
#   E-Learning > <judul kelas> > Materi N        (kelas dan materi dibaca dari database bila ada)
# --------------------------------------------------------------------------
@bp.route("/dev/ui-test/navigasi/kelas/<int:course_id>")
def nav_demo_course(course_id):
    _require_test_page()
    return render_template("main/nav_demo.html", page_title="Contoh Navigasi", course_id=course_id, order_no=None)


@bp.route("/dev/ui-test/navigasi/kelas/<int:course_id>/materi/<int:order_no>")
def nav_demo_lesson(course_id, order_no):
    _require_test_page()
    return render_template("main/nav_demo.html", page_title="Contoh Navigasi", course_id=course_id, order_no=order_no)
