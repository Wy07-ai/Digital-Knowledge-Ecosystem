from flask import abort, current_app, flash, g, redirect, render_template, session, url_for

from .. import LANDED_KEY, MODULES
from . import bp
from .launcher import build_widgets, resume_target


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
            "Melanjutkan: " + " › ".join(resume["labels"]) + ". Pilih DKE di Top-Bar untuk kembali ke Beranda.",
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
        resume=resume,
        first_name=user["full_name"].split()[0] if user else None,
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
    flash("Produk ditambahkan ke keranjang.", "success")
    flash("Email atau kata sandi salah. Periksa kembali dan coba lagi.", "error")
    flash("Progres belajar tersimpan otomatis.", "info")
    flash("Koneksi lambat. Perubahan akan disimpan saat tersambung kembali.", "warning")
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
