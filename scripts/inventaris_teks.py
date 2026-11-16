#!/usr/bin/env python3
"""Inventaris teks tampilan DKE: mengekstrak kalimat yang dilihat pengguna dari
`app/templates/**/*.html`, string Python di `app/**/*.py`, dan string JavaScript di `app/static/js/*.js`.

Dipakai dua cara:

  * Baris perintah (untuk meninjau/mengaudit teks, mis. sebelum menulis ulang sebuah halaman):

        python scripts/inventaris_teks.py                      # ringkasan jumlah per jenis
        python scripts/inventaris_teks.py --csv docs/INVENTARIS_TEKS.csv
        python scripts/inventaris_teks.py --cari "login|checkout"   # cari teks (regex, abaikan huruf besar)

  * Modul (dipakai `tests/test_teks_ui.py` untuk memeriksa istilah terlarang, panjang subjudul, dst.):

        from scripts.inventaris_teks import collect
        for item in collect(root): item.file, item.line, item.kind, item.text

Jenis teks (`kind`):
    html-teks    teks di antara tag HTML (judul, subjudul, tombol, label, catatan)
    html-atribut aria-label, title, placeholder, alt, label, data-busy, data-label, data-empty
    jinja        string di dalam {{ ... }} / {% ... %} (mis. argumen empty_state, stat_card, flash)
    py           string Python yang tampil ke pengguna (flash, galat, label, deskripsi aplikasi)
    js           string JavaScript yang tampil ke pengguna (toast, validasi inline, label tombol)

Yang SENGAJA tidak dimasukkan: docstring, komentar, SQL, pesan log developer (`logger.*`), nama kelas
CSS, selector, jalur SVG, dan identifier (kata tunggal huruf kecil, `a.b`, `a_b`, `a-b`).
"""
import ast
import csv
import os
import re
import sys
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ATTR_TAMPIL = ("aria-label", "title", "placeholder", "alt", "label", "data-busy", "data-label",
               "data-empty", "aria-valuetext")
SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|ORDER BY|GROUP BY|PRAGMA|CREATE TABLE)\b")
HURUF = re.compile(r"[A-Za-zÀ-ÿ]{2,}")


@dataclass(frozen=True)
class Teks:
    file: str      # relatif terhadap root
    line: int
    kind: str
    text: str


def _tampil(value):
    """True bila string tampak seperti kalimat/label untuk pengguna, bukan identifier atau kode."""
    v = value.strip()
    if not v or not HURUF.search(v) or SQL.search(v):
        return False
    if " " not in v:
        return bool(re.match(r"^[A-Z][a-zà-ÿ]+$", v))          # satu kata berkapital = label ("Simpan")
    first = v.split(" ")[0]
    if re.search(r"[_/=#]", first) or first.endswith(("()", ";")):
        return False
    if "<" in v or v.startswith(("(", "[", ".", "#")):
        return False
    if re.match(r"^[a-z0-9:\-\[\]/.%!]+( [a-z0-9:\-\[\]/.%!]+)*$", v):   # daftar kelas CSS: "btn btn--primary"
        return False
    return True


def _rapikan(text):
    return re.sub(r"\s+", " ", text).strip()


def _lineno(source, offset):
    return source.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------- HTML
_TOK = re.compile(r"\{#.*?#\}|\{\{.*?\}\}|\{%.*?%\}", re.S)
_LIT = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"([^\"\n]*)\"")
_ATTR = re.compile(r'\b(' + "|".join(ATTR_TAMPIL) + r')="([^"]*)"')


