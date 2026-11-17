"""Tes pencarian terpadu (GET /cari): hasil lima jenis, saringan terbit/aktif, wildcard literal,
escape XSS, pembatasan jumlah, jenis tak dikenal, serta kolom dan tombol pencarian di bilah atas.

Jalankan:  python -m unittest tests.test_search
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app.search import (
    KINDS, LIMIT_PER_KIND, LIMIT_SINGLE_KIND, MAX_QUERY_CHARS, highlight_parts, like_pattern,
    make_snippet, normalize_query,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSS = '<script>alert("x")</script>'


class SearchCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'Rina Putri', 'rina@dke.test', ?)",
                     (generate_password_hash("Rahasia123"),))
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(statement, params)
            conn.commit()
        finally:
            conn.close()

    def login(self):
        with self.client.session_transaction() as s:
            s["user_id"] = 1

    def html(self, path, status=200):
        r = self.client.get(path)
        self.assertEqual(r.status_code, status, path)
        return r.get_data(as_text=True)

    # ---- data contoh ----
    def course(self, n, title="Kelas Pelangi", desc="Belajar dasar", published=1):
        self.sql("INSERT INTO courses (id, title, slug, description, is_published) VALUES (?,?,?,?,?)",
                 (n, title, f"kelas-{n}", desc, published))

    def product(self, n, name="Produk Pelangi", desc="Paket belajar", active=1):
        self.sql("INSERT INTO products (id, name, slug, description, price, is_active) VALUES (?,?,?,?,?,?)",
                 (n, name, f"produk-{n}", desc, 50000, active))

    def tutorial(self, n, title="Tutorial Pelangi", summary="Langkah awal"):
        self.sql("INSERT INTO tutorials (id, title, slug, summary) VALUES (?,?,?,?)", (n, title, f"tutorial-{n}", summary))

    def article(self, n, title="Artikel Pelangi", excerpt="Ringkasan berita"):
        self.sql("INSERT INTO articles (id, title, slug, excerpt, body) VALUES (?,?,?,?,?)",
                 (n, title, f"artikel-{n}", excerpt, "Isi artikel lengkap."))

    def thread(self, n, title="Topik Pelangi", body="Isi pertanyaan"):
        self.sql("INSERT INTO threads (id, user_id, title, body) VALUES (?,1,?,?)", (n, title, body))

    def seed_one_of_each(self):
        self.course(1)
        self.product(1)
        self.tutorial(1)
        self.article(1)
        self.thread(1)

    def result_links(self, html):
        """href setiap hasil (tautan judul), berurutan sesuai halaman."""
        return re.findall(r'<a href="([^"]+)" class="card-link', html)


# --------------------------------------------------------------------------
class SearchPageTest(SearchCase):
    def test_guest_bisa_membuka_halaman_cari(self):
        html = self.html("/cari")
        self.assertIn("Pencarian", html)
        self.assertIn("Cari di seluruh DKE", html)

    def test_member_bisa_membuka_halaman_cari(self):
        self.seed_one_of_each()
        self.login()
        html = self.html("/cari?q=pelangi")
        self.assertEqual(len(self.result_links(html)), 5)

    def test_q_kosong_dan_hanya_spasi_menampilkan_empty_state(self):
        for path in ("/cari", "/cari?q=", "/cari?q=%20%20%20"):
            with self.subTest(path=path):
                html = self.html(path)
                self.assertIn("Cari di seluruh DKE", html)
                self.assertNotIn("data-search-result", html)

    def test_q_terlalu_pendek_tidak_mencari(self):
        self.seed_one_of_each()
        self.thread(2, title="x kecil", body="x")
        html = self.html("/cari?q=x")
        self.assertIn("Kata kunci terlalu pendek", html)
        self.assertIn("minimal 2 karakter", html)
        self.assertNotIn("data-search-result", html)

    def test_dua_karakter_sudah_dicari(self):
        self.course(1, title="Go Dasar")
        html = self.html("/cari?q=go")
        self.assertEqual(self.result_links(html), ["/elearning/kelas/1"])

    def test_tanpa_hasil_menampilkan_satu_empty_state_dengan_solusi(self):
        self.seed_one_of_each()
        html = self.html("/cari?q=tidakadakatainiapapun")
        self.assertIn("Tidak ada hasil untuk", html)
        self.assertIn("Coba kata kunci lain", html)
        self.assertEqual(html.count("empty-state animate-fade-in"), 1)
        self.assertNotIn("data-search-result", html)

    def test_satu_hasil_untuk_tiap_jenis_dan_menaut_ke_halaman_detail(self):
        self.seed_one_of_each()
        html = self.html("/cari?q=pelangi")
        self.assertEqual(
            self.result_links(html),
            ["/elearning/kelas/1", "/ecommerce/produk/produk-1", "/etutorial/tutorial/tutorial-1",
             "/portal/artikel/artikel-1", "/forum/thread/1"],
        )
        for link in self.result_links(html):
            with self.subTest(link=link):
                self.assertEqual(self.client.get(link).status_code, 200)

    def test_kelompok_berlabel_aplikasi_dan_forum_bernama_topik(self):
        self.seed_one_of_each()
        html = self.html("/cari?q=pelangi")
        for key, label, app_name in (("kelas", "Kelas", "E-Learning"), ("produk", "Produk", "E-Commerce"),
                                     ("tutorial", "Tutorial", "E-Tutorial"), ("artikel", "Artikel", "Portal"),
                                     ("topik", "Topik", "Forum")):
            with self.subTest(kind=key):
                section = html.split(f'data-search-group="{key}"')[1].split("</section>")[0]
                self.assertIn(f"<span>{label}</span>", section)
                self.assertIn(f">{app_name}</a>", section)
        self.assertNotIn("Thread", html)

    def test_pencocokan_tidak_peka_huruf_besar_dan_cuplikan_memakai_mark(self):
        self.course(1, title="Belajar Python", desc="Dasar python untuk pemula")
        html = self.html("/cari?q=PYTHON")
        self.assertIn('<mark class="search-hit">Python</mark>', html)
        self.assertIn('<mark class="search-hit">python</mark>', html)

    def test_isi_topik_dan_deskripsi_ikut_dicari_tetapi_isi_artikel_tidak(self):
        self.thread(1, title="Tanya biasa", body="Bagaimana memakai kata-ajaib?")
        self.article(1, title="Artikel biasa", excerpt="Ringkasan")
        self.sql("UPDATE articles SET body = 'kata-ajaib ada di isi' WHERE id = 1")
        links = self.result_links(self.html("/cari?q=kata-ajaib"))
        self.assertEqual(links, ["/forum/thread/1"])

    def test_tidak_ada_data_akun_yang_dicari(self):
        self.seed_one_of_each()
        for q in ("rina@dke.test", "Rina Putri"):
            with self.subTest(q=q):
                html = self.html("/cari?q=" + q)
                self.assertIn("Tidak ada hasil untuk", html)
                self.assertNotIn("data-search-result", html)


class VisibilityFilterTest(SearchCase):
    def test_kelas_belum_terbit_tidak_pernah_muncul(self):
        self.course(1, title="Kelas Terbit Merah", published=1)
        self.course(2, title="Kelas Draf Merah", published=0)
        self.course(3, title="Lain", desc="draf merah di deskripsi", published=0)
        html = self.html("/cari?q=merah")
        self.assertEqual(self.result_links(html), ["/elearning/kelas/1"])
        self.assertNotIn("Draf", html)
        self.assertIn("(1)", html)        # jumlah juga tidak menghitung yang tak terbit

    def test_produk_tidak_aktif_tidak_pernah_muncul(self):
        self.product(1, name="Paket Biru Aktif", active=1)
        self.product(2, name="Paket Biru Mati", active=0)
        self.product(3, name="Lain", desc="biru tersembunyi", active=0)
        html = self.html("/cari?q=biru")
        self.assertEqual(self.result_links(html), ["/ecommerce/produk/produk-1"])
        self.assertNotIn("Mati", html)
        self.assertNotIn("tersembunyi", html)

    def test_jenis_kelas_dan_produk_juga_menyaring(self):
        self.course(1, title="Merah", published=0)
        self.product(1, name="Merah", active=0)
        html = self.html("/cari?q=merah&jenis=kelas")
        self.assertIn("Tidak ada hasil untuk", html)
        html = self.html("/cari?q=merah&jenis=produk")
        self.assertIn("Tidak ada hasil untuk", html)


class LiteralWildcardTest(SearchCase):
    def test_persen_dicari_sebagai_teks_biasa(self):
        self.course(1, title="Diskon 100% Hemat")
        self.course(2, title="Diskon 1000 Hemat")
        links = self.result_links(self.html("/cari?q=100%25"))
        self.assertEqual(links, ["/elearning/kelas/1"])

    def test_garis_bawah_dicari_sebagai_teks_biasa(self):
        self.course(1, title="Variabel snake_case")
        self.course(2, title="Variabel snakeXcase")
        links = self.result_links(self.html("/cari?q=snake_case"))
        self.assertEqual(links, ["/elearning/kelas/1"])

    def test_garis_miring_terbalik_dicari_sebagai_teks_biasa(self):
        self.course(1, title="Path C:\\data\\file")
        self.course(2, title="Path C:data")
        links = self.result_links(self.html("/cari?q=C:%5Cdata"))
        self.assertEqual(links, ["/elearning/kelas/1"])

    def test_hanya_wildcard_tidak_mencocokkan_semuanya(self):
        self.course(1, title="Kelas Apa Saja")
        for q in ("%25%25", "__", "%25_"):
            with self.subTest(q=q):
                self.assertIn("Tidak ada hasil untuk", self.html("/cari?q=" + q))

    def test_like_pattern_meng_escape_tiga_karakter(self):
        self.assertEqual(like_pattern("a%b_c\\d"), "%a\\%b\\_c\\\\d%")


class XssTest(SearchCase):
    def test_kueri_script_tampil_sebagai_teks(self):
        self.course(1, title="Tentang tag", desc=f"Contoh {XSS} di deskripsi")
        html = self.html("/cari?q=" + XSS)
        self.assertNotIn(XSS, html)
        self.assertIn("&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;", html)
        self.assertEqual(self.result_links(html), ["/elearning/kelas/1"])

    def test_kueri_tanpa_hasil_juga_di_escape(self):
        html = self.html("/cari?q=" + XSS)
        self.assertNotIn(XSS, html)
        self.assertIn("&lt;script&gt;", html)

    def test_judul_dan_cuplikan_dari_database_di_escape(self):
        self.course(1, title=f"Judul {XSS} pelangi", desc="x")
        self.thread(1, title="Biasa pelangi", body=f"Isi {XSS} pelangi")
        html = self.html("/cari?q=pelangi")
        self.assertNotIn(XSS, html)
        self.assertGreaterEqual(html.count("&lt;script&gt;"), 2)

    def test_kutip_di_kueri_tidak_keluar_dari_atribut_input(self):
        html = self.html('/cari?q=%22%20autofocus%20onfocus%3Dalert(1)%20x%3D%22')
        self.assertNotIn('" autofocus onfocus=alert(1)', html)
        self.assertIn("&#34; autofocus onfocus=alert(1) x=&#34;", html)

    def test_kueri_sql_injeksi_hanyalah_teks(self):
        self.seed_one_of_each()
        html = self.html("/cari?q=%27%20OR%201%3D1%20--")
        self.assertIn("Tidak ada hasil untuk", html)
        self.assertEqual(self.sql_count("courses"), 1)

    def sql_count(self, table):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()


class LimitAndKindTest(SearchCase):
    def setUp(self):
        super().setUp()
        for n in range(1, 9):
            self.course(n, title=f"Kelas Bintang {n}")
        self.product(1, name="Produk Bintang")

    def test_semua_jenis_dibatasi_lima_per_jenis(self):
        html = self.html("/cari?q=bintang")
        kelas = html.split('data-search-group="kelas"')[1].split("</section>")[0]
        self.assertEqual(kelas.count("data-search-result"), LIMIT_PER_KIND)
        self.assertIn("Lihat semua 8 hasil kelas", kelas)
        self.assertIn("jenis=kelas", kelas)
        self.assertEqual(len(self.result_links(html)), LIMIT_PER_KIND + 1)    # 5 kelas + 1 produk

    def test_jumlah_sebenarnya_tetap_ditampilkan(self):
        html = self.html("/cari?q=bintang")
        self.assertIn("9 hasil untuk", html)
        self.assertIn("Kelas <span", html)
        self.assertIn("(8)", html)

    def test_jenis_dipilih_menampilkan_lebih_banyak_dan_menyembunyikan_jenis_lain(self):
        html = self.html("/cari?q=bintang&jenis=kelas")
        self.assertEqual(len(self.result_links(html)), 8)
        self.assertNotIn('data-search-group="produk"', html)
        self.assertIn('aria-current="true"', html)

    def test_batas_jenis_tunggal_juga_ada(self):
        for n in range(9, LIMIT_SINGLE_KIND + 6):
            self.course(n, title=f"Kelas Bintang {n}")
        html = self.html("/cari?q=bintang&jenis=kelas")
        self.assertEqual(len(self.result_links(html)), LIMIT_SINGLE_KIND)
        self.assertIn(f"Menampilkan {LIMIT_SINGLE_KIND} dari {LIMIT_SINGLE_KIND + 5} hasil", html)

    def test_jenis_tak_dikenal_diabaikan_dengan_pemberitahuan(self):
        html = self.html("/cari?q=bintang&jenis=hantu")
        self.assertIn("Jenis hasil itu tidak dikenal, jadi semua jenis dicari.", html)
        self.assertIn('data-search-group="kelas"', html)
        self.assertIn('data-search-group="produk"', html)

    def test_jenis_sah_tidak_memunculkan_pemberitahuan(self):
        self.assertNotIn("tidak dikenal", self.html("/cari?q=bintang&jenis=KELAS"))
        self.assertNotIn("tidak dikenal", self.html("/cari?q=bintang"))

    def test_jenis_terpilih_tanpa_kecocokan_menawarkan_semua_hasil(self):
        html = self.html("/cari?q=bintang&jenis=artikel")
        self.assertIn("Tidak ada artikel yang cocok", html)
        self.assertIn("Lihat semua hasil", html)
        self.assertNotIn("data-search-result", html)

    def test_kueri_dipotong_seratus_karakter(self):
        self.assertEqual(normalize_query("  " + "a" * 150 + "  "), "a" * MAX_QUERY_CHARS)
        self.assertEqual(normalize_query(None), "")
        self.course(20, title="a" * 100 + " panjang")
        html = self.html("/cari?q=" + "a" * 150)
        self.assertEqual(len(self.result_links(html)), 1)

    def test_urutan_judul_cocok_lebih_dulu(self):
        self.course(30, title="Lain", desc="membahas nebula")
        self.course(31, title="Nebula Lanjut", desc="x")
        links = self.result_links(self.html("/cari?q=nebula&jenis=kelas"))
        self.assertEqual(links, ["/elearning/kelas/31", "/elearning/kelas/30"])


# --------------------------------------------------------------------------
class TopbarSearchTest(SearchCase):
    PAGES = ("/", "/cari", "/elearning/", "/ecommerce/", "/forum/")

    def test_bilah_atas_memuat_form_pencarian_di_semua_halaman(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.html(page)
                self.assertIn('role="search"', html)
                self.assertIn('action="/cari"', html)
                self.assertIn('method="get"', html)
                self.assertIn('placeholder="Cari kelas, produk, tutorial..."', html)

    def test_form_desktop_memakai_dke_hide_mobile_dan_punya_label(self):
        html = self.html("/")
        form = html.split('role="search"')[1].split("</form>")[0]
        self.assertIn("dke-hide-mobile", html.split('role="search"')[1][:200])
        self.assertIn('for="topbar-search"', form)
        self.assertIn('id="topbar-search"', form)
        self.assertIn('name="q"', form)
        self.assertIn('type="search"', form)

    def test_tombol_ikon_mobile_ada_dan_cukup_besar(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.html(page)
                link = re.search(r'<a href="/cari" class="([^"]*)" aria-label="Cari"', html)
                self.assertIsNotNone(link, page)
                self.assertIn("dke-show-mobile", link.group(1))
                self.assertIn("tb-btn", link.group(1))       # .tb-btn = min 44 x 44 px (custom.css)

    def test_member_juga_mendapat_kolom_dan_tombol_pencarian(self):
        self.login()
        html = self.html("/")
        self.assertIn('role="search"', html)
        self.assertIn('aria-label="Cari"', html)

    def test_kolom_atas_terisi_kata_kunci_saat_ini(self):
        html = self.html("/cari?q=python")
        self.assertIn('id="topbar-search" type="search" name="q" value="python"', html)

    def test_autofocus_hanya_di_cari_saat_q_kosong(self):
        self.assertIn(" autofocus", self.html("/cari").split("</header>")[0])
        self.assertIn("autofocus", self.html("/cari?q="))
        self.assertNotIn("autofocus", self.html("/cari?q=python"))
        self.assertNotIn("autofocus", self.html("/"))
        self.assertNotIn("autofocus", self.html("/forum/"))

    def test_form_halaman_untuk_mobile_ada_di_cari(self):
        html = self.html("/cari")
        form = [part for part in html.split("<form") if 'aria-label="Cari di halaman ini"' in part][0]
        self.assertIn("dke-show-mobile", form.split(">")[0] + form.split(">")[1])
        self.assertIn('action="/cari"', form)

    def test_skrip_pintasan_eksternal_dan_tanpa_skrip_inline_baru(self):
        html = self.html("/")
        self.assertIn("/static/js/search.js", html)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "app", "static", "js", "search.js")))
        for inline in re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html):
            self.assertIn("nonce=", inline)

    def test_tombol_slash_tidak_merebut_kolom_isian(self):
        with open(os.path.join(ROOT, "app", "static", "js", "search.js"), encoding="utf-8") as f:
            js = f.read()
        for guard in ("INPUT", "TEXTAREA", "isContentEditable", "offsetParent"):
            self.assertIn(guard, js)


class MobileViewCssTest(unittest.TestCase):
    """Kelas md: Tailwind tidak mengikuti Mobile View, jadi dke-show-mobile harus ada di custom.css."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "app", "static", "css", "custom.css"), encoding="utf-8") as f:
            cls.css = f.read()

    def test_dke_show_mobile_berlaku_di_mobile_view_dan_layar_sempit(self):
        self.assertRegex(self.css, r"html\[data-view='mobile'\]\s+\.dke-show-mobile\s*\{[^}]*display:\s*inline-flex")
        media = re.search(r"@media \(max-width: 767px\) \{(.*?)\n\}", self.css, re.S).group(1)
        self.assertIn(".dke-show-mobile", media)

    def test_dke_show_mobile_tersembunyi_di_desktop(self):
        self.assertRegex(self.css, r"html \.dke-show-mobile\s*\{\s*display:\s*none\s*!important")

    def test_tailwind_css_dibangun_ulang_dengan_kelas_halaman_cari(self):
        with open(os.path.join(ROOT, "app", "static", "css", "tailwind.css"), encoding="utf-8") as f:
            built = f.read()
        self.assertIn("min-h-\\[28px\\]", built)          # kelas baru di templat main/search.html

    def test_ikon_search_tersedia(self):
        with open(os.path.join(ROOT, "app", "templates", "_components", "_icons.html"), encoding="utf-8") as f:
            self.assertIn("name == 'search'", f.read())


