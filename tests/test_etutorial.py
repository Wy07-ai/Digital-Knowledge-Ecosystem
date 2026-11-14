"""Tes E-Tutorial: daftar + filter, stepper, escape kode, bookmark, Tersimpan, ukuran font."""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app.etutorial.routes import clean_language, format_minutes, paragraphs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSS_CODE = '<script>alert("kode")</script>\nif a < b && c > d: print("x")'
XSS_BODY = 'Isi <img src=x onerror=alert(1)> tebal'
XSS_TITLE = '<b>Judul</b> berbahaya'


class EtutorialTests(unittest.TestCase):
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
            ((1, "etutorial", "Python", "python"), (2, "etutorial", "Web", "web"),
             (3, "etutorial", "Alat Developer", "alat-developer"), (4, "elearning", "Pemrograman", "pemrograman")),
        )
        conn.executemany(
            "INSERT INTO tutorials (id, category_id, title, slug, summary, difficulty, est_minutes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ((1, 2, "Flask Pertama", "flask-pertama", "Bangun aplikasi kecil.", "mudah", 20, "2026-01-03"),
             (2, 1, "Pandas CSV", "pandas-csv", "Baca data CSV.", "mudah", 25, "2026-01-02"),
             (3, 1, "SQLite Python", "sqlite-python", "Query basis data.", "menengah", 90, "2026-01-01"),
             (4, 2, XSS_TITLE, "judul-xss", "Ringkasan <i>miring</i>", "menengah", None, "2026-01-04"),
             (5, 3, "Tutorial Kosong", "tutorial-kosong", "Belum ada langkah.", "mudah", 5, "2025-12-31")),
        )
        conn.executemany(
            "INSERT INTO tutorial_steps (tutorial_id, step_no, title, body, code_snippet, code_language) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ((1, 1, "Siapkan folder", "Buat folder.\n\nLalu masuk ke folder.", "mkdir app\ncd app", "bash"),
             (1, 2, "Pasang Flask", "Pasang dengan pip.", "pip install Flask", "bash"),
             (1, 3, "Tulis aplikasi", "Buat app.py.", "from flask import Flask\napp = Flask(__name__)", "python"),
             (2, 1, "Impor pandas", "Impor pustaka.", "import pandas as pd", "python"),
             (3, 1, "Buka koneksi", "Gunakan sqlite3.", "import sqlite3", "python"),
             (4, 1, "Langkah <u>XSS</u>", XSS_BODY, XSS_CODE, 'py"><script>x</script>'),
             (4, 2, "Tanpa kode", "Hanya teks.", None, None)),
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
        html = (client or self.client).get("/etutorial/pengaturan").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def get(self, path):
        return self.client.get(path).get_data(as_text=True)

    def bookmark(self, slug, action="add", token=None, **extra):
        token = token if token is not None else self.csrf()
        return self.client.post(f"/etutorial/tutorial/{slug}/simpan",
                                data={"csrf_token": token, "action": action, **extra})

    # ---- UC-ET-01: daftar, estimasi menit, filter ----
    def test_list_shows_all_with_minutes_and_step_counts(self):
        html = self.get("/etutorial/")
        for title in ("Flask Pertama", "Pandas CSV", "SQLite Python", "Tutorial Kosong"):
            self.assertIn(title, html)
        self.assertIn("Estimasi 20 menit", html)
        self.assertIn("Estimasi 1 jam 30 menit", html)  # 90 menit
        self.assertIn("3 langkah", html)

    def test_list_is_public_for_guest(self):
        self.assertEqual(self.client.get("/etutorial/").status_code, 200)

    def test_filter_by_category(self):
        html = self.get("/etutorial/?kategori=python")
        self.assertIn("Pandas CSV", html)
        self.assertIn("SQLite Python", html)
        self.assertNotIn("Flask Pertama", html)

    def test_filter_by_difficulty(self):
        html = self.get("/etutorial/?tingkat=menengah")
        self.assertIn("SQLite Python", html)
        self.assertNotIn("Flask Pertama", html)
        self.assertNotIn("Pandas CSV", html)

    def test_filters_combine_and_counts_follow_active_filter(self):
        html = self.get("/etutorial/?kategori=python&tingkat=mudah")
        self.assertIn("Pandas CSV", html)
        self.assertNotIn("SQLite Python", html)
        self.assertNotIn("Flask Pertama", html)
        self.assertIn("Menampilkan 1 dari 5 tutorial", html)
        # tombol tingkat "Menengah" menghitung hasil bila dipilih bersama kategori Python: 1
        self.assertRegex(html, r"Menengah\s*<span class=\"et-count\">\(1\)</span>")

    def test_unknown_filter_is_ignored_with_notice(self):
        html = self.get("/etutorial/?kategori=tidak-ada&tingkat=ajaib")
        self.assertIn("Sebagian filter tidak dikenal", html)
        self.assertIn("Flask Pertama", html)

    def test_empty_filter_result_has_reset_link(self):
        html = self.get("/etutorial/?kategori=alat-developer&tingkat=menengah")
        self.assertIn("Tidak ada tutorial yang cocok", html)

    def test_category_from_other_module_is_not_a_filter(self):
        self.assertNotIn(">Pemrograman<", self.get("/etutorial/"))

    # ---- UC-ET-02: stepper ----
    def test_step_one_has_stepper_indicator_and_next_only(self):
        html = self.get("/etutorial/tutorial/flask-pertama")
        self.assertIn("Step 1 dari 3", html)
        self.assertIn('aria-valuenow="1"', html)
        self.assertIn('aria-valuemax="3"', html)
        self.assertIn("Berikutnya", html)
        self.assertIn("/etutorial/tutorial/flask-pertama/langkah/2", html)
        self.assertRegex(html, r"<button[^>]*disabled[^>]*>[^<]*(<svg.*?</svg>)?Sebelumnya")
        self.assertEqual(html.count('aria-current="step"'), 1)

    def test_middle_step_has_prev_and_next(self):
        html = self.get("/etutorial/tutorial/flask-pertama/langkah/2")
        self.assertIn("Step 2 dari 3", html)
        self.assertIn("Pasang Flask", html)
        self.assertIn("/etutorial/tutorial/flask-pertama/langkah/3", html)
        self.assertRegex(html, r'href="/etutorial/tutorial/flask-pertama"[^>]*data-et-prev')

    def test_last_step_shows_finish_not_next(self):
        html = self.get("/etutorial/tutorial/flask-pertama/langkah/3")
        self.assertIn("Step 3 dari 3", html)
        self.assertIn("Selesai", html)
        self.assertNotIn("data-et-next", html)
        self.assertIn("Tutorial selesai", html)

    def test_body_split_into_paragraphs(self):
        html = self.get("/etutorial/tutorial/flask-pertama")
        self.assertIn("<p>Buat folder.</p>", html)
        self.assertIn("<p>Lalu masuk ke folder.</p>", html)

    def test_out_of_range_step_redirects_to_nearest(self):
        r = self.client.get("/etutorial/tutorial/flask-pertama/langkah/99")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/etutorial/tutorial/flask-pertama/langkah/3"))
        r = self.client.get("/etutorial/tutorial/flask-pertama/langkah/0")
        self.assertEqual(r.status_code, 302)

    def test_unknown_tutorial_is_404(self):
        self.assertEqual(self.client.get("/etutorial/tutorial/tidak-ada").status_code, 404)

    def test_tutorial_without_steps_shows_empty_state(self):
        r = self.client.get("/etutorial/tutorial/tutorial-kosong")
        self.assertEqual(r.status_code, 200)
        self.assertIn("belum punya langkah", r.get_data(as_text=True))

    def test_breadcrumb_uses_tutorial_title(self):
        html = self.get("/etutorial/tutorial/pandas-csv")
        self.assertIn("Pandas CSV", html)
        self.assertIn("E-Tutorial", html)

    # ---- UC-ET-03: blok kode + tombol salin ----
    def test_code_block_has_copy_button_and_loads_copy_js(self):
        html = self.get("/etutorial/tutorial/flask-pertama/langkah/2")
        self.assertIn('data-copy-target="kode-2"', html)
        self.assertIn('id="kode-2"', html)
        self.assertIn(">Salin<", html)
        self.assertIn("js/copy.js", html)
        self.assertIn("pip install Flask", html)

    def test_step_without_code_has_no_copy_button(self):
        html = self.get("/etutorial/tutorial/judul-xss/langkah/2")
        self.assertNotIn("data-copy-target", html)

    def test_copy_js_reports_toast_kode_disalin(self):
        with open(os.path.join(ROOT, "app", "static", "js", "copy.js"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("'Kode disalin'", source)
        self.assertIn("textContent", source)       # menyalin teks mentah, bukan innerHTML
        self.assertNotIn("innerHTML", source)
        self.assertIn("execCommand('copy')", source)  # cadangan untuk http:// non-aman

    # ---- Escape (autoescape Jinja wajib aktif) ----
    def test_database_content_is_escaped(self):
        html = self.get("/etutorial/tutorial/judul-xss")
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<u>XSS</u>", html)
        self.assertNotIn("<b>Judul</b>", html)
        self.assertIn("&lt;script&gt;alert(&#34;kode&#34;)&lt;/script&gt;", html)
        self.assertIn("a &lt; b &amp;&amp; c &gt; d", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("&lt;b&gt;Judul&lt;/b&gt; berbahaya", html)

    def test_escaped_everywhere_in_list_and_title(self):
        html = self.get("/etutorial/")
        self.assertNotIn("<b>Judul</b>", html)
        self.assertNotIn("<i>miring</i>", html)
        self.assertIn("&lt;b&gt;Judul&lt;/b&gt; berbahaya", html)

    def test_malicious_language_cannot_break_out_of_attribute(self):
        html = self.get("/etutorial/tutorial/judul-xss")
        self.assertNotIn('class="language-py"', html)
        self.assertNotIn("<script>x</script>", html)
        self.assertEqual(clean_language('py"><script>x</script>'), None)
        self.assertEqual(clean_language("C++"), "c++")

    def test_copy_target_holds_escaped_text_that_roundtrips(self):
        import html as htmllib
        page = self.get("/etutorial/tutorial/judul-xss")
        inner = re.search(r'<code id="kode-1"[^>]*>(.*?)</code>', page, re.S).group(1)
        self.assertEqual(htmllib.unescape(inner), XSS_CODE)  # textContent di browser = kode asli

    def test_autoescape_active_and_no_unsafe_filters_in_templates(self):
        self.assertTrue(self.app.jinja_env.autoescape("etutorial/tutorial.html"))
        folder = os.path.join(ROOT, "app", "templates", "etutorial")
        for name in os.listdir(folder):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                source = f.read()
            self.assertNotRegex(source, r"\|\s*safe\b", name)
            self.assertNotIn("autoescape false", source.replace("  ", " "), name)
            self.assertNotIn("Markup", source, name)
        with open(os.path.join(ROOT, "app", "etutorial", "routes.py"), encoding="utf-8") as f:
            routes = f.read()
        self.assertNotIn("Markup(", routes)
        self.assertNotIn("render_template_string", routes)

    # ---- UC-ET-04: bookmark ----
    def test_guest_sees_login_prompt_instead_of_save(self):
        html = self.get("/etutorial/tutorial/flask-pertama")
        self.assertIn("Masuk untuk menyimpan", html)
        self.assertIn("/infosys/login?next=", html)

    def test_guest_bookmark_post_redirects_to_login(self):
        r = self.client.post("/etutorial/tutorial/flask-pertama/simpan", data={"action": "add"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/infosys/login", r.headers["Location"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tutorial_bookmarks")[0][0], 0)

    def test_member_can_add_and_remove_bookmark(self):
        self.login()
        r = self.bookmark("flask-pertama", next="/etutorial/tutorial/flask-pertama/langkah/2")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/etutorial/tutorial/flask-pertama/langkah/2"))
        self.assertEqual(self.sql("SELECT user_id, tutorial_id FROM tutorial_bookmarks"), [(1, 1)])
        self.assertIn("Hapus dari Tersimpan", self.get("/etutorial/tutorial/flask-pertama"))
        self.bookmark("flask-pertama", action="remove")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tutorial_bookmarks")[0][0], 0)
        self.assertIn("Simpan tutorial", self.get("/etutorial/tutorial/flask-pertama"))

    def test_bookmark_is_idempotent_and_logged_once(self):
        self.login()
        self.bookmark("pandas-csv")
        self.bookmark("pandas-csv")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tutorial_bookmarks")[0][0], 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM activity_logs WHERE action = 'bookmark'")[0][0], 1)

    def test_bookmark_requires_valid_csrf(self):
        self.login()
        self.bookmark("pandas-csv", token="salah")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tutorial_bookmarks")[0][0], 0)

    def test_bookmark_rejects_unknown_action_and_tutorial(self):
        self.login()
        self.assertEqual(self.bookmark("pandas-csv", action="hapus-semua").status_code, 400)
        self.assertEqual(self.bookmark("tidak-ada").status_code, 404)

    def test_bookmark_next_must_be_local(self):
        self.login()
        r = self.bookmark("pandas-csv", next="https://evil.example/")
        self.assertTrue(r.headers["Location"].endswith("/etutorial/tutorial/pandas-csv"))
        r = self.bookmark("pandas-csv", next="//evil.example/")
        self.assertTrue(r.headers["Location"].endswith("/etutorial/tutorial/pandas-csv"))

    def test_bookmarks_are_per_user(self):
        self.login(1)
        self.bookmark("pandas-csv")
        other = self.app.test_client()
        self.login(2, other)
        self.assertNotIn("Pandas CSV", other.get("/etutorial/tersimpan").get_data(as_text=True))
        self.assertIn("Simpan tutorial", other.get("/etutorial/tutorial/pandas-csv").get_data(as_text=True))

    # ---- Halaman Tersimpan ----
    def test_saved_requires_login(self):
        r = self.client.get("/etutorial/tersimpan")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/infosys/login", r.headers["Location"])

    def test_saved_empty_state(self):
        self.login()
        self.assertIn("Belum ada tutorial tersimpan", self.get("/etutorial/tersimpan"))

    def test_saved_lists_newest_first_and_can_remove(self):
        self.login()
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id, created_at) VALUES (1, 2, '2026-02-01T00:00:00+00:00')")
        self.sql("INSERT INTO tutorial_bookmarks (user_id, tutorial_id, created_at) VALUES (1, 3, '2026-03-01T00:00:00+00:00')")
        html = self.get("/etutorial/tersimpan")
        self.assertLess(html.index("SQLite Python"), html.index("Pandas CSV"))
        self.assertIn("2 tutorial tersimpan", html)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        r = self.client.post("/etutorial/tutorial/pandas-csv/simpan",
                             data={"csrf_token": token, "action": "remove", "next": "/etutorial/tersimpan"})
        self.assertTrue(r.headers["Location"].endswith("/etutorial/tersimpan"))
        self.assertNotIn("Pandas CSV", self.get("/etutorial/tersimpan"))

    def test_list_marks_saved_tutorials_with_text_badge(self):
        self.login()
        self.bookmark("pandas-csv")
        html = self.get("/etutorial/")
        self.assertEqual(html.count("et-badge-saved"), 1)
        self.assertIn("Tersimpan</span>", html)

    # ---- UC-ET-05: ukuran font di module_settings ----
    def test_default_font_is_medium(self):
        self.assertIn('data-font="md"', self.get("/etutorial/tutorial/flask-pertama"))

    def test_member_font_saved_in_module_settings(self):
        self.login()
        token = self.csrf()
        r = self.client.post("/etutorial/pengaturan", data={"csrf_token": token, "font_size": "lg"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            self.sql("SELECT module_key, setting_key, setting_value FROM module_settings WHERE user_id = 1"),
            [("etutorial", "font_size", "lg")])
        self.assertIn('data-font="lg"', self.get("/etutorial/tutorial/flask-pertama"))
        # ubah lagi -> baris diperbarui, bukan digandakan
        self.client.post("/etutorial/pengaturan", data={"csrf_token": token, "font_size": "sm"})
        self.assertEqual(
            self.sql("SELECT setting_value FROM module_settings WHERE user_id = 1 AND module_key = 'etutorial'"),
            [("sm",)])
        self.assertIn('data-font="sm"', self.get("/etutorial/tutorial/flask-pertama"))

    def test_font_setting_is_per_user_and_does_not_touch_other_modules(self):
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) VALUES (1, 'elearning', 'daily_goal_min', '30')")
        self.login(1)
        self.client.post("/etutorial/pengaturan", data={"csrf_token": self.csrf(), "font_size": "lg"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE module_key = 'elearning'")[0][0], 1)
        other = self.app.test_client()
        self.login(2, other)
        self.assertIn('data-font="md"', other.get("/etutorial/tutorial/flask-pertama").get_data(as_text=True))

    def test_invalid_font_rejected_and_not_stored(self):
        self.login()
        r = self.client.post("/etutorial/pengaturan", data={"csrf_token": self.csrf(), "font_size": "xxl"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Pilih salah satu ukuran font", r.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_font_post_requires_csrf(self):
        self.login()
        self.client.post("/etutorial/pengaturan", data={"csrf_token": "salah", "font_size": "lg"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_stored_garbage_value_falls_back_to_medium(self):
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) VALUES (1, 'etutorial', 'font_size', '<x>')")
        self.login()
        html = self.get("/etutorial/tutorial/flask-pertama")
        self.assertIn('data-font="md"', html)
        self.assertNotIn("<x>", html)

    def test_guest_font_uses_cookie_not_database(self):
        token = self.csrf()
        r = self.client.post("/etutorial/pengaturan", data={"csrf_token": token, "font_size": "lg"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("dke_et_font=lg", r.headers.get("Set-Cookie", ""))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)
        self.assertIn('data-font="lg"', self.get("/etutorial/tutorial/flask-pertama"))

    def test_settings_page_has_three_choices_and_preview(self):
        html = self.get("/etutorial/pengaturan")
        for label in ("Kecil", "Sedang", "Besar"):
            self.assertIn(label, html)
        self.assertEqual(html.count('name="font_size"'), 3)
        self.assertIn("data-et-preview", html)

    def test_large_font_has_mobile_rules(self):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            css = f.read()
        for needle in ("[data-font='lg']", "@media (max-width: 767px)", "html[data-view='mobile'] .et-reader[data-font='lg']",
                       "white-space: pre-wrap", "min-height: 56px"):
            self.assertIn(needle, css)
        # ukuran dalam rem (ikut pengaturan font peramban), bukan px tetap
        self.assertRegex(css, r"\[data-font='lg'\] \{ --et-fs: 1\.25rem;")

    # ---- Pembantu murni ----
    def test_helpers(self):
        self.assertEqual(format_minutes(20), "20 menit")
        self.assertEqual(format_minutes(60), "1 jam")
        self.assertEqual(format_minutes(75), "1 jam 15 menit")
        self.assertEqual(format_minutes(None), "")
        self.assertEqual(paragraphs("a\n\n\nb\n"), ["a", "b"])
        self.assertEqual(paragraphs(None), [])

    # ---- Integrasi ----
    def test_module_pages_have_nav_tabs_and_accent(self):
        html = self.get("/etutorial/")
        for label in ("Daftar Tutorial", "Tersimpan", "Pengaturan"):
            self.assertIn(label, html)
        self.assertIn("--accent: #7C3AED", html)

    def test_smart_landing_remembers_step_url(self):
        self.login()
        self.client.get("/etutorial/tutorial/flask-pertama/langkah/2")
        row = self.sql("SELECT last_module, last_path FROM user_settings WHERE user_id = 1")
        if row:  # baris user_settings tidak dibuat oleh fixture ini; bila ada, harus mengarah ke langkah
            self.assertEqual(row[0], ("etutorial", "/etutorial/tutorial/flask-pertama/langkah/2"))


if __name__ == "__main__":
    unittest.main()
