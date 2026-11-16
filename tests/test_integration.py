"""Tes integrasi lintas modul: notifikasi Top-Bar, Smart Landing, statistik Information System,
helper module_settings, dan pola seragam tab Pengaturan lima modul (Blueprint 5.4).

Jalankan:  python -m unittest tests.test_integration
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import MODULES, create_app
from app.module_settings import get_setting, set_setting

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON = {"Content-Type": "application/json"}


class IntegrationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        for uid, name, email in ((1, "Rina Putri", "rina@dke.test"), (2, "Budi Santoso", "budi@dke.test")):
            conn.execute("INSERT INTO users (id, full_name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
                         (uid, name, email, generate_password_hash("Rahasia123"), "2026-11-01T03:00:00+00:00"))
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (uid,))
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(statement, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def login(self, uid=1, client=None):
        with (client or self.client).session_transaction() as s:
            s["user_id"] = uid

    def html(self, path, status=200):
        r = self.client.get(path)
        self.assertEqual(r.status_code, status, path)
        return r.get_data(as_text=True)

    def csrf(self):
        self.client.get("/")
        with self.client.session_transaction() as s:
            return s["_csrf_token"]

    def post_form(self, path, data):
        return self.client.post(path, data={**data, "csrf_token": self.csrf()})


# --------------------------------------------------------------------------
class ModuleSettingsHelperTest(IntegrationCase):
    def test_default_simpan_timpa_dan_hapus(self):
        with self.app.app_context():
            self.assertIsNone(get_setting(1, "forum", "x"))
            self.assertEqual(get_setting(1, "forum", "x", "bawaan"), "bawaan")
            set_setting(1, "forum", "x", "a")
            set_setting(1, "forum", "x", "b")                     # upsert, bukan baris ganda
            self.assertEqual(get_setting(1, "forum", "x", "bawaan"), "b")
            set_setting(1, "forum", "n", 45)                       # nilai selalu disimpan sebagai teks
            self.assertEqual(get_setting(1, "forum", "n"), "45")
            set_setting(1, "forum", "x", None)                     # None = hapus
            self.assertEqual(get_setting(1, "forum", "x", "bawaan"), "bawaan")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE setting_key = 'x'")[0][0], 0)

    def test_terpisah_per_pengguna_dan_per_modul(self):
        with self.app.app_context():
            set_setting(1, "forum", "k", "satu")
            self.assertIsNone(get_setting(2, "forum", "k"))
            self.assertIsNone(get_setting(1, "portal", "k"))

    def test_commit_false_ikut_rollback_pemanggil(self):
        with self.app.app_context():
            from app.db import get_db
            set_setting(1, "forum", "k", "v", commit=False)
            get_db().rollback()
            self.assertIsNone(get_setting(1, "forum", "k"))

    def test_nama_kunci_tidak_dirangkai_ke_sql(self):
        with self.app.app_context():
            set_setting(1, "forum", "k'; DROP TABLE users; --", "aman")
            self.assertEqual(get_setting(1, "forum", "k'; DROP TABLE users; --"), "aman")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM users")[0][0], 2)

    def test_tidak_ada_sql_module_settings_di_modul(self):
        """Pola seragam: SQL module_settings hanya boleh ada di app/module_settings.py."""
        app_dir = os.path.join(ROOT, "app")
        for folder, _dirs, files in os.walk(app_dir):
            for name in files:
                if not name.endswith(".py") or name == "module_settings.py":
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    self.assertNotIn("module_settings", re.sub(r"(?m)^\s*#.*$|\"\"\".*?\"\"\"", "", f.read(), flags=re.S)
                                     .replace("from ..module_settings", "").replace("from .module_settings", "")
                                     .replace("'module_settings'", ""), os.path.join(folder, name))


# --------------------------------------------------------------------------
class NotificationTest(IntegrationCase):
    def setUp(self):
        super().setUp()
        rows = (
            (1, "forum", "Balasan baru: Ada jawaban", "/forum/thread/1", 0, "2026-11-14T03:00:00+00:00"),
            (1, "ecommerce", "Pesanan berhasil dibuat", None, 0, "2026-11-13T03:00:00+00:00"),
            (1, "infosys", "Kata sandi diubah", "/infosys/keamanan", 1, "2026-11-12T03:00:00+00:00"),
            (2, "forum", "Milik Budi", "/forum/", 0, "2026-11-14T04:00:00+00:00"),
        )
        for r in rows:
            self.sql("INSERT INTO notifications (user_id, module_key, message, link_url, is_read, created_at) "
                     "VALUES (?,?,?,?,?,?)", r)
        self.login(1)

    def unread(self, uid=1):
        return self.sql("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (uid,))[0][0]

    def read(self, **body):
        return self.client.post("/api/notifications/read", json=body)

    def test_lonceng_menampilkan_jumlah_panel_tautan_dan_tombol(self):
        html = self.html("/")
        self.assertRegex(html, r'data-notif-badge[^>]*>\s*2\s*<')
        self.assertIn("Notifikasi, 2 belum dibaca", html)
        self.assertIn("data-notif-read-all", html)
        self.assertIn('href="/forum/thread/1"', html)             # tautan ke asal
        self.assertIn("Pesanan berhasil dibuat", html)            # tanpa tautan tetap tampil
        self.assertNotIn("Milik Budi", html)                      # notifikasi orang lain tidak bocor

    def test_tandai_satu_dibaca_hanya_milik_sendiri(self):
        first = self.sql("SELECT id FROM notifications WHERE user_id = 1 AND is_read = 0 ORDER BY id")[0][0]
        r = self.read(id=first)
        self.assertEqual((r.status_code, r.get_json()), (200, {"ok": True, "unread": 1}))
        self.assertEqual(self.unread(1), 1)
        budi = self.sql("SELECT id FROM notifications WHERE user_id = 2")[0][0]
        self.assertEqual(self.read(id=budi).get_json()["unread"], 1)   # id orang lain diabaikan
        self.assertEqual(self.unread(2), 1)

    def test_tandai_semua_dibaca(self):
        r = self.read(all=True)
        self.assertEqual(r.get_json(), {"ok": True, "unread": 0})
        self.assertEqual(self.unread(1), 0)
        self.assertEqual(self.unread(2), 1)
        html = self.html("/")
        self.assertNotIn("data-notif-badge", html)
        self.assertIn('Notifikasi"', html)

    def test_validasi_dan_penjaga_api(self):
        for body in ({}, {"id": "1"}, {"id": True}, {"all": "ya"}, {"id": None}):
            self.assertEqual(self.read(**body).status_code, 400, body)
        self.assertEqual(self.client.post("/api/notifications/read", data="id=1").status_code, 415)
        self.assertEqual(self.client.post("/api/notifications/read", json={"all": True},
                                          headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertEqual(self.unread(1), 2)                       # semua penolakan tidak mengubah data
        guest = self.app.test_client()
        self.assertEqual(guest.post("/api/notifications/read", json={"all": True}).status_code, 401)

    def test_widget_forum_beranda_ikut_berkurang_setelah_dibaca(self):
        self.assertIn("1 balasan baru", self.html("/"))
        self.read(all=True)
        self.assertIn("Tidak ada balasan baru", self.html("/"))

    def test_guest_tidak_memuat_skrip_notifikasi(self):
        guest = self.app.test_client()
        self.assertNotIn("notif.js", guest.get("/").get_data(as_text=True))
        self.assertIn("notif.js", self.html("/"))


# --------------------------------------------------------------------------
class SmartLandingTest(IntegrationCase):
    def setUp(self):
        super().setUp()
        self.login(1)

    def set_mode(self, mode):
        return self.client.post("/api/settings/global", json={"landing_mode": mode})

    def fresh_session_client(self):
        c = self.app.test_client()
        self.login(1, c)
        return c

    def test_aktif_mengalihkan_kedatangan_pertama_lalu_mati_kembali_ke_beranda(self):
        self.assertEqual(self.client.get("/portal/").status_code, 200)         # simpan halaman terakhir
        self.assertEqual(self.set_mode("last_module").status_code, 200)
        first = self.fresh_session_client().get("/")
        self.assertEqual((first.status_code, first.headers["Location"]), (302, "/portal/"))

        self.assertEqual(self.set_mode("launcher").status_code, 200)          # dimatikan
        c = self.fresh_session_client()
        self.assertEqual(c.get("/").status_code, 200)                          # tidak lagi dialihkan

    def test_tombol_dke_tetap_membuka_beranda_saat_aktif(self):
        self.client.get("/portal/")
        self.set_mode("last_module")
        self.assertEqual(self.client.get("/").status_code, 200)               # sesi sudah mendarat

    def test_kontrol_di_beranda_menyebut_status(self):
        html = self.html("/")
        self.assertIn("Saat membuka DKE", html)
        self.assertRegex(html, r"data-landing-state>Beranda<")
        self.set_mode("last_module")
        self.assertRegex(self.html("/"), r"data-landing-state>aplikasi terakhir<")

    def test_nilai_tak_sah_ditolak(self):
        self.assertEqual(self.set_mode("acak").status_code, 400)


# --------------------------------------------------------------------------
class StatsAllModulesTest(IntegrationCase):
    def test_statistik_memuat_keenam_modul_dengan_angka_nyata(self):
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1,'portal','Umum','umum'),(2,'elearning','Umum','umum')")
        self.sql("INSERT INTO articles (id, category_id, title, slug, body) VALUES (1,1,'A','a','x'),(2,1,'B','b','y')")
        self.sql("INSERT INTO courses (id, category_id, title, slug) VALUES (1,2,'K','k')")
        self.sql("INSERT INTO quizzes (id, course_id, title, pass_score) VALUES (1,1,'Kuis',70)")
        self.sql("INSERT INTO quiz_attempts (user_id, quiz_id, score, passed) VALUES (1,1,50,0),(1,1,80,1),(1,1,90,1),(2,1,100,1)")
        for action, module in (("login", "infosys"), ("login", "infosys"), ("reply", "forum")):
            self.sql("INSERT INTO activity_logs (user_id, module_key, action) VALUES (1,?,?)", (module, action))
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) VALUES (1,'portal','preferred_categories','umum')")
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1,1)")     # kartu statistik muncul bila ada data
        self.login(1)
        html = self.html("/infosys/statistik")
        values = re.findall(r"data-stat-value>([^<]+)<", html)
        # Kuis lulus (1 kuis, bukan 2 percobaan), Artikel Portal, Kategori favorit, Aktivitas tercatat
        self.assertEqual(values[6:], ["1", "2", "1", "3"])
        self.assertIn("2 kali masuk.", html)
        self.assertIn("data-module-activity", html)
        for m in MODULES:
            self.assertIn(m["name"], html.split("data-module-activity")[1])
        self.assertIn("/infosys/log?modul=forum", html)

    def test_beranda_widget_memakai_data_nyata_semua_modul(self):
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1,'portal','Umum','umum'),(2,'etutorial','Umum','umum'),(3,'forum','Umum','umum')")
        self.sql("INSERT INTO products (id, name, slug, price) VALUES (1,'Paket Python','paket-python',100000)")
        self.sql("INSERT INTO cart_items (user_id, product_id, qty) VALUES (1,1,3)")
        self.sql("INSERT INTO tutorials (id, category_id, title, slug) VALUES (1,2,'Tutorial Git','git')")
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id) VALUES (1,1)")
        self.sql("INSERT INTO articles (id, category_id, title, slug, body, published_at) VALUES (1,1,'Artikel Terbaru Saya','terbaru','x',datetime('now'))")
        self.sql("INSERT INTO threads (id, category_id, user_id, title, body) VALUES (1,3,2,'Thread Terbaru Saya','x')")
        self.sql("INSERT INTO activity_logs (user_id, module_key, action) VALUES (1,'forum','reply'),(1,'infosys','login')")
        self.login(1)
        html = self.html("/")
        for m in MODULES:
            self.assertIn(f'data-module="{m["key"]}"', html)
        for text in ("2 aktivitas hari ini", "3 di keranjang", "1 tersimpan",
                     "1 artikel baru minggu ini"):
            self.assertIn(text, html)


# --------------------------------------------------------------------------
class SettingsUniformityTest(IntegrationCase):
    """Kelima tab Pengaturan: simpan lewat helper, tercatat di log, dan sama-sama menolak tanpa token."""

    def setUp(self):
        super().setUp()
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1,'portal','Teknologi','teknologi')")
        self.login(1)

    CASES = (
        ("ecommerce", "/ecommerce/pengaturan", {"address": "Jl. Mawar 1", "payment_method": "transfer"},
         "ecommerce_settings", {"shipping_address": "Jl. Mawar 1"}),
        ("elearning", "/elearning/pengaturan", {"playback_speed": "1.5", "daily_goal_min": "45"},
         "elearning_settings", {"playback_speed": "1.5", "daily_goal_min": "45"}),
        ("etutorial", "/etutorial/pengaturan", {"font_size": "lg"},
         "etutorial_settings", {"font_size": "lg"}),
        ("portal", "/portal/pengaturan", {"categories": "teknologi"},
         "portal_preferences", {"preferred_categories": "teknologi"}),
        ("forum", "/forum/pengaturan", {"profile_privacy": "members", "notify_reply": "0"},
         "forum_settings", {"profile_privacy": "members", "notify_reply": "0"}),
    )

    def test_setiap_tab_menyimpan_ke_module_settings_dan_mencatat_log(self):
        for module, path, data, action, expected in self.CASES:
            with self.subTest(module=module):
                r = self.post_form(path, data)
                self.assertEqual(r.status_code, 302, module)
                rows = {r_["setting_key"]: r_["setting_value"] for r_ in self.sql(
                    "SELECT setting_key, setting_value FROM module_settings WHERE user_id = 1 AND module_key = ?", (module,))}
                for key, value in expected.items():
                    self.assertEqual(rows.get(key), value, f"{module}/{key}")
                logs = self.sql("SELECT module_key FROM activity_logs WHERE user_id = 1 AND action = ?", (action,))
                self.assertEqual([x[0] for x in logs], [module])

    def test_setiap_tab_menolak_post_tanpa_token_csrf(self):
        for module, path, data, _action, _expected in self.CASES:
            with self.subTest(module=module):
                self.client.get("/")
                r = self.client.post(path, data=data)                 # tanpa csrf_token
                self.assertEqual(r.status_code, 302, module)
                self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE module_key = ?", (module,))[0][0], 0)

    def test_aksi_pengaturan_punya_label_ramah_di_log(self):
        from app.infosys.panel import ACTION_LABELS
        for _m, _p, _d, action, _e in self.CASES:
            self.assertIn(action, ACTION_LABELS)

    def test_pengaturan_milik_pengguna_lain_tidak_terbaca(self):
        self.post_form("/etutorial/pengaturan", {"font_size": "lg"})
        self.login(2)
        self.assertIn('value="md"', self.html("/etutorial/pengaturan"))   # Budi tetap bawaan


# --------------------------------------------------------------------------
class NavigationCoverageTest(IntegrationCase):
    NO_NODE_OK = {"main.ui_test", "main.ui_test_flash", "infosys.register", "infosys.login", "infosys.logout"}

    def test_semua_halaman_modul_ada_di_hierarki_navigasi(self):
        """Halaman baru tanpa node di app/navigation.py tidak punya breadcrumb/Kembali: tes ini mencegahnya."""
        from app.navigation import NAV
        missing = sorted({r.endpoint for r in self.app.url_map.iter_rules()
                          if "GET" in r.methods and r.endpoint != "static"
                          and not r.endpoint.endswith(".index") and r.endpoint not in NAV
                          and r.endpoint not in self.NO_NODE_OK})
        self.assertEqual(missing, [])

    def test_ecommerce_menampilkan_breadcrumb_dan_kembali(self):
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1,'ecommerce','Umum','umum')")
        self.sql("INSERT INTO products (id, category_id, name, slug, price) VALUES (1,1,'Paket Python','paket-python',100000)")
        self.login(1)
        for path in ("/ecommerce/keranjang", "/ecommerce/pengaturan", "/ecommerce/pesanan", "/ecommerce/produk/paket-python"):
            html = self.html(path)
            self.assertIn('aria-label="Jejak halaman"', html, path)
        self.assertIn("Paket Python", self.html("/ecommerce/produk/paket-python").split('aria-label="Jejak halaman"')[1][:900])


if __name__ == "__main__":
    unittest.main()
