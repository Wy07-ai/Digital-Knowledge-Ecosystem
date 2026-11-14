"""Tes Portal: beranda (featured + kartu), filter kategori, paginasi, empty state, detail artikel
(waktu baca, penulis, tanggal, terkait, views), preferensi kategori, gambar lazy + alt, keamanan."""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app.portal.routes import (cover_src, estimate_minutes, format_date, format_views, paginate,
                               paragraphs, parse_page)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSS_TITLE = '<b>Judul</b> berbahaya'
XSS_BODY = 'Isi <img src=x onerror=alert(1)> tebal\n\nParagraf <script>alert(2)</script> kedua'


class PortalTests(unittest.TestCase):
    """Data dasar: kategori portal teknologi(2), pendidikan(2), karier(1), kosong(0) + 1 kategori modul lain."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.executemany(
            "INSERT INTO users (id, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            ((1, "Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345")),
             (2, "Orang Lain", "lain@dke.test", generate_password_hash("Lain12345")),
             (3, "Penulis Utama", "penulis@dke.test", generate_password_hash("Penulis123"))),
        )
        conn.executemany(
            "INSERT INTO categories (id, module_key, name, slug) VALUES (?, ?, ?, ?)",
            ((1, "portal", "Teknologi", "teknologi"), (2, "portal", "Pendidikan", "pendidikan"),
             (3, "portal", "Karier", "karier"), (4, "portal", "Kesehatan", "kesehatan"),
             (5, "etutorial", "Python", "python")),
        )
        # (id, kategori, penulis, judul, slug, kutipan, isi, cover, featured, menit, views, terbit)
        conn.executemany(
            "INSERT INTO articles (id, category_id, author_id, title, slug, excerpt, body, cover_url, "
            "is_featured, read_minutes, views, published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ((1, 1, 3, "Tekno Lama Featured", "tekno-lama", "Kutipan tekno lama.", "Isi satu.\n\nIsi dua.",
              "img/portal/default.svg", 1, 6, 100, "2026-01-01T03:00:00+00:00"),
             (2, 1, 3, "Tekno Baru", "tekno-baru", "Kutipan tekno baru.", "Isi tekno baru.",
              None, 0, 4, 50, "2026-01-10T03:00:00+00:00"),
             (3, 2, 3, "Pendidikan Featured", "pendidikan-featured", "Kutipan pendidikan.", "Isi pendidikan.",
              None, 1, 5, 10, "2026-01-05T03:00:00+00:00"),
             (4, 2, 3, "Pendidikan Terbaru", "pendidikan-terbaru", "Kutipan.", "Isi.",
              None, 0, 3, 5, "2026-01-12T03:00:00+00:00"),
             (5, 3, None, "Karier Tanpa Penulis", "karier-tanpa-penulis", "Kutipan karier.", "x" * 2400,
              None, 0, None, 7, "2026-01-08T03:00:00+00:00")),
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

    def get(self, path, client=None):
        return (client or self.client).get(path).get_data(as_text=True)

    def csrf(self, client=None):
        html = (client or self.client).get("/portal/pengaturan").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def save_prefs(self, slugs, action="save", token=None, client=None):
        token = token if token is not None else self.csrf(client)
        return (client or self.client).post(
            "/portal/pengaturan", data={"csrf_token": token, "action": action, "categories": slugs})

    def add_articles(self, count, category_id=1, start=100):
        rows = [(start + i, category_id, 3, f"Massal {start + i}", f"massal-{start + i}", "Kutipan.", "Isi.", None,
                 0, 2, 0, f"2026-02-{(i % 27) + 1:02d}T03:00:00+00:00") for i in range(count)]
        self.sql("SELECT 1")  # pastikan koneksi bebas
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            "INSERT INTO articles (id, category_id, author_id, title, slug, excerpt, body, cover_url, "
            "is_featured, read_minutes, views, published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

    @staticmethod
    def checked_slugs(html):
        """Slug kategori yang kotak centangnya tercentang di formulir Pengaturan."""
        return re.findall(r'<input type="checkbox" name="categories" value="([^"]+)"\s+checked', html)

    @staticmethod
    def titles(html, tag="h3"):
        return [re.sub(r"\s+", " ", t).strip() for t in re.findall(rf"<{tag}[^>]*>\s*<a[^>]*>(.*?)</a>", html, re.S)]

    @staticmethod
    def hero_title(html):
        m = re.search(r'<h2 id="pt-hero-title"[^>]*>\s*<a[^>]*>(.*?)</a>', html, re.S)
        return m.group(1).strip() if m else None

    # ---- UC-PT-01: beranda featured + kartu ----
    def test_home_is_public_with_featured_on_top_and_cards_below(self):
        response = self.client.get("/portal/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # featured terbaru (is_featured menang atas artikel yang lebih baru): Pendidikan Featured (5 Jan)
        self.assertEqual(self.hero_title(html), "Pendidikan Featured")
        self.assertIn("Featured", html)
        # artikel besar muncul sebelum daftar kartu
        self.assertLess(html.index('id="pt-hero-title"'), html.index('id="pt-more"'))
        cards = self.titles(html)
        self.assertEqual(cards, ["Pendidikan Terbaru", "Tekno Baru", "Karier Tanpa Penulis", "Tekno Lama Featured"])
        self.assertNotIn("Pendidikan Featured", cards)  # tidak dobel

    def test_home_falls_back_to_newest_when_nothing_is_featured(self):
        self.sql("UPDATE articles SET is_featured = 0")
        html = self.get("/portal/")
        self.assertEqual(self.hero_title(html), "Pendidikan Terbaru")
        self.assertIn(">Terbaru<", html)
        self.assertNotIn(">Featured<", html)

    def test_cards_show_category_excerpt_read_time_and_date(self):
        html = self.get("/portal/")
        self.assertIn("Kutipan tekno baru.", html)
        self.assertIn("4 menit baca", html)
        self.assertIn("10 Jan 2026", html)
        self.assertIn('datetime="2026-01-10"', html)

    def test_read_minutes_are_estimated_when_missing(self):
        html = self.get("/portal/")  # artikel 5: 2400 karakter -> 2400/6/200 = 2 menit
        self.assertIn("2 menit baca", html)

    def test_pages_use_rose_accent_and_module_name(self):
        html = self.get("/portal/")
        self.assertIn("--accent: #E11D48", html)
        self.assertIn("pt-card", html)

    # ---- UC-PT-02: chip kategori ----
    def test_category_chips_list_all_portal_categories_with_counts_only_for_portal(self):
        html = self.get("/portal/")
        self.assertRegex(html, r"Semua\s*<span class=\"pt-count\">\(5\)</span>")
        self.assertRegex(html, r"Teknologi\s*<span class=\"pt-count\">\(2\)</span>")
        self.assertRegex(html, r"Kesehatan\s*<span class=\"pt-count\">\(0\)</span>")
        self.assertNotIn("Python", html)  # kategori modul lain tidak bocor

    def test_filter_by_category_shows_only_that_category(self):
        html = self.get("/portal/?kategori=teknologi")
        self.assertIn('aria-current="true"', html)
        self.assertEqual(self.hero_title(html), "Tekno Lama Featured")
        self.assertEqual(self.titles(html), ["Tekno Baru"])
        self.assertNotIn("Pendidikan", self.titles(html) + [self.hero_title(html)])
        self.assertIn("Artikel lainnya di Teknologi", html)

    def test_filtered_category_without_featured_promotes_newest(self):
        html = self.get("/portal/?kategori=karier")
        self.assertEqual(self.hero_title(html), "Karier Tanpa Penulis")
        self.assertNotIn('id="pt-more"', html)  # hanya satu artikel: tidak ada kartu

    def test_unknown_category_is_ignored_with_notice(self):
        html = self.get("/portal/?kategori=ngawur")
        self.assertIn("Kategori itu tidak dikenal", html)
        self.assertEqual(self.hero_title(html), "Pendidikan Featured")

    def test_category_filter_is_case_insensitive(self):
        self.assertEqual(self.hero_title(self.get("/portal/?kategori=TEKNOLOGI")), "Tekno Lama Featured")

    # ---- empty state ----
    def test_category_without_articles_shows_empty_state(self):
        response = self.client.get("/portal/?kategori=kesehatan")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Belum ada artikel di kategori Kesehatan", html)
        self.assertIn("Lihat semua artikel", html)
        self.assertNotIn('id="pt-hero-title"', html)
        self.assertNotIn('id="pt-more"', html)

    def test_portal_without_any_article_shows_empty_state(self):
        self.sql("DELETE FROM articles")
        html = self.get("/portal/")
        self.assertIn("Belum ada artikel", html)
        self.assertNotIn("Belum ada artikel di kategori", html)
        self.assertEqual(self.client.get("/portal/").status_code, 200)

    def test_empty_chip_still_links_to_empty_state(self):
        self.assertIn("/portal/?kategori=kesehatan", self.get("/portal/"))

    # ---- paginasi ----
    def test_pagination_splits_cards_and_hides_hero_after_page_one(self):
        self.add_articles(10)  # total 15: 1 hero + 14 kartu => 3 halaman (6 + 6 + 2)
        page1, page2, page3 = (self.get(f"/portal/?halaman={n}") for n in (1, 2, 3))
        self.assertIsNotNone(self.hero_title(page1))
        self.assertIsNone(self.hero_title(page2))
        self.assertEqual(len(self.titles(page1)), 6)
        self.assertEqual(len(self.titles(page2)), 6)
        self.assertEqual(len(self.titles(page3)), 2)
        self.assertIn("Menampilkan 1&ndash;6 dari 14 artikel lainnya", page1)
        self.assertIn("Menampilkan 13&ndash;14 dari 14 artikel lainnya", page3)
        seen = self.titles(page1) + self.titles(page2) + self.titles(page3) + [self.hero_title(page1)]
        self.assertEqual(len(seen), len(set(seen)), "tidak boleh ada artikel yang tampil dua kali")

    def test_pagination_links_keep_category_and_mark_current_page(self):
        self.add_articles(10)
        html = self.get("/portal/?kategori=teknologi")
        self.assertIn('rel="next"', html)
        self.assertIn("/portal/?kategori=teknologi&amp;halaman=2", html)
        self.assertIn('aria-current="page"', html)
        self.assertIn('aria-disabled="true"', html)  # Sebelumnya nonaktif di halaman 1

    def test_pagination_not_shown_for_single_page(self):
        self.assertNotIn('rel="next"', self.get("/portal/"))

    def test_bad_page_numbers_are_clamped(self):
        self.add_articles(10)
        for raw in ("abc", "-4", "0", ""):
            self.assertEqual(self.client.get(f"/portal/?halaman={raw}").status_code, 200)
            self.assertIsNotNone(self.hero_title(self.get(f"/portal/?halaman={raw}")), raw)
        last = self.get("/portal/?halaman=999")
        self.assertIn("Menampilkan 13&ndash;14 dari 14", last)

    # ---- UC-PT-03: detail artikel ----
    def test_detail_shows_title_author_date_read_time_and_views(self):
        html = self.get("/portal/artikel/tekno-baru")
        self.assertIn("<h1", html)
        self.assertIn("Tekno Baru", html)
        self.assertIn("Penulis Utama", html)
        self.assertIn("10 Jan 2026", html)
        self.assertIn("4 menit baca", html)
        self.assertIn("51 kali dibaca", html)  # 50 + kunjungan ini
        self.assertIn("Isi tekno baru.", html)

    def test_detail_without_author_uses_editorial_name_and_estimated_time(self):
        html = self.get("/portal/artikel/karier-tanpa-penulis")
        self.assertIn("Redaksi DKE", html)
        self.assertIn("2 menit baca", html)

    def test_detail_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/portal/artikel/tidak-ada").status_code, 404)

    def test_detail_renders_paragraphs(self):
        html = self.get("/portal/artikel/tekno-lama")
        self.assertIn("<p>Isi satu.</p>", html)
        self.assertIn("<p>Isi dua.</p>", html)

    def test_detail_breadcrumb_and_back_link_point_to_portal(self):
        html = self.get("/portal/artikel/tekno-baru")
        self.assertIn('href="/portal/"', html)
        self.assertIn("Tekno Baru", html)

    # ---- penambahan views ----
    def views(self, article_id=2):
        return self.sql("SELECT views FROM articles WHERE id = ?", (article_id,))[0][0]

    def test_views_increase_by_one_on_first_visit(self):
        self.assertEqual(self.views(), 50)
        self.client.get("/portal/artikel/tekno-baru")
        self.assertEqual(self.views(), 51)

    def test_views_counted_once_per_session_but_again_for_new_visitor(self):
        self.client.get("/portal/artikel/tekno-baru")
        self.client.get("/portal/artikel/tekno-baru")  # muat ulang: tidak dihitung
        self.assertEqual(self.views(), 51)
        other = self.app.test_client()
        other.get("/portal/artikel/tekno-baru")
        self.assertEqual(self.views(), 52)

    def test_views_are_counted_per_article(self):
        self.client.get("/portal/artikel/tekno-baru")
        self.client.get("/portal/artikel/tekno-lama")
        self.assertEqual((self.views(1), self.views(2)), (101, 51))

    def test_views_every_visit_when_dedupe_disabled(self):
        from app.portal import routes
        original = routes.COUNT_ONCE_PER_SESSION
        routes.COUNT_ONCE_PER_SESSION = False
        try:
            self.client.get("/portal/artikel/tekno-baru")
            self.client.get("/portal/artikel/tekno-baru")
        finally:
            routes.COUNT_ONCE_PER_SESSION = original
        self.assertEqual(self.views(), 52)

    def test_head_request_and_404_do_not_count(self):
        self.client.head("/portal/artikel/tekno-baru")
        self.client.get("/portal/artikel/tidak-ada")
        self.assertEqual(self.views(), 50)

    def test_home_and_cards_do_not_count_views(self):
        self.get("/portal/")
        self.assertEqual(self.views(), 50)

    def test_views_display_uses_indonesian_thousands_separator(self):
        self.sql("UPDATE articles SET views = 1247 WHERE id = 2")
        self.assertIn("1.248 kali dibaca", self.get("/portal/artikel/tekno-baru"))

    # ---- artikel terkait ----
    def test_related_are_same_category_excluding_current_newest_first(self):
        html = self.get("/portal/artikel/tekno-baru")
        self.assertIn("Artikel terkait di Teknologi", html)
        related = self.titles(html[html.index('id="pt-related"'):])
        self.assertEqual(related, ["Tekno Lama Featured"])

    def test_related_limited_to_three(self):
        self.add_articles(6, category_id=1)
        html = self.get("/portal/artikel/tekno-baru")
        self.assertEqual(len(self.titles(html[html.index('id="pt-related"'):])), 3)

    def test_related_never_includes_other_categories(self):
        html = self.get("/portal/artikel/pendidikan-featured")
        related = self.titles(html[html.index('id="pt-related"'):])
        self.assertEqual(related, ["Pendidikan Terbaru"])

    def test_related_empty_message_when_alone_in_category(self):
        html = self.get("/portal/artikel/karier-tanpa-penulis")
        self.assertIn("Belum ada artikel lain di kategori ini.", html)

    def test_article_without_category_has_no_related_section(self):
        self.sql("UPDATE articles SET category_id = NULL WHERE id = 2")
        html = self.get("/portal/artikel/tekno-baru")
        self.assertNotIn('id="pt-related"', html)
        self.assertEqual(self.client.get("/portal/artikel/tekno-baru").status_code, 200)

    # ---- gambar: lazy loading + alt ----
    def test_all_images_are_lazy_with_alt_and_dimensions(self):
        for path in ("/portal/", "/portal/?kategori=teknologi", "/portal/artikel/tekno-baru"):
            html = self.get(path)
            images = re.findall(r"<img\b[^>]*>", html)
            self.assertTrue(images, path)
            for tag in images:
                self.assertIn('loading="lazy"', tag, tag)
                self.assertRegex(tag, r'alt="[^"]+"', tag)
                self.assertIn('width="1200"', tag)
                self.assertIn('height="630"', tag)
                self.assertIn('decoding="async"', tag)

    def test_alt_text_mentions_the_article_title(self):
        html = self.get("/portal/artikel/tekno-baru")
        self.assertIn('alt="Sampul artikel: Tekno Baru"', html)

    def test_missing_cover_uses_default_image(self):
        html = self.get("/portal/artikel/tekno-baru")  # cover_url NULL
        self.assertIn("/static/img/portal/default.svg", html)

    def test_cover_src_accepts_static_path_and_http_but_rejects_dangerous_values(self):
        with self.app.test_request_context("/"):
            self.assertTrue(cover_src("img/portal/x.svg").endswith("/static/img/portal/x.svg"))
            self.assertEqual(cover_src("https://contoh.id/a.jpg"), "https://contoh.id/a.jpg")
            default = cover_src(None)
            for bad in ("javascript:alert(1)", "data:text/html,<script>", "../rahasia.png", "/etc/passwd",
                        "//evil.com/a.png", 'https://x.id/a.jpg" onerror="alert(1)', "", "   "):
                self.assertEqual(cover_src(bad), default, bad)

    def test_dangerous_cover_url_in_database_never_reaches_html(self):
        self.sql("UPDATE articles SET cover_url = ? WHERE id = 2", ("javascript:alert(1)",))
        html = self.get("/portal/")
        self.assertNotIn("javascript:", html)

    def test_cover_files_referenced_by_seed_exist(self):
        covers = os.path.join(ROOT, "app", "static", "img", "portal")
        self.assertTrue(os.path.isfile(os.path.join(covers, "default.svg")))

    # ---- UC-PT-04: preferensi kategori ----
    def test_settings_requires_login_and_returns_after_login(self):
        response = self.client.get("/portal/pengaturan")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/infosys/login", response.headers["Location"])
        self.assertIn("next=", response.headers["Location"])

    def test_settings_lists_only_portal_categories(self):
        self.login()
        html = self.get("/portal/pengaturan")
        for name in ("Teknologi", "Pendidikan", "Karier", "Kesehatan"):
            self.assertIn(name, html)
        self.assertNotIn("Python", html)
        self.assertEqual(self.checked_slugs(html), [])

    def test_save_preferences_writes_module_settings(self):
        self.login()
        response = self.save_prefs(["pendidikan", "karier"])
        self.assertEqual(response.status_code, 302)
        rows = self.sql("SELECT user_id, module_key, setting_key, setting_value FROM module_settings")
        self.assertEqual(rows, [(1, "portal", "preferred_categories", "karier,pendidikan")])  # urutan kategori
        self.assertEqual(self.sql("SELECT action FROM activity_logs WHERE module_key = 'portal'"),
                         [("portal_preferences",)])

    def test_saved_preferences_are_checked_in_form_and_update_in_place(self):
        self.login()
        self.save_prefs(["teknologi"])
        self.save_prefs(["pendidikan"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 1)
        html = self.get("/portal/pengaturan")
        self.assertEqual(self.checked_slugs(html), ["pendidikan"])
        self.assertIn("Saat ini diutamakan: Pendidikan.", html)

    def test_unknown_slugs_are_ignored_on_save(self):
        self.login()
        self.save_prefs(["teknologi", "ngawur", "python"])  # 'python' = kategori modul lain
        self.assertEqual(self.sql("SELECT setting_value FROM module_settings")[0][0], "teknologi")

    def test_saving_nothing_or_reset_removes_the_row(self):
        self.login()
        self.save_prefs(["teknologi"])
        self.save_prefs([])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)
        self.save_prefs(["teknologi"])
        self.save_prefs(["teknologi"], action="reset")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_invalid_action_is_rejected(self):
        self.login()
        self.assertEqual(self.save_prefs(["teknologi"], action="hapus-semua").status_code, 400)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_settings_post_requires_csrf(self):
        self.login()
        self.csrf()
        response = self.save_prefs(["teknologi"], token="palsu")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_guest_cannot_post_settings(self):
        response = self.client.post("/portal/pengaturan", data={"categories": ["teknologi"]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM module_settings")[0][0], 0)

    def test_preferences_are_per_user_and_do_not_touch_other_modules(self):
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
                 "VALUES (1, 'etutorial', 'font_size', 'lg')")
        self.login(1)
        self.save_prefs(["teknologi"])
        other = self.app.test_client()
        self.login(2, other)
        self.assertEqual(self.checked_slugs(self.get("/portal/pengaturan", other)), [])
        self.assertEqual(self.sql("SELECT setting_value FROM module_settings WHERE module_key = 'etutorial'"),
                         [("lg",)])

    # ---- preferensi memengaruhi urutan beranda ----
    def test_preferences_reorder_cards_and_pick_preferred_featured(self):
        self.login()
        self.save_prefs(["teknologi"])
        html = self.get("/portal/")
        # kedua featured bersaing: Tekno Lama (teknologi) menang atas Pendidikan Featured yang lebih baru
        self.assertEqual(self.hero_title(html), "Tekno Lama Featured")
        # kartu: favorit (teknologi) dulu, lalu lainnya terbaru -> pendidikan terbaru, karier, pendidikan featured
        self.assertEqual(self.titles(html), ["Tekno Baru", "Pendidikan Terbaru", "Karier Tanpa Penulis",
                                             "Pendidikan Featured"])
        self.assertIn("Urutan disesuaikan dengan kategori favorit Anda", html)
        self.assertIn("Teknologi", html[html.index("Urutan disesuaikan"):][:300])

    def test_preference_for_two_categories_puts_both_first(self):
        self.login()
        self.save_prefs(["karier", "pendidikan"])
        html = self.get("/portal/")
        self.assertEqual(self.hero_title(html), "Pendidikan Featured")
        self.assertEqual(self.titles(html), ["Pendidikan Terbaru", "Karier Tanpa Penulis", "Tekno Baru",
                                             "Tekno Lama Featured"])

    def test_preferences_never_hide_articles(self):
        self.login()
        self.save_prefs(["karier"])
        html = self.get("/portal/")
        shown = self.titles(html) + [self.hero_title(html)]
        self.assertEqual(len(shown), 5)

    def test_preference_does_not_change_guest_or_other_members_order(self):
        self.login()
        self.save_prefs(["teknologi"])
        guest = self.app.test_client()
        self.assertEqual(self.hero_title(self.get("/portal/", guest)), "Pendidikan Featured")
        other = self.app.test_client()
        self.login(2, other)
        self.assertEqual(self.hero_title(self.get("/portal/", other)), "Pendidikan Featured")

    def test_preferred_chips_come_first_and_are_marked(self):
        self.login()
        self.save_prefs(["karier"])
        html = self.get("/portal/")
        chips = re.findall(r'class="pt-chip[^"]*"[^>]*>\s*(?:<span aria-hidden="true">&#9733;</span>)?\s*([A-Za-z]+)', html)
        self.assertEqual(chips[:3], ["Semua", "Karier", "Kesehatan"])
        self.assertIn("(favorit)", html)

    def test_filter_overrides_preference_but_stays_within_category(self):
        self.login()
        self.save_prefs(["teknologi"])
        html = self.get("/portal/?kategori=pendidikan")
        self.assertEqual(self.hero_title(html), "Pendidikan Featured")
        self.assertEqual(self.titles(html), ["Pendidikan Terbaru"])

    def test_stale_preference_slug_in_database_is_ignored(self):
        self.sql("INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
                 "VALUES (1, 'portal', 'preferred_categories', 'hilang, Teknologi ,,teknologi')")
        self.login()
        html = self.get("/portal/")
        self.assertEqual(self.hero_title(html), "Tekno Lama Featured")
        self.assertEqual(html.count("(favorit)"), 1)

    def test_preference_works_with_pagination(self):
        self.add_articles(10, category_id=2)  # banyak artikel pendidikan
        self.login()
        self.save_prefs(["karier"])
        p1, p2 = self.get("/portal/?halaman=1"), self.get("/portal/?halaman=2")
        self.assertEqual(self.titles(p1)[0], "Karier Tanpa Penulis")
        all_titles = self.titles(p1) + self.titles(p2)
        self.assertEqual(len(all_titles), len(set(all_titles)))

    # ---- keamanan ----
    def test_autoescape_active_and_no_unsafe_filters_in_templates(self):
        folder = os.path.join(ROOT, "app", "templates", "portal")
        names = [n for n in os.listdir(folder) if n.endswith(".html")]
        self.assertTrue(names)
        for name in names:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotRegex(source, r"\|\s*safe\b", name)
            self.assertNotIn("Markup(", source, name)
            self.assertNotIn("autoescape false", source, name)

    def test_database_text_is_escaped_everywhere(self):
        self.sql("UPDATE articles SET title = ?, excerpt = ?, body = ? WHERE id = 2",
                 (XSS_TITLE, "Ringkasan <i>miring</i>", XSS_BODY))
        self.sql("UPDATE users SET full_name = ? WHERE id = 3", ('<script>alert(9)</script>',))
        for path in ("/portal/", "/portal/artikel/tekno-baru", "/portal/artikel/tekno-lama"):
            html = self.get(path)
            self.assertNotIn("<b>Judul</b>", html, path)
            self.assertNotIn("<script>alert", html, path)
            self.assertNotIn("<i>miring</i>", html, path)
            self.assertNotIn("<img src=x", html, path)
        self.assertIn("&lt;b&gt;Judul&lt;/b&gt;", self.get("/portal/artikel/tekno-baru"))

    def test_sql_injection_in_query_string_is_inert(self):
        for value in ("' OR 1=1 --", "teknologi'; DROP TABLE articles;--", "%"):
            self.assertEqual(self.client.get("/portal/", query_string={"kategori": value}).status_code, 200)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM articles")[0][0], 5)

    # ---- pembantu murni ----
    def test_helpers(self):
        self.assertEqual(parse_page("3"), 3)
        self.assertEqual((parse_page(None), parse_page("x"), parse_page("-2")), (1, 1, 1))
        info = paginate(14, 99, 6)
        self.assertEqual((info["page"], info["pages"], info["first"], info["last"]), (3, 3, 13, 14))
        empty = paginate(0, 5, 6)
        self.assertEqual((empty["page"], empty["pages"], empty["first"], empty["last"]), (1, 1, 0, 0))
        self.assertEqual(format_date("2026-01-10T20:00:00+00:00"), "11 Jan 2026")  # WIB = UTC+7
        self.assertEqual(format_date("bukan tanggal"), "bukan tanggal")
        self.assertEqual(format_date(None), "")
        self.assertEqual(format_views(1248), "1.248")
        self.assertEqual(format_views(0), "0")
        self.assertEqual(format_views(1234567), "1.234.567")
        self.assertEqual((estimate_minutes(0), estimate_minutes(None), estimate_minutes(2400), estimate_minutes(6000)),
                         (1, 1, 2, 5))
        self.assertEqual(paragraphs("a\n\nb\r\n\r\nc"), ["a", "b", "c"])
        self.assertEqual(paragraphs(None), [])


if __name__ == "__main__":
    unittest.main()
