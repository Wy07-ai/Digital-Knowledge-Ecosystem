"""Tes halaman galat (Blueprint 5.5): 403, 404, 405, 500; JSON untuk /api/*; tanpa detail galat.

Jalankan:  python -m unittest tests.test_errors
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from flask import abort
from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_DETAIL = "rahasia-internal-jangan-bocor"


class ErrorPageCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (id, full_name, email, password_hash, created_at) VALUES (1,'Rina Putri','rina@dke.test',?,?)",
                     (generate_password_hash("Rahasia123"), "2026-11-01T03:00:00+00:00"))
        conn.execute("INSERT INTO user_settings (user_id, theme, view_mode) VALUES (1, 'dark', 'mobile')")
        conn.commit()
        conn.close()
        # PROPAGATE_EXCEPTIONS=False: galat tak tertangkap harus lewat errorhandler(500), seperti di produksi.
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test",
                               "PROPAGATE_EXCEPTIONS": False})

        @self.app.route("/uji/terlarang")
        def uji_terlarang():
            abort(403)

        @self.app.route("/uji/meledak")
        def uji_meledak():
            raise RuntimeError(SECRET_DETAIL)

        @self.app.route("/api/uji/meledak")
        def api_meledak():
            raise RuntimeError(SECRET_DETAIL)

        @self.app.route("/api/uji/salah")
        def api_salah():
            abort(400)

        @self.app.route("/uji/salah")
        def uji_salah():
            abort(400)

        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login(self):
        with self.client.session_transaction() as s:
            s["user_id"] = 1

    def get(self, path, status):
        r = self.client.get(path)
        self.assertEqual(r.status_code, status, path)
        return r


class HtmlErrorTest(ErrorPageCase):
    def assert_halaman_galat(self, html, judul):
        self.assertIn(judul, html)
        self.assertIn("Kembali ke Beranda", html)
        self.assertIn('href="/"', html)                    # tombol menuju Beranda
        self.assertIn('class="topbar', html)               # Top-Bar tetap ada
        self.assertIn('aria-label="Beranda DKE"', html)
        self.assertNotIn('aria-label="Breadcrumb"', html)  # halaman galat bukan bagian hierarki navigasi

    def test_url_tidak_dikenal_menampilkan_404_dengan_tombol_beranda(self):
        r = self.get("/halaman/yang/tidak/ada", 404)
        self.assertEqual(r.mimetype, "text/html")
        html = r.get_data(as_text=True)
        self.assert_halaman_galat(html, "Halaman tidak ditemukan")
        self.assertIn('data-error-page="404"', html)

    def test_404_di_dalam_modul_juga_memakai_halaman_ramah(self):
        for path in ("/forum/thread/99999", "/portal/artikel/tidak-ada", "/ecommerce/produk/tidak-ada"):
            with self.subTest(path=path):
                self.assert_halaman_galat(self.get(path, 404).get_data(as_text=True), "Halaman tidak ditemukan")

    def test_403_dan_405(self):
        self.assert_halaman_galat(self.get("/uji/terlarang", 403).get_data(as_text=True), "Akses ditolak")
        r = self.client.post("/dev/ui-test")                # rute hanya GET
        self.assertEqual(r.status_code, 405)
        self.assertIn("GET", r.headers["Allow"])            # header Allow dipertahankan
        self.assert_halaman_galat(r.get_data(as_text=True), "Cara akses tidak diizinkan")

    def test_500_tidak_menampilkan_detail_galat(self):
        r = self.get("/uji/meledak", 500)
        html = r.get_data(as_text=True)
        self.assert_halaman_galat(html, "Terjadi kesalahan di server")
        for bocor in (SECRET_DETAIL, "RuntimeError", "Traceback", "uji_meledak"):
            self.assertNotIn(bocor, html)

    def test_500_memakai_halaman_cadangan_bila_template_gagal(self):
        with mock.patch("app.errors.render_template", side_effect=RuntimeError(SECRET_DETAIL)):
            r = self.get("/uji/meledak", 500)
        html = r.get_data(as_text=True)
        self.assertIn("Terjadi kesalahan di server", html)
        self.assertIn("Kembali ke Beranda", html)
        self.assertNotIn(SECRET_DETAIL, html)

    def test_tema_dan_mobile_view_member_tetap_berlaku(self):
        self.login()
        html = self.get("/tidak-ada", 404).get_data(as_text=True)
        self.assertIn('data-theme="dark"', html)           # Dark Mode dari pengaturan Member
        self.assertIn('data-view="mobile"', html)          # Mobile View dari pengaturan Member
        self.assertIn('data-member="1"', html)
        self.assertIn("theme.js", html)                    # skrip tema dimuat (Top-Bar interaktif)

    def test_guest_mendapat_pengaturan_bawaan(self):
        html = self.get("/tidak-ada", 404).get_data(as_text=True)
        self.assertIn('data-member="0"', html)
        self.assertIn('data-theme="system"', html)
        self.assertIn('data-view="desktop"', html)

    def test_halaman_galat_memakai_kelas_token_tema_bukan_warna_tetap(self):
        with open(os.path.join(ROOT, "app", "templates", "main", "error.html"), encoding="utf-8") as f:
            source = f.read()
        for token in ("bg-surface", "text-ink", "text-muted", "border-line", "btn btn-primary"):
            self.assertIn(token, source)                   # token berubah otomatis di Light/Dark
        for tetap in ("bg-white", "text-black", "text-gray-", "bg-gray-"):
            self.assertNotIn(tetap, source)

    def test_kode_lain_tetap_bawaan_untuk_halaman_html(self):
        r = self.get("/uji/salah", 400)
        self.assertNotIn('class="topbar', r.get_data(as_text=True))


class ApiErrorTest(ErrorPageCase):
    def test_api_tidak_dikenal_menghasilkan_json_404(self):
        r = self.get("/api/tidak-ada", 404)
        self.assertTrue(r.is_json)
        data = r.get_json()
        self.assertIs(data["ok"], False)
        self.assertEqual(data["status"], 404)
        self.assertTrue(data["error"])
        self.assertNotIn("<html", r.get_data(as_text=True).lower())

    def test_api_di_bawah_prefiks_modul_juga_json(self):
        r = self.get("/elearning/api/materi/999999/tidak-ada", 404)
        self.assertTrue(r.is_json)

    def test_api_405_json_dengan_header_allow(self):
        r = self.client.get("/api/settings/global")        # rute ini hanya POST
        self.assertEqual(r.status_code, 405)
        self.assertTrue(r.is_json)
        self.assertIn("POST", r.headers["Allow"])

    def test_api_kode_lain_juga_json(self):
        self.assertTrue(self.get("/api/uji/salah", 400).is_json)

    def test_api_500_tanpa_detail(self):
        r = self.get("/api/uji/meledak", 500)
        self.assertTrue(r.is_json)
        body = r.get_data(as_text=True)
        self.assertNotIn(SECRET_DETAIL, body)
        self.assertNotIn("Traceback", body)
        self.assertEqual(r.get_json()["status"], 500)

    def test_respons_json_endpoint_yang_ada_tidak_berubah(self):
        r = self.client.post("/api/settings/global", json={"theme": "dark"})   # Guest: 401 dari endpoint sendiri
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"], "Silakan masuk terlebih dahulu.")

    def test_jalur_mirip_api_bukan_api(self):
        r = self.get("/apiary/tidak-ada", 404)             # bukan segmen "api"
        self.assertEqual(r.mimetype, "text/html")


class NavigationTest(ErrorPageCase):
    def test_halaman_galat_bukan_rute_sehingga_tidak_perlu_node_navigasi(self):
        from app.navigation import NAV
        endpoints = {r.endpoint for r in self.app.url_map.iter_rules()}
        self.assertFalse([e for e in endpoints if "error" in e])
        self.assertFalse([e for e in NAV if "error" in e])


if __name__ == "__main__":
    unittest.main()
