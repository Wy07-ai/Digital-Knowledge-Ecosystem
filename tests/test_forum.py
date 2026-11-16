"""Tes Forum: daftar (filter, urutan, balasan, Solved), buat thread (validasi), detail + balasan bersarang
(batas 3 tingkat tampilan), balas (slide-up, notifikasi), tandai solusi, ubah/hapus balasan (hanya pemilik),
Thread Saya, pengaturan (privasi + notifikasi), profil, dan keamanan (XSS, CSRF, kepemilikan)."""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from app import create_app
from app.forum import logic as lg
from app.utils import is_safe_next

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSS = "<script>alert(1)</script>"
XSS_ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"
ATTR = '" onmouseover="alert(2)" x="'


# ==========================================================================
# Logika murni
# ==========================================================================
class LogicTests(unittest.TestCase):
    def test_clean_text_and_collapse(self):
        self.assertEqual(lg.clean_text("  a\r\nb\x00\x07 "), "a\nb")
        self.assertEqual(lg.clean_text(None), "")
        self.assertEqual(lg.collapse_spaces("  Judul \n\n  panjang   sekali "), "Judul panjang sekali")
        self.assertEqual(lg.clean_text("<b>&</b>"), "<b>&</b>")  # tidak diubah menjadi HTML; di-escape saat dicetak

    def test_validate_thread(self):
        ok, errors = lg.validate_thread("  Judul valid  ", "Isi cukup panjang", "2", {1, 2})
        self.assertEqual(errors, {})
        self.assertEqual(ok, {"title": "Judul valid", "body": "Isi cukup panjang", "category_id": 2})
        _, errors = lg.validate_thread("", "", "", {1})
        self.assertEqual(set(errors), {"title", "category", "body"})
        _, errors = lg.validate_thread("abcd", "Isi cukup panjang", 1, {1})
        self.assertIn("minimal 5", errors["title"])
        _, errors = lg.validate_thread("x" * 151, "Isi cukup panjang", 1, {1})
        self.assertIn("Maksimal 150", errors["title"])
        _, errors = lg.validate_thread("Judul valid", "pendek", 1, {1})
        self.assertIn("minimal 10", errors["body"])
        _, errors = lg.validate_thread("Judul valid", "x" * 5001, 1, {1})
        self.assertIn("Maksimal 5000", errors["body"])
        values, errors = lg.validate_thread("Judul valid", "Isi cukup panjang", "99", {1})
        self.assertIn("category", errors)
        self.assertIsNone(values["category_id"])
        _, errors = lg.validate_thread("Judul valid", "Isi cukup panjang", "abc", {1})
        self.assertIn("category", errors)
        _, errors = lg.validate_thread("     ", "          ", 1, {1})  # hanya spasi dianggap kosong
        self.assertIn("belum diisi", errors["title"])
        self.assertIn("belum diisi", errors["body"])

    def test_validate_post(self):
        self.assertEqual(lg.validate_post("  Balasan ok ")[1], None)
        self.assertIn("belum diisi", lg.validate_post("   ")[1])
        self.assertIn("minimal 3", lg.validate_post("ab")[1])
        self.assertIn("Maksimal 3000", lg.validate_post("x" * 3001)[1])

    def test_settings_helpers(self):
        self.assertEqual(lg.normalize_privacy("PUBLIC "), "public")
        self.assertEqual(lg.normalize_privacy("ngawur"), "public")
        self.assertEqual(lg.normalize_privacy(None), "public")
        self.assertTrue(lg.notify_enabled(None))
        self.assertTrue(lg.notify_enabled("1"))
        self.assertFalse(lg.notify_enabled("0"))
        self.assertFalse(lg.notify_enabled("false"))

    def test_profile_privacy_rules(self):
        self.assertTrue(lg.can_view_profile("public", None, 5))
        self.assertTrue(lg.can_view_profile("members", 1, 5))
        self.assertFalse(lg.can_view_profile("members", None, 5))
        self.assertFalse(lg.can_view_profile("private", 1, 5))
        self.assertFalse(lg.can_view_profile("private", None, 5))
        self.assertTrue(lg.can_view_profile("private", 5, 5))     # pemilik selalu boleh
        self.assertTrue(lg.can_view_profile("members", 5, 5))
        self.assertTrue(lg.can_view_profile("ngawur", None, 5))

    @staticmethod
    def rows(*specs):
        # (id, parent, created) -> baris
        return [{"id": i, "parent_post_id": p, "created_at": c, "user_id": 1, "author_name": f"U{i}"} for i, p, c in specs]

    def test_flatten_levels_and_clamp(self):
        rows = self.rows((1, None, "t1"), (2, 1, "t2"), (3, 2, "t3"), (4, 3, "t4"), (5, 4, "t5"), (6, None, "t6"))
        flat = lg.flatten_posts(rows)
        self.assertEqual([p["id"] for p in flat], [1, 2, 3, 4, 5, 6])
        self.assertEqual([p["depth"] for p in flat], [1, 2, 3, 4, 5, 1])
        self.assertEqual([p["level"] for p in flat], [1, 2, 3, 3, 3, 1])         # tampilan maksimal 3 tingkat
        self.assertEqual([p["reply_to"] for p in flat], [None, None, None, "U3", "U4", None])
        self.assertEqual([p["parent_author"] for p in flat], [None, "U1", "U2", "U3", "U4", None])
        self.assertEqual(flat[0]["child_count"], 1)

    def test_flatten_order_is_dfs_oldest_first(self):
        rows = self.rows((1, None, "a1"), (2, None, "a2"), (3, 1, "b2"), (4, 1, "b1"), (5, 3, "c1"))
        self.assertEqual([p["id"] for p in lg.flatten_posts(rows)], [1, 4, 3, 5, 2])

    def test_flatten_orphans_and_cycles(self):
        rows = self.rows((1, 99, "a"), (2, 2, "b"))           # induk tidak ada; menunjuk diri sendiri
        flat = lg.flatten_posts(rows)
        self.assertEqual(sorted(p["id"] for p in flat), [1, 2])
        self.assertTrue(all(p["level"] == 1 for p in flat))
        cyc = self.rows((1, 2, "a"), (2, 1, "b"))             # siklus: tetap tampil, tidak berputar selamanya
        flat = lg.flatten_posts(cyc)
        self.assertEqual(sorted(p["id"] for p in flat), [1, 2])
        self.assertEqual(lg.flatten_posts([]), [])

    def test_descendants(self):
        rows = self.rows((1, None, "a"), (2, 1, "b"), (3, 2, "c"), (4, None, "d"))
        self.assertEqual(lg.descendants(rows, 1), {2, 3})
        self.assertEqual(lg.descendants(rows, 4), set())

    def test_formatting(self):
        self.assertEqual(lg.initials("Dewi Anggraini"), "DA")
        self.assertEqual(lg.initials("  budi  "), "B")
        self.assertEqual(lg.initials("<b>x</b> y"), "BY")   # hanya huruf/angka pertama tiap kata
        self.assertEqual(lg.initials(""), "?")
        self.assertEqual(lg.format_date("2026-11-13T17:30:00+00:00"), "14 Nov 2026")  # WIB
        self.assertEqual(lg.format_datetime("2026-11-13T03:05:00+00:00"), "13 Nov 2026, 10.05 WIB")
        self.assertEqual(lg.format_date("bukan tanggal"), "bukan tanggal")
        now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(lg.relative_time("2026-11-14T11:59:50+00:00", now), "baru saja")
        self.assertEqual(lg.relative_time("2026-11-14T11:55:00+00:00", now), "5 menit lalu")
        self.assertEqual(lg.relative_time("2026-11-14T09:00:00+00:00", now), "3 jam lalu")
        self.assertEqual(lg.relative_time("2026-11-12T12:00:00+00:00", now), "2 hari lalu")
        self.assertEqual(lg.relative_time("2026-08-01T12:00:00+00:00", now), "1 Agu 2026")
        self.assertEqual(lg.plural_replies(0), "Belum ada balasan")
        self.assertEqual(lg.plural_replies(3), "3 balasan")
        self.assertEqual(lg.paragraphs("a\n\nb\nc\n\n\n"), ["a", "b\nc"])
        self.assertEqual(lg.parse_page("abc"), 1)
        self.assertEqual(lg.parse_page("-4"), 1)
        info = lg.paginate(20, 99, 8)
        self.assertEqual((info["page"], info["pages"], info["first"], info["last"]), (3, 3, 17, 20))
        self.assertEqual(lg.paginate(0, 1, 8)["first"], 0)


