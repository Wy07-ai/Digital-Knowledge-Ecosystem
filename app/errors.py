"""Halaman dan respons galat DKE (Blueprint 5.5): 403, 404, 405, dan 500.

  * Permintaan HTML  -> halaman `main/error.html` (mewarisi base.html: Top-Bar, tema, Dark Mode, Mobile View)
                        dengan teks Bahasa Indonesia dan tombol "Kembali ke Beranda".
  * Permintaan API   -> JSON {"ok": false, "error": "...", "status": <kode>} (bentuk sama dengan
                        respons galat endpoint JSON lain). API = jalur /api/... atau /<modul>/api/...
  * 503              -> "Server sedang sibuk, coba lagi" (database terkunci); sesi login tidak disentuh.
  * 500              -> pesan umum saja. Detail galat TIDAK PERNAH dikirim ke pengguna; jejaknya
                        tetap dicatat di log server oleh Flask.

Kode galat lain (mis. 400) tetap memakai respons bawaan Flask untuk halaman HTML; khusus permintaan
API semuanya dijadikan JSON agar klien JavaScript tidak menerima HTML.
"""
from flask import current_app, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

# kode -> (judul, pesan). Teks ramah, tanpa istilah teknis.
ERROR_TEXT = {
    403: ("Akses ditolak",
          "Akun Anda tidak punya izin membuka halaman ini. Kembali ke Beranda untuk melanjutkan."),
    404: ("Halaman tidak ditemukan",
          "Alamat ini tidak tersedia atau halamannya sudah dipindahkan. Kembali ke Beranda untuk mencari lagi."),
    405: ("Halaman tidak bisa dibuka dengan cara ini",
          "Kembali ke halaman sebelumnya, lalu gunakan tombol atau tautan yang tersedia."),
    500: ("Ada gangguan di sisi kami",
          "Ini bukan salah Anda. Coba lagi sebentar lagi."),
    503: ("Server sedang sibuk, coba lagi",
          "Data sedang dipakai proses lain. Anda tidak keluar dari akun. Muat ulang halaman beberapa saat lagi."),
}
API_TEXT = {
    403: "Akun Anda tidak punya izin untuk tindakan ini.",
    404: "Data yang diminta tidak ditemukan.",
    405: "Tindakan ini tidak tersedia untuk alamat tersebut.",
    500: "Ada gangguan di sisi kami. Coba lagi sebentar lagi.",
    503: "Server sedang sibuk, coba lagi.",
}
GENERIC_TITLE = "Permintaan belum bisa diproses"
GENERIC_MESSAGE = "Muat ulang halaman lalu coba lagi."

# Cadangan bila template gagal dirender (mis. database rusak sehingga Top-Bar ikut galat).
# Berdiri sendiri: tanpa template, database, maupun skrip.
_FALLBACK_HTML = """<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><title>{title} · DKE</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:15vh auto;padding:0 1rem;text-align:center;line-height:1.5}}
a{{display:inline-block;margin-top:1rem;padding:.6rem 1.2rem;border-radius:.5rem;background:#1d4ed8;color:#fff;text-decoration:none;font-weight:600}}</style>
</head><body><h1>{title}</h1><p>{message}</p><a href="/">Kembali ke Beranda</a></body></html>
"""


def is_api_request():
    """True untuk /api/... dan /<modul>/api/... (mis. /elearning/api/materi/3/selesai)."""
    from . import MODULE_BY_KEY  # impor tertunda: app/__init__.py mengimpor modul ini

    parts = [p for p in request.path.split("/") if p][:2]
    return bool(parts) and (parts[0] == "api" or (len(parts) == 2 and parts[0] in MODULE_BY_KEY and parts[1] == "api"))


def _status_of(error):
    code = getattr(error, "code", None)
    return code if isinstance(code, int) else 500


def _extra_headers(error):
    """Header bawaan galat HTTP yang bermakna (mis. Allow pada 405); Content-* dibuat ulang oleh Flask."""
    get_headers = getattr(error, "get_headers", None)
    if get_headers is None:
        return []
    return [(k, v) for k, v in get_headers() if k.lower() not in ("content-type", "content-length")]


def _json_response(status, error):
    resp = jsonify(ok=False, error=API_TEXT.get(status) or GENERIC_MESSAGE, status=status)
    resp.status_code = status
    for key, value in _extra_headers(error):
        resp.headers[key] = value
    resp.headers["Cache-Control"] = "no-store"
    if status == 503:
        resp.headers["Retry-After"] = "2"
    return resp


def _html_response(status, error):
    title, message = ERROR_TEXT.get(status, (GENERIC_TITLE, GENERIC_MESSAGE))
    try:
        body = render_template("main/error.html", page_title=title, error_status=status,
                               error_title=title, error_message=message)
    except Exception:  # noqa: BLE001 - halaman galat tidak boleh ikut galat
        current_app.logger.warning("Template galat gagal dirender; memakai halaman cadangan", exc_info=True)
        body = _FALLBACK_HTML.format(title=title, message=message)
    headers = _extra_headers(error)
    if status == 503:
        headers.append(("Retry-After", "2"))
    return body, status, headers


def handle_error(error):
    """Handler 403/404/405/500: JSON untuk /api/*, halaman HTML untuk selainnya."""
    status = _status_of(error)
    if is_api_request():
        return _json_response(status, error)
    return _html_response(status, error)


def handle_other_http_error(error):
    """Kode HTTP lain: hanya permintaan API yang diubah menjadi JSON; selebihnya respons bawaan."""
    if not isinstance(error, HTTPException) or (error.code or 0) < 400 or not is_api_request():
        return error
    return _json_response(_status_of(error), error)


def register_error_handlers(app):
    for status in ERROR_TEXT:
        app.register_error_handler(status, handle_error)
    app.register_error_handler(HTTPException, handle_other_http_error)
