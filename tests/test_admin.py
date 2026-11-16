"""Tes Admin minimal (UC-AD-01 kelola konten, UC-AD-02 moderasi).

Yang dibuktikan:
  * Guest -> login; Member biasa -> 403 di SEMUA rute admin (GET dan POST), tanpa mengubah data.
  * Admin berhasil: daftar, hapus thread (cascade), hapus balasan (anak naik, solusi dibatalkan),
    nonaktifkan/aktifkan akun.
  * Setiap aksi admin tercatat di activity_logs (user_id admin, action admin_*).
  * CSRF wajib; admin tak bisa menonaktifkan diri sendiri/admin lain; akun nonaktif langsung kehilangan sesi.
  * Forum tetap menolak admin mengubah/menghapus balasan orang lain (moderasi hanya lewat halaman admin).

Jalankan:  python -m unittest tests.test_admin -v
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORDS = {"admin@dke.test": "Pengelola-Uji-2026", "rina@dke.test": "Rina12345", "budi@dke.test": "Budi12345"}


class AdminTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        users = ((1, "Admin DKE", "admin@dke.test", "admin"), (2, "Rina Putri", "rina@dke.test", "member"),
                 (3, "Budi Santoso", "budi@dke.test", "member"))
        for uid, name, email, role in users:
            conn.execute("INSERT INTO users (id, full_name, email, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
                         (uid, name, email, generate_password_hash(PASSWORDS[email]), role, "2026-11-01T03:00:00+00:00"))
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (uid,))
        conn.execute("INSERT INTO categories (id, module_key, name, slug) VALUES (1, 'forum', 'Umum', 'umum')")
        conn.execute("INSERT INTO threads (id, category_id, user_id, title, body, created_at, updated_at) "
                     "VALUES (10, 1, 2, 'Thread milik Rina', 'Isi thread Rina cukup panjang', '2026-11-02T03:00:00+00:00', '2026-11-02T03:00:00+00:00')")
        conn.execute("INSERT INTO threads (id, category_id, user_id, title, body, created_at, updated_at) "
                     "VALUES (11, 1, 3, 'Thread milik Budi', 'Isi thread Budi cukup panjang', '2026-11-03T03:00:00+00:00', '2026-11-03T03:00:00+00:00')")
        # Thread 10: balasan 100 (Budi, tingkat atas) <- 101 (Rina, anak 100) <- 102 (Budi, anak 101). 100 = solusi.
        for pid, uid, parent, body in ((100, 3, None, "Balasan tingkat atas"), (101, 2, 100, "Balasan anak satu"),
                                       (102, 3, 101, "Balasan anak dua")):
            conn.execute("INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (?,?,?,?,?,?)",
                         (pid, 10, uid, parent, body, "2026-11-02T04:00:00+00:00"))
        conn.execute("UPDATE threads SET is_solved = 1, accepted_post_id = 100 WHERE id = 10")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})

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

    def login(self, email):
        client = self.app.test_client()
        html = client.get("/infosys/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        r = client.post("/infosys/login", data={"csrf_token": token, "email": email, "password": PASSWORDS[email]})
        self.assertEqual(r.status_code, 302, f"login {email} gagal")
        return client

    @staticmethod
    def token(client, path):
        html = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def admin_logs(self, action=None):
        sql, params = "SELECT * FROM activity_logs WHERE action LIKE 'admin\\_%' ESCAPE '\\'", []
        if action:
            sql, params = "SELECT * FROM activity_logs WHERE action = ?", [action]
        return self.sql(sql + " ORDER BY id", params)

    def snapshot(self):
        return (self.sql("SELECT id FROM threads ORDER BY id"), self.sql("SELECT id, parent_post_id FROM posts ORDER BY id"),
                self.sql("SELECT id, is_active FROM users ORDER BY id"))


ADMIN_ROUTES = (
    "/infosys/admin",
    "/infosys/admin?tab=balasan",
    "/infosys/admin?tab=akun",
    "/infosys/admin/thread/10/hapus",
    "/infosys/admin/balasan/101/hapus",
    "/infosys/admin/akun/3/nonaktifkan",
    "/infosys/admin/akun/3/aktifkan",
)


class AccessControlTests(AdminTestCase):
    def test_guest_diarahkan_ke_login(self):
        client = self.app.test_client()
        for path in ADMIN_ROUTES:
            with self.subTest(path=path):
                r = client.get(path)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/infosys/login", r.headers["Location"])

    def test_non_admin_mendapat_403_di_semua_rute_get(self):
        client = self.login("rina@dke.test")
        for path in ADMIN_ROUTES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)

    def test_non_admin_mendapat_403_di_semua_rute_post_dan_data_tidak_berubah(self):
        client = self.login("rina@dke.test")
        token = self.token(client, "/infosys/profil")
        before = self.snapshot()
        for path in [p for p in ADMIN_ROUTES if "/hapus" in p or "/nonaktifkan" in p or "/aktifkan" in p]:
            with self.subTest(path=path):
                r = client.post(path, data={"csrf_token": token})  # token SAH, tetap ditolak karena bukan admin
                self.assertEqual(r.status_code, 403)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.admin_logs()), 0)

    def test_non_admin_tidak_melihat_tab_admin(self):
        html = self.login("rina@dke.test").get("/infosys/profil").get_data(as_text=True)
        self.assertNotIn("/infosys/admin", html)

    def test_admin_melihat_tab_admin(self):
        html = self.login("admin@dke.test").get("/infosys/profil").get_data(as_text=True)
        self.assertIn('href="/infosys/admin"', html)

    def test_peran_diperiksa_dari_database_bukan_dari_cookie(self):
        """Admin diturunkan jadi member -> langsung 403 pada permintaan berikutnya."""
        client = self.login("admin@dke.test")
        self.assertEqual(client.get("/infosys/admin").status_code, 200)
        self.sql("UPDATE users SET role = 'member' WHERE id = 1")
        self.assertEqual(client.get("/infosys/admin").status_code, 403)


class AdminListTests(AdminTestCase):
    def test_admin_melihat_daftar_thread_balasan_akun(self):
        client = self.login("admin@dke.test")
        html = client.get("/infosys/admin").get_data(as_text=True)
        self.assertIn("Thread milik Rina", html)
        self.assertIn("Thread milik Budi", html)
        self.assertIn('href="/infosys/admin/thread/10/hapus"', html)
        html = client.get("/infosys/admin?tab=balasan").get_data(as_text=True)
        self.assertIn("Balasan anak satu", html)
        self.assertIn('href="/infosys/admin/balasan/101/hapus"', html)
        html = client.get("/infosys/admin?tab=akun").get_data(as_text=True)
        self.assertIn("rina@dke.test", html)
        self.assertIn('href="/infosys/admin/akun/3/nonaktifkan"', html)
        self.assertNotIn('href="/infosys/admin/akun/1/nonaktifkan"', html)  # admin tidak punya tombol nonaktifkan

    def test_tab_dan_halaman_tidak_sah_diperlakukan_aman(self):
        client = self.login("admin@dke.test")
        self.assertEqual(client.get("/infosys/admin?tab=ngawur&halaman=abc").status_code, 200)
        self.assertEqual(client.get("/infosys/admin?tab=akun&halaman=999").status_code, 200)

    def test_isi_pengguna_di_escape(self):
        self.sql("UPDATE threads SET title = ? WHERE id = 10", ("<script>alert(1)</script>",))
        html = self.login("admin@dke.test").get("/infosys/admin").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)


class DeleteThreadTests(AdminTestCase):
    def test_halaman_konfirmasi_tidak_menghapus(self):
        client = self.login("admin@dke.test")
        r = client.get("/infosys/admin/thread/10/hapus")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Hapus topik ini?", r.get_data(as_text=True))
        self.assertEqual(len(self.sql("SELECT id FROM threads WHERE id = 10")), 1)

    def test_admin_menghapus_thread_beserta_balasan_dan_tercatat(self):
        client = self.login("admin@dke.test")
        token = self.token(client, "/infosys/admin/thread/10/hapus")
        r = client.post("/infosys/admin/thread/10/hapus", data={"csrf_token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT id FROM threads WHERE id = 10"), [])
        self.assertEqual(self.sql("SELECT id FROM posts WHERE thread_id = 10"), [])
        self.assertEqual(len(self.sql("SELECT id FROM threads WHERE id = 11")), 1)  # thread lain utuh
        logs = self.admin_logs("admin_delete_thread")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user_id"], 1)
        self.assertEqual(logs[0]["module_key"], "infosys")
        self.assertIn("Thread milik Rina", logs[0]["detail"])
        self.assertIn("3 balasan", logs[0]["detail"])

    def test_tanpa_csrf_ditolak_dan_tidak_menghapus(self):
        client = self.login("admin@dke.test")
        r = client.post("/infosys/admin/thread/10/hapus", data={"csrf_token": "palsu"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(self.sql("SELECT id FROM threads WHERE id = 10")), 1)
        self.assertEqual(len(self.admin_logs()), 0)
        r = client.post("/infosys/admin/thread/10/hapus")  # tanpa field sama sekali
        self.assertEqual(len(self.sql("SELECT id FROM threads WHERE id = 10")), 1)

    def test_thread_tak_ada_404(self):
        client = self.login("admin@dke.test")
        self.assertEqual(client.get("/infosys/admin/thread/999/hapus").status_code, 404)
        token = self.token(client, "/infosys/admin")
        self.assertEqual(client.post("/infosys/admin/thread/999/hapus", data={"csrf_token": token}).status_code, 404)


class DeletePostTests(AdminTestCase):
    def test_admin_menghapus_balasan_anak_naik_solusi_dibatalkan_dan_tercatat(self):
        client = self.login("admin@dke.test")
        page = client.get("/infosys/admin/balasan/100/hapus").get_data(as_text=True)
        self.assertIn("naik satu tingkat", page)
        self.assertIn("solusi", page)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        r = client.post("/infosys/admin/balasan/100/hapus", data={"csrf_token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT id FROM posts WHERE id = 100"), [])
        self.assertIsNone(self.sql("SELECT parent_post_id FROM posts WHERE id = 101")[0][0])  # anak naik jadi tingkat atas
        self.assertEqual(self.sql("SELECT parent_post_id FROM posts WHERE id = 102")[0][0], 101)
        thread = self.sql("SELECT is_solved, accepted_post_id FROM threads WHERE id = 10")[0]
        self.assertEqual((thread[0], thread[1]), (0, None))
        logs = self.admin_logs("admin_delete_reply")
        self.assertEqual(len(logs), 1)
        self.assertEqual((logs[0]["user_id"], logs[0]["module_key"]), (1, "infosys"))
        self.assertIn("#100", logs[0]["detail"])

    def test_tanpa_csrf_tidak_menghapus(self):
        client = self.login("admin@dke.test")
        client.post("/infosys/admin/balasan/101/hapus", data={"csrf_token": "palsu"})
        self.assertEqual(len(self.sql("SELECT id FROM posts WHERE id = 101")), 1)
        self.assertEqual(len(self.admin_logs()), 0)

    def test_balasan_tak_ada_404(self):
        self.assertEqual(self.login("admin@dke.test").get("/infosys/admin/balasan/999/hapus").status_code, 404)

    def test_forum_tetap_menolak_admin_mengubah_balasan_orang_lain(self):
        client = self.login("admin@dke.test")
        self.assertEqual(client.get("/forum/balasan/101/ubah").status_code, 403)
        self.assertEqual(client.get("/forum/balasan/101/hapus").status_code, 403)


class UserStatusTests(AdminTestCase):
    def test_admin_menonaktifkan_lalu_mengaktifkan_akun_dan_tercatat(self):
        client = self.login("admin@dke.test")
        token = self.token(client, "/infosys/admin/akun/3/nonaktifkan")
        r = client.post("/infosys/admin/akun/3/nonaktifkan", data={"csrf_token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT is_active FROM users WHERE id = 3")[0][0], 0)
        log = self.admin_logs("admin_deactivate_user")
        self.assertEqual(len(log), 1)
        self.assertEqual((log[0]["user_id"], log[0]["module_key"]), (1, "infosys"))
        self.assertIn("budi@dke.test", log[0]["detail"])

        token = self.token(client, "/infosys/admin/akun/3/aktifkan")
        r = client.post("/infosys/admin/akun/3/aktifkan", data={"csrf_token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT is_active FROM users WHERE id = 3")[0][0], 1)
        self.assertEqual(len(self.admin_logs("admin_activate_user")), 1)

    def test_akun_nonaktif_kehilangan_sesi_dan_tidak_bisa_login(self):
        budi = self.login("budi@dke.test")
        self.assertEqual(budi.get("/forum/buat").status_code, 200)
        admin = self.login("admin@dke.test")
        token = self.token(admin, "/infosys/admin/akun/3/nonaktifkan")
        admin.post("/infosys/admin/akun/3/nonaktifkan", data={"csrf_token": token})
        r = budi.get("/forum/buat")                       # sesi lama langsung tidak berlaku
        self.assertEqual(r.status_code, 302)
        self.assertIn("/infosys/login", r.headers["Location"])
        fresh = self.app.test_client()
        html = fresh.get("/infosys/login").get_data(as_text=True)
        t = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        r = fresh.post("/infosys/login", data={"csrf_token": t, "email": "budi@dke.test", "password": PASSWORDS["budi@dke.test"]})
        self.assertEqual(r.status_code, 403)

    def test_tidak_bisa_menonaktifkan_diri_sendiri_atau_admin_lain(self):
        self.sql("INSERT INTO users (id, full_name, email, password_hash, role) VALUES (4, 'Admin Dua', 'admin2@dke.test', 'x', 'admin')")
        client = self.login("admin@dke.test")
        token = self.token(client, "/infosys/admin")
        for uid in (1, 4):
            with self.subTest(uid=uid):
                client.get(f"/infosys/admin/akun/{uid}/nonaktifkan")
                client.post(f"/infosys/admin/akun/{uid}/nonaktifkan", data={"csrf_token": token})
                self.assertEqual(self.sql("SELECT is_active FROM users WHERE id = ?", (uid,))[0][0], 1)
        self.assertEqual(len(self.admin_logs()), 0)

    def test_tanpa_csrf_tidak_mengubah_status(self):
        client = self.login("admin@dke.test")
        client.post("/infosys/admin/akun/3/nonaktifkan", data={"csrf_token": "palsu"})
        self.assertEqual(self.sql("SELECT is_active FROM users WHERE id = 3")[0][0], 1)
        self.assertEqual(len(self.admin_logs()), 0)

    def test_akun_tak_ada_404(self):
        self.assertEqual(self.login("admin@dke.test").get("/infosys/admin/akun/999/nonaktifkan").status_code, 404)


class AdminLogVisibleTests(AdminTestCase):
    def test_aksi_admin_tampil_di_log_aktivitas_admin_dengan_label_ramah(self):
        client = self.login("admin@dke.test")
        token = self.token(client, "/infosys/admin/balasan/102/hapus")
        client.post("/infosys/admin/balasan/102/hapus", data={"csrf_token": token})
        html = client.get("/infosys/log").get_data(as_text=True)
        self.assertIn("Admin: hapus balasan", html)


if __name__ == "__main__":
    unittest.main()