# ==========================================================================
# Integrasi (Flask test client + SQLite sementara)
# ==========================================================================
class ForumTestCase(unittest.TestCase):
    """Data dasar:
    pengguna 1 Demo (bio), 2 Orang Lain, 3 Penulis Utama; kategori forum 1 Diskusi Umum, 2 Tanya Jawab, 3 Kosong.
    thread 1 (Demo, belum solved, 2 balasan: p10 oleh 2, p11 oleh 3 membalas p10)
    thread 2 (Orang Lain, belum solved, 1 balasan: p20 oleh Demo)
    thread 3 (Penulis Utama, Solved dengan p31 oleh Orang Lain; 2 balasan: p30 oleh Demo, p31)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.executemany(
            "INSERT INTO users (id, full_name, email, password_hash, bio, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ((1, "Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345"), "Bio rahasia demo", "2026-01-01T00:00:00+00:00"),
             (2, "Orang Lain", "lain@dke.test", generate_password_hash("Lain12345"), "Bio orang lain", "2026-01-02T00:00:00+00:00"),
             (3, "Penulis Utama", "penulis@dke.test", generate_password_hash("Penulis123"), None, "2026-01-03T00:00:00+00:00")))
        conn.executemany(
            "INSERT INTO categories (id, module_key, name, slug) VALUES (?, ?, ?, ?)",
            ((1, "forum", "Diskusi Umum", "diskusi-umum"), (2, "forum", "Tanya Jawab", "tanya-jawab"),
             (3, "forum", "Kosong", "kosong"), (4, "portal", "Teknologi", "teknologi")))
        conn.executemany(
            "INSERT INTO threads (id, category_id, user_id, title, body, is_solved, accepted_post_id, views, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ((1, 1, 1, "Topik Milik Demo", "Isi topik milik demo yang cukup panjang.", 0, None, 10, "2026-01-01T03:00:00+00:00"),
             (2, 1, 2, "Topik Orang Lain", "Isi topik orang lain yang cukup panjang.", 0, None, 5, "2026-01-05T03:00:00+00:00"),
             (3, 2, 3, "Topik Terjawab", "Isi topik solved yang cukup panjang.", 1, 31, 7, "2026-01-03T03:00:00+00:00")))
        conn.executemany(
            "INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ((10, 1, 2, None, "Balasan sepuluh dari orang lain", "2026-01-01T04:00:00+00:00"),
             (11, 1, 3, 10, "Balasan sebelas menanggapi sepuluh", "2026-01-01T05:00:00+00:00"),
             (20, 2, 1, None, "Balasan dua puluh dari demo", "2026-01-05T04:00:00+00:00"),
             (30, 3, 1, None, "Balasan tiga puluh dari demo", "2026-01-03T04:00:00+00:00"),
             (31, 3, 2, None, "Balasan tiga puluh satu adalah solusi", "2026-01-03T05:00:00+00:00")))
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

    def client_for(self, user_id=None):
        client = self.app.test_client()
        if user_id is not None:
            with client.session_transaction() as session:
                session["user_id"] = user_id
        return client

    def as_user(self, user_id=1):
        self.client = self.client_for(user_id)
        return self.client

    def get(self, path, client=None):
        return (client or self.client).get(path).get_data(as_text=True)

    def csrf(self, client=None):
        html = (client or self.client).get("/forum/pengaturan").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post(self, path, data=None, client=None, token=True, **kwargs):
        client = client or self.client
        payload = dict(data or {})
        if token is True:
            payload["csrf_token"] = self.csrf(client)
        elif token:
            payload["csrf_token"] = token
        return client.post(path, data=payload, **kwargs)

    def reply(self, thread_id, body, parent=None, client=None, **kw):
        data = {"body": body}
        if parent is not None:
            data["parent_post_id"] = str(parent)
        return self.post(f"/forum/thread/{thread_id}/balas", data, client=client, **kw)

    def new_thread(self, title="Judul topik baru", body="Isi topik baru yang cukup panjang.", category=1, **kw):
        return self.post("/forum/buat", {"title": title, "body": body, "category_id": str(category)}, **kw)

    @staticmethod
    def titles(html):
        return [re.sub(r"\s+", " ", t).strip() for t in re.findall(r'<h3[^>]*>\s*<a[^>]*class="card-link"[^>]*>(.*?)</a>', html, re.S)]

    @staticmethod
    def levels(html):
        return [(int(i), int(lv)) for i, lv in re.findall(r'<li id="balasan-(\d+)" class="fm-post[^"]*" data-level="(\d)"', html)]

    def setting(self, user_id, key):
        row = self.sql("SELECT setting_value FROM module_settings WHERE user_id=? AND module_key='forum' AND setting_key=?",
                       (user_id, key))
        return row[0][0] if row else None


# --------------------------------------------------------------------------
class ListTests(ForumTestCase):
    def test_guest_can_view_list(self):
        html = self.get("/forum/")
        self.assertEqual(self.titles(html), ["Topik Orang Lain", "Topik Terjawab", "Topik Milik Demo"])  # terbaru dulu
        self.assertIn("Forum diskusi", html)

    def test_reply_counts_and_solved_badge(self):
        html = self.get("/forum/")
        rows = re.findall(r'<article class="[^"]*\bfm-row\b[^"]*.*?</article>', html, re.S)
        by_title = {self.titles(r)[0]: r for r in rows}
        self.assertIn('<span class="fm-count-num">2</span>', by_title["Topik Terjawab"])
        self.assertIn('<span class="fm-count-num">1</span>', by_title["Topik Orang Lain"])
        self.assertIn('<span class="fm-count-num">2</span>', by_title["Topik Milik Demo"])
        self.assertIn("Terjawab", by_title["Topik Terjawab"])
        self.assertNotIn("fm-solved", by_title["Topik Orang Lain"])
        self.assertEqual(html.count('<span class="fm-solved">'), 1)

    def test_zero_replies_shown(self):
        self.sql("INSERT INTO threads (id, category_id, user_id, title, body, created_at) VALUES (9, 3, 3, 'Tanpa Balasan', "
                 "'Isi tanpa balasan sama sekali.', '2026-02-01T00:00:00+00:00')")
        html = self.get("/forum/")
        row = re.search(r'<article class="[^"]*\bfm-row\b[^"]*(?:(?!</article>).)*Tanpa Balasan.*?</article>', html, re.S).group(0)
        self.assertIn('<span class="fm-count-num">0</span>', row)

    def test_category_filter_and_counts(self):
        html = self.get("/forum/?kategori=tanya-jawab")
        self.assertEqual(self.titles(html), ["Topik Terjawab"])
        self.assertRegex(html, r'aria-current="true">\s*Tanya Jawab')
        all_html = self.get("/forum/")
        self.assertIn("Semua <span", all_html)
        self.assertRegex(all_html, r"Diskusi Umum <span[^>]*>\(2\)")
        self.assertRegex(all_html, r"Kosong <span[^>]*>\(0\)")
        self.assertNotIn("Teknologi", all_html)                       # kategori modul lain tidak ikut

    def test_unknown_category_ignored(self):
        html = self.get("/forum/?kategori=ngawur")
        self.assertIn("Kategori itu tidak dikenal", html)
        self.assertEqual(len(self.titles(html)), 3)

    def test_empty_category_state(self):
        html = self.get("/forum/?kategori=kosong")
        self.assertIn("Belum ada topik di kategori Kosong", html)
        self.assertEqual(self.titles(html), [])

    def test_unanswered_sort(self):
        html = self.get("/forum/?urut=belum-terjawab")
        # Solved disembunyikan; yang paling sedikit balasannya dulu (2: 1 balasan, 1: 2 balasan)
        self.assertEqual(self.titles(html), ["Topik Orang Lain", "Topik Milik Demo"])
        self.assertRegex(html, r'aria-current="true">Belum terjawab')
        # Angka chip mengikuti urutan terpilih
        self.assertRegex(html, r"Tanya Jawab <span[^>]*>\(0\)")

    def test_unanswered_combined_with_category(self):
        html = self.get("/forum/?urut=belum-terjawab&kategori=tanya-jawab")
        self.assertIn("sudah terjawab", html)                         # satu-satunya thread di sana sudah Solved
        self.assertEqual(self.titles(html), [])

    def test_unknown_sort_falls_back(self):
        html = self.get("/forum/?urut=ngawur")
        self.assertIn("Urutan itu tidak dikenal", html)
        self.assertEqual(self.titles(html)[0], "Topik Orang Lain")

    def test_empty_forum(self):
        self.sql("DELETE FROM posts")
        self.sql("DELETE FROM threads")
        self.assertIn("Belum ada topik", self.get("/forum/"))

    def test_pagination(self):
        rows = [(100 + i, 1, 3, f"Massal {100 + i}", "Isi massal cukup panjang.", f"2026-03-{(i % 27) + 1:02d}T03:00:00+00:00")
                for i in range(12)]
        conn = sqlite3.connect(self.db_path)
        conn.executemany("INSERT INTO threads (id, category_id, user_id, title, body, created_at) VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
        conn.close()
        page1 = self.get("/forum/")
        page2 = self.get("/forum/?halaman=2")
        self.assertEqual(len(self.titles(page1)), 8)
        self.assertEqual(len(self.titles(page2)), 7)                  # 15 thread: 8 + 7
        self.assertIn("Menampilkan 9&ndash;15 dari 15 topik", page2)
        self.assertEqual(self.titles(self.get("/forum/?halaman=999")), self.titles(page2))
        self.assertEqual(self.titles(self.get("/forum/?halaman=abc")), self.titles(page1))
        self.assertNotIn("halaman=1", page1)                          # halaman 1 memakai URL bersih
        self.assertIn("halaman=2", page1)

    def test_guest_sees_login_redirects_for_member_pages(self):
        for path in ("/forum/buat", "/forum/saya", "/forum/pengaturan"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/infosys/login", response.headers["Location"])
            self.assertIn("next=", response.headers["Location"])


# --------------------------------------------------------------------------
class CreateThreadTests(ForumTestCase):
    def test_form_renders_for_member(self):
        self.as_user(1)
        html = self.get("/forum/buat")
        self.assertIn('name="title"', html)
        self.assertIn('name="body"', html)
        self.assertIn("Diskusi Umum", html)
        self.assertNotIn("Teknologi", html)

    def test_category_prefilled_from_query(self):
        self.as_user(1)
        self.assertRegex(self.get("/forum/buat?kategori=tanya-jawab"), r'<option value="2" selected>')

    def test_success_creates_thread(self):
        self.as_user(1)
        response = self.new_thread(title="  Pertanyaan   baru  ", body="  Isi pertanyaan yang cukup panjang.  ", category=2)
        self.assertEqual(response.status_code, 302)
        new_id = self.sql("SELECT MAX(id) FROM threads")[0][0]
        self.assertTrue(response.headers["Location"].endswith(f"/forum/thread/{new_id}"))
        row = self.sql("SELECT user_id, category_id, title, body, is_solved, views FROM threads WHERE id=?", (new_id,))[0]
        self.assertEqual(row, (1, 2, "Pertanyaan baru", "Isi pertanyaan yang cukup panjang.", 0, 0))
        self.assertEqual(self.sql("SELECT action, module_key FROM activity_logs WHERE user_id=1"), [("create_thread", "forum")])
        page = self.client.get(response.headers["Location"]).get_data(as_text=True)
        self.assertIn("Pertanyaan baru", page)
        self.assertIn("flash-data", page)

    def test_validation_errors_keep_input(self):
        self.as_user(1)
        before = self.sql("SELECT COUNT(*) FROM threads")[0][0]
        response = self.new_thread(title="abc", body="pendek", category=99)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], before)
        for fragment in ("Judul terlalu pendek", "Isi terlalu pendek", "Pilih salah satu kategori"):
            self.assertIn(fragment, html)
        self.assertIn('value="abc"', html)                           # isian dipertahankan
        self.assertIn(">pendek</textarea>", html)
        self.assertEqual(html.count('aria-invalid="true"'), 3)

    def test_empty_submission(self):
        self.as_user(1)
        response = self.post("/forum/buat", {})
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Judul belum diisi", html)
        self.assertIn("Isi topik belum diisi", html)

    def test_title_too_long(self):
        self.as_user(1)
        response = self.new_thread(title="x" * 151)
        self.assertEqual(response.status_code, 422)
        self.assertIn("terlalu panjang", response.get_data(as_text=True))

    def test_category_of_other_module_rejected(self):
        self.as_user(1)
        response = self.new_thread(category=4)                       # kategori portal
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], 3)

    def test_csrf_required(self):
        self.as_user(1)
        for token in (False, "salah"):
            response = self.new_thread(token=token)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], 3)

    def test_guest_cannot_post(self):
        response = self.client.post("/forum/buat", data={"title": "Judul valid", "body": "Isi cukup panjang sekali", "category_id": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/infosys/login", response.headers["Location"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], 3)


# --------------------------------------------------------------------------
class DetailTests(ForumTestCase):
    def test_detail_renders_for_guest(self):
        html = self.get("/forum/thread/1")
        self.assertIn("Topik Milik Demo", html)
        self.assertIn("Isi topik milik demo", html)
        self.assertIn("Balasan sepuluh dari orang lain", html)
        self.assertIn("2 balasan", html)
        self.assertIn("Masuk untuk membalas", html)                  # tanpa form untuk Guest
        self.assertNotIn('id="form-balas"', html)
        self.assertNotIn("data-fm-reply ", html)

    def test_404(self):
        self.assertEqual(self.client.get("/forum/thread/999").status_code, 404)
        self.assertEqual(self.client.get("/forum/thread/abc").status_code, 404)

    def test_views_once_per_session(self):
        before = self.sql("SELECT views FROM threads WHERE id=1")[0][0]
        self.client.get("/forum/thread/1")
        self.client.get("/forum/thread/1")
        self.assertEqual(self.sql("SELECT views FROM threads WHERE id=1")[0][0], before + 1)
        self.client_for(None).get("/forum/thread/1")
        self.assertEqual(self.sql("SELECT views FROM threads WHERE id=1")[0][0], before + 2)

    def test_nested_replies_indent_and_limit_three_levels(self):
        # rantai di thread 2: p20 (tingkat 1) <- p21 <- p22 <- p23 <- p24
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            "INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (?,?,?,?,?,?)",
            ((21, 2, 2, 20, "Tingkat dua", "2026-01-05T05:00:00+00:00"),
             (22, 2, 3, 21, "Tingkat tiga", "2026-01-05T06:00:00+00:00"),
             (23, 2, 1, 22, "Tingkat empat nyata", "2026-01-05T07:00:00+00:00"),
             (24, 2, 2, 23, "Tingkat lima nyata", "2026-01-05T08:00:00+00:00")))
        conn.commit()
        conn.close()
        html = self.get("/forum/thread/2")
        self.assertEqual(self.levels(html), [(20, 1), (21, 2), (22, 3), (23, 3), (24, 3)])
        self.assertNotIn('data-level="4"', html)
        self.assertIn("lebih dari 3 tingkat", html)                  # catatan penjelas muncul
        # parent_post_id asli tetap tersimpan di database
        self.assertEqual(self.sql("SELECT parent_post_id FROM posts WHERE id=24")[0][0], 23)
        self.assertRegex(html, r'Membalas <a href="#balasan-23"[^>]*>Demo Pengguna</a>')

    def test_two_level_thread_has_no_depth_note(self):
        html = self.get("/forum/thread/1")
        self.assertEqual(self.levels(html), [(10, 1), (11, 2)])
        self.assertNotIn("lebih dari 3 tingkat", html)
        self.assertRegex(html, r'Membalas <a href="#balasan-10"[^>]*>Orang Lain</a>')

    def test_solution_and_solved_badge_in_detail(self):
        html = self.get("/forum/thread/3")
        self.assertEqual(html.count('<span class="fm-solved">'), 2)  # lencana thread + lencana "Solusi" pada balasan
        self.assertIn("is-solution", html)
        self.assertIn('href="#balasan-31"', html)

    def test_reply_form_for_member_and_balas_param(self):
        self.as_user(2)
        html = self.get("/forum/thread/1")
        self.assertIn('id="form-balas"', html)
        self.assertIn('name="parent_post_id" value=""', html)
        self.assertNotIn("fm-form-in", html)
        targeted = self.get("/forum/thread/1?balas=10")
        self.assertIn('name="parent_post_id" value="10"', targeted)
        self.assertIn("fm-form-in", targeted)                        # form meluncur naik (slide-up)
        self.assertIn("Orang Lain</strong>", targeted)
        bad = self.get("/forum/thread/1?balas=999")                  # induk asing diabaikan
        self.assertIn('name="parent_post_id" value=""', bad)
        foreign = self.get("/forum/thread/1?balas=20")               # balasan milik thread lain diabaikan
        self.assertIn('name="parent_post_id" value=""', foreign)


# --------------------------------------------------------------------------
class ReplyTests(ForumTestCase):
    def test_guest_cannot_reply(self):
        response = self.client.post("/forum/thread/1/balas", data={"body": "Balasan dari tamu"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/infosys/login", response.headers["Location"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE thread_id=1")[0][0], 2)

    def test_reply_top_level_and_notification(self):
        self.as_user(2)
        response = self.reply(1, "  Balasan baru yang bagus  ")
        new_id = self.sql("SELECT MAX(id) FROM posts")[0][0]
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/forum/thread/1#balasan-{new_id}"))
        row = self.sql("SELECT thread_id, user_id, parent_post_id, body FROM posts WHERE id=?", (new_id,))[0]
        self.assertEqual(row, (1, 2, None, "Balasan baru yang bagus"))
        note = self.sql("SELECT user_id, module_key, message, link_url, is_read FROM notifications")
        self.assertEqual(len(note), 1)
        self.assertEqual(note[0][:3], (1, "forum", "Orang Lain membalas topik Anda: Topik Milik Demo"))
        self.assertEqual(note[0][3], f"/forum/thread/1#balasan-{new_id}")
        self.assertEqual(note[0][4], 0)
        self.assertTrue(is_safe_next(note[0][3]))
        self.assertIn(("reply", "forum"), self.sql("SELECT action, module_key FROM activity_logs WHERE user_id=2"))
        self.assertIsNotNone(self.sql("SELECT updated_at FROM threads WHERE id=1")[0][0])

    def test_notification_visible_in_topbar_for_thread_author(self):
        self.as_user(2)
        self.reply(1, "Balasan untuk dibaca pemilik")
        owner = self.client_for(1)
        html = owner.get("/forum/").get_data(as_text=True)
        self.assertIn("Orang Lain membalas topik Anda: Topik Milik Demo", html)

    def test_nested_reply_stores_parent(self):
        self.as_user(3)
        self.reply(1, "Menanggapi balasan sepuluh", parent=10)
        row = self.sql("SELECT parent_post_id FROM posts WHERE id=(SELECT MAX(id) FROM posts)")[0]
        self.assertEqual(row[0], 10)

    def test_reply_to_parent_in_other_thread_rejected(self):
        self.as_user(2)
        before = self.sql("SELECT COUNT(*) FROM posts")[0][0]
        response = self.reply(1, "Induk dari topik lain", parent=20)
        self.assertEqual(response.status_code, 422)
        self.assertIn("tidak ditemukan", response.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], before)

    def test_reply_with_garbage_parent_rejected(self):
        self.as_user(2)
        before = self.sql("SELECT COUNT(*) FROM posts")[0][0]
        for parent in ("abc", "99999", "-1"):
            self.assertEqual(self.reply(1, "Induk ngawur", parent=parent).status_code, 422, parent)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], before)

    def test_reply_validation_keeps_text(self):
        self.as_user(2)
        response = self.reply(1, "ab")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Balasan terlalu pendek", html)
        self.assertIn(">ab</textarea>", html)
        self.assertIn('aria-invalid="true"', html)
        empty = self.reply(1, "   ").get_data(as_text=True)
        self.assertIn("Balasan belum diisi", empty)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE thread_id=1")[0][0], 2)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 0)

    def test_validation_error_page_keeps_reply_target(self):
        self.as_user(2)
        html = self.reply(1, "ab", parent=10).get_data(as_text=True)
        self.assertIn('name="parent_post_id" value="10"', html)
        self.assertIn("fm-form-in", html)

    def test_reply_too_long(self):
        self.as_user(2)
        self.assertEqual(self.reply(1, "x" * 3001).status_code, 422)

    def test_reply_to_missing_thread_404(self):
        self.as_user(2)
        self.assertEqual(self.reply(999, "Balasan ke topik hilang").status_code, 404)

    def test_csrf_required(self):
        self.as_user(2)
        for token in (False, "salah"):
            response = self.reply(1, "Balasan tanpa token sah", token=token)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE thread_id=1")[0][0], 2)

    def test_new_reply_slides_up_once(self):
        self.as_user(2)
        response = self.reply(1, "Balasan yang meluncur naik")
        new_id = self.sql("SELECT MAX(id) FROM posts")[0][0]
        page = self.client.get(response.headers["Location"].split("#")[0]).get_data(as_text=True)
        self.assertIn(f'<li id="balasan-{new_id}" class="fm-post is-new animate-slide-up"', page)
        self.assertEqual(page.count("is-new animate-slide-up"), 1)
        self.assertIn("Balasan terkirim", page)
        again = self.get("/forum/thread/1")
        self.assertNotIn("is-new", again)                            # hanya sekali

    def test_notification_not_sent_for_own_reply(self):
        self.as_user(1)
        self.reply(1, "Pemilik membalas threadnya sendiri")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 0)

    def test_notification_respects_setting(self):
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) VALUES (1,'forum','notify_reply','0')")
        self.as_user(2)
        self.reply(1, "Balasan saat notifikasi dimatikan")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE thread_id=1")[0][0], 3)   # balasan tetap tersimpan
        self.sql("UPDATE module_settings SET setting_value='1' WHERE user_id=1 AND setting_key='notify_reply'")
        self.reply(1, "Balasan saat notifikasi dinyalakan")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications WHERE user_id=1")[0][0], 1)

    def test_notification_goes_only_to_thread_author(self):
        self.as_user(3)
        self.reply(1, "Menanggapi balasan orang lain", parent=10)    # penulis p10 = pengguna 2, tapi thread milik 1
        rows = self.sql("SELECT user_id FROM notifications")
        self.assertEqual(rows, [(1,)])

    def test_database_error_rolls_back(self):
        self.as_user(2)
        self.sql("CREATE TRIGGER boom BEFORE INSERT ON notifications BEGIN SELECT RAISE(ABORT, 'gagal'); END")
        response = self.reply(1, "Balasan yang gagal disimpan")
        self.assertEqual(response.status_code, 500)
        self.assertIn("belum bisa disimpan", response.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE thread_id=1")[0][0], 2)  # semua dibatalkan
        self.assertIn("Balasan yang gagal disimpan", response.get_data(as_text=True))        # teks tidak hilang


# --------------------------------------------------------------------------
class SolutionTests(ForumTestCase):
    def solve(self, thread_id, post_id=None, action="mark", client=None, **kw):
        data = {"action": action}
        if post_id is not None:
            data["post_id"] = str(post_id)
        return self.post(f"/forum/thread/{thread_id}/solusi", data, client=client, **kw)

    def state(self, thread_id):
        return self.sql("SELECT is_solved, accepted_post_id FROM threads WHERE id=?", (thread_id,))[0]

    def test_owner_marks_solution(self):
        self.as_user(1)
        response = self.solve(1, 10)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/forum/thread/1#balasan-10"))
        self.assertEqual(self.state(1), (1, 10))
        self.assertIn("mark_solution", [r[0] for r in self.sql("SELECT action FROM activity_logs")])
        self.assertIn("Terjawab", self.get("/forum/"))

    def test_non_owner_forbidden(self):
        self.as_user(2)
        self.assertEqual(self.solve(1, 10).status_code, 403)
        self.assertEqual(self.state(1), (0, None))
        self.assertEqual(self.solve(3, 30, action="unmark").status_code, 403)   # juga tidak boleh membatalkan
        self.assertEqual(self.state(3), (1, 31))

    def test_guest_redirected(self):
        response = self.client.post("/forum/thread/1/solusi", data={"action": "mark", "post_id": "10"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/infosys/login", response.headers["Location"])
        self.assertEqual(self.state(1), (0, None))

    def test_post_from_other_thread_rejected(self):
        self.as_user(1)
        response = self.solve(1, 20)                                  # p20 milik thread 2
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.state(1), (0, None))
        self.assertIn("flash-data", self.client.get("/forum/thread/1").get_data(as_text=True))
        self.assertEqual(self.solve(1, "abc").status_code, 302)
        self.assertEqual(self.solve(1).status_code, 302)              # tanpa post_id
        self.assertEqual(self.state(1), (0, None))

    def test_change_solution_and_unmark(self):
        self.as_user(1)
        self.solve(1, 10)
        self.solve(1, 11)
        self.assertEqual(self.state(1), (1, 11))                      # satu solusi saja
        self.solve(1, action="unmark")
        self.assertEqual(self.state(1), (0, None))
        self.assertIn("unmark_solution", [r[0] for r in self.sql("SELECT action FROM activity_logs")])

    def test_csrf_required(self):
        self.as_user(1)
        self.solve(1, 10, token=False)
        self.solve(1, 10, token="salah")
        self.assertEqual(self.state(1), (0, None))

    def test_invalid_action(self):
        self.as_user(1)
        self.assertEqual(self.solve(1, 10, action="hapus").status_code, 400)

    def test_missing_thread(self):
        self.as_user(1)
        self.assertEqual(self.solve(999, 10).status_code, 404)

    def test_buttons_only_for_thread_owner(self):
        self.as_user(1)
        self.assertIn("Tandai sebagai solusi", self.get("/forum/thread/1"))
        self.assertNotIn("Tandai sebagai solusi", self.get("/forum/thread/2"))     # bukan pemilik thread 2
        self.as_user(2)
        self.assertNotIn("Tandai sebagai solusi", self.get("/forum/thread/1"))
        self.assertNotIn("Tandai sebagai solusi", self.client_for(None).get("/forum/thread/1").get_data(as_text=True))
        self.as_user(3)
        self.assertIn("Batalkan tanda solusi", self.get("/forum/thread/3"))


# --------------------------------------------------------------------------
class OwnPostTests(ForumTestCase):
    def body(self, post_id):
        return self.sql("SELECT body FROM posts WHERE id=?", (post_id,))[0][0]

    def test_owner_sees_actions_only_on_own_posts(self):
        self.as_user(2)
        html = self.get("/forum/thread/1")
        self.assertIn("/forum/balasan/10/ubah", html)
        self.assertIn("/forum/balasan/10/hapus", html)
        self.assertNotIn("/forum/balasan/11/ubah", html)
        self.assertNotIn("/forum/balasan/11/hapus", html)
        guest = self.client_for(None).get("/forum/thread/1").get_data(as_text=True)
        self.assertNotIn("/forum/balasan/", guest)

    def test_owner_can_edit(self):
        self.as_user(2)
        self.assertIn("Balasan sepuluh dari orang lain", self.get("/forum/balasan/10/ubah"))
        response = self.post("/forum/balasan/10/ubah", {"body": "  Isi balasan yang sudah diubah  "})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/forum/thread/1#balasan-10"))
        self.assertEqual(self.body(10), "Isi balasan yang sudah diubah")
        self.assertEqual(self.sql("SELECT created_at, parent_post_id, user_id FROM posts WHERE id=10")[0],
                         ("2026-01-01T04:00:00+00:00", None, 2))
        self.assertIn("edit_reply", [r[0] for r in self.sql("SELECT action FROM activity_logs")])

    def test_edit_validation(self):
        self.as_user(2)
        response = self.post("/forum/balasan/10/ubah", {"body": "ab"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("terlalu pendek", response.get_data(as_text=True))
        self.assertEqual(self.body(10), "Balasan sepuluh dari orang lain")

    def test_others_cannot_edit(self):
        # pengguna 3 (bukan penulis p10), dan pengguna 1 (pemilik thread 1) sama-sama ditolak
        for uid in (3, 1):
            self.as_user(uid)
            self.assertEqual(self.client.get("/forum/balasan/10/ubah").status_code, 403, uid)
            self.assertEqual(self.post("/forum/balasan/10/ubah", {"body": "Dibajak orang lain"}).status_code, 403, uid)
            self.assertEqual(self.body(10), "Balasan sepuluh dari orang lain")

    def test_others_cannot_delete(self):
        for uid in (3, 1):
            self.as_user(uid)
            self.assertEqual(self.client.get("/forum/balasan/10/hapus").status_code, 403, uid)
            self.assertEqual(self.post("/forum/balasan/10/hapus").status_code, 403, uid)
            self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=10")[0][0], 1)

    def test_guest_cannot_edit_or_delete(self):
        for path in ("/forum/balasan/10/ubah", "/forum/balasan/10/hapus"):
            self.assertEqual(self.client.get(path).status_code, 302)
            self.assertEqual(self.client.post(path, data={"body": "tamu"}).status_code, 302)
        self.assertEqual(self.body(10), "Balasan sepuluh dari orang lain")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=10")[0][0], 1)

    def test_missing_post_404(self):
        self.as_user(2)
        self.assertEqual(self.client.get("/forum/balasan/999/ubah").status_code, 404)
        self.assertEqual(self.client.get("/forum/balasan/999/hapus").status_code, 404)

    def test_csrf_required(self):
        self.as_user(2)
        self.post("/forum/balasan/10/ubah", {"body": "Tanpa token sah"}, token=False)
        self.post("/forum/balasan/10/hapus", token="salah")
        self.assertEqual(self.body(10), "Balasan sepuluh dari orang lain")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=10")[0][0], 1)

    def test_delete_confirm_page_and_delete(self):
        self.as_user(3)
        page = self.get("/forum/balasan/11/hapus")
        self.assertIn("Hapus balasan ini?", page)
        self.assertIn("Balasan sebelas menanggapi sepuluh", page)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=11")[0][0], 1)        # GET tidak menghapus
        response = self.post("/forum/balasan/11/hapus")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=11")[0][0], 0)
        self.assertIn("delete_reply", [r[0] for r in self.sql("SELECT action FROM activity_logs")])

    def test_delete_promotes_children(self):
        self.as_user(2)
        self.assertIn("1 balasan lain", self.get("/forum/balasan/10/hapus"))
        self.post("/forum/balasan/10/hapus")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts WHERE id=10")[0][0], 0)
        self.assertEqual(self.sql("SELECT parent_post_id FROM posts WHERE id=11")[0][0], None)  # naik jadi tingkat atas
        self.assertEqual(self.levels(self.get("/forum/thread/1")), [(11, 1)])

    def test_delete_middle_of_chain_reparents_to_grandparent(self):
        conn = sqlite3.connect(self.db_path)
        conn.executemany("INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (?,?,?,?,?,?)",
                         ((21, 2, 2, 20, "Tengah rantai", "2026-01-05T05:00:00+00:00"),
                          (22, 2, 3, 21, "Ujung rantai", "2026-01-05T06:00:00+00:00")))
        conn.commit()
        conn.close()
        self.as_user(2)
        self.post("/forum/balasan/21/hapus")
        self.assertEqual(self.sql("SELECT parent_post_id FROM posts WHERE id=22")[0][0], 20)

    def test_deleting_solution_unsolves_thread(self):
        self.as_user(2)
        self.assertIn("kembali berstatus belum terjawab", self.get("/forum/balasan/31/hapus"))
        self.post("/forum/balasan/31/hapus")
        self.assertEqual(self.sql("SELECT is_solved, accepted_post_id FROM threads WHERE id=3")[0], (0, None))

    def test_reply_count_drops_after_delete(self):
        self.as_user(2)
        self.post("/forum/balasan/10/hapus")
        self.assertIn("1 balasan", self.get("/forum/thread/1"))


# --------------------------------------------------------------------------
class MyThreadsTests(ForumTestCase):
    def test_lists_only_own_threads(self):
        self.as_user(1)
        html = self.get("/forum/saya")
        self.assertEqual(self.titles(html), ["Topik Milik Demo"])
        self.assertIn("1 topik yang Anda mulai", html)
        self.assertIn("0 di antaranya sudah terjawab", html)

    def test_solved_count_and_badge(self):
        self.as_user(3)
        html = self.get("/forum/saya")
        self.assertEqual(self.titles(html), ["Topik Terjawab"])
        self.assertIn("1 di antaranya sudah terjawab", html)
        self.assertEqual(html.count('<span class="fm-solved">'), 1)

    def test_empty_state(self):
        self.sql("UPDATE threads SET user_id = 2 WHERE user_id = 1")
        self.as_user(1)
        html = self.get("/forum/saya")
        self.assertIn("Anda belum membuat topik", html)
        self.assertEqual(self.titles(html), [])

    def test_new_thread_appears(self):
        self.as_user(2)
        self.new_thread(title="Topik terbaru milik dua")
        self.assertEqual(self.titles(self.get("/forum/saya"))[0], "Topik terbaru milik dua")


# --------------------------------------------------------------------------
class SettingsTests(ForumTestCase):
    def save(self, privacy="public", notify="1", **kw):
        return self.post("/forum/pengaturan", {"profile_privacy": privacy, "notify_reply": notify}, **kw)

    def test_defaults(self):
        self.as_user(2)
        html = self.get("/forum/pengaturan")
        self.assertRegex(html, r'name="profile_privacy" value="public"\s+checked')
        self.assertRegex(html, r'name="notify_reply" value="1"\s+checked')

    def test_save_both_settings(self):
        self.as_user(2)
        response = self.save("private", "0")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.setting(2, "profile_privacy"), "private")
        self.assertEqual(self.setting(2, "notify_reply"), "0")
        html = self.get("/forum/pengaturan")
        self.assertRegex(html, r'name="profile_privacy" value="private"\s+checked')
        self.assertRegex(html, r'name="notify_reply" value="0"\s+checked')
        self.assertIn("forum_settings", [r[0] for r in self.sql("SELECT action FROM activity_logs WHERE user_id=2")])

    def test_update_is_upsert_not_duplicate(self):
        self.as_user(2)
        self.save("members", "1")
        self.save("private", "0")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE user_id=2 AND module_key='forum'")[0][0], 2)

    def test_invalid_values_rejected(self):
        self.as_user(2)
        self.save("ngawur", "1")
        self.save("public", "mungkin")
        self.save("", "")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings WHERE user_id=2")[0][0], 0)

    def test_csrf_required(self):
        self.as_user(2)
        self.save("private", "0", token=False)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_settings_are_per_user(self):
        self.as_user(2)
        self.save("private", "0")
        self.assertIsNone(self.setting(1, "profile_privacy"))
        self.assertRegex(self.get("/forum/pengaturan", client=self.client_for(1)), r'name="profile_privacy" value="public"\s+checked')

    def test_notify_setting_changes_notifications(self):
        self.as_user(1)
        self.save("public", "0")
        self.reply(1, "Balasan setelah dimatikan", client=self.client_for(2))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 0)
        self.save("public", "1")
        self.reply(1, "Balasan setelah dinyalakan", client=self.client_for(2))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications")[0][0], 1)


class ProfilePrivacyTests(ForumTestCase):
    def set_privacy(self, user_id, value):
        self.sql("INSERT OR REPLACE INTO module_settings (user_id, module_key, setting_key, setting_value) "
                 "VALUES (?, 'forum', 'profile_privacy', ?)", (user_id, value))

    def test_public_profile_visible_to_guest(self):
        html = self.get("/forum/pengguna/1")
        self.assertIn("Bio rahasia demo", html)
        self.assertIn("Topik Milik Demo", html)
        self.assertNotIn("demo@dke.test", html)                      # email tidak pernah tampil

    def test_members_only(self):
        self.set_privacy(1, "members")
        guest = self.get("/forum/pengguna/1")
        self.assertNotIn("Bio rahasia demo", guest)
        self.assertNotIn("Topik Milik Demo", guest)
        self.assertIn("Masuk untuk melihat profil ini", guest)
        member = self.get("/forum/pengguna/1", client=self.client_for(2))
        self.assertIn("Bio rahasia demo", member)

    def test_private(self):
        self.set_privacy(1, "private")
        for client in (self.client_for(None), self.client_for(2)):
            html = self.get("/forum/pengguna/1", client=client)
            self.assertIn("Profil ini privat", html)
            self.assertNotIn("Bio rahasia demo", html)
            self.assertNotIn("Topik Milik Demo", html)
            self.assertIn("Demo Pengguna", html)                     # nama tetap tampil
        own = self.get("/forum/pengguna/1", client=self.client_for(1))
        self.assertIn("Bio rahasia demo", own)
        self.assertIn("Profil Anda diatur", own)

    def test_privacy_change_takes_effect_through_settings_page(self):
        owner = self.client_for(1)
        self.post("/forum/pengaturan", {"profile_privacy": "private", "notify_reply": "1"}, client=owner)
        self.assertIn("Profil ini privat", self.get("/forum/pengguna/1", client=self.client_for(None)))

    def test_missing_or_inactive_user_404(self):
        self.assertEqual(self.client.get("/forum/pengguna/999").status_code, 404)
        self.sql("UPDATE users SET is_active = 0 WHERE id = 3")
        self.assertEqual(self.client.get("/forum/pengguna/3").status_code, 404)


# --------------------------------------------------------------------------
class SecurityTests(ForumTestCase):
    def test_user_content_is_escaped_everywhere(self):
        self.sql("UPDATE users SET full_name = ?, bio = ? WHERE id = 2", (f"Nama {XSS}", f"Bio {XSS}"))
        self.sql("INSERT INTO threads (id, category_id, user_id, title, body, created_at) VALUES (50, 1, 2, ?, ?, '2026-04-01T00:00:00+00:00')",
                 (f"Judul {XSS}", f"Isi {XSS}\n\nParagraf <img src=x onerror=alert(3)>"))
        self.sql("INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (60, 50, 2, NULL, ?, '2026-04-01T01:00:00+00:00')",
                 (f"Balasan {XSS} dan {ATTR}",))
        self.sql("INSERT INTO posts (id, thread_id, user_id, parent_post_id, body, created_at) VALUES (61, 50, 1, 60, ?, '2026-04-01T02:00:00+00:00')",
                 (f"Anak {XSS}",))
        member = self.client_for(1)
        pages = {
            "list": self.get("/forum/", client=member),
            "list-guest": self.get("/forum/"),
            "detail": self.get("/forum/thread/50", client=member),
            "reply-target": self.get("/forum/thread/50?balas=60", client=member),
            "profile": self.get("/forum/pengguna/2", client=member),
            "edit": self.get("/forum/balasan/61/ubah", client=member),
            "delete": self.get("/forum/balasan/61/hapus", client=member),
        }
        self.sql("UPDATE threads SET user_id = 1 WHERE id = 50")
        pages["mine"] = self.get("/forum/saya", client=member)
        for name, html in pages.items():
            self.assertNotIn(XSS, html, name)
            self.assertNotIn("<img src=x onerror", html, name)
            self.assertNotIn(ATTR, html, name)                       # tanda kutip pada atribut ikut di-escape
        self.assertIn(XSS_ESCAPED, pages["detail"])
        self.assertIn("Judul " + XSS_ESCAPED, pages["list"])

    def test_xss_in_notification_message(self):
        self.sql("UPDATE threads SET title = ? WHERE id = 1", (f"Judul {XSS}",))
        self.sql("UPDATE users SET full_name = ? WHERE id = 2", (f"Pengirim {XSS}",))
        self.reply(1, "Balasan memicu notifikasi", client=self.client_for(2))
        html = self.get("/forum/", client=self.client_for(1))
        self.assertNotIn(XSS, html)
        self.assertIn("membalas topik Anda", html)

    def test_xss_payload_stored_verbatim_not_mangled(self):
        self.as_user(1)
        self.new_thread(title=f"Judul {XSS} ok", body=f"Isi topik {XSS} cukup panjang")
        row = self.sql("SELECT title, body FROM threads ORDER BY id DESC LIMIT 1")[0]
        self.assertIn(XSS, row[0])                                   # disimpan apa adanya; dilindungi saat dicetak
        self.assertIn(XSS, row[1])

    def test_templates_never_disable_escaping(self):
        folders = [os.path.join(ROOT, "app", "templates", "forum"), os.path.join(ROOT, "app", "forum")]
        checked = 0
        for folder in folders:
            for name in os.listdir(folder):
                if not name.endswith((".html", ".py")):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    text = handle.read()
                checked += 1
                for banned in ("|safe", "| safe", "Markup(", "autoescape false", "autoescape=False"):
                    if name.endswith(".py") and banned == "autoescape false":
                        continue  # kata itu muncul di docstring sebagai larangan
                    if name == "routes.py" and banned in ("|safe",):
                        continue  # docstring menyebut larangan ini
                    self.assertNotIn(banned, text, f"{name}: {banned}")
        self.assertGreater(checked, 10)

    def test_javascript_never_uses_innerhtml(self):
        with open(os.path.join(ROOT, "app", "static", "js", "forum.js"), encoding="utf-8") as handle:
            code = handle.read()
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(banned, code)

    def test_sql_injection_in_filters_is_inert(self):
        for path in ("/forum/?kategori=' OR 1=1 --", "/forum/?urut=x'; DROP TABLE threads; --", "/forum/?halaman=1;DROP TABLE posts"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], 3)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], 5)

    def test_sql_injection_in_forms_is_inert(self):
        self.as_user(1)
        self.new_thread(title="x'); DROP TABLE posts; --", body="Isi dengan kutip ' dan \" dan ; cukup panjang")
        self.reply(1, "Balasan '); DROP TABLE threads; --", parent="1 OR 1=1")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM threads")[0][0], 4)
        self.assertGreaterEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], 5)

    def test_forged_ids_in_forms_cannot_impersonate(self):
        self.as_user(2)
        self.post("/forum/thread/1/balas", {"body": "Balasan dengan user_id palsu", "user_id": "1", "thread_id": "3"})
        row = self.sql("SELECT user_id, thread_id FROM posts WHERE body='Balasan dengan user_id palsu'")[0]
        self.assertEqual(row, (2, 1))
        self.post("/forum/buat", {"title": "Judul valid", "body": "Isi cukup panjang sekali", "category_id": "1", "user_id": "3", "is_solved": "1"})
        self.assertEqual(self.sql("SELECT user_id, is_solved FROM threads ORDER BY id DESC LIMIT 1")[0], (2, 0))

    def test_get_requests_do_not_modify_data(self):
        self.as_user(2)
        before = self.sql("SELECT COUNT(*) FROM posts")[0][0], self.sql("SELECT body FROM posts WHERE id=10")[0][0]
        for path in ("/forum/balasan/10/hapus", "/forum/balasan/10/ubah", "/forum/thread/1/solusi", "/forum/thread/1/balas"):
            self.client.get(path)
        self.assertEqual((self.sql("SELECT COUNT(*) FROM posts")[0][0], self.sql("SELECT body FROM posts WHERE id=10")[0][0]), before)


# --------------------------------------------------------------------------
class NavigationAndIntegrationTests(ForumTestCase):
    def test_breadcrumb_for_detail(self):
        html = self.get("/forum/thread/1")
        self.assertIn("Topik Milik Demo", html)
        self.assertRegex(html, r'data-breadcrumb')

    def test_breadcrumb_and_back_for_edit_goes_to_thread(self):
        self.as_user(2)
        html = self.get("/forum/balasan/10/ubah")
        self.assertIn("Ubah Balasan", html)
        self.assertIn('/forum/thread/1', html)

    def test_tabs_are_present_and_current(self):
        html = self.get("/forum/")
        self.assertRegex(html, r'href="/forum/"\s+class="fm-nav-link is-active"')
        self.assertIn("Topik Saya", html)
        self.assertRegex(self.get("/forum/pengaturan", client=self.client_for(1)),
                         r'href="/forum/pengaturan"\s+class="fm-nav-link is-active"')

    def test_launcher_widget_counts_unread_forum_notifications(self):
        self.reply(1, "Balasan memicu widget", client=self.client_for(2))
        html = self.get("/", client=self.client_for(1))
        self.assertIn("1 balasan baru", html)

    def test_activity_log_labels_are_friendly(self):
        owner = self.client_for(2)
        self.reply(1, "Balasan untuk label", client=owner)
        self.post("/forum/pengaturan", {"profile_privacy": "public", "notify_reply": "1"}, client=owner)
        html = self.get("/infosys/log", client=owner)
        self.assertIn("Balas topik", html)
        self.assertIn("Ubah pengaturan Forum", html)

    def test_accent_is_teal_in_css(self):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as handle:
            css = handle.read()
        self.assertIn("--fm-accent: 13 148 136", css)
        self.assertIn("fm-form-in", css)
        self.assertIn("fm-slide-up", css)

    def test_pages_declare_forum_accent_and_script(self):
        html = self.get("/forum/")
        self.assertIn("--accent: #0D9488", html)
        self.assertIn("js/forum.js", html)


if __name__ == "__main__":
    unittest.main()
