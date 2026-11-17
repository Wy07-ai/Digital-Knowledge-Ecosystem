"""Tes hero Beranda berupa carousel lima aplikasi (markup, aksesibilitas, CSP, CSS, dan kontras).

Jalankan dari akar proyek:   python -m unittest tests.test_home_hero -v
Memakai database SQLite sementara dari schema.sql, seperti tests/test_launcher_nav.py.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import MODULE_BY_KEY, create_app
from app.main.launcher import HERO_SLIDES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_ORDER = ["elearning", "ecommerce", "etutorial", "portal", "forum"]
EXPECTED_LINKS = ["/elearning/", "/ecommerce/", "/etutorial/", "/portal/", "/forum/"]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def luminance(rgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def blend(top, bottom, alpha):
    return tuple(t * alpha + b * (1 - alpha) for t, b in zip(top, bottom))


class HeroTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(read("schema.sql"))
        conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'Rina Putri', 'rina@dke.test', ?)",
                     (generate_password_hash("Rina12345"),))
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login(self):
        with self.client.session_transaction() as s:
            s["user_id"] = 1

    def settings(self, **values):
        conn = sqlite3.connect(self.db_path)
        sets = ", ".join(f"{k} = ?" for k in values)
        conn.execute(f"UPDATE user_settings SET {sets} WHERE user_id = 1", list(values.values()))
        conn.commit()
        conn.close()

    def html(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def carousel(self, html=None):
        html = html or self.html()
        m = re.search(r'<section class="hero-carousel".*?</section>', html, re.S)
        self.assertIsNotNone(m, "komponen carousel tidak ditemukan di Beranda")
        return m.group(0)


class MarkupTests(HeroTestCase):
    def check_markup(self):
        html = self.html()
        block = self.carousel(html)
        self.assertIn('aria-roledescription="carousel"', block)
        self.assertEqual(len(re.findall(r'aria-roledescription="slide"', block)), 5)
        self.assertEqual(len(re.findall(r"data-carousel-dot=", block)), 5)
        self.assertIn('data-interval="10000"', block)
        self.assertNotIn("home-orbit", html)
        return html, block

    def test_guest_merender_carousel(self):
        self.check_markup()

    def test_member_merender_carousel(self):
        self.login()
        self.check_markup()

    def test_tautan_slide_urut_dan_tanpa_infosys(self):
        block = self.carousel()
        slide_hrefs = re.findall(r'<a href="([^"]+)" class="hero-slide-cta"', block)
        self.assertEqual(slide_hrefs, EXPECTED_LINKS)
        self.assertNotIn("/infosys", block)
        self.assertNotIn("Information System", block)

    def test_tiap_slide_grup_berlabel_dan_hanya_slide_pertama_aktif(self):
        block = self.carousel()
        labels = re.findall(r'role="group" aria-roledescription="slide" aria-label="([^"]+)"', block)
        self.assertEqual(labels, [f"{n} dari 5" for n in range(1, 6)])
        self.assertEqual(len(re.findall(r'class="hero-slide( is-active)?"', block)), 5)
        self.assertEqual(block.count("hero-slide is-active"), 1)
        first = re.search(r'<div class="hero-slide is-active".*?</h2>', block, re.S).group(0)
        self.assertIn("E-LEARNING", first)

    def test_titik_indikator_tombol_berlabel_dan_aria_current(self):
        block = self.carousel()
        dots = re.findall(r"<button[^>]*data-carousel-dot=[^>]*>", block)
        self.assertEqual(len(dots), 5)
        names = ["E-Learning", "E-Commerce", "E-Tutorial", "Portal", "Forum"]
        for i, (dot, name) in enumerate(zip(dots, names), 1):
            self.assertIn('type="button"', dot)
            self.assertIn(f'aria-label="Slide {i}: {name}"', dot)
        self.assertEqual(block.count('aria-current="true"'), 1)
        self.assertIn('aria-current="true"', dots[0])

    def test_kontrol_jeda_sebelumnya_berikutnya_ada(self):
        block = self.carousel()
        for attr, label in (("data-carousel-toggle", "Jeda geser otomatis"), ("data-carousel-prev", "Sebelumnya"),
                            ("data-carousel-next", "Berikutnya")):
            self.assertRegex(block, rf'<button[^>]*{attr}[^>]*aria-label="{label}"')
        self.assertIn('aria-live="off"', block)

    def test_ilustrasi_dekoratif_dan_tanpa_dependensi_tailwind_baru(self):
        block = self.carousel()
        self.assertEqual(len(re.findall(r'class="hero-slide-art" aria-hidden="true"', block)), 5)

    def test_teks_slide_tanpa_istilah_modul(self):
        block = self.carousel()
        text = re.sub(r"<[^>]+>", " ", block).lower()
        self.assertNotRegex(text, r"modul(?!e)")


class ScriptAndCspTests(HeroTestCase):
    def test_halaman_memuat_carousel_js_dengan_defer_dan_tanpa_event_inline(self):
        for member in (False, True):
            if member:
                self.login()
            html = self.html()
            self.assertRegex(html, r'<script defer src="/static/js/carousel\.js"></script>')
            self.assertNotRegex(html, r"\bonclick=")
            self.assertNotRegex(html, r"\son(click|change|keydown|mouseover|mouseenter|focus|load)=")

    def test_tidak_ada_skrip_inline_baru(self):
        """Satu-satunya skrip inline yang dieksekusi adalah skrip tema ber-nonce di base.html."""
        r = self.client.get("/")
        html = r.get_data(as_text=True)
        nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
        executable = [a for a in re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html) if "application/json" not in a]
        self.assertEqual(len(executable), 1)
        self.assertIn(f'nonce="{nonce}"', executable[0])

    def test_csp_tidak_dilonggarkan(self):
        csp = self.client.get("/").headers["Content-Security-Policy"]
        script_src = [d for d in csp.split("; ") if d.startswith("script-src")][0]
        self.assertNotIn("unsafe-inline", script_src)
        self.assertNotIn("unsafe-eval", script_src)

    def test_carousel_js_memuat_perilaku_wajib_tanpa_angka_jeda(self):
        js = read("app", "static", "js", "carousel.js")
        for needle in ("prefers-reduced-motion", "visibilitychange", "data-interval", "mouseenter", "mouseleave",
                       "focusin", "focusout", "matchMedia", "ArrowLeft", "ArrowRight", "carousel-js", "aria-live"):
            self.assertIn(needle, js)
        self.assertIn("addEventListener('change'", js)
        self.assertNotIn("10000", js)

    def test_carousel_js_tanpa_eval_dan_tanpa_innerhtml(self):
        js = read("app", "static", "js", "carousel.js")
        self.assertNotRegex(js, r"\beval\(|new Function|innerHTML|document\.write")


class SlideDataTests(unittest.TestCase):
    def test_urutan_dan_aplikasi(self):
        self.assertEqual([s["key"] for s in HERO_SLIDES], EXPECTED_ORDER)
        self.assertNotIn("infosys", [s["key"] for s in HERO_SLIDES])
        for s in HERO_SLIDES:
            self.assertIn(s["key"], MODULE_BY_KEY)

    def test_teks_sesuai_glosarium(self):
        for s in HERO_SLIDES:
            self.assertLessEqual(len(s["text"].split()), 15, s["key"])
            self.assertIn("Anda", s["text"], s["key"])
            self.assertTrue(s["title"] and s["cta"], s["key"])
            joined = " ".join((s["title"], s["text"], s["cta"])).lower()
            self.assertNotRegex(joined, r"modul(?!e)")
            self.assertNotRegex(joined, r"\bkamu\b|\bsilakan\b")


class ResumeStripTests(HeroTestCase):
    def test_guest_tanpa_lanjutkan_tetapi_dengan_sapaan_umum(self):
        html = self.html()
        self.assertNotIn("data-resume", html)
        self.assertIn("Satu akun untuk enam aplikasi", html)
        self.assertEqual(len(re.findall(r"<h1\b", html)), 1)

    def test_member_dengan_riwayat_melihat_strip_lanjutkan(self):
        self.login()
        self.settings(last_module="forum", last_path="/forum/")
        html = self.html()
        self.assertIn("Halo, Rina", html)
        strip = re.search(r'<section class="home-strip".*?</section>', html, re.S).group(0)
        self.assertRegex(strip, r'<a href="/forum/"[^>]*data-resume')
        self.assertIn("Lanjutkan:", strip)
        # strip berada tepat di bawah carousel, bukan di dalamnya
        self.assertGreater(html.index('class="home-strip"'), html.index("</section>", html.index('class="hero-carousel"')))

    def test_member_tanpa_riwayat_tetap_punya_ajakan_jelajahi_kelas(self):
        self.login()
        html = self.html()
        self.assertNotIn("data-resume", html)
        self.assertIn("Jelajahi kelas", html)


class CssTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = read("app", "static", "css", "custom.css")

    def rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, f"aturan {selector} tidak ditemukan")
        return re.sub(r"\s+", " ", m.group(1))

    def test_slide_tak_aktif_disembunyikan_dengan_visibility(self):
        self.assertIn("visibility: hidden", self.rule(".hero-slide"))
        self.assertIn("visibility: visible", self.rule(".hero-slide.is-active"))

    def test_transisi_opacity_dan_transform_sekitar_400ms(self):
        body = self.rule(".hero-slide")
        self.assertIn("opacity 400ms", body)
        self.assertIn("transform 400ms", body)

    def test_kontrol_tersembunyi_sampai_js_aktif(self):
        self.assertIn("display: none", self.rule(".hero-carousel:not(.carousel-js) .hero-carousel-controls"))

    def test_target_sentuh_minimal_44px(self):
        for selector in (".hero-carousel-dot", ".hero-carousel-btn"):
            body = self.rule(selector)
            self.assertRegex(body, r"(min-)?width: 44px")
            self.assertRegex(body, r"(min-)?height: 44px")
        self.assertIn("min-height: 44px", self.rule("html[data-view='mobile'] .hero-slide-cta"))
        self.assertIn("min-height: 44px", self.rule(".home-strip-cta"))

    def test_mobile_view_dan_layar_sempit_tanpa_ilustrasi(self):
        self.assertIn("display: none", self.rule("html[data-view='mobile'] .hero-slide-art"))
        self.assertRegex(self.css, r"@media \(max-width: 767px\) \{[^@]*?\.hero-slide-art \{ display: none; \}")

    def test_reduced_motion_mematikan_transisi_carousel(self):
        m = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\.hero-slide,[^}]*transition: none;", self.css)
        self.assertIsNotNone(m)

    def test_fokus_terlihat_di_dalam_carousel(self):
        self.assertIn("outline: 2px solid #fff", self.rule(".hero-carousel :focus-visible"))

    def test_carousel_berada_di_luar_blok_hover(self):
        """Aturan carousel tidak boleh terkurung @media (hover: hover) supaya berlaku di layar sentuh."""
        start = self.css.index("/* ---------- 8c.")
        depth = 0
        open_hover = None
        for m in re.finditer(r"@media[^{]*\{|\{|\}", self.css[:start]):
            token = m.group(0)
            if token == "}":
                depth -= 1
                if open_hover is not None and depth < open_hover:
                    open_hover = None
            else:
                depth += 1
                if token.startswith("@media") and "hover: hover" in token and open_hover is None:
                    open_hover = depth
        self.assertIsNone(open_hover, "bagian 8c berada di dalam blok @media (hover: hover)")

    def test_kontras_teks_putih_di_atas_dasar_dan_cahaya_aksen_terburuk(self):
        """Tiap slide: teks putih harus >= 4,5:1 di atas titik terang dasar navy yang dicampur cahaya aksen penuh.

        Hero memakai dasar navy yang sama di Terang dan Gelap, jadi satu perhitungan berlaku untuk keduanya.
        Kasus terburuk: aksen dicampur sebesar --slide-glow di atas warna dasar paling terang (#294eaa).
        """
        glow = int(re.search(r"--slide-glow:\s*(\d+)%", self.css).group(1)) / 100
        lightest_base = hex_rgb("#294eaa")
        white = (255, 255, 255)
        for s in HERO_SLIDES:
            accent = hex_rgb(MODULE_BY_KEY[s["key"]]["accent"])
            worst = blend(accent, lightest_base, glow)
            self.assertGreaterEqual(contrast(white, worst), 4.5, f"{s['key']}: teks putih di atas cahaya aksen")
            # teks isi memakai putih 90%: periksa juga setelah dicampur ke dasar tersebut
            body = blend(white, worst, 0.9)
            self.assertGreaterEqual(contrast(body, worst), 4.5, f"{s['key']}: teks isi")
        # label kecil (eyebrow) harus putih (#c7d2fe bawaan hero lama tidak lolos di atas cahaya amber/teal)
        self.assertRegex(self.rule(".hero-slide .home-eyebrow"), r"color: #fff")
        # tombol putih dengan teks navy tidak bergantung pada aksen
        self.assertGreaterEqual(contrast(hex_rgb("#172e68"), white), 4.5)

    def test_amber_dan_teal_tidak_dipakai_sebagai_latar_teks(self):
        """Putih di atas #F59E0B atau #0D9488 polos tidak lolos 4,5:1; pastikan memang tidak dijadikan latar teks."""
        self.assertLess(contrast((255, 255, 255), hex_rgb("#F59E0B")), 4.5)
        self.assertLess(contrast((255, 255, 255), hex_rgb("#0D9488")), 4.5)
        for selector in (".hero-slide", ".hero-slide-copy", ".hero-slide-cta", ".hero-carousel"):
            self.assertNotRegex(self.rule(selector), r"background(-color)?:\s*var\(--slide-accent")


if __name__ == "__main__":
    unittest.main()
