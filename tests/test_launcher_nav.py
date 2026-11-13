"""Tes otomatis Beranda (Dashboard Launcher) dan navigasi 3 level.

Jalankan dari akar proyek:   python -m unittest discover -s tests -v
Memakai database SQLite sementara yang dibangun dari schema.sql (data asli tidak tersentuh).
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from app import create_app
from app.main.launcher import friendly_when

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso(delta=timedelta()):
    return (datetime.now(timezone.utc) - delta).isoformat(timespec="seconds")


class LauncherTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (id, full_name, email, password_hash, last_login_at) VALUES (1, 'Rina Putri', 'rina@dke.test', ?, ?)",
                     (generate_password_hash("Rina12345"), iso()))
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- bantuan ----
    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(statement, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def login(self, client=None):
        with (client or self.client).session_transaction() as s:
            s["user_id"] = 1

    def settings(self, **values):
        sets = ", ".join(f"{k} = ?" for k in values)
        self.sql(f"UPDATE user_settings SET {sets} WHERE user_id = 1", list(values.values()))

    def html(self, path, **kw):
        r = self.client.get(path, **kw)
        self.assertEqual(r.status_code, 200, path)
        return r.get_data(as_text=True)

    def widget_text(self, html, key):
        card = re.search(rf'data-module="{key}".*?</a>', html, re.S).group(0)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card)).strip()

    def seed_content(self):
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1, 'elearning', 'Umum', 'umum')")
        self.sql("INSERT INTO courses (id, title, slug) VALUES (1, 'Python Dasar', 'python-dasar')")
        for n in range(1, 6):
            self.sql("INSERT INTO lessons (course_id, order_no, title) VALUES (1, ?, ?)", (n, f"Pelajaran {n}"))
        self.sql("INSERT INTO products (id, name, slug, price) VALUES (1, 'Ebook Flask', 'ebook-flask', 50000)")
        self.sql("INSERT INTO tutorials (id, title, slug) VALUES (1, 'Tutorial Flask', 'tutorial-flask')")
        self.sql("INSERT INTO articles (title, slug, body, read_minutes) VALUES ('Artikel Baru', 'artikel-baru', 'isi', 4)")
        self.sql("INSERT INTO threads (user_id, title, body) VALUES (1, 'Thread Pertama', 'isi')")


class BerandaGuestTests(LauncherTestCase):
    def test_grid_enam_kartu_dengan_kelas_responsif(self):
        html = self.html("/")
        self.assertEqual(re.findall(r'data-module="(\w+)"', html),
                         ["infosys", "ecommerce", "elearning", "etutorial", "portal", "forum"])
        grid = re.search(r'<div class="([^"]*launcher-grid[^"]*)"', html).group(1)
        self.assertIn("grid-cols-1", grid)       # 1 kolom di mobile
        self.assertIn("lg:grid-cols-3", grid)    # 3 kolom (3x2) di desktop

    def test_kartu_memuat_nama_dan_aksen_modul(self):
        html = self.html("/")
        for key, name, accent in (("infosys", "Information System", "#4F46E5"), ("forum", "Forum", "#0D9488")):
            card = re.search(rf'data-module="{key}".*?</a>', html, re.S).group(0)
            self.assertIn(name, card)
            self.assertIn(accent, card)

    def test_css_hover_lift_200ms(self):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertRegex(css, r"\.launcher-card\s*\{[^}]*transform 200ms")
        self.assertIn("translateY(-4px)", css)

    def test_guest_tanpa_lanjutkan_dan_tanpa_pengaturan_landing(self):
        html = self.html("/")
        self.assertNotIn("data-resume", html)
        self.assertNotIn("data-landing-section", html)
        self.assertIn("Masuk untuk melihat aktivitas Anda", html)

    def test_guest_melihat_konten_publik_bukan_angka_pribadi(self):
        self.seed_content()
        html = self.html("/")
        self.assertIn("Terbaru: Ebook Flask", self.widget_text(html, "ecommerce"))
        self.assertIn("1 kelas tersedia", self.widget_text(html, "elearning"))
        self.assertIn("Populer: Tutorial Flask", self.widget_text(html, "etutorial"))
        self.assertIn("Artikel Baru", self.widget_text(html, "portal"))
        self.assertIn("Thread terbaru: Thread Pertama", self.widget_text(html, "forum"))

    def test_database_belum_ada_tabel_tidak_membuat_error(self):
        os.remove(self.db_path)
        open(self.db_path, "w").close()
        with self.assertLogs(self.app.logger, level="WARNING"):
            html = self.html("/")
        # 5 widget gagal dengan aman; widget Information System untuk Guest memang statis
        self.assertEqual(html.count("Ringkasan belum tersedia"), 5)
        self.assertEqual(len(re.findall(r'data-module="', html)), 6)


class BerandaMemberTests(LauncherTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_data_kosong_ditangani_dengan_pesan_ramah(self):
        html = self.html("/")
        self.assertIn("Halo, Rina", html)
        self.assertEqual(html.count("data-widget-empty"), 6)
        self.assertIn("Belum ada aktivitas hari ini", self.widget_text(html, "infosys"))
        self.assertIn("Keranjang masih kosong", self.widget_text(html, "ecommerce"))
        self.assertIn("Belum mengikuti kelas", self.widget_text(html, "elearning"))
        self.assertIn("Belum ada tutorial tersimpan", self.widget_text(html, "etutorial"))
        self.assertIn("Belum ada artikel", self.widget_text(html, "portal"))
        self.assertIn("Tidak ada balasan baru", self.widget_text(html, "forum"))

    def test_widget_dari_data_nyata(self):
        self.seed_content()
        self.sql("INSERT INTO cart_items (user_id, product_id, qty) VALUES (1, 1, 2)")
        self.sql("INSERT INTO enrollments (user_id, course_id, enrolled_at) VALUES (1, 1, ?)", (iso(timedelta(days=3)),))
        for lesson_id in (1, 2):
            self.sql("INSERT INTO lesson_progress (user_id, lesson_id, completed_at) VALUES (1, ?, ?)", (lesson_id, iso(timedelta(days=1))))
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id) VALUES (1, 1)")
        self.sql("INSERT INTO activity_logs (user_id, module_key, action, created_at) VALUES (1, 'infosys', 'login', ?)", (iso(),))
        self.sql("INSERT INTO notifications (user_id, module_key, message, is_read) VALUES (1, 'forum', 'A membalas', 0)")
        self.sql("INSERT INTO notifications (user_id, module_key, message, is_read) VALUES (1, 'forum', 'B membalas', 0)")
        self.sql("INSERT INTO notifications (user_id, module_key, message, is_read) VALUES (1, 'forum', 'C membalas', 1)")
        html = self.html("/")
        self.assertEqual(html.count("data-widget-empty"), 0)
        self.assertIn("1 aktivitas hari ini", self.widget_text(html, "infosys"))
        self.assertIn("Login terakhir: hari ini", self.widget_text(html, "infosys"))
        self.assertIn("2 item di keranjang", self.widget_text(html, "ecommerce"))
        self.assertIn("Python Dasar", self.widget_text(html, "elearning"))
        self.assertIn("2 dari 5 materi selesai", self.widget_text(html, "elearning"))
        self.assertIn('aria-valuenow="40"', html)
        self.assertIn("1 tutorial tersimpan", self.widget_text(html, "etutorial"))
        self.assertIn("2 balasan baru", self.widget_text(html, "forum"))

    def test_kelas_selesai_progres_100(self):
        self.seed_content()
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1, 1)")
        for lesson_id in range(1, 6):
            self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, ?)", (lesson_id,))
        html = self.html("/")
        self.assertIn('aria-valuenow="100"', html)
        self.assertIn("Kelas selesai", html)


class LanjutkanDanLandingTests(LauncherTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_tombol_lanjutkan_modul_dan_halaman_terakhir(self):
        self.settings(last_module="infosys", last_path="/infosys/profil")
        html = self.html("/")
        self.assertIn("data-resume", html)
        self.assertIn('href="/infosys/profil"', html)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.search(r"data-resume.*?</a>", html, re.S).group(0)))
        self.assertIn("Lanjutkan:", text)
        self.assertIn("Information System", text)
        self.assertIn("Profil &amp; Pengaturan", html)

    def test_lanjutkan_ke_halaman_utama_modul_bila_path_kosong(self):
        self.settings(last_module="forum")
        html = self.html("/")
        self.assertRegex(html, r'<a href="/forum/"[^>]*data-resume')

    def test_lanjutkan_disembunyikan_untuk_data_tidak_valid(self):
        for module, path in (("tidak-ada", "/forum/"), ("forum", "https://evil.example/"), ("forum", "//evil.example"),
                             ("forum", "/forum/halaman-yang-tidak-ada"), ("forum", "/infosys/profil")):
            self.settings(last_module=module, last_path=path)
            self.assertNotIn("data-resume", self.html("/"), (module, path))

    def test_mode_launcher_tidak_mengalihkan(self):
        self.settings(landing_mode="launcher", last_module="infosys", last_path="/infosys/profil")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("data-resume", r.get_data(as_text=True))

    def test_mode_last_module_mengalihkan_sekali_lalu_beranda_tetap_bisa_dibuka(self):
        self.settings(landing_mode="last_module", last_module="infosys", last_path="/infosys/profil")
        first = self.client.get("/")
        self.assertEqual(first.status_code, 302)
        self.assertTrue(first.headers["Location"].endswith("/infosys/profil"))
        # tombol DKE (Beranda) di Top-Bar tidak boleh memantul kembali ke modul
        second = self.client.get("/")
        self.assertEqual(second.status_code, 200)
        self.assertIn("Halo, Rina", second.get_data(as_text=True))

    def test_pesan_toast_saat_melanjutkan(self):
        self.settings(landing_mode="last_module", last_module="infosys", last_path="/infosys/profil")
        html = self.client.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn("Melanjutkan: Information System", html)

    def test_membuka_halaman_lain_dulu_membatalkan_pengalihan(self):
        self.settings(landing_mode="last_module", last_module="infosys", last_path="/infosys/profil")
        self.assertEqual(self.client.get("/forum/").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_baru_mengalihkan_lagi(self):
        self.settings(landing_mode="last_module", last_module="infosys", last_path="/infosys/profil")
        self.client.get("/forum/")
        self.client.get("/")                       # sesi lama sudah mendarat
        other = self.app.test_client()             # sesi baru (login ulang)
        self.login(other)
        self.assertEqual(other.get("/").status_code, 302)

    def test_alur_login_sungguhan_mengalihkan_ke_modul_terakhir(self):
        self.settings(landing_mode="last_module", last_module="infosys", last_path="/infosys/profil")
        guest = self.app.test_client()
        token = re.search(r'name="csrf_token" value="([^"]+)"', guest.get("/infosys/login").get_data(as_text=True)).group(1)
        r = guest.post("/infosys/login", data={"email": "rina@dke.test", "password": "Rina12345", "csrf_token": token})
        self.assertEqual(r.status_code, 302)               # login -> Beranda ("/")
        r = guest.get(r.headers["Location"])
        self.assertEqual(r.status_code, 302)               # Beranda -> halaman terakhir
        self.assertTrue(r.headers["Location"].endswith("/infosys/profil"))

    def test_guest_tidak_pernah_dialihkan(self):
        guest = self.app.test_client()
        self.assertEqual(guest.get("/").status_code, 200)

    def test_pilihan_landing_mode_tercermin_di_tombol(self):
        self.settings(landing_mode="last_module")
        self.client.get("/forum/")                          # sudah mendarat -> Beranda tampil
        html = self.html("/")
        self.assertRegex(html, r'data-landing-option="last_module"\s+aria-pressed="true"')
        self.assertRegex(html, r'data-landing-option="launcher"\s+aria-pressed="false"')


class NavigasiTests(LauncherTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.seed_content()

    def test_halaman_bersarang_tiga_jenjang(self):
        html = self.html("/dev/ui-test/navigasi/kelas/1/materi/2")
        nav = re.search(r"data-breadcrumb.*?</nav>", html, re.S).group(0)
        self.assertEqual(len(re.findall(r'class="bc-item', nav)), 3)
        self.assertIn('href="/elearning/"', nav)
        self.assertIn('href="/dev/ui-test/navigasi/kelas/1"', nav)
        self.assertIn("Python Dasar", nav)
        self.assertRegex(nav, r'aria-current="page">Materi 2: Pelajaran 2<')   # halaman aktif bukan tautan
        self.assertIn("bc-ellipsis", nav)                                      # ringkasan mobile

    def test_tombol_kembali_mengikuti_hierarki_bukan_riwayat(self):
        for referer in (None, "http://localhost/portal/", "http://localhost/forum/", "http://localhost/"):
            headers = {"Referer": referer} if referer else {}
            html = self.html("/dev/ui-test/navigasi/kelas/1/materi/2", headers=headers)
            back = re.search(r'<a href="([^"]+)"[^>]*data-back-link', html)
            self.assertEqual(back.group(1), "/dev/ui-test/navigasi/kelas/1", referer)
            self.assertIn('aria-label="Kembali ke Python Dasar"', html)

    def test_kembali_dari_kelas_menuju_daftar_modul(self):
        html = self.html("/dev/ui-test/navigasi/kelas/1")
        self.assertEqual(re.search(r'<a href="([^"]+)"[^>]*data-back-link', html).group(1), "/elearning/")

    def test_halaman_nyata_dua_jenjang(self):
        html = self.html("/infosys/profil")
        self.assertEqual(re.search(r'<a href="([^"]+)"[^>]*data-back-link', html).group(1), "/infosys/")
        self.assertEqual(len(re.findall(r'class="bc-item', html)), 2)
        self.assertNotIn("bc-ellipsis", html)      # dua jenjang tidak perlu diringkas

    def test_halaman_utama_modul_dan_beranda_tanpa_kembali(self):
        for path in ("/infosys/", "/forum/", "/"):
            html = self.html(path)
            self.assertNotIn("data-back-link", html, path)
            self.assertNotIn("data-page-nav", html, path)

    def test_halaman_login_tanpa_breadcrumb(self):
        guest = self.app.test_client()
        html = guest.get("/infosys/login").get_data(as_text=True)
        self.assertNotIn("data-page-nav", html)

    def test_label_cadangan_bila_data_tidak_ada(self):
        html = self.html("/dev/ui-test/navigasi/kelas/99/materi/3")
        self.assertIn(">Materi 3<", html)
        self.assertIn("Kelas 99", html)

    def test_app_switcher_menandai_modul_aktif_dan_menaut_semua_modul(self):
        html = self.html("/forum/")
        panel = re.search(r'id="app-switcher-panel".*?</div>\s*<a href="/"', html, re.S).group(0)
        self.assertEqual(len(re.findall(r'data-popover-item', panel)), 6)
        self.assertEqual(len(re.findall(r'aria-current="page"', panel)), 1)
        self.assertIn("Semua modul (Beranda)", html)

    def test_halaman_uji_nonaktif_memberi_404(self):
        app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "x", "UI_TEST_PAGE": False})
        self.assertEqual(app.test_client().get("/dev/ui-test/navigasi/kelas/1").status_code, 404)


class WaktuTests(unittest.TestCase):
    def test_friendly_when(self):
        self.assertTrue(friendly_when(iso()).startswith("hari ini"))
        self.assertTrue(friendly_when(iso(timedelta(days=1))).startswith("kemarin") or "hari" in friendly_when(iso(timedelta(days=1))))
        self.assertEqual(friendly_when(iso(timedelta(days=3))), "3 hari lalu")
        self.assertRegex(friendly_when("2026-01-05T03:00:00+00:00"), r"^5 Jan 2026$")
        self.assertIsNone(friendly_when(None))
        self.assertIsNone(friendly_when("bukan tanggal"))


if __name__ == "__main__":
    unittest.main()