class NavigationTest(SearchCase):
    def test_cari_punya_breadcrumb_dan_tombol_kembali_ke_beranda(self):
        html = self.html("/cari?q=pelangi")
        self.assertIn('aria-label="Jejak halaman"', html)
        self.assertIn("data-back-link", html)
        self.assertIn('aria-label="Kembali ke Beranda"', html)
        crumb = html.split('aria-label="Jejak halaman"')[1].split("</nav>")[0]
        self.assertIn(">Beranda</a>", crumb)
        self.assertIn('aria-current="page">Pencarian', crumb)

    def test_node_navigasi_terdaftar(self):
        from app.navigation import NAV
        self.assertIn("main.search", NAV)
        self.assertEqual(NAV["main.search"].parent, "main.index")

    def test_beranda_tetap_tanpa_breadcrumb(self):
        self.assertNotIn("data-page-nav", self.html("/"))

    def test_semua_jenis_punya_pencari_dan_aplikasi_yang_sah(self):
        from app import MODULE_BY_KEY
        from app.search import SEARCHERS
        self.assertEqual([k["key"] for k in KINDS], list(SEARCHERS))
        for spec in KINDS:
            self.assertIn(spec["app"], MODULE_BY_KEY)


class HelperTest(unittest.TestCase):
    def test_highlight_parts_memecah_tanpa_html(self):
        self.assertEqual(highlight_parts("Belajar Python dan python", "python"),
                         [("Belajar ", False), ("Python", True), (" dan ", False), ("python", True)])
        self.assertEqual(highlight_parts("<b>x</b>", "<b>"), [("<b>", True), ("x</b>", False)])
        self.assertEqual(highlight_parts(None, "a"), [])
        self.assertEqual(highlight_parts("abc", "zz"), [("abc", False)])

    def test_make_snippet_memotong_di_sekitar_kecocokan(self):
        text = "awal " * 60 + "KATA-KUNCI " + "akhir " * 60
        snippet = make_snippet(text, "kata-kunci", width=80)
        self.assertIn("KATA-KUNCI", snippet)
        self.assertTrue(snippet.startswith("\u2026") and snippet.endswith("\u2026"))
        self.assertLessEqual(len(snippet), 82)
        self.assertEqual(make_snippet("pendek saja", "x"), "pendek saja")
        self.assertEqual(make_snippet(None, "x"), "")
        self.assertTrue(make_snippet("a " * 200, "zzz", width=50).endswith("\u2026"))


if __name__ == "__main__":
    unittest.main()
