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

from app import MODULES, create_app
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
        self.sql("INSERT INTO articles (title, slug, body, read_minutes, published_at) VALUES ('Artikel Baru', 'artikel-baru', 'isi', 4, ?)", (iso(),))
        self.sql("INSERT INTO threads (user_id, title, body) VALUES (1, 'Thread Pertama', 'isi')")


class BerandaGuestTests(LauncherTestCase):
    def test_grid_enam_kartu_dengan_kelas_responsif(self):
        html = self.html("/")
        self.assertEqual(re.findall(r'data-module="(\w+)"', html),
                         ["infosys", "ecommerce", "elearning", "etutorial", "portal", "forum"])
        grid = re.search(r'<div class="([^"]*launcher-grid[^"]*)"', html).group(1).split()
        self.assertIn("grid-cols-2", grid)       # 2 kolom (2x3) di mobile
        self.assertIn("lg:grid-cols-3", grid)    # 3 kolom (3x2) di desktop
        self.assertIn("gap-3", grid)
        self.assertIn("lg:gap-4", grid)
        self.assertNotIn("grid-cols-1", grid)    # tidak ada lagi satu kolom
        self.assertNotIn("md:grid-cols-2", grid)

    def test_kartu_memuat_nama_dan_aksen_modul(self):
        html = self.html("/")
        for key, name, accent in (("infosys", "Information System", "#4F46E5"), ("forum", "Forum", "#0D9488")):
            card = re.search(rf'<a [^>]*data-module="{key}".*?</a>', html, re.S).group(0)
            self.assertIn(name, card)
            self.assertIn(accent, card)

    def test_css_hover_lift_uses_shared_design_tokens(self):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertRegex(css, r"\.launcher-card\s*\{[^}]*transform var\(--dur-fast\)")
        self.assertIn("translateY(-4px)", css)
        self.assertIn("--radius-card:", css)
        self.assertIn("--text-hero:", css)

    def test_guest_tanpa_lanjutkan_dan_tanpa_pengaturan_landing(self):
        html = self.html("/")
        self.assertNotIn("data-resume", html)
        self.assertNotIn("data-landing-section", html)
        self.assertIn("Masuk ke akun", self.widget_text(html, "infosys"))

    def test_guest_melihat_satu_ajakan_pendek_per_kartu(self):
        self.seed_content()
        html = self.html("/")
        for key, cta in (("infosys", "Masuk ke akun"), ("ecommerce", "Lihat produk"), ("elearning", "Lihat kelas"),
                         ("etutorial", "Lihat tutorial"), ("portal", "Baca artikel"), ("forum", "Lihat diskusi")):
            self.assertIn(cta, self.widget_text(html, key), key)
        # tidak ada lagi teks "Masuk untuk melihat ..." maupun judul konten yang panjang di kartu
        self.assertNotIn("Masuk untuk melihat", html)
        self.assertNotIn("Ebook Flask", html)
        self.assertNotIn("Topik Pertama", html)

    def test_guest_data_kosong_tetap_ramah(self):
        html = self.html("/")
        self.assertIn("Belum ada produk", self.widget_text(html, "ecommerce"))
        self.assertIn("Belum ada kelas", self.widget_text(html, "elearning"))
        self.assertIn("Belum ada artikel", self.widget_text(html, "portal"))

    def test_subjudul_guest_singkat_dengan_istilah_aplikasi(self):
        html = self.html("/")
        self.assertIn("Satu akun untuk enam aplikasi", html)
        self.assertNotIn("modul", re.sub(r"data-module|module", "", html.lower().split("<main")[1].split("launcher-grid")[0]))

    def test_deskripsi_ada_di_title_dan_aria_describedby_bukan_teks_tampil(self):
        html = self.html("/")
        literal = {"infosys": "Profil, log aktivitas, dan statistik dari semua aplikasi.",
                   "forum": "Diskusi, tanya jawab, dan balasan komunitas."}
        for m in MODULES:
            key, desc = m["key"], m["desc"]
            if key in literal:
                self.assertEqual(desc, literal[key])
            card = re.search(rf'<a [^>]*data-module="{key}".*?</a>', html, re.S).group(0)
            start_tag = card.split(">", 1)[0]
            # (1) deskripsi tetap ada di atribut title
            self.assertIn(f'title="{desc}"', start_tag, key)
            # (2) aria-describedby menunjuk satu elemen yang ada, sr-only, berisi deskripsi
            ref = re.search(r'aria-describedby="([^"]+)"', start_tag).group(1)
            self.assertEqual(ref, f"card-desc-{key}")
            self.assertEqual(html.count(f'id="{ref}"'), 1, ref)
            target = re.search(rf'<span id="{ref}" class="([^"]*)" aria-hidden="true">(.*?)</span>', card, re.S)
            self.assertIsNotNone(target, key)
            self.assertIn("sr-only", target.group(1).split())
            self.assertEqual(target.group(2), desc)
            # (3) tanpa aria-label di tautan: aria-label menggantikan isi tautan dan menyembunyikan metrik
            self.assertNotIn("aria-label=", start_tag, key)
            # (4) tidak ada kalimat deskripsi yang terlihat: buang elemen sr-only dan atribut tooltip/label
            visible = re.sub(r'<span id="card-desc-[^>]*>.*?</span>', "", card, flags=re.S)
            visible = re.sub(r'(?:title|aria-label)="[^"]*"', "", visible)
            self.assertNotIn(desc, visible, key)
            self.assertNotIn("module-card-desc", card, key)
            # (5) nama aplikasi dan metrik tetap menjadi isi tautan (nama aksesibel tetap lengkap)
            self.assertIn(m["name"], self.widget_text(html, key))
            self.assertIn("data-widget", card)

    def test_kartu_maksimal_dua_baris_teks_selain_nama_dan_tanpa_pengulangan(self):
        self.seed_content()
        for login in (False, True):
            if login:
                self.login()
            html = self.html("/")
            for key in ("infosys", "ecommerce", "elearning", "etutorial", "portal", "forum"):
                card = re.search(rf'<a [^>]*data-module="{key}".*?</a>', html, re.S).group(0)
                self.assertEqual(card.count("<p "), 1, key)           # satu baris metrik
                self.assertNotIn("<hr", card)
                text = re.sub(r'<span id="card-desc-[^>]*>.*?</span>', "", card, flags=re.S)
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
                words = text.lower().split()
                self.assertLessEqual(len(words), 12, text)

    def test_zona_metrik_seragam_dan_menempel_di_dasar(self):
        html = self.html("/")
        zones = re.findall(r'<div class="mt-auto pt-4">\s*<div class="(h-11[^"]*)"', html)
        self.assertEqual(len(zones), 6)
        self.assertEqual(len(set(zones)), 1)   # tinggi sama di semua kartu, jadi garis sejajar

    def test_status_bukan_hanya_warna_dan_nama_aplikasi_selalu_tertulis(self):
        html = self.html("/")
        for m in MODULES:
            self.assertIn(m["name"], self.widget_text(html, m["key"]))
        self.assertIn("Masuk ke akun", html)   # ajakan berupa teks, bukan hanya warna

    def test_database_belum_ada_tabel_tidak_membuat_error(self):
        os.remove(self.db_path)
        open(self.db_path, "w").close()
        with self.assertLogs(self.app.logger, level="WARNING"):
            html = self.html("/")
        # 5 widget gagal dengan aman; widget Information System untuk Guest memang statis
        self.assertEqual(sum("Ringkasan belum tersedia" in self.widget_text(html, m["key"]) for m in MODULES), 5)
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

    def test_member_artikel_baru_minggu_ini_dan_tanpa_artikel_baru(self):
        self.seed_content()
        self.assertIn("1 artikel baru minggu ini", self.widget_text(self.html("/"), "portal"))
        self.sql("UPDATE articles SET published_at = ?", (iso(timedelta(days=30)),))
        html = self.html("/")
        self.assertIn("Belum ada artikel baru", self.widget_text(html, "portal"))
        self.assertEqual(html.count("data-widget-empty") >= 1, True)

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
        self.assertIn("2 di keranjang", self.widget_text(html, "ecommerce"))
        self.assertIn("Python Dasar", self.widget_text(html, "elearning"))
        self.assertIn("40%", self.widget_text(html, "elearning"))
        self.assertIn('aria-valuenow="40"', html)
        self.assertIn("1 tersimpan", self.widget_text(html, "etutorial"))
        self.assertIn("2 balasan baru", self.widget_text(html, "forum"))
        self.assertNotIn("Login terakhir", html)

    def test_kelas_selesai_progres_100(self):
        self.seed_content()
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1, 1)")
        for lesson_id in range(1, 6):
            self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, ?)", (lesson_id,))
        html = self.html("/")
        self.assertIn('aria-valuenow="100"', html)
        self.assertIn("100%", self.widget_text(html, "elearning"))


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
        self.assertIn("Semua aplikasi (Beranda)", html)

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


