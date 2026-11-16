"""Pengerasan keamanan HTTP: cookie sesi, ProxyFix opsional, dan header respons.

Semua pengaturan dibaca dari variabel lingkungan saat `create_app()` dipanggil, lalu disimpan di
`app.config` sehingga tes dapat menimpanya lewat `test_config`:

    DKE_HTTPS=1          cookie sesi memakai atribut Secure (hanya kirim lewat HTTPS)
    DKE_BEHIND_PROXY=1   percayai X-Forwarded-For/-Proto dari reverse proxy (ProxyFix)
    DKE_PROXY_HOPS=1     jumlah proxy tepercaya di depan aplikasi (bawaan 1)
"""
import secrets

from flask import g
from werkzeug.middleware.proxy_fix import ProxyFix

TRUE_VALUES = {"1", "true", "yes", "on"}

# Sumber eksternal yang benar-benar dipakai aplikasi (lihat base.html, elearning.js, routes E-Learning):
#   Tailwind Play CDN (skrip), Google Fonts (stylesheet + berkas font), embed video YouTube/Vimeo (iframe).
TAILWIND_CDN = "https://cdn.tailwindcss.com"
GOOGLE_FONTS_CSS = "https://fonts.googleapis.com"
GOOGLE_FONTS_FILES = "https://fonts.gstatic.com"
VIDEO_FRAME_HOSTS = ("https://www.youtube-nocookie.com", "https://player.vimeo.com")


def env_flag(environ, name, default=False):
    """True bila variabel lingkungan `name` bernilai 1/true/yes/on (tanpa membedakan huruf besar)."""
    value = environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in TRUE_VALUES


def env_int(environ, name, default):
    try:
        return max(1, int(environ.get(name, "").strip()))
    except ValueError:
        return default


def default_security_config(environ):
    """Konfigurasi bawaan dari lingkungan (dipakai create_app sebelum test_config menimpanya)."""
    https = env_flag(environ, "DKE_HTTPS")
    return {
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        # Tidak dipaksa: di http://127.0.0.1 cookie Secure tidak akan terkirim dan login mustahil.
        "SESSION_COOKIE_SECURE": https,
        "PREFERRED_URL_SCHEME": "https" if https else "http",
        "BEHIND_PROXY": env_flag(environ, "DKE_BEHIND_PROXY"),
        "PROXY_HOPS": env_int(environ, "DKE_PROXY_HOPS", 1),
    }


def csp_nonce():
    """Nonce CSP untuk permintaan ini (dibuat sekali, lazy). Dipakai di <script nonce="...">."""
    nonce = g.get("csp_nonce")
    if nonce is None:
        nonce = g.csp_nonce = secrets.token_urlsafe(16)
    return nonce


def build_csp(nonce):
    """Susun nilai header Content-Security-Policy.

    - script-src : hanya berkas sendiri, Tailwind CDN, dan skrip inline ber-nonce (tema anti-kedip,
                   tailwind.config). Tanpa 'unsafe-inline' dan tanpa 'unsafe-eval'.
    - style-src  : 'unsafe-inline' tetap perlu karena Tailwind Play CDN menyisipkan <style> saat runtime
                   dan templat memakai atribut style="width: N%". Turunkan setelah Tailwind dibuat statis.
    - img-src    : gambar produk/avatar/sampul dapat berasal dari URL https mana pun (tersimpan di database).
    """
    frames = " ".join(VIDEO_FRAME_HOSTS)
    directives = [
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}' {TAILWIND_CDN}",
        f"style-src 'self' 'unsafe-inline' {GOOGLE_FONTS_CSS}",
        f"font-src 'self' {GOOGLE_FONTS_FILES}",
        "img-src 'self' data: https:",
        "media-src 'self' https:",
        f"frame-src {frames}",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(directives)


def init_security(app):
    """Pasang ProxyFix (opsional) dan hook header keamanan. Panggil setelah config final."""
    if app.config.get("BEHIND_PROXY"):
        hops = int(app.config.get("PROXY_HOPS", 1))
        # Hanya X-Forwarded-For dan -Proto; Host/Prefix sengaja tidak dipercaya.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_prefix=0)

    @app.after_request
    def set_security_headers(response):
        """Header keamanan untuk semua respons (halaman HTML, API JSON, berkas statis, galat)."""
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Content-Security-Policy", build_csp(csp_nonce()))
        return response

    app.jinja_env.globals["csp_nonce"] = csp_nonce
