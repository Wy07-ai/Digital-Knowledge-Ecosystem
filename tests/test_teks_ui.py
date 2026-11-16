"""Konsistensi istilah antarmuka: kata "modul" tidak boleh muncul di teks tampilan (pakai "aplikasi").

Lihat docs/GLOSARIUM_TEKS.md. Identifier internal (module_key, MODULES, current_module, ...), komentar,
docstring, dan parameter URL ?modul= sengaja dibiarkan.
"""
import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


if __name__ == "__main__":
    unittest.main()