class HeroMobileCssTests(unittest.TestCase):
    """Hero Beranda: aturan Mobile View harus ada di CSS (bukan hanya media query)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            cls.css = f.read()

    def _rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, f"aturan {selector} tidak ditemukan di custom.css")
        return re.sub(r"\s+", " ", m.group(1))

    def test_orbit_disembunyikan_di_mobile_view(self):
        self.assertIn("display: none", self._rule("html[data-view='mobile'] .home-orbit"))

    def test_hero_menjadi_blok_di_mobile_view(self):
        body = self._rule("html[data-view='mobile'] .home-hero")
        self.assertIn("display: block", body)
        self.assertIn("min-height: 0", body)

    def test_judul_dan_cta_mobile_view(self):
        self.assertIn("max-width: none", self._rule("html[data-view='mobile'] .home-hero h1"))
        self.assertIn("min-height: 44px", self._rule("html[data-view='mobile'] .home-hero-cta"))

    def test_media_query_sempit_memuat_aturan_yang_sama(self):
        m = re.search(r"@media \(max-width: 767px\) \{\s*\.home-hero \{[^}]*display: block[^}]*\}\s*\.home-orbit \{ display: none; \}", self.css)
        self.assertIsNotNone(m)


class LauncherGridCssTests(unittest.TestCase):
    """Grid kartu Beranda: 2 kolom di Mobile View dan layar sempit; grid lain tetap 1 kolom.

    Pola ganda seperti hero (custom.css bagian 6): aturan html[data-view='mobile'] untuk Mobile View di
    desktop dan @media (max-width: 767px) untuk layar sungguhan.
    """
    TWO_COLS = "grid-template-columns: repeat(2, minmax(0, 1fr))"

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            cls.css = f.read().replace("\r\n", "\n")

    def _rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, f"aturan {selector} tidak ditemukan di custom.css")
        return re.sub(r"\s+", " ", m.group(1))

    def _media_bodies(self, header):
        """Isi semua blok @media dengan header persis ini (kurung kurawal diseimbangkan)."""
        bodies, pos = [], 0
        while True:
            i = self.css.find(header, pos)
            if i < 0:
                return bodies
            j = self.css.index("{", i)
            depth = 0
            for k in range(j, len(self.css)):
                depth += {"{": 1, "}": -1}.get(self.css[k], 0)
                if depth == 0:
                    bodies.append(self.css[j + 1:k])
                    break
            pos = j + 1

    def test_mobile_view_launcher_grid_dua_kolom(self):
        self.assertIn(self.TWO_COLS, self._rule("html[data-view='mobile'] .launcher-grid"))

    def test_media_query_sempit_launcher_grid_dua_kolom(self):
        bodies = [b for b in self._media_bodies("@media (max-width: 767px)") if re.search(r"(^|\s)\.launcher-grid\s*\{", b)]
        self.assertEqual(len(bodies), 1)
        m = re.search(r"(?:^|\s)\.launcher-grid\s*\{([^}]*)\}", bodies[0])
        self.assertIn(self.TWO_COLS, re.sub(r"\s+", " ", m.group(1)))

    def test_product_grid_dan_card_grid_tetap_satu_kolom(self):
        mv = re.search(r"html\[data-view='mobile'\] \.product-grid,\s*html\[data-view='mobile'\] \.card-grid\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(mv)
        self.assertIn("grid-template-columns: 1fr", mv.group(1))
        narrow = [b for b in self._media_bodies("@media (max-width: 767px)") if ".product-grid, .card-grid" in b]
        self.assertEqual(len(narrow), 1)
        self.assertRegex(narrow[0], r"\.product-grid, \.card-grid \{ grid-template-columns: 1fr; \}")
        # .launcher-grid tidak boleh ikut aturan satu kolom di mana pun
        self.assertNotRegex(self.css, r"\.launcher-grid[^{}]*\{[^}]*grid-template-columns: 1fr\b")

    def test_animasi_masuk_bertahap_tidak_berubah(self):
        for n, delay in ((2, 50), (3, 100), (6, 250)):
            self.assertIn(f"animation-delay: {delay}ms", self._rule(
                f".launcher-grid > :nth-child({n}), .card-grid > :nth-child({n}), .product-grid > :nth-child({n}), .fm-row:nth-child({n})"))

    def test_hover_lift_hanya_untuk_hover_sungguhan_dan_tanpa_reduced_motion(self):
        self.assertEqual(self.css.count(".launcher-card:hover"), 1)
        bodies = self._media_bodies("@media (hover: hover) and (prefers-reduced-motion: no-preference)")
        self.assertTrue(any(".launcher-card:hover" in b and "translateY(-4px)" in b for b in bodies))
        # umpan tekan juga dimatikan saat gerak dikurangi
        active = self._media_bodies("@media (prefers-reduced-motion: no-preference)")
        self.assertTrue(any(".launcher-card:active" in b for b in active))

    def test_gradien_dan_ikon_memakai_token_bukan_warna_tetap(self):
        for selector in (".module-card-visual", ".module-card-icon", ".module-card-title"):
            body = self._rule(selector)
            self.assertNotRegex(body, r"#[0-9a-fA-F]{3,8}\b", selector)
        self.assertIn("var(--card-accent)", self._rule(".module-card-visual"))
        self.assertIn("rgb(var(--c-surface))", self._rule(".module-card-visual"))
        self.assertIn("rgb(var(--c-ink))", self._rule(".module-card-icon"))
        self.assertIn("rgb(var(--c-ink))", self._rule(".module-card-title"))

    def test_ikon_berkontras_di_atas_3_banding_1_pada_terang_dan_gelap(self):
        """Mereplikasi color-mix(in srgb) di CSS: ikon = 58% aksen + 42% ink; latar = 9-26% aksen + surface."""
        def token(scope, name):
            m = re.search(scope + r"\s*\{[^}]*?--" + name + r":\s*(\d+) (\d+) (\d+)", self.css)
            return tuple(int(v) for v in m.groups())

        def lum(c):
            lin = lambda v: v / 255 / 12.92 if v / 255 <= .03928 else ((v / 255 + .055) / 1.055) ** 2.4
            r, g, b = (lin(v) for v in c)
            return .2126 * r + .7152 * g + .0722 * b

        def contrast(a, b):
            return (max(lum(a), lum(b)) + .05) / (min(lum(a), lum(b)) + .05)

        mix = lambda a, b, p: tuple(a[i] * p + b[i] * (1 - p) for i in range(3))
        self.assertIn("color-mix(in srgb, var(--card-accent) 58%, rgb(var(--c-ink)))", self._rule(".module-card-icon"))
        for mode, scope in (("terang", r":root"), ("gelap", r"html\.dark")):
            surface, ink = token(scope, "c-surface"), token(scope, "c-ink")
            for m in MODULES:
                accent = tuple(int(m["accent"][i:i + 2], 16) for i in (1, 3, 5))
                icon = mix(accent, ink, .58)
                for share in (.26, .09):      # kedua ujung gradien area visual
                    self.assertGreaterEqual(contrast(icon, mix(accent, surface, share)), 3.0, (mode, m["key"], share))


class KartuAplikasiTemplatTests(LauncherTestCase):
    """Kartu dipakai di Beranda dan halaman uji; keduanya harus memakai grid dan struktur yang sama."""

    def test_halaman_uji_memakai_grid_dan_kartu_yang_sama(self):
        self.login()
        html = self.html("/dev/ui-test")
        grid = re.search(r'<div class="([^"]*launcher-grid[^"]*)"', html).group(1).split()
        self.assertIn("grid-cols-2", grid)
        self.assertIn("lg:grid-cols-3", grid)
        self.assertNotIn("grid-cols-1", grid)
        self.assertEqual(len(re.findall(r'class="launcher-card ', html)), 6)
        self.assertEqual(len(re.findall(r'class="module-card-visual"', html)), 6)

    def test_struktur_kartu_visual_judul_metrik(self):
        html = self.html("/")
        for m in MODULES:
            card = re.search(rf'<a [^>]*data-module="{m["key"]}".*?</a>', html, re.S).group(0)
            self.assertEqual(card.count('class="module-card-visual"'), 1)
            self.assertEqual(card.count("<svg"), 1)                 # satu ikon besar, dekoratif
            self.assertRegex(card, rf'<h3 class="module-card-title">{re.escape(m["name"])}</h3>')
            self.assertIn(f"--card-accent: {m['accent']}", card)
            self.assertLess(card.index("module-card-visual"), card.index("module-card-title"))
            self.assertLess(card.index("module-card-title"), card.index("data-widget"))

    def test_progress_bar_elearning_dan_empty_state_tetap_tampil(self):
        self.seed_content()
        self.login()
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1, 1)")
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, 1)")
        html = self.html("/")
        card = re.search(r'<a [^>]*data-module="elearning".*?</a>', html, re.S).group(0)
        self.assertIn('role="progressbar"', card)
        self.assertIn('aria-valuenow="20"', card)
        self.assertIn("20%", card)
        self.assertIn("data-widget-empty", re.search(r'<a [^>]*data-module="infosys".*?</a>', html, re.S).group(0))
        self.assertIn("text-muted", re.search(r'<a [^>]*data-module="infosys".*?</a>', html, re.S).group(0))


if __name__ == "__main__":
    unittest.main()
