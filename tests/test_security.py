"""Tes cookie sesi dan header keamanan HTTP (CSP, X-Frame-Options, dll.), serta ProxyFix opsional.

Jalankan:  python -m unittest tests.test_security -v
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECURITY_ENV = ("DKE_HTTPS", "DKE_BEHIND_PROXY", "DKE_PROXY_HOPS")


def make_app(db_path, env=None, **config):
    environ = {k: v for k, v in os.environ.items() if k not in SECURITY_ENV}
    environ.update(env or {})
    with mock.patch.dict(os.environ, environ, clear=True):
        return create_app({"TESTING": True, "DATABASE": db_path, "SECRET_KEY": "test", **config})


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = os.path.join(self.tmp, "t.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (full_name, email, password_hash) VALUES (?,?,?)",
                     ("Demo", "demo@dke.test", generate_password_hash("Demo12345")))
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()

    def login(self, app, **kwargs):
        c = app.test_client()
        html = c.get("/infosys/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        return c, c.post("/infosys/login", data={"csrf_token": token, "email": "demo@dke.test",
                                                 "password": "Demo12345"}, **kwargs)

    @staticmethod
    def session_cookie(resp):
        cookies = [h for h in resp.headers.getlist("Set-Cookie") if h.startswith("session=")]
        return cookies[-1] if cookies else ""


class SessionCookieTests(SecurityTestCase):
    def test_login_set_cookie_memuat_httponly_dan_samesite_lax(self):
        _, r = self.login(make_app(self.db_path))
        self.assertEqual(r.status_code, 302)
        cookie = self.session_cookie(r)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_tanpa_dke_https_cookie_tidak_secure(self):
        app = make_app(self.db_path)
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])
        _, r = self.login(app)
        self.assertNotIn("Secure", self.session_cookie(r))

    def test_dengan_dke_https_cookie_secure(self):
        app = make_app(self.db_path, env={"DKE_HTTPS": "1"})
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        _, r = self.login(app)
        cookie = self.session_cookie(r)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_nilai_dke_https_selain_aktif_dianggap_mati(self):
        for value in ("0", "false", "", "  "):
            with self.subTest(value=value):
                self.assertFalse(make_app(self.db_path, env={"DKE_HTTPS": value}).config["SESSION_COOKIE_SECURE"])


class ProxyTests(SecurityTestCase):
    def remote_addr(self, app, headers):
        @app.get("/_ip")
        def _ip():
            from flask import request
            return request.remote_addr or ""
        return app.test_client().get("/_ip", headers=headers,
                                     environ_overrides={"REMOTE_ADDR": "10.0.0.1"}).get_data(as_text=True)

    def test_bawaan_x_forwarded_for_tidak_dipercaya(self):
        app = make_app(self.db_path)
        self.assertEqual(self.remote_addr(app, {"X-Forwarded-For": "198.51.100.9"}), "10.0.0.1")

    def test_behind_proxy_memakai_x_forwarded_for(self):
        app = make_app(self.db_path, env={"DKE_BEHIND_PROXY": "1"})
        self.assertEqual(self.remote_addr(app, {"X-Forwarded-For": "198.51.100.9"}), "198.51.100.9")

    def test_behind_proxy_satu_hop_mengambil_entri_terakhir_bukan_yang_dipalsukan_klien(self):
        app = make_app(self.db_path, env={"DKE_BEHIND_PROXY": "1"})
        # Klien memalsukan "1.1.1.1"; proxy kita menambahkan IP asli di ujung kanan.
        self.assertEqual(self.remote_addr(app, {"X-Forwarded-For": "1.1.1.1, 198.51.100.9"}), "198.51.100.9")

    def test_proxy_hops_dua(self):
        app = make_app(self.db_path, env={"DKE_BEHIND_PROXY": "1", "DKE_PROXY_HOPS": "2"})
        self.assertEqual(self.remote_addr(app, {"X-Forwarded-For": "1.1.1.1, 198.51.100.9, 10.9.9.9"}),
                         "198.51.100.9")


class SecurityHeaderTests(SecurityTestCase):
    def setUp(self):
        super().setUp()
        self.app = make_app(self.db_path)
        self.client = self.app.test_client()

    def assert_headers(self, resp):
        h = resp.headers
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("Content-Security-Policy", h)

    def csp(self, resp):
        return {d.split(" ", 1)[0]: d.split(" ", 1)[1] if " " in d else ""
                for d in resp.headers["Content-Security-Policy"].split("; ")}

    def test_halaman_html(self):
        for path in ("/", "/infosys/login", "/forum/", "/portal/", "/ecommerce/", "/elearning/", "/etutorial/"):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assert_headers(r)

    def test_respons_api_json(self):
        r = self.client.post("/api/settings/global", json={"theme": "dark"})
        self.assertEqual(r.mimetype, "application/json")
        self.assert_headers(r)

    def test_berkas_statis_dan_halaman_galat_juga_diberi_header(self):
        with self.client.get("/static/css/custom.css") as r:
            self.assert_headers(r)
        r = self.client.get("/tidak-ada")
        self.assertEqual(r.status_code, 404)
        self.assert_headers(r)

    def test_redirect_juga_diberi_header(self):
        r = self.client.get("/infosys/profil")
        self.assertEqual(r.status_code, 302)
        self.assert_headers(r)

    def test_csp_memuat_sumber_yang_dipakai(self):
        csp = self.csp(self.client.get("/"))
        self.assertIn("https://cdn.tailwindcss.com", csp["script-src"])
        self.assertIn("https://fonts.googleapis.com", csp["style-src"])
        self.assertIn("https://fonts.gstatic.com", csp["font-src"])
        self.assertIn("https://www.youtube-nocookie.com", csp["frame-src"])
        self.assertIn("https://player.vimeo.com", csp["frame-src"])
        self.assertEqual(csp["frame-ancestors"], "'none'")
        self.assertEqual(csp["object-src"], "'none'")
        self.assertEqual(csp["base-uri"], "'self'")
        self.assertNotIn("'unsafe-inline'", csp["script-src"])
        self.assertNotIn("'unsafe-eval'", csp["script-src"])

    def test_semua_skrip_inline_memakai_nonce_yang_sama_dengan_header(self):
        r = self.client.get("/")
        nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
        html = r.get_data(as_text=True)
        inline = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html)
        executable = [a for a in inline if "application/json" not in a]
        self.assertGreaterEqual(len(executable), 2)           # tema anti-kedip + tailwind.config
        for attrs in executable:
            self.assertIn(f'nonce="{nonce}"', attrs)

    def test_nonce_berbeda_tiap_permintaan(self):
        n = [re.search(r"'nonce-([^']+)'", self.client.get("/").headers["Content-Security-Policy"]).group(1)
             for _ in range(3)]
        self.assertEqual(len(set(n)), 3)

    def test_semua_modul_tanpa_skrip_inline_tanpa_nonce(self):
        """Setiap halaman modul (Guest dan Member): tak ada <script> inline yang akan diblokir CSP."""
        c, _ = self.login(self.app)
        pages = ["/", "/infosys/", "/infosys/profil", "/infosys/keamanan", "/infosys/aktivitas", "/infosys/statistik",
                 "/ecommerce/", "/ecommerce/keranjang", "/elearning/", "/elearning/kelas-saya", "/etutorial/",
                 "/portal/", "/forum/", "/forum/buat", "/dev/ui-test"]
        for client in (self.client, c):
            for path in pages:
                r = client.get(path)
                if r.status_code != 200:
                    continue
                html = r.get_data(as_text=True)
                for attrs in re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html):
                    if "application/json" in attrs:
                        continue
                    self.assertIn("nonce=", attrs, f"{path}: skrip inline tanpa nonce")
                self.assertNotRegex(html, r"\son(click|change|submit|load|error|input|keydown)=",
                                    f"{path}: atribut event inline akan diblokir CSP")
                self.assertNotRegex(html, r'href="javascript:', f"{path}: javascript: URL")

    def test_header_tidak_menimpa_nilai_yang_diset_rute(self):
        @self.app.get("/_custom")
        def _custom():
            from flask import make_response
            resp = make_response("x")
            resp.headers["X-Frame-Options"] = "SAMEORIGIN"
            return resp
        self.assertEqual(self.client.get("/_custom").headers["X-Frame-Options"], "SAMEORIGIN")

    def test_embed_video_elearning_tetap_diizinkan_csp(self):
        """Halaman materi berisi iframe YouTube; origin-nya harus tercakup frame-src."""
        from app.elearning.routes import video_embed
        embed = video_embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(embed["src"].startswith("https://www.youtube-nocookie.com/embed/"))
        embed = video_embed("https://vimeo.com/123456789")
        self.assertTrue(embed["src"].startswith("https://player.vimeo.com/"))


if __name__ == "__main__":
    unittest.main()
