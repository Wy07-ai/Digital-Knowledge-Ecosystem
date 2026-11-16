"""Konsistensi teks antarmuka (Blueprint 5.5): istilah baku, kalimat bersama, dan batas panjang.

Aturannya ada di docs/GLOSARIUM_TEKS.md ("Panduan gaya"). Tes di sini:
  * kata "modul" dan semua istilah terlarang tidak boleh muncul di teks tampilan;
  * salinan pesan di JavaScript sama persis dengan app/messages.py, dan tidak ada kalimat ganda;
  * subjudul halaman maksimal 15 kata, empty state satu kalimat penjelas.

Identifier internal (module_key, MODULES, current_module, ...), komentar, docstring, dan parameter URL
?modul= sengaja dibiarkan. Teks diambil lewat scripts/inventaris_teks.py.
"""
import ast
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app import messages as pesan  # noqa: E402
from scripts.inventaris_teks import collect, from_html  # noqa: E402

APP = os.path.join(ROOT, "app")
MODUL = re.compile(r"modul(?!e)", re.IGNORECASE)    # "module" (kode) tidak termasuk

# Teks yang memang boleh memuat "modul": nilai parameter URL ?modul= dan id HTML yang tak terlihat.
ALLOWED_PY_LITERALS = {"modul"}
ALLOWED_TEMPLATE_FRAGMENTS = ('name="modul"', 'id="f-modul"', 'for="f-modul"',
                              'id="h-modul"', 'aria-labelledby="h-modul"', "modul=")


def walk(base, suffixes):
    for folder, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(suffixes):
                yield os.path.join(folder, name)


def rel(path):
    return os.path.relpath(path, ROOT)


class TeksAntarmukaTest(unittest.TestCase):
    def test_template_tanpa_kata_modul_di_teks_tampilan(self):
        found = []
        for path in walk(os.path.join(APP, "templates"), (".html",)):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            text = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)      # komentar Jinja
            for fragment in ALLOWED_TEMPLATE_FRAGMENTS:
                text = text.replace(fragment, "")
            for n, line in enumerate(text.splitlines(), 1):
                if MODUL.search(line):
                    found.append(f"{rel(path)} (baris {n} setelah komentar dibuang): {line.strip()[:90]}")
        self.assertEqual(found, [], "Pakai 'aplikasi' pada teks tampilan:\n" + "\n".join(found))

    def test_string_python_tanpa_kata_modul(self):
        """Semua literal string di app/ kecuali docstring (flash, deskripsi, label navigasi, dst.)."""
        found = []
        for path in walk(APP, (".py",)):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    body = node.body
                    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        docstrings.add(id(body[0].value))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                    if node.value not in ALLOWED_PY_LITERALS and MODUL.search(node.value):
                        found.append(f"{rel(path)}:{node.lineno}: {node.value[:80]!r}")
        self.assertEqual(found, [], "Pakai 'aplikasi' pada teks tampilan:\n" + "\n".join(found))

    def test_string_javascript_tanpa_kata_modul(self):
        found = []
        literal = re.compile(r"""'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*\"""")
        for path in walk(os.path.join(APP, "static", "js"), (".js",)):
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in literal.findall(line):
                        if MODUL.search(m):
                            found.append(f"{rel(path)}:{n}: {m[:80]}")
        self.assertEqual(found, [], "Pakai 'aplikasi' pada teks tampilan:\n" + "\n".join(found))

    def test_glosarium_ada_dan_ditautkan_dari_readme(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "docs", "GLOSARIUM_TEKS.md")))
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("docs/GLOSARIUM_TEKS.md", f.read())


# ---------------------------------------------------------------------------------------------
# Panduan gaya (Blueprint 5.5, docs/GLOSARIUM_TEKS.md): istilah terlarang, pesan bersama, panjang teks
# ---------------------------------------------------------------------------------------------
# pola -> pengganti yang benar. Hanya diperiksa pada teks tampilan (scripts/inventaris_teks.py).
ISTILAH_TERLARANG = {
    r"control panel": "Akun Saya",
    r"\bcheck-?out\b": "Pembayaran / Bayar",
    r"\blog-?in\b": "masuk",
    r"\blog-?out\b": "keluar",
    r"\bbookmark\b": "simpan / tersimpan",
    r"\bthreads?\b": "topik",
    r"\bsolved\b": "terjawab",
    r"top-bar": "bilah atas",
    r"smart landing": "Saat membuka DKE",
    r"\bbreadcrumb\b": "jejak halaman",
    r"\bstep\b": "langkah",
    r"\bestimasi\b": "perkiraan waktu",
    r"\bbrowser\b": "peramban",
    r"\bavatar\b": "foto profil",
    r"\bsilakan\b": "kata kerja langsung (mis. 'Masuk dulu ...')",
    r"\bwajib diisi\b": "belum diisi + petunjuk",
    r"\btidak valid\b": "belum valid / belum sesuai + petunjuk",
    r"\bkamu\b": "Anda",
    r"\b(?!ilmu\b)\w{3,}mu\b": "Anda",
    r"\bdapat (melihat|diubah|dibatalkan|diatur|login|masuk)\b": "bisa",
}
# Berkas yang boleh memuat istilah teknis karena memang halaman untuk developer.
BEBAS_ISTILAH = {os.path.join("app", "templates", "main", "ui_test.html")}


class PanduanGayaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.teks = collect(ROOT)

    def test_tidak_ada_istilah_terlarang_di_teks_tampilan(self):
        found = []
        for item in self.teks:
            if item.file in BEBAS_ISTILAH:
                continue
            for pola, ganti in ISTILAH_TERLARANG.items():
                if re.search(pola, item.text, re.IGNORECASE):
                    found.append(f"{item.file}:{item.line} [{item.kind}] pakai '{ganti}': {item.text[:90]}")
        self.assertEqual(found, [], "Istilah terlarang di teks tampilan:\n" + "\n".join(found))

    def test_inventaris_menemukan_teks_dari_semua_jenis(self):
        kinds = {t.kind for t in self.teks}
        self.assertEqual(kinds, {"html-teks", "html-atribut", "jinja", "py", "js"})
        self.assertGreater(len(self.teks), 1000)

    # ---- Pesan bersama (app/messages.py) ----
    def _konstanta_pesan(self):
        with open(os.path.join(APP, "messages.py"), encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        out = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id.startswith("MSG_") and isinstance(node.value, ast.Constant):
                tagged_js = "# [JS]" in src.splitlines()[node.lineno - 1]
                out[node.targets[0].id] = (node.value.value, tagged_js)
        return out

    def _literal_js(self):
        found = {}
        literal = re.compile(r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)\"""")
        for path in walk(os.path.join(APP, "static", "js"), (".js",)):
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in literal.finditer(line):
                        found.setdefault(m.group(1) or m.group(2), []).append(f"{rel(path)}:{n}")
        return found

    def test_pesan_bertanda_js_ada_persis_di_javascript(self):
        js = self._literal_js()
        missing = [f"{name}: {value!r}" for name, (value, tagged) in self._konstanta_pesan().items()
                   if tagged and value not in js]
        self.assertEqual(missing, [], "Pesan bertanda [JS] di app/messages.py tidak ada persis di static/js:\n"
                         + "\n".join(missing))

    def test_pesan_validasi_di_js_berasal_dari_messages_py(self):
        """auth.js dan panel.js hanya boleh memuat kalimat yang ada di app/messages.py."""
        katalog = {v for v, _ in self._konstanta_pesan().values()}
        extra = []
        for item in self.teks:
            if item.kind == "js" and item.file.endswith(("auth.js", "panel.js")) and len(item.text.split()) >= 4:
                if item.text not in katalog:
                    extra.append(f"{item.file}:{item.line}: {item.text}")
        self.assertEqual(extra, [], "Kalimat di JavaScript yang tidak ada di app/messages.py:\n" + "\n".join(extra))

    def test_tidak_ada_kalimat_ganda_di_python(self):
        """Kalimat panjang yang sama tidak boleh ditulis dua kali (atau menyalin app/messages.py)."""
        katalog = {v for v, _ in self._konstanta_pesan().values()}
        counts = {}
        for item in self.teks:
            if item.kind == "py" and not item.file.endswith("messages.py") and len(item.text) >= 30:
                counts.setdefault(item.text, []).append(f"{item.file}:{item.line}")
        dup = [f"{text!r} di {', '.join(where)}" for text, where in counts.items()
               if len(where) > 1 or text in katalog]
        self.assertEqual(dup, [], "Pindahkan kalimat ini ke app/messages.py:\n" + "\n".join(dup))

    def test_pesan_galat_menyebut_solusi_dan_tidak_menyalahkan(self):
        masalah = re.compile(r"belum bisa|gagal|terlalu|belum diisi|belum valid|belum sama|salah|kedaluwarsa|"
                             r"belum sesuai|belum terdaftar|tidak diterima|ditolak|kosong", re.IGNORECASE)
        solusi = re.compile(r"Coba|Muat ulang|Periksa|Tulis|Ketik|Pilih|Gunakan|Masuk|Tunggu|Maksimal|Minimal|"
                            r"Contoh|Hubungi|Tambahkan|Isi |Pakai|Ikuti|Lanjutkan")
        menyalahkan = re.compile(r"salah Anda|Anda salah|Anda harus|Anda lupa|Anda tidak boleh|kesalahan Anda|"
                                 r"tidak boleh|Anda gagal", re.IGNORECASE)
        found = []
        for name, (value, _) in self._konstanta_pesan().items():
            if menyalahkan.search(value):
                found.append(f"{name}: menyalahkan pengguna: {value}")
            if masalah.search(value) and not solusi.search(value):
                found.append(f"{name}: tidak menyebut solusi: {value}")
        self.assertEqual(found, [], "\n".join(found))

    # ---- Panjang teks ----
    def test_subjudul_halaman_maksimal_15_kata(self):
        """<h1> diikuti <p class="text-muted"> = subjudul. Tiap cabang {% if %}/{% else %} dihitung sendiri."""
        batas, found = 15, []
        for path in walk(os.path.join(APP, "templates"), (".html",)):
            if os.path.basename(path) in ("nav_demo.html", "ui_test.html"):
                continue                                              # halaman uji untuk developer
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r'</h1>\s*<p class="[^"]*text-muted[^"]*">(.*?)</p>', text, re.S):
                for cabang in re.split(r"\{%\s*(?:else\s*|elif[^%]*)%\}", m.group(1)):
                    bersih = re.sub(r"\{%.*?%\}", " ", cabang, flags=re.S)
                    bersih = re.sub(r"\{\{.*?\}\}", "X", bersih, flags=re.S)
                    bersih = re.sub(r"<[^>]+>", " ", bersih)
                    n = len(bersih.split())
                    if n > batas:
                        found.append(f"{rel(path)}: {n} kata: {' '.join(bersih.split())[:100]}")
        self.assertEqual(found, [], f"Subjudul lebih dari {batas} kata:\n" + "\n".join(found))

    def _empty_state_calls(self):
        """Semua pemanggilan {{ empty_state(...) }} di template -> (berkas, [argumen mentah])."""
        calls = []
        for path in walk(os.path.join(APP, "templates"), (".html",)):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r"\{\{\s*empty_state\(", text):
                args, depth, cur, quote, i = [], 0, "", None, m.end()
                while i < len(text):
                    ch = text[i]
                    if quote:
                        cur += ch
                        if ch == quote and text[i - 1] != "\\":
                            quote = None
                    elif ch in "'\"":
                        quote = ch
                        cur += ch
                    elif ch in "([{":
                        depth += 1
                        cur += ch
                    elif ch in ")]}":
                        if depth == 0:
                            args.append(cur.strip())
                            break
                        depth -= 1
                        cur += ch
                    elif ch == "," and depth == 0:
                        args.append(cur.strip())
                        cur = ""
                    else:
                        cur += ch
                    i += 1
                calls.append((rel(path), args))
        return calls

    def test_empty_state_satu_kalimat_penjelas(self):
        found, dicek = [], 0
        for path, args in self._empty_state_calls():
            if len(args) >= 2 and re.fullmatch(r"'[^']*'|\"[^\"]*\"", args[1]):
                dicek += 1
                kalimat = [k for k in re.split(r"(?<=[.!?])\s+", args[1][1:-1].strip()) if k]
                if len(kalimat) > 1 or len(args[1].split()) > 20:
                    found.append(f"{path}: {args[1][:110]}")
        self.assertGreater(dicek, 15)
        self.assertEqual(found, [], "Empty state harus satu kalimat penjelas (maks. 20 kata):\n" + "\n".join(found))

    def test_empty_state_punya_satu_tombol_aksi(self):
        """Panduan: empty state = judul + satu kalimat + satu tombol (label dan alamat terisi)."""
        tanpa_aksi = [f"{path}: {args[0][:60]}" for path, args in self._empty_state_calls() if len(args) < 4]
        self.assertEqual(tanpa_aksi, [], "Empty state tanpa tombol aksi:\n" + "\n".join(tanpa_aksi))

    def test_panduan_gaya_ada_di_glosarium(self):
        with open(os.path.join(ROOT, "docs", "GLOSARIUM_TEKS.md"), encoding="utf-8") as f:
            text = f.read()
        for judul in ("## Panduan gaya", "## Istilah terlarang", "## Katalog pesan"):
            self.assertIn(judul, text)


if __name__ == "__main__":
    unittest.main()
