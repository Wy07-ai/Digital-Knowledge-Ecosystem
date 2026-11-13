"""Tes Control Panel Information System (UC-IS-04..08).

Jalankan:  python -m unittest discover -s tests -v
Dua pengguna (Rina dan Budi) berbagi satu database supaya terbukti data tidak bocor antar akun.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOASTS = re.compile(r'id="flash-data">(.*?)</script>', re.S)


class PanelTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        for uid, name, email, pw in ((1, "Rina Putri", "rina@dke.test", "Rina12345"),
                                     (2, "Budi Santoso", "budi@dke.test", "Budi12345")):
            conn.execute("INSERT INTO users (id, full_name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
                         (uid, name, email, generate_password_hash(pw), "2026-11-01T03:00:00+00:00"))
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (uid,))
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

    def login(self, uid=1, client=None):
        with (client or self.client).session_transaction() as s:
            s["user_id"] = uid

    def html(self, path, client=None, status=200):
        r = (client or self.client).get(path)
        self.assertEqual(r.status_code, status, path)
        return r.get_data(as_text=True)

    def token(self, path="/infosys/profil"):
        return re.search(r'name="csrf_token" value="([^"]+)"', self.html(path)).group(1)

    def post_profile(self, **data):
        data.setdefault("csrf_token", self.token())
        return self.client.post("/infosys/profil", data=data)

    def post_password(self, current, new, confirm, **extra):
        return self.client.post("/infosys/profil/sandi", data={
            "csrf_token": extra.get("csrf_token") or self.token(), "current_password": current,
            "new_password": new, "confirm_password": confirm})

    def flashes(self, response_or_html):
        html = response_or_html if isinstance(response_or_html, str) else response_or_html.get_data(as_text=True)
        m = TOASTS.search(html)
        return m.group(1) if m else ""

    def add_logs(self, uid, n, module="forum", action="reply", ip="127.0.0.1"):
        for i in range(n):
            self.sql("INSERT INTO activity_logs (user_id, module_key, action, detail, ip_address, created_at) "
                     "VALUES (?,?,?,?,?,?)",
                     (uid, module, action, f"detail {module} {uid}-{i}", ip, f"2026-11-10T{i % 24:02d}:{i % 60:02d}:00+00:00"))


class AksesTest(PanelTestCase):
    def test_semua_tab_butuh_login(self):
        for path in ("/infosys/profil", "/infosys/log", "/infosys/statistik", "/infosys/keamanan"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/infosys/login?next=", r.headers["Location"])

    def test_post_tanpa_login_dialihkan(self):
        self.assertEqual(self.client.post("/infosys/profil", data={"name": "x"}).status_code, 302)
        self.assertEqual(self.client.post("/infosys/profil/sandi", data={}).status_code, 302)

    def test_guest_di_halaman_utama_melihat_ajakan_masuk(self):
        html = self.html("/infosys/")
        self.assertIn("Masuk untuk membuka Control Panel", html)
        self.assertNotIn("cp-tabs", html)

    def test_sidebar_lima_tab_dan_tab_aktif(self):
        self.login()
        html = self.html("/infosys/log")
        for label in ("Ringkasan", "Profil", "Log Aktivitas", "Statistik Lintas Modul", "Pengaturan Keamanan"):
            self.assertIn(label, html)
        self.assertEqual(len(re.findall(r'class="cp-tab[ "]', html)), 5)
        sidebar = re.search(r'<nav class="cp-tabs".*?</nav>', html, re.S).group(0)
        self.assertEqual(len(re.findall(r'aria-current="page"', sidebar)), 1)
        self.assertRegex(html, r'href="/infosys/log" class="cp-tab is-active"')


class RingkasanTest(PanelTestCase):
    def test_empty_state_akun_baru(self):
        self.login()
        html = self.html("/infosys/")
        self.assertIn('data-empty="stats"', html)
        self.assertIn('data-empty="recent"', html)
        self.assertIn("Ini login pertama Anda", html)

    def test_tanpa_tombol_kembali_di_halaman_utama(self):
        self.login()
        html = self.html("/infosys/")
        self.assertNotIn("data-back-link", html)
        self.assertNotIn("data-page-nav", html)

    def test_menampilkan_aktivitas_terbaru_milik_sendiri(self):
        self.add_logs(1, 2, "forum")
        self.add_logs(2, 2, "ecommerce", "checkout")
        self.login()
        html = self.html("/infosys/")
        self.assertIn("Balas thread", html)
        self.assertNotIn("Checkout", html)


class ProfilTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_form_terisi_dari_database(self):
        self.sql("UPDATE users SET bio = 'Halo dunia', avatar_url = 'https://img.test/a.png' WHERE id = 1")
        html = self.html("/infosys/profil")
        self.assertIn('value="Rina Putri"', html)
        self.assertIn("Halo dunia", html)
        self.assertIn('src="https://img.test/a.png"', html)

    def test_simpan_berhasil_toast_log_dan_data(self):
        r = self.post_profile(name="  Rina   Aulia  Putri ", bio="Mahasiswa TI\r\n\r\n\r\n\r\nSuka Flask",
                              avatar_url=" https://img.test/rina.png ")
        self.assertEqual(r.status_code, 302)
        u = self.sql("SELECT * FROM users WHERE id = 1")[0]
        self.assertEqual(u["full_name"], "Rina Aulia Putri")
        self.assertEqual(u["bio"], "Mahasiswa TI\n\nSuka Flask")
        self.assertEqual(u["avatar_url"], "https://img.test/rina.png")
        follow = self.client.get(r.headers["Location"])
        self.assertIn("Profil berhasil disimpan.", self.flashes(follow))
        log = self.sql("SELECT * FROM activity_logs WHERE user_id = 1 AND action = 'update_profile'")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["module_key"], "infosys")
        self.assertIn("nama", log[0]["detail"])
        self.assertNotIn("Mahasiswa", log[0]["detail"])      # isi bio tidak masuk log

    def test_bio_dan_avatar_boleh_dikosongkan(self):
        self.sql("UPDATE users SET bio = 'lama', avatar_url = 'https://a.test/x.png' WHERE id = 1")
        self.post_profile(name="Rina Putri", bio="", avatar_url="")
        u = self.sql("SELECT * FROM users WHERE id = 1")[0]
        self.assertIsNone(u["bio"])
        self.assertIsNone(u["avatar_url"])

    def test_tanpa_perubahan_toast_info_dan_tidak_dicatat(self):
        r = self.post_profile(name="Rina Putri", bio="", avatar_url="")
        self.assertEqual(r.status_code, 302)
        self.assertIn("Tidak ada perubahan", self.flashes(self.client.get(r.headers["Location"])))
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM activity_logs")[0]["n"], 0)

    def test_validasi_inline_dan_toast_error(self):
        r = self.post_profile(name="   ", bio="x" * 301, avatar_url="javascript:alert(1)")
        self.assertEqual(r.status_code, 400)
        html = r.get_data(as_text=True)
        for msg in ("Nama lengkap wajib diisi.", "Bio maksimal 300 karakter.", "Tautan avatar belum valid."):
            self.assertIn(msg, html)
        self.assertIn("Periksa kembali isian yang ditandai.", self.flashes(html))
        self.assertEqual(self.sql("SELECT full_name FROM users WHERE id = 1")[0]["full_name"], "Rina Putri")
        self.assertIn('data-focus="name"', html)

    def test_nilai_yang_salah_dikembalikan_ke_form(self):
        html = self.post_profile(name="Nama Baru", bio="x" * 301, avatar_url="").get_data(as_text=True)
        self.assertIn('value="Nama Baru"', html)

    def test_avatar_url_ditolak_untuk_skema_berbahaya_dan_spasi(self):
        for bad in ("javascript:alert(1)", "data:image/png;base64,AAAA", "ftp://x.test/a.png",
                    "//evil.test/a.png", "https://", "https://a b.test/x.png", "gambar.png",
                    "https://x.test/" + "a" * 500):
            r = self.post_profile(name="Rina Putri", bio="", avatar_url=bad)
            self.assertEqual(r.status_code, 400, bad)

    def test_nama_terlalu_panjang(self):
        r = self.post_profile(name="A" * 101, bio="", avatar_url="")
        self.assertIn("Nama lengkap maksimal 100 karakter.", r.get_data(as_text=True))

    def test_xss_di_nama_dan_bio_di_escape(self):
        self.post_profile(name="<script>alert(1)</script>", bio="<img src=x onerror=alert(1)>", avatar_url="")
        html = self.html("/infosys/profil")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<img src=x onerror", html)

    def test_csrf_salah_ditolak(self):
        r = self.client.post("/infosys/profil", data={"csrf_token": "salah", "name": "Hacker", "bio": "", "avatar_url": ""})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT full_name FROM users WHERE id = 1")[0]["full_name"], "Rina Putri")

    def test_hanya_baris_milik_sendiri_yang_berubah_walau_id_dikirim(self):
        self.post_profile(name="Rina Baru", bio="", avatar_url="", id="2", user_id="2")
        self.assertEqual(self.sql("SELECT full_name FROM users WHERE id = 2")[0]["full_name"], "Budi Santoso")
        self.assertEqual(self.sql("SELECT full_name FROM users WHERE id = 1")[0]["full_name"], "Rina Baru")


class KataSandiTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def stored_ok(self, password):
        return check_password_hash(self.sql("SELECT password_hash FROM users WHERE id = 1")[0]["password_hash"], password)

    def test_berhasil(self):
        r = self.post_password("Rina12345", "SandiBaru99", "SandiBaru99")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.stored_ok("SandiBaru99"))
        self.assertFalse(self.stored_ok("Rina12345"))
        self.assertIn("Kata sandi berhasil diubah.", self.flashes(self.client.get(r.headers["Location"])))
        self.assertEqual(len(self.sql("SELECT 1 FROM activity_logs WHERE user_id = 1 AND action = 'change_password'")), 1)
        self.assertEqual(len(self.sql("SELECT 1 FROM notifications WHERE user_id = 1 AND message LIKE 'Kata sandi diubah%'")), 1)
        self.assertEqual(self.client.get("/infosys/profil").status_code, 200)    # tetap masuk

    def test_kata_sandi_lama_salah(self):
        r = self.post_password("SalahSalah1", "SandiBaru99", "SandiBaru99")
        self.assertEqual(r.status_code, 400)
        html = r.get_data(as_text=True)
        self.assertIn("Kata sandi saat ini salah.", html)
        self.assertIn('data-focus="current_password"', html)
        self.assertTrue(self.stored_ok("Rina12345"))
        self.assertEqual(len(self.sql("SELECT 1 FROM activity_logs WHERE action = 'password_change_failed'")), 1)

    def test_validasi_format(self):
        html = self.post_password("", "pendek", "beda").get_data(as_text=True)
        for msg in ("Kata sandi saat ini wajib diisi.", "Kata sandi minimal 8 karakter.", "Konfirmasi kata sandi baru belum sama."):
            self.assertIn(msg, html)

    def test_sandi_baru_tidak_boleh_sama_dengan_lama(self):
        html = self.post_password("Rina12345", "Rina12345", "Rina12345").get_data(as_text=True)
        self.assertIn("harus berbeda", html)

    def test_batas_maksimal_128(self):
        r = self.post_password("Rina12345", "a" * 129, "a" * 129)
        self.assertIn("maksimal 128", r.get_data(as_text=True))

    def test_kata_sandi_tidak_dikirim_balik_ke_html(self):
        html = self.post_password("Rina12345", "pendek", "beda").get_data(as_text=True)
        for secret in ("Rina12345", "pendek", "beda"):
            self.assertNotIn(f'value="{secret}"', html)

    def test_terkunci_setelah_lima_kali_salah(self):
        token = self.token()
        for _ in range(5):
            self.post_password("Salah12345", "SandiBaru99", "SandiBaru99", csrf_token=token)
        r = self.post_password("Rina12345", "SandiBaru99", "SandiBaru99", csrf_token=token)   # benar, tapi terkunci
        self.assertEqual(r.status_code, 429)
        self.assertIn("Terlalu banyak percobaan", r.get_data(as_text=True))
        self.assertTrue(self.stored_ok("Rina12345"))

    def test_csrf_salah(self):
        r = self.post_password("Rina12345", "SandiBaru99", "SandiBaru99", csrf_token="salah")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.stored_ok("Rina12345"))

    def test_hanya_akun_sendiri(self):
        self.post_password("Rina12345", "SandiBaru99", "SandiBaru99")
        self.assertTrue(check_password_hash(self.sql("SELECT password_hash FROM users WHERE id = 2")[0]["password_hash"], "Budi12345"))


class LogAktivitasTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_empty_state_belum_ada_log(self):
        html = self.html("/infosys/log")
        self.assertIn("Belum ada aktivitas", html)
        self.assertNotIn("data-log-table", html)

    def test_paginasi_10_per_halaman(self):
        self.add_logs(1, 25)
        p1, p2, p3 = (self.html(f"/infosys/log?halaman={n}") for n in (1, 2, 3))
        self.assertEqual(p1.count("<tr>") - 1, 10)
        self.assertEqual(p3.count("<tr>") - 1, 5)
        self.assertIn("Menampilkan 1&ndash;10 dari 25 aktivitas", p1)
        self.assertIn("Menampilkan 21&ndash;25 dari 25 aktivitas", p3)
        self.assertIn('rel="next"', p1)
        self.assertNotIn('rel="next"', p3)
        self.assertNotEqual(re.findall(r"detail forum 1-\d+", p1), re.findall(r"detail forum 1-\d+", p2))

    def test_halaman_di_luar_rentang_dijepit(self):
        self.add_logs(1, 12)
        self.assertIn("Menampilkan 11&ndash;12 dari 12", self.html("/infosys/log?halaman=999"))
        self.assertIn("Menampilkan 1&ndash;10 dari 12", self.html("/infosys/log?halaman=-4"))
        self.assertIn("Menampilkan 1&ndash;10 dari 12", self.html("/infosys/log?halaman=abc"))

    def test_filter_modul(self):
        self.add_logs(1, 3, "forum", "reply")
        self.add_logs(1, 2, "ecommerce", "checkout")
        html = self.html("/infosys/log?modul=ecommerce")
        self.assertEqual(html.count("<tr>") - 1, 2)
        self.assertIn("Menampilkan 1&ndash;2 dari 2", html)
        self.assertNotIn("Balas thread", html)
        self.assertRegex(html, r'<option value="ecommerce" selected>')
        self.assertIn("Hapus filter", html)

    def test_filter_dan_paginasi_berjalan_bersama(self):
        self.add_logs(1, 14, "forum")
        self.add_logs(1, 3, "ecommerce", "checkout")
        html = self.html("/infosys/log?modul=forum")
        self.assertIn("dari 14 aktivitas", html)
        self.assertIn("/infosys/log?modul=forum&amp;halaman=2", html)    # filter terbawa di tautan halaman

    def test_empty_state_filter_tanpa_hasil(self):
        self.add_logs(1, 2, "forum")
        html = self.html("/infosys/log?modul=portal")
        self.assertIn("Belum ada aktivitas di modul ini", html)
        self.assertIn("Tampilkan semua", html)

    def test_filter_tak_dikenal_diabaikan_aman(self):
        self.add_logs(1, 2, "forum")
        for bad in ("hacker", "forum' OR '1'='1", "'; DROP TABLE users;--"):
            html = self.client.get("/infosys/log", query_string={"modul": bad}).get_data(as_text=True)
            self.assertIn("Filter modul tidak dikenal", html)
            self.assertIn("dari 2 aktivitas", html)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM users")[0]["n"], 2)

    def test_data_pengguna_lain_tidak_pernah_tampil(self):
        self.add_logs(1, 3, "forum")
        self.add_logs(2, 7, "forum")
        for path in ("/infosys/log", "/infosys/log?modul=forum", "/infosys/log?user_id=2", "/infosys/log?uid=2&halaman=1"):
            html = self.html(path)
            self.assertIn("dari 3 aktivitas", html, path)
            self.assertNotIn("forum 2-", html, path)

    def test_label_aksi_dan_waktu_wib(self):
        self.sql("INSERT INTO activity_logs (user_id, module_key, action, detail, created_at) VALUES (1,'elearning','enroll','Kursus X','2026-11-13T03:06:00+00:00')")
        html = self.html("/infosys/log")
        self.assertIn("Ikut kelas", html)
        self.assertIn("13 Nov 2026, 10:06 WIB", html)

    def test_detail_di_escape(self):
        self.sql("INSERT INTO activity_logs (user_id, module_key, action, detail, created_at) VALUES (1,'forum','create_thread','<b>tebal</b>','2026-11-13T03:06:00+00:00')")
        html = self.html("/infosys/log")
        self.assertNotIn("<b>tebal</b>", html)
        self.assertIn("&lt;b&gt;tebal&lt;/b&gt;", html)


class StatistikTest(PanelTestCase):
    def seed_content(self):
        self.sql("INSERT INTO categories (id, module_key, name, slug) VALUES (1,'elearning','Umum','umum'),(2,'etutorial','Umum','umum'),(3,'forum','Umum','umum')")
        for cid, title in ((1, "Python Dasar"), (2, "Desain UI")):
            self.sql("INSERT INTO courses (id, category_id, title, slug) VALUES (?,1,?,?)", (cid, title, f"c{cid}"))
            for n in range(1, 5):
                self.sql("INSERT INTO lessons (id, course_id, order_no, title) VALUES (?,?,?,?)", (cid * 10 + n, cid, n, f"M{n}"))
        self.sql("INSERT INTO tutorials (id, title, slug) VALUES (1,'T1','t1'),(2,'T2','t2')")
        self.sql("INSERT INTO products (id, name, slug, price) VALUES (1,'Kelas','p1',100000)")
        self.sql("INSERT INTO threads (id, category_id, user_id, title, body) VALUES (1,3,1,'A','a'),(2,3,1,'B','b'),(3,3,2,'C','c')")

    def test_empty_state_bila_semua_nol(self):
        self.login()
        html = self.html("/infosys/statistik")
        self.assertIn("Belum ada statistik", html)
        self.assertNotIn("data-stat-card", html)

    def test_kartu_dan_angka_milik_sendiri(self):
        self.seed_content()
        # Rina: 2 pesanan (1 paid 100000, 1 cancelled), 2 kelas, progres 2/4 dan 4/4, 1 bookmark, 2 thread, 3 balasan
        self.sql("INSERT INTO orders (id, order_code, user_id, total, status) VALUES (1,'DKE-1',1,100000,'paid'),(2,'DKE-2',1,50000,'cancelled'),(3,'DKE-3',2,999000,'paid')")
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1,1),(1,2),(2,1)")
        for lid in (11, 12, 21, 22, 23, 24):
            self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1,?)", (lid,))
        for lid in (11, 12, 13, 14):
            self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (2,?)", (lid,))
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id) VALUES (1,1),(2,1),(2,2)")
        self.sql("INSERT INTO posts (thread_id, user_id, body) VALUES (3,1,'x'),(3,1,'y'),(1,1,'z'),(3,2,'q'),(3,2,'r')")
        self.login()
        html = self.html("/infosys/statistik")
        values = re.findall(r'data-stat-value>([^<]+)<', html)
        self.assertEqual(values, ["2", "2", "75%", "1", "2", "3"])
        self.assertIn("Total belanja Rp 100.000", html)           # hanya pesanan paid milik Rina
        self.assertIn("2 dari 4 materi", html)
        self.assertIn("4 dari 4 materi", html)
        self.assertNotIn("999.000", html)

    def test_statistik_pengguna_lain_tidak_bocor(self):
        self.seed_content()
        self.sql("DELETE FROM threads WHERE user_id = 1")          # Rina tidak punya data apa pun
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (2,1)")
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id) VALUES (2,1)")
        self.login(1)
        self.assertIn("Belum ada statistik", self.html("/infosys/statistik"))   # Rina tidak punya data sama sekali, walau Budi punya
        self.login(2)
        self.assertIn("data-stat-card", self.html("/infosys/statistik"))

    def test_sebagian_kosong_kartu_tetap_tampil_dengan_petunjuk(self):
        self.seed_content()
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id) VALUES (1,1)")
        self.login()
        html = self.html("/infosys/statistik")
        self.assertIn("Belum ada pesanan.", html)
        self.assertIn("Muncul setelah Anda mengikuti kelas.", html)
        self.assertIn('data-empty="courses"', html)
        self.assertIn('data-stat-value>-<', html)

    def test_kelas_tanpa_materi_tidak_merusak_rata_rata(self):
        self.sql("INSERT INTO courses (id, title, slug) VALUES (9,'Kosong','kosong')")
        self.sql("INSERT INTO enrollments (user_id, course_id) VALUES (1,9)")
        self.login()
        html = self.html("/infosys/statistik")
        self.assertIn("Belum ada materi", html)
        self.assertIn('data-stat-value>-<', html)


class KeamananTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_empty_state_tanpa_riwayat(self):
        html = self.html("/infosys/keamanan")
        self.assertIn("Belum ada riwayat login", html)

    def test_hanya_login_milik_sendiri(self):
        self.add_logs(1, 3, "infosys", "login", "10.0.0.1")
        self.add_logs(2, 4, "infosys", "login", "10.9.9.9")
        self.add_logs(1, 2, "forum", "reply", "10.7.7.7")        # bukan login
        html = self.html("/infosys/keamanan")
        self.assertIn("dari 3 login", html)
        self.assertIn("10.0.0.1", html)
        self.assertNotIn("10.9.9.9", html)
        self.assertNotIn("10.7.7.7", html)

    def test_paginasi_riwayat_login(self):
        self.add_logs(1, 13, "infosys", "login")
        self.assertIn("dari 13 login", self.html("/infosys/keamanan"))
        p2 = self.html("/infosys/keamanan?halaman=2")
        self.assertIn("Menampilkan 11&ndash;13 dari 13 login", p2)
        self.assertNotIn("Terbaru", p2)

    def test_peringatan_bila_banyak_ip(self):
        self.add_logs(1, 1, "infosys", "login", "10.0.0.1")
        self.assertNotIn('data-note="ip"', self.html("/infosys/keamanan"))
        self.add_logs(1, 1, "infosys", "login", "10.0.0.2")
        self.assertIn('data-note="ip"', self.html("/infosys/keamanan"))

    def test_login_nyata_tercatat_dan_tampil(self):
        guest = self.app.test_client()
        token = re.search(r'name="csrf_token" value="([^"]+)"', guest.get("/infosys/login").get_data(as_text=True)).group(1)
        guest.post("/infosys/login", data={"email": "rina@dke.test", "password": "Rina12345", "csrf_token": token})
        html = guest.get("/infosys/keamanan").get_data(as_text=True)
        self.assertIn("dari 1 login", html)
        self.assertIn("Terbaru", html)


class NavigasiTest(PanelTestCase):
    def test_breadcrumb_dua_jenjang_di_semua_tab(self):
        self.login()
        for path in ("/infosys/profil", "/infosys/log", "/infosys/statistik", "/infosys/keamanan"):
            html = self.html(path)
            self.assertEqual(re.search(r'<a href="([^"]+)"[^>]*data-back-link', html).group(1), "/infosys/", path)
            self.assertEqual(len(re.findall(r'class="bc-item', html)), 2, path)


if __name__ == "__main__":
    unittest.main()
