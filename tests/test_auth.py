"""Tes otomatis UC-IS-01..03 (registrasi, login, logout).

Jalankan dari akar proyek:   python -m unittest discover -s tests -v
Memakai database SQLite sementara yang dibangun dari schema.sql (data asli tidak tersentuh).
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL_MSG = "Email belum valid. Contoh: nama@email.com"
MIN_MSG = "Kata sandi minimal 8 karakter."
FAIL_MSG = "Email atau kata sandi salah. Periksa kembali dan coba lagi."


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?,?,?)",
            ("Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345")))
        conn.execute(
            "INSERT INTO users (full_name, email, password_hash, is_active) VALUES (?,?,?,0)",
            ("Akun Nonaktif", "off@dke.test", generate_password_hash("Nonaktif123")))
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- bantuan ----
    def q(self, sql, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def token(self, path="/infosys/login", client=None):
        html = (client or self.client).get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post_login(self, email, password, next_url="", client=None):
        c = client or self.client
        return c.post("/infosys/login", data={
            "csrf_token": self.token(client=c), "email": email, "password": password, "next": next_url})

    def post_register(self, **kw):
        data = {"name": "Siti Aisyah", "email": "siti@mail.test", "password": "rahasia123",
                "confirm": "rahasia123", "next": "", "csrf_token": self.token("/infosys/register")}
        data.update(kw)
        return self.client.post("/infosys/register", data=data)

    def logged_in_client(self):
        c = self.app.test_client()
        r = self.post_login("demo@dke.test", "Demo12345", client=c)
        self.assertEqual(r.status_code, 302)
        return c


class RegisterTests(AuthTestCase):
    def test_form_renders(self):
        r = self.client.get("/infosys/register")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-auth-form="register"', r.get_data(as_text=True))

    def test_inline_validation_messages(self):
        r = self.post_register(email="bukan-email", password="pendek", confirm="beda")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn(EMAIL_MSG, html)
        self.assertIn(MIN_MSG, html)
        self.assertIn("Konfirmasi kata sandi belum sama.", html)
        self.assertEqual(self.q("SELECT COUNT(*) c FROM users WHERE email='bukan-email'")[0]["c"], 0)

    def test_password_exactly_8_is_accepted_and_7_rejected(self):
        self.assertIn(MIN_MSG, self.post_register(password="1234567", confirm="1234567").get_data(as_text=True))
        self.assertEqual(self.post_register(password="12345678", confirm="12345678").status_code, 302)

    def test_confirm_mismatch_only(self):
        html = self.post_register(confirm="rahasia124").get_data(as_text=True)
        self.assertIn("Konfirmasi kata sandi belum sama.", html)
        self.assertNotIn(MIN_MSG, html)
        self.assertNotIn(EMAIL_MSG, html)

    def test_success_creates_user_settings_and_log_with_hashed_password(self):
        r = self.post_register(email="  Siti@Mail.TEST ")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/infosys/login"))
        user = self.q("SELECT * FROM users WHERE email='siti@mail.test'")[0]   # email dinormalisasi
        self.assertEqual(user["role"], "member")
        self.assertNotIn("rahasia123", user["password_hash"])
        self.assertTrue(user["password_hash"].startswith(("scrypt:", "pbkdf2:")))
        us = self.q("SELECT * FROM user_settings WHERE user_id=?", (user["id"],))
        self.assertEqual(len(us), 1)
        self.assertEqual(us[0]["landing_mode"], "launcher")
        logs = self.q("SELECT * FROM activity_logs WHERE user_id=? AND action='register'", (user["id"],))
        self.assertEqual(len(logs), 1)

    def test_guest_theme_is_carried_over_only_if_valid(self):
        self.post_register(email="a@mail.test", pref_theme="dark", pref_view="mobile")
        self.post_register(email="b@mail.test", pref_theme="<script>", pref_view="x")
        a = self.q("SELECT s.* FROM user_settings s JOIN users u ON u.id=s.user_id WHERE u.email='a@mail.test'")[0]
        b = self.q("SELECT s.* FROM user_settings s JOIN users u ON u.id=s.user_id WHERE u.email='b@mail.test'")[0]
        self.assertEqual((a["theme"], a["view_mode"]), ("dark", "mobile"))
        self.assertEqual((b["theme"], b["view_mode"]), ("system", "desktop"))

    def test_duplicate_email_is_inline_error_and_case_insensitive(self):
        before = self.q("SELECT COUNT(*) c FROM users")[0]["c"]
        r = self.post_register(email="DEMO@dke.test")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 409)
        self.assertIn("Email ini sudah terdaftar.", html)
        self.assertIn('data-focus="email"', html)
        self.assertEqual(self.q("SELECT COUNT(*) c FROM users")[0]["c"], before)
        self.assertNotIn("rahasia123", html)           # kata sandi tidak dikirim balik

    def test_missing_or_bad_csrf_is_rejected(self):
        r = self.client.post("/infosys/register", data={
            "name": "X", "email": "x@mail.test", "password": "12345678", "confirm": "12345678"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.q("SELECT COUNT(*) c FROM users WHERE email='x@mail.test'")[0]["c"], 0)

    def test_register_then_login_prefills_email(self):
        self.post_register()
        html = self.client.get("/infosys/login").get_data(as_text=True)
        self.assertIn('value="siti@mail.test"', html)
        self.assertIn('data-focus="password"', html)


class LoginTests(AuthTestCase):
    def test_wrong_password_toast_and_focus_password(self):
        r = self.post_login("demo@dke.test", "salah-banget")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 401)
        self.assertIn(FAIL_MSG, html)                       # dikirim ke toast lewat flash-data
        self.assertIn('id="flash-data"', html)
        self.assertIn('"error"', html)
        self.assertIn('data-focus="password"', html)
        self.assertIn('value="demo@dke.test"', html)        # email tetap terisi
        self.assertNotIn("salah-banget", html)
        self.assertEqual(self.q("SELECT COUNT(*) c FROM activity_logs WHERE action='login'")[0]["c"], 0)
        self.assertEqual(self.client.get("/infosys/profil").status_code, 302)   # masih Guest

    def test_unknown_email_gets_same_message(self):
        r = self.post_login("tidakada@mail.test", "apasaja123")
        self.assertEqual(r.status_code, 401)
        self.assertIn(FAIL_MSG, r.get_data(as_text=True))

    def test_format_errors_are_inline(self):
        html = self.post_login("bukan-email", "").get_data(as_text=True)
        self.assertIn(EMAIL_MSG, html)
        self.assertIn("Kata sandi wajib diisi.", html)
        self.assertIn('data-focus="email"', html)

    def test_login_does_not_enforce_min_length(self):
        r = self.post_login("demo@dke.test", "x")           # format sah; hanya salah kredensial
        self.assertEqual(r.status_code, 401)

    def test_success_sets_session_logs_and_goes_home(self):
        r = self.post_login("DEMO@dke.test", "Demo12345")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/")
        with self.client.session_transaction() as s:
            self.assertIsNotNone(s.get("user_id"))
        logs = self.q("SELECT * FROM activity_logs WHERE action='login'")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["module_key"], "infosys")
        self.assertIsNotNone(self.q("SELECT last_login_at FROM users WHERE email='demo@dke.test'")[0][0])
        self.assertIn("Demo Pengguna", self.client.get("/").get_data(as_text=True))   # Top-Bar

    def test_inactive_account_cannot_login(self):
        r = self.post_login("off@dke.test", "Nonaktif123")
        self.assertEqual(r.status_code, 403)
        self.assertIn("dinonaktifkan", r.get_data(as_text=True))

    def test_logged_in_user_visiting_login_is_redirected(self):
        c = self.logged_in_client()
        self.assertEqual(c.get("/infosys/login").status_code, 302)
        self.assertEqual(c.get("/infosys/register").status_code, 302)


class ProtectedPageTests(AuthTestCase):
    def test_guest_is_redirected_to_login_with_next_then_returned(self):
        r = self.client.get("/infosys/profil")
        self.assertEqual(r.status_code, 302)
        loc = urlsplit(r.headers["Location"])
        self.assertEqual(loc.path, "/infosys/login")
        self.assertEqual(parse_qs(loc.query)["next"], ["/infosys/profil"])
        page = self.client.get(r.headers["Location"])
        self.assertIn('name="next" value="/infosys/profil"', page.get_data(as_text=True))
        self.assertIn("Silakan masuk terlebih dahulu", page.get_data(as_text=True))   # toast peringatan
        r = self.post_login("demo@dke.test", "Demo12345", next_url="/infosys/profil")
        self.assertEqual(r.headers["Location"], "/infosys/profil")
        self.assertEqual(self.client.get("/infosys/profil").status_code, 200)

    def test_query_string_survives_round_trip(self):
        r = self.client.get("/infosys/profil?tab=log&page=2")
        nxt = parse_qs(urlsplit(r.headers["Location"]).query)["next"]
        self.assertEqual(nxt, ["/infosys/profil?tab=log&page=2"])
        r = self.post_login("demo@dke.test", "Demo12345", next_url=nxt[0])
        self.assertEqual(r.headers["Location"], "/infosys/profil?tab=log&page=2")

    def test_open_redirect_is_blocked_on_get_and_post(self):
        evil = ["https://evil.example/x", "//evil.example", "/\\evil.example", "///evil.example",
                "http:evil.example", "javascript:alert(1)", "evil.example", "/ok\r\nSet-Cookie: a=b",
                "/ok\tevil", "/infosys/login", "/infosys/register?next=/", "/infosys/logout"]
        for target in evil:
            with self.subTest(next=target):
                html = self.client.get("/infosys/login", query_string={"next": target}).get_data(as_text=True)
                self.assertIn('name="next" value=""', html)      # nilai berbahaya dibuang saat render
                c = self.app.test_client()
                r = self.post_login("demo@dke.test", "Demo12345", next_url=target, client=c)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers["Location"], "/")     # jatuh ke Beranda, bukan situs lain

    def test_safe_local_paths_are_allowed(self):
        for target in ("/forum/", "/ecommerce/?q=buku", "/infosys/profil"):
            with self.subTest(next=target):
                c = self.app.test_client()
                r = self.post_login("demo@dke.test", "Demo12345", next_url=target, client=c)
                self.assertEqual(r.headers["Location"], target)


class LogoutTests(AuthTestCase):
    def test_logout_logs_activity_and_ends_session(self):
        c = self.logged_in_client()
        token = self.token("/", client=c)
        r = c.post("/infosys/logout", data={"csrf_token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/")
        self.assertEqual(len(self.q("SELECT * FROM activity_logs WHERE action='logout'")), 1)
        with c.session_transaction() as s:
            self.assertNotIn("user_id", s)
        self.assertEqual(c.get("/infosys/profil").status_code, 302)     # kembali menjadi Guest
        self.assertIn("Anda sudah keluar", c.get("/").get_data(as_text=True))

    def test_get_logout_does_nothing(self):
        c = self.logged_in_client()
        r = c.get("/infosys/logout")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get("/infosys/profil").status_code, 200)
        self.assertEqual(len(self.q("SELECT * FROM activity_logs WHERE action='logout'")), 0)

    def test_post_without_csrf_does_nothing(self):
        c = self.logged_in_client()
        c.post("/infosys/logout")
        self.assertEqual(c.get("/infosys/profil").status_code, 200)

    def test_topbar_has_post_logout_form_for_member_and_login_link_for_guest(self):
        c = self.logged_in_client()
        html = c.get("/").get_data(as_text=True)
        self.assertRegex(html, r'<form method="post" action="/infosys/logout">')
        guest = self.client.get("/").get_data(as_text=True)
        self.assertIn("/infosys/login", guest)
        self.assertNotIn('action="/infosys/logout"', guest)

    def test_guest_logout_is_harmless(self):
        r = self.client.post("/infosys/logout", data={"csrf_token": self.token()})
        self.assertEqual(r.status_code, 302)


if __name__ == "__main__":
    unittest.main()
