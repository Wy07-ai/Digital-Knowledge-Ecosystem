"""Tes bilah navigasi bawah (mobile): markup, tujuan menu, penanda aktif, aturan CSS, dan keamanan.

Jalankan:  python -m unittest tests.test_bottom_nav -v
Tampil/sembunyi dan ukuran ditentukan CSS (tidak bisa dijalankan di sini), jadi tes memeriksa teks aturannya;
uji visualnya ada di docs/UJI_MANUAL_NAV_MOBILE.md.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import MODULES, create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "app", "templates")
CSS = os.path.join(ROOT, "app", "static", "css", "custom.css")
NAV_RE = re.compile(r'<nav class="bottom-nav".*?</nav>', re.DOTALL)
ITEM_RE = re.compile(r"<(a|button)\b([^>]*)>(.*?)</\1>", re.DOTALL)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def items_of(html):
    """[(tag, atribut, label)] untuk empat menu di dalam <nav class="bottom-nav">."""
    nav = NAV_RE.search(html)
    assert nav, "bilah navigasi bawah tidak ada"
    out = []
    for tag, attrs, inner in ITEM_RE.findall(nav.group(0)):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
        out.append((tag, attrs, label))
    return out


def attr(attrs, name):
    m = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', attrs)
    return m.group(1) if m else None


class BottomNavCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'Rina Putri', 'rina@dke.test', ?)",
                     (generate_password_hash("Rahasia123"),))
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login(self):
        with self.client.session_transaction() as s:
            s["user_id"] = 1

    def html(self, path, status=200):
        r = self.client.get(path)
        self.assertEqual(r.status_code, status, path)
        return r.get_data(as_text=True)

    def current_labels(self, path):
        return [label for _t, attrs, label in items_of(self.html(path)) if attr(attrs, "aria-current") == "page"]


class StrukturTest(BottomNavCase):
    def test_ada_empat_menu_dengan_tujuan_yang_benar(self):
        html = self.html("/")
        self.assertEqual(len(NAV_RE.findall(html)), 1, "bilah harus muncul satu kali per halaman")
        self.assertIn('aria-label="Navigasi bawah"', html)
        items = items_of(html)
        self.assertEqual([i[2] for i in items], ["Beranda", "Aplikasi", "Cari", "Akun"])
        with self.app.test_request_context():
            from flask import url_for
            home, search = url_for("main.index"), url_for("main.search")
        self.assertEqual(attr(items[0][1], "href"), home)
        self.assertEqual(items[1][0], "button")
        self.assertEqual(attr(items[2][1], "href"), search)

    def test_aplikasi_adalah_pemicu_app_switcher_yang_sama(self):
        html = self.html("/")
        _tag, attrs, _label = items_of(html)[1]
        self.assertEqual(attr(attrs, "type"), "button")
        self.assertEqual(attr(attrs, "aria-expanded"), "false")
        self.assertEqual(attr(attrs, "aria-controls"), "app-switcher-panel")
        self.assertIn("data-popover-open", attrs)
        self.assertEqual(html.count('id="app-switcher-panel"'), 1, "panel App Switcher tidak boleh digandakan")
        self.assertIn("data-popover-open", read("app", "static", "js", "switcher.js"))

    def test_daftar_aplikasi_tidak_digandakan_di_bilah_bawah(self):
        nav = NAV_RE.search(self.html("/")).group(0)
        for m in MODULES:
            self.assertNotIn(m["name"], nav)
            if m["key"] != "infosys":          # Akun (Guest) menuju /infosys/login, itu bukan daftar aplikasi
                self.assertNotIn(f"/{m['key']}/", nav)
        hrefs = [attr(a, "href") for _t, a, _l in items_of(self.html("/")) if attr(a, "href")]
        self.assertEqual(len(hrefs), 3, "hanya Beranda, Cari, dan Akun yang berupa tautan")

    def test_semua_item_punya_ikon_dan_label_terlihat(self):
        nav = NAV_RE.search(self.html("/")).group(0)
        self.assertEqual(nav.count("<svg"), 4)
        self.assertEqual(nav.count('class="bottom-nav-label"'), 4)
        self.assertNotIn("sr-only", nav, "label harus terlihat, bukan hanya untuk pembaca layar")

    def test_ikon_grid_dan_user_tersedia(self):
        icons = read("app", "templates", "_components", "_icons.html")
        self.assertIn("name == 'grid'", icons)
        self.assertIn("name == 'user'", icons)


class AkunTest(BottomNavCase):
    def test_guest_ke_halaman_masuk(self):
        href = attr(items_of(self.html("/"))[3][1], "href")
        with self.app.test_request_context():
            from flask import url_for
            self.assertTrue(href.startswith(url_for("infosys.login")), href)

    def test_member_ke_information_system(self):
        self.login()
        href = attr(items_of(self.html("/"))[3][1], "href")
        with self.app.test_request_context():
            from flask import url_for
            self.assertEqual(href, url_for("infosys.index"))


class PenandaAktifTest(BottomNavCase):
    def test_beranda(self):
        self.assertEqual(self.current_labels("/"), ["Beranda"])

    def test_pencarian(self):
        self.assertEqual(self.current_labels("/cari"), ["Cari"])
        self.assertEqual(self.current_labels("/cari?q=python"), ["Cari"])

    def test_halaman_information_system(self):
        self.login()
        self.assertEqual(self.current_labels("/infosys/"), ["Akun"])
        self.assertEqual(self.current_labels("/infosys/profil"), ["Akun"])

    def test_halaman_masuk_guest_menandai_akun(self):
        self.assertEqual(self.current_labels("/infosys/login"), ["Akun"])

    def test_aplikasi_aktif_di_semua_aplikasi_selain_information_system(self):
        for key in ("ecommerce", "elearning", "etutorial", "portal", "forum"):
            self.assertEqual(self.current_labels(f"/{key}/"), ["Aplikasi"], key)

    def test_aplikasi_tidak_aktif_di_information_system(self):
        self.login()
        self.assertNotIn("Aplikasi", self.current_labels("/infosys/"))

    def test_hanya_satu_item_aktif(self):
        self.login()
        for path in ("/", "/cari", "/infosys/", "/forum/", "/ecommerce/"):
            self.assertEqual(len(self.current_labels(path)), 1, path)


class HalamanGalatTest(BottomNavCase):
    def test_halaman_galat_menampilkan_bilah_tanpa_item_aktif(self):
        html = self.html("/tidak-ada-halaman-ini", status=404)
        self.assertIn("data-error-page", html)
        self.assertEqual(len(NAV_RE.findall(html)), 1)
        self.assertEqual([i[2] for i in items_of(html)], ["Beranda", "Aplikasi", "Cari", "Akun"])
        self.assertEqual([l for _t, a, l in items_of(html) if attr(a, "aria-current") == "page"], [])


class CssTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = read("app", "static", "css", "custom.css")
        m = re.search(r"/\* -+ 16\. Bilah navigasi bawah.*", cls.css, re.DOTALL)
        assert m, "bagian 16 custom.css tidak ada"
        cls.section = m.group(0)

    def rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.section)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_tersembunyi_secara_bawaan(self):
        self.assertRegex(self.rule(".bottom-nav"), r"display:\s*none")

    def test_tampil_pada_layar_sempit_dan_mobile_view(self):
        self.assertRegex(self.section, r"@media \(max-width: 767px\)\s*\{\s*\.bottom-nav \{ display: block; \}")
        self.assertRegex(self.section, r"html\[data-view='mobile'\] \.bottom-nav \{[^}]*display: block")

    def test_menempel_di_bawah_dengan_area_aman_dan_z_index_rendah(self):
        rule = self.rule(".bottom-nav")
        self.assertIn("position: fixed", rule)
        self.assertIn("bottom: 0", rule)
        self.assertIn("padding-bottom: env(safe-area-inset-bottom, 0)", rule)
        z = int(re.search(r"z-index:\s*(\d+)", rule).group(1))
        toast_z = int(re.search(r"#toast-root \{[^}]*z-index:\s*(\d+)", self.css).group(1))
        self.assertLess(z, toast_z, "bilah harus di bawah toast")
        self.assertLess(z, 40, "bilah harus di bawah bilah atas dan panelnya")

    def test_mobile_view_dibatasi_selebar_body(self):
        m = re.search(r"html\[data-view='mobile'\] \.bottom-nav \{([^}]*)\}", self.section)
        self.assertIn("min(430px, 100%)", m.group(1))
        self.assertIn("margin-inline: auto", m.group(1))

    def test_ruang_dasar_dan_toast_digeser_pada_kedua_kondisi_mobile(self):
        for selector in ("body:has(> .bottom-nav) { padding-bottom: var(--bottom-nav-space)",
                         "html[data-view='mobile'] body:has(> .bottom-nav) { padding-bottom: var(--bottom-nav-space)",
                         "body:has(> .bottom-nav) #toast-root { top: auto; bottom: calc(var(--bottom-nav-space)",
                         "html[data-view='mobile'] body:has(> .bottom-nav) #toast-root { top: auto; bottom: calc(var(--bottom-nav-space)",
                         "scroll-padding-bottom: var(--bottom-nav-space)"):
            self.assertIn(selector, self.section)
        self.assertIn("env(safe-area-inset-bottom, 0px)", self.section)

    def test_target_sentuh_minimal_44_px(self):
        rule = self.rule(".bottom-nav-item")
        self.assertIn("min-width: 44px", rule)
        self.assertIn("min-height: 44px", rule)

    def test_fokus_terlihat_dan_penanda_aktif_bukan_hanya_warna(self):
        self.assertIn(".bottom-nav-item:focus-visible { outline:", self.section)
        self.assertIn(".bottom-nav-item[aria-current='page']::before { transform: scaleX(1)", self.section)

    def test_disembunyikan_saat_cetak(self):
        m = re.search(r"@media print \{(.*?)\n\}", self.section, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"\.bottom-nav \{ display: none !important")

    def test_warna_hanya_dari_token(self):
        self.assertNotRegex(self.section, r"#[0-9a-fA-F]{3,8}\b", "pakai token (--c-*), bukan warna tetap")
        for token in ("--c-surface", "--c-border"):
            self.assertIn(token, self.rule(".bottom-nav"))


class PemasanganTest(unittest.TestCase):
    def test_komponen_hanya_di_include_satu_kali(self):
        found = []
        for folder, dirs, files in os.walk(TEMPLATES):
            for name in files:
                if name.endswith(".html"):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    found += [os.path.relpath(path, TEMPLATES)] * len(re.findall(r"_components/bottom_nav\.html", text))
        self.assertEqual([f for f in found if f != "base.html"], [], "hanya base.html yang boleh meng-include komponen")
        base = read("app", "templates", "base.html")
        self.assertEqual(len(re.findall(r"\{%\s*include\s+'_components/bottom_nav\.html'\s*%\}", base)), 1)
        self.assertRegex(base, r"\{% block bottom_nav %\}\{% include '_components/bottom_nav\.html' %\}\{% endblock %\}")

    def test_tanpa_skrip_inline_dan_atribut_event(self):
        for rel in (("app", "templates", "_components", "bottom_nav.html"),):
            text = re.sub(r"\{#.*?#\}", "", read(*rel), flags=re.DOTALL)
            self.assertNotIn("<script", text.lower())
            self.assertNotRegex(text, r"\son[a-z]+\s*=", "atribut on...= melanggar CSP")
            self.assertNotIn("javascript:", text.lower())

    def test_switcher_js_tanpa_eval_dan_inline(self):
        js = read("app", "static", "js", "switcher.js")
        self.assertNotRegex(js, r"\beval\(|new Function\(|innerHTML")


if __name__ == "__main__":
    unittest.main()
