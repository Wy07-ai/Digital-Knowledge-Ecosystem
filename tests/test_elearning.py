"""Tes E-Learning bagian 1: daftar kelas, enroll gratis, Kelas Saya, Ruang Belajar, progres, pengaturan."""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit

from werkzeug.security import generate_password_hash

from app import create_app
from app.elearning.routes import progress_percent, text_blocks, video_embed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ElearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.executemany(
            "INSERT INTO users (id, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            ((1, "Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345")),
             (2, "Orang Lain", "lain@dke.test", generate_password_hash("Lain12345"))),
        )
        conn.executemany(
            "INSERT INTO categories (id, module_key, name, slug) VALUES (?, ?, ?, ?)",
            ((1, "elearning", "Pemrograman", "pemrograman"), (2, "ecommerce", "Kursus Digital", "kursus-digital")),
        )
        conn.executemany(
            "INSERT INTO courses (id, category_id, title, slug, description, level, instructor_name) "
            "VALUES (?, 1, ?, ?, ?, ?, 'Pengajar Uji')",
            ((1, "Desain Dasar", "desain-dasar", "Kelas gratis.", "pemula"),          # gratis (tanpa produk)
             (2, "Python Menengah", "python-menengah", "Kelas berbayar.", "menengah"),  # berbayar
             (3, "Algoritma Lanjut", "algoritma-lanjut", "Kelas lanjut gratis.", "lanjut")),
        )
        conn.executemany(
            "INSERT INTO lessons (id, course_id, order_no, title, content_type, content_body, video_url, duration_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ((1, 1, 1, "Apa itu desain", "text", "Paragraf satu.\n\n    print('halo')\n\nPenutup <b>tebal</b>.", None, 10),
             (2, 1, 2, "Warna dan kontras", "video", "Catatan video.", "https://www.youtube.com/watch?v=rfscVS0vtbw", 20),
             (3, 1, 3, "Tipografi", "text", "Isi tipografi.", None, 30),
             (4, 1, 4, "Tata letak", "text", "Isi tata letak.", None, 40),
             (5, 2, 1, "Mulai Python", "text", "Isi python.", None, 15),
             (6, 2, 2, "Fungsi", "text", "Isi fungsi.", None, 15),
             (7, 3, 1, "Big-O", "text", "Isi big-o.", None, 5)),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, course_id, name, slug, description, price, product_type) "
            "VALUES (1, 2, 2, 'Kursus Python Menengah', 'kursus-python-menengah', 'Beli', 150000, 'course')"
        )
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- pembantu ----
    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute(statement, params).fetchall()
            conn.commit()
            return result
        finally:
            conn.close()

    def login(self, user_id=1, client=None):
        with (client or self.client).session_transaction() as session:
            session["user_id"] = user_id

    def csrf(self, client=None):
        """Token CSRF sesi (Member harus sudah login); diambil dari formulir Pengaturan."""
        html = (client or self.client).get("/elearning/pengaturan").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def enroll_direct(self, course_id, user_id=1, source="free"):
        self.sql("INSERT INTO enrollments (user_id, course_id, source) VALUES (?, ?, ?)", (user_id, course_id, source))

    def complete(self, lesson_id, completed=True, token=None, client=None, **headers):
        client = client or self.client
        token = token if token is not None else self.csrf(client)
        return client.post(
            f"/elearning/api/materi/{lesson_id}/selesai",
            json={"completed": completed},
            headers={"X-CSRF-Token": token, **headers},
        )

    # ---- UC-EL-01: daftar kelas dan filter level ----
    def test_guest_sees_course_list_and_level_filter(self):
        html = self.client.get("/elearning/").get_data(as_text=True)
        for title in ("Desain Dasar", "Python Menengah", "Algoritma Lanjut"):
            self.assertIn(title, html)
        self.assertIn("Gratis", html)
        self.assertIn("Rp 150.000", html)

        html = self.client.get("/elearning/?level=menengah").get_data(as_text=True)
        self.assertIn("Python Menengah", html)
        self.assertNotIn("Desain Dasar", html)
        self.assertNotIn("Algoritma Lanjut", html)

    def test_unknown_level_falls_back_to_all_courses_with_note(self):
        html = self.client.get("/elearning/?level=ngawur").get_data(as_text=True)
        self.assertIn("Filter level tidak dikenal", html)
        self.assertIn("Desain Dasar", html)
        self.assertIn("Algoritma Lanjut", html)

    def test_level_without_courses_shows_empty_state(self):
        self.sql("DELETE FROM lessons WHERE course_id = 3")
        self.sql("DELETE FROM courses WHERE id = 3")
        html = self.client.get("/elearning/?level=lanjut").get_data(as_text=True)
        self.assertIn("Belum ada kelas level lanjut", html)

    def test_unpublished_course_is_hidden_and_not_found(self):
        self.sql("UPDATE courses SET is_published = 0 WHERE id = 1")
        self.assertNotIn("Desain Dasar", self.client.get("/elearning/").get_data(as_text=True))
        self.assertEqual(self.client.get("/elearning/kelas/1").status_code, 404)

    def test_course_detail_is_public_and_lists_lessons_without_links(self):
        response = self.client.get("/elearning/kelas/1")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tipografi", html)
        self.assertNotIn("/elearning/kelas/1/materi/1", html)  # tautan materi hanya untuk peserta
        self.assertIn("Masuk untuk mengikuti kelas", html)
        self.assertEqual(self.client.get("/elearning/kelas/999").status_code, 404)

    def test_paid_course_detail_points_to_ecommerce(self):
        html = self.client.get("/elearning/kelas/2").get_data(as_text=True)
        self.assertIn("/ecommerce/produk/kursus-python-menengah", html)
        self.assertNotIn("Ikuti kelas gratis", html)

    # ---- UC-EL-02: enroll kelas gratis ----
    def test_guest_enroll_redirects_to_login(self):
        response = self.client.post("/elearning/kelas/1/daftar", data={"csrf_token": "x"},
                                    headers={"Referer": "http://localhost/elearning/kelas/1"})
        self.assertEqual(urlsplit(response.location).path, "/infosys/login")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM enrollments")[0][0], 0)

    def test_member_enrolls_free_course_and_lands_in_lesson_one(self):
        self.login()
        html = self.client.get("/elearning/kelas/1").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        self.assertIn("Ikuti kelas gratis", html)
        response = self.client.post("/elearning/kelas/1/daftar", data={"csrf_token": token})
        self.assertEqual(urlsplit(response.location).path, "/elearning/kelas/1/materi/1")
        self.assertEqual(self.sql("SELECT user_id, course_id, source, order_id FROM enrollments"), [(1, 1, "free", None)])
        self.assertEqual(self.sql("SELECT module_key, action FROM activity_logs"), [("elearning", "enroll")])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 1)

        # Kelas Saya langsung memuatnya
        self.assertIn("Desain Dasar", self.client.get("/elearning/kelas-saya").get_data(as_text=True))

    def test_enroll_twice_does_not_duplicate(self):
        self.login()
        token = self.csrf()
        for _ in range(2):
            self.client.post("/elearning/kelas/1/daftar", data={"csrf_token": token})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM enrollments")[0][0], 1)

    def test_enroll_requires_valid_csrf(self):
        self.login()
        self.client.post("/elearning/kelas/1/daftar", data={"csrf_token": "salah"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM enrollments")[0][0], 0)

    def test_paid_course_cannot_be_enrolled_for_free(self):
        self.login()
        response = self.client.post("/elearning/kelas/2/daftar", data={"csrf_token": self.csrf()}, follow_redirects=True)
        self.assertIn("Kelas ini berbayar", response.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM enrollments")[0][0], 0)

    # ---- Pembelian -> Kelas Saya ----
    def test_purchased_course_appears_in_my_courses_immediately(self):
        self.login()
        self.assertIn("Belum mengikuti kelas", self.client.get("/elearning/kelas-saya").get_data(as_text=True))
        self.sql("INSERT INTO cart_items (user_id, product_id, qty) VALUES (1, 1, 1)")
        html = self.client.get("/ecommerce/checkout").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        response = self.client.post("/ecommerce/checkout", data={
            "csrf_token": token, "address": "Jl. Melati 1, Bandung", "payment_method": "transfer"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT course_id, source FROM enrollments"), [(2, "order")])

        order_page = self.client.get(response.location).get_data(as_text=True)
        self.assertIn("Mulai belajar di Kelas Saya", order_page)
        mine = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("Python Menengah", mine)
        self.assertIn("Mulai belajar", mine)
        # dan ruang belajarnya terbuka
        self.assertEqual(self.client.get("/elearning/kelas/2/materi/1").status_code, 200)

    # ---- Akses Ruang Belajar ----
    def test_learning_room_denies_guest_and_unenrolled_member(self):
        guest = self.client.get("/elearning/kelas/1/materi/1")
        self.assertEqual(urlsplit(guest.location).path, "/infosys/login")

        self.login()
        denied = self.client.get("/elearning/kelas/1/materi/1")
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(urlsplit(denied.location).path, "/elearning/kelas/1")
        page = self.client.get(denied.location).get_data(as_text=True)
        self.assertIn("Anda belum terdaftar di kelas ini", page)
        self.assertNotIn("Paragraf satu", page)

    def test_enrollment_in_one_course_does_not_open_another(self):
        self.enroll_direct(1)
        self.login()
        self.assertEqual(self.client.get("/elearning/kelas/1/materi/1").status_code, 200)
        self.assertEqual(self.client.get("/elearning/kelas/3/materi/1").status_code, 302)

    def test_other_users_enrollment_does_not_grant_access(self):
        self.enroll_direct(1, user_id=2)
        self.login(1)
        self.assertEqual(self.client.get("/elearning/kelas/1/materi/1").status_code, 302)

    def test_missing_lesson_is_404_for_enrolled_member(self):
        self.enroll_direct(1)
        self.login()
        self.assertEqual(self.client.get("/elearning/kelas/1/materi/99").status_code, 404)

    # ---- UC-EL-03: ruang belajar ----
    def test_learning_room_shows_text_content_sidebar_and_navigation(self):
        self.enroll_direct(1)
        self.login()
        html = self.client.get("/elearning/kelas/1/materi/1").get_data(as_text=True)
        self.assertIn("Paragraf satu.", html)
        self.assertIn("<pre", html)
        self.assertIn("print(&#39;halo&#39;)", html)
        self.assertIn("&lt;b&gt;tebal&lt;/b&gt;", html)            # konten di-escape
        for title in ("Apa itu desain", "Warna dan kontras", "Tipografi", "Tata letak"):
            self.assertIn(title, html)                              # sidebar daftar bab
        self.assertIn('href="/elearning/kelas/1/materi/2"', html)
        self.assertNotIn('rel="prev"', html)                        # materi pertama tak punya "sebelumnya"
        self.assertIn("Tandai Selesai", html)

        middle = self.client.get("/elearning/kelas/1/materi/3").get_data(as_text=True)
        self.assertIn('rel="prev"', middle)
        self.assertIn('rel="next"', middle)
        last = self.client.get("/elearning/kelas/1/materi/4").get_data(as_text=True)
        self.assertIn("Ini materi terakhir", last)
        self.assertNotIn('rel="next"', last)

    def test_video_lesson_embeds_only_supported_hosts(self):
        self.enroll_direct(1)
        self.login()
        html = self.client.get("/elearning/kelas/1/materi/2").get_data(as_text=True)
        self.assertIn("https://www.youtube-nocookie.com/embed/rfscVS0vtbw", html)
        self.assertIn("Catatan video.", html)

        self.sql("UPDATE lessons SET video_url = 'https://evil.example/x.html' WHERE id = 2")
        html = self.client.get("/elearning/kelas/1/materi/2").get_data(as_text=True)
        self.assertNotIn("<iframe", html)
        self.assertIn("Video belum bisa ditampilkan", html)

    def test_video_embed_parser(self):
        self.assertEqual(video_embed("https://youtu.be/rfscVS0vtbw")["kind"], "youtube")
        self.assertEqual(video_embed("https://www.youtube.com/embed/rfscVS0vtbw")["kind"], "youtube")
        self.assertEqual(video_embed("https://vimeo.com/123456789")["src"], "https://player.vimeo.com/video/123456789")
        self.assertEqual(video_embed("https://cdn.example.com/a/b.mp4")["kind"], "file")
        for bad in (None, "", "http://youtu.be/rfscVS0vtbw", "javascript:alert(1)",
                    "https://youtube.com.evil.com/watch?v=rfscVS0vtbw", "https://youtube.com/watch?v=pendek",
                    "https://example.com/page"):
            self.assertIsNone(video_embed(bad), bad)

    def test_text_blocks_split_paragraphs_and_code(self):
        blocks = text_blocks("Satu\nbaris.\n\n    a = 1\n\n    b = 2\n\nAkhir.")
        self.assertEqual([b["type"] for b in blocks], ["p", "code", "p"])
        self.assertEqual(blocks[0]["text"], "Satu baris.")
        self.assertEqual(blocks[1]["text"], "a = 1\n\nb = 2")

    # ---- UC-EL-04: tandai selesai + progres ----
    def test_progress_percent_helper(self):
        self.assertEqual(progress_percent(0, 0), 0)
        self.assertEqual(progress_percent(1, 3), 33)
        self.assertEqual(progress_percent(2, 3), 67)
        self.assertEqual(progress_percent(5, 5), 100)
        self.assertEqual(progress_percent(9, 5), 100)

    def test_mark_complete_updates_lesson_progress_and_returns_new_percent(self):
        self.enroll_direct(1)
        self.login()
        response = self.complete(1)
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual((data["ok"], data["completed"], data["done"], data["total"], data["progress_percent"]),
                         (True, True, 1, 4, 25))
        self.assertEqual(self.sql("SELECT user_id, lesson_id FROM lesson_progress"), [(1, 1)])

        data = self.complete(2).get_json()
        self.assertEqual((data["done"], data["progress_percent"], data["course_completed"]), (2, 50, False))
        self.complete(3)
        data = self.complete(4).get_json()
        self.assertEqual((data["done"], data["progress_percent"], data["course_completed"]), (4, 100, True))

    def test_mark_complete_is_idempotent_and_can_be_undone(self):
        self.enroll_direct(1)
        self.login()
        token = self.csrf()
        self.complete(1, token=token)
        again = self.complete(1, token=token).get_json()
        self.assertEqual(again["done"], 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM activity_logs WHERE action = 'lesson_complete'")[0][0], 1)

        undone = self.complete(1, completed=False, token=token).get_json()
        self.assertEqual((undone["completed"], undone["done"], undone["progress_percent"]), (False, 0, 0))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

    def test_progress_is_rendered_from_lesson_progress_in_all_views(self):
        self.enroll_direct(1)
        self.login()
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, 1), (1, 2), (1, 3)")
        room = self.client.get("/elearning/kelas/1/materi/4").get_data(as_text=True)
        self.assertIn("3 dari 4 materi · 75%", room)
        self.assertIn('aria-valuenow="75"', room)
        self.assertIn("width: 75%", room)
        self.assertIn("3 dari 4 materi", self.client.get("/elearning/kelas-saya").get_data(as_text=True))
        self.assertIn("75%", self.client.get("/elearning/kelas/1").get_data(as_text=True))
        # Progres pengguna lain tidak ikut terhitung
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (2, 4)")
        self.assertIn("3 dari 4 materi · 75%", self.client.get("/elearning/kelas/1/materi/1").get_data(as_text=True))

    def test_progress_api_rejects_unenrolled_guest_bad_csrf_and_bad_payload(self):
        # Guest
        self.assertEqual(self.client.post("/elearning/api/materi/1/selesai", json={"completed": True}).status_code, 401)
        # Member belum terdaftar
        self.login()
        denied = self.complete(1)
        self.assertEqual(denied.status_code, 403)
        self.assertIn("belum terdaftar", denied.get_json()["error"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

        self.enroll_direct(1)
        self.assertEqual(self.complete(1, token="salah").status_code, 403)
        self.assertEqual(self.complete(1, **{"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        token = self.csrf()
        self.assertEqual(self.client.post("/elearning/api/materi/1/selesai", data="completed=1",
                                          headers={"X-CSRF-Token": token}).status_code, 415)
        bad = self.client.post("/elearning/api/materi/1/selesai", json={"completed": "ya"},
                               headers={"X-CSRF-Token": token})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.complete(999, token=token).status_code, 404)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

    def test_progress_api_cannot_mark_lesson_of_course_not_enrolled(self):
        self.enroll_direct(1)
        self.login()
        self.assertEqual(self.complete(7).status_code, 403)  # materi milik kelas 3
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

    def test_progress_failure_rolls_back_and_reports_error(self):
        self.enroll_direct(1)
        self.login()
        token = self.csrf()
        self.sql("CREATE TRIGGER fail_log BEFORE INSERT ON activity_logs "
                 "WHEN NEW.action = 'lesson_complete' BEGIN SELECT RAISE(ABORT, 'gagal'); END")
        response = self.complete(1, token=token)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

    def test_my_courses_resume_link_points_to_first_unfinished_lesson(self):
        self.enroll_direct(1)
        self.login()
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, 1), (1, 2)")
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn('href="/elearning/kelas/1/materi/3"', html)
        self.assertIn("Lanjutkan belajar", html)
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, 3), (1, 4)")
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("Tinjau ulang", html)

    def test_my_courses_requires_login(self):
        response = self.client.get("/elearning/kelas-saya")
        self.assertEqual(urlsplit(response.location).path, "/infosys/login")

    def test_my_courses_empty_state(self):
        self.login()
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("Belum mengikuti kelas", html)
        self.assertIn("Lihat daftar kelas", html)

    # ---- UC-EL-07: pengaturan ----
    def test_settings_default_save_and_apply_to_learning_room(self):
        self.login()
        html = self.client.get("/elearning/pengaturan").get_data(as_text=True)
        self.assertRegex(html, r'value="1"\s+class="peer sr-only" checked')
        self.assertIn('value="30"', html)

        response = self.client.post("/elearning/pengaturan", data={
            "csrf_token": self.csrf(), "playback_speed": "1.5", "daily_goal_min": "45"})
        self.assertEqual(urlsplit(response.location).path, "/elearning/pengaturan")
        self.assertEqual(
            sorted(self.sql("SELECT setting_key, setting_value FROM module_settings WHERE module_key = 'elearning'")),
            [("daily_goal_min", "45"), ("playback_speed", "1.5")])

        self.enroll_direct(1)
        room = self.client.get("/elearning/kelas/1/materi/2").get_data(as_text=True)
        self.assertIn('data-speed="1.5"', room)
        # simpan ulang memperbarui, bukan menggandakan baris
        self.client.post("/elearning/pengaturan", data={
            "csrf_token": self.csrf(), "playback_speed": "2", "daily_goal_min": "60"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE module_key = 'elearning'")[0][0], 2)

    def test_settings_validation(self):
        self.login()
        token = self.csrf()
        for speed, goal, expected in (("3", "30", "Pilih salah satu kecepatan"),
                                      ("1", "0", "antara 5 dan 480"),
                                      ("1", "9999", "antara 5 dan 480"),
                                      ("1", "abc", "angka bulat"),
                                      ("1", "", "angka bulat")):
            response = self.client.post("/elearning/pengaturan", data={
                "csrf_token": token, "playback_speed": speed, "daily_goal_min": goal})
            self.assertEqual(response.status_code, 400, (speed, goal))
            self.assertIn(expected, response.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_settings_require_login_and_csrf(self):
        self.assertEqual(urlsplit(self.client.get("/elearning/pengaturan").location).path, "/infosys/login")
        self.login()
        self.client.post("/elearning/pengaturan", data={"csrf_token": "salah", "playback_speed": "2", "daily_goal_min": "20"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_daily_goal_counts_minutes_of_lessons_completed_today(self):
        self.enroll_direct(1)
        self.login()
        self.complete(1)  # 10 menit
        self.complete(2)  # 20 menit
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("Target tercapai", html)
        self.sql("UPDATE lesson_progress SET completed_at = '2020-01-01T00:00:00+00:00' WHERE lesson_id = 2")
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("10 dari 30 menit", html)

    # ---- Navigasi 3 level ----
    def test_breadcrumb_for_lesson_page(self):
        self.enroll_direct(1)
        self.login()
        html = self.client.get("/elearning/kelas/1/materi/2").get_data(as_text=True)
        self.assertRegex(html, r'data-back-link[^>]*>')
        self.assertIn("Materi 2: Warna dan kontras", html)
        back = re.search(r'<a href="([^"]+)"[^>]*data-back-link', html).group(1)
        self.assertEqual(back, "/elearning/kelas/1")


if __name__ == "__main__":
    unittest.main()
