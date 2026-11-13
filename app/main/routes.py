from flask import abort, current_app, flash, redirect, render_template, url_for

from .. import MODULES
from . import bp


@bp.route("/")
def index():
    return render_template("main/index.html", page_title="Beranda")


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