def from_html(path, rel):
    src = open(path, encoding="utf-8").read()
    out = []
    # 1) string di dalam ekspresi Jinja (komentar {# #} dilewati)
    for m in _TOK.finditer(src):
        if m.group(0).startswith("{#"):
            continue
        for lm in _LIT.finditer(m.group(0)):
            val = lm.group(1) if lm.group(1) is not None else lm.group(2)
            if _tampil(val):
                out.append(Teks(rel, _lineno(src, m.start()), "jinja", _rapikan(val)))
    # 2) markup: topeng Jinja dan <script>/<style> dengan spasi, sisakan panjang agar nomor baris tetap
    masked = _TOK.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
    masked = re.sub(r"<(script|style)\b.*?</\1>", lambda m: re.sub(r"[^\n]", " ", m.group(0)), masked, flags=re.S | re.I)
    masked_attr = _TOK.sub(lambda m: "\x00" * len(m.group(0)), src)       # untuk atribut: isi Jinja ditandai
    for m in re.finditer(r"<[^>]*>", masked):
        tag = m.group(0)
        for am in _ATTR.finditer(src[m.start():m.end()]):
            val = _TOK.sub(" ", am.group(2))
            if _tampil(val):
                out.append(Teks(rel, _lineno(src, m.start()), "html-atribut", _rapikan(val)))
    for m in re.finditer(r"(?<=>)[^<>]+(?=<)|^[^<>]+(?=<)", masked, re.M):
        for piece in re.split(r"\n\s*\n|(?<=[.!?])\s*\n", m.group(0)):
            t = _rapikan(re.sub(r"&[a-z]+;|&#\d+;", " ", piece))
            if t and HURUF.search(t) and not re.fullmatch(r"[\W\d_]*", t):
                out.append(Teks(rel, _lineno(src, m.start()), "html-teks", t))
    return out


# ---------------------------------------------------------------------------- Python
def from_py(path, rel):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if isinstance(parent.get(node), ast.Expr):                      # docstring / string lepas
            continue
        q = node
        while q in parent and not isinstance(q, ast.Call):
            q = parent[q]
        if isinstance(q, ast.Call) and isinstance(q.func, ast.Attribute) \
                and q.func.attr in ("exception", "warning", "error", "info", "debug") \
                and "log" in ast.unparse(q.func.value).lower():         # pesan log untuk developer
            continue
        if _tampil(node.value):
            out.append(Teks(rel, node.lineno, "py", _rapikan(node.value)))
    return out


# ---------------------------------------------------------------------------- JavaScript
_JS = re.compile(r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)\"""")


def from_js(path, rel):
    out = []
    in_block = False
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        stripped = line.strip()
        if in_block:
            in_block = "*/" not in stripped
            continue
        if stripped.startswith("/*"):
            in_block = "*/" not in stripped
            continue
        code = line.split("//")[0] if "//" in line and "'" not in line.split("//")[0][-1:] else line
        for m in _JS.finditer(code):
            val = m.group(1) if m.group(1) is not None else m.group(2)
            if " " in val and _tampil(val) and re.match(r"^[A-ZÀ-Þ]", val.strip()):
                out.append(Teks(rel, n, "js", _rapikan(val)))
            elif re.fullmatch(r"[A-Z][a-zà-ÿ]+", val.strip()):
                out.append(Teks(rel, n, "js", val.strip()))
    return out


# ---------------------------------------------------------------------------- Gabungan
def _walk(base, ext):
    for folder, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name.endswith(ext):
                yield os.path.join(folder, name)


def collect(root=ROOT):
    app = os.path.join(root, "app")
    items = []
    for path in _walk(os.path.join(app, "templates"), ".html"):
        items += from_html(path, os.path.relpath(path, root))
    for path in _walk(app, ".py"):
        items += from_py(path, os.path.relpath(path, root))
    for path in _walk(os.path.join(app, "static", "js"), ".js"):
        items += from_js(path, os.path.relpath(path, root))
    return items


def main(argv):
    root = ROOT
    items = collect(root)
    if "--csv" in argv:
        target = argv[argv.index("--csv") + 1]
        with open(target, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["berkas", "baris", "jenis", "teks"])
            for it in items:
                w.writerow([it.file, it.line, it.kind, it.text])
        print(f"{len(items)} teks ditulis ke {target}")
        return 0
    if "--cari" in argv:
        rx = re.compile(argv[argv.index("--cari") + 1], re.IGNORECASE)
        hit = [it for it in items if rx.search(it.text)]
        for it in hit:
            print(f"{it.file}:{it.line} [{it.kind}] {it.text}")
        print(f"{len(hit)} cocok dari {len(items)} teks")
        return 0
    per = {}
    for it in items:
        per[it.kind] = per.get(it.kind, 0) + 1
    print(f"{len(items)} teks tampilan")
    for k, v in sorted(per.items()):
        print(f"  {k:<13}{v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
