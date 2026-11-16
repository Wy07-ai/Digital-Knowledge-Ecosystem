"""Tes seed.py: kata sandi admin tidak lagi tertulis di repositori, dan seed tetap idempoten.

Jalankan:  python -m unittest tests.test_seed
"""
import contextlib
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from werkzeug.security import check_password_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import seed  # noqa: E402

OLD_ADMIN_PASSWORD = "Admin12345"  # awalan kata sandi lama yang pernah tertulis di repositori


class SeedPasswordCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "seed.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_seed(self, env=None, extra=()):
        """Jalankan seed.main dengan lingkungan bersih (hanya `env`). Mengembalikan (kode_keluar, keluaran)."""
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=True), contextlib.redirect_stdout(buf):
            code = seed.main(["--db", self.db, *extra])
        return code, buf.getvalue()

    def hash_of(self, email):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()[0]
        finally:
            conn.close()

    def printed_admin_password(self, output):
        m = re.search(r"^\s{6}(\S+)\s*$", output, re.M)
        self.assertIsNotNone(m, "kata sandi acak admin tidak dicetak:\n" + output)
        return m.group(1)


class AdminPasswordTest(SeedPasswordCase):
    def test_database_baru_tanpa_env_berhasil_dan_mencetak_kata_sandi_acak_sekali(self):
        code, out = self.run_seed()
        self.assertEqual(code, 0, out)
        pw = self.printed_admin_password(out)
        self.assertGreaterEqual(len(pw), 20)
        self.assertEqual(out.count(pw), 1)                                 # dicetak SATU kali
        self.assertTrue(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), pw))
        self.assertIn("DKE_ADMIN_PASSWORD", out)                            # instruksi cara mengisi sendiri
        self.assertIn("Catat SEKARANG", out)

    def test_kata_sandi_admin_lama_tidak_berlaku(self):
        self.run_seed()
        for lama in ("Admin12345!", "Admin12345"):
            self.assertFalse(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), lama))

    def test_kata_sandi_acak_berbeda_di_tiap_database_baru(self):
        pw1 = self.printed_admin_password(self.run_seed()[1])
        self.db = os.path.join(self.tmp, "lain.db")
        pw2 = self.printed_admin_password(self.run_seed()[1])
        self.assertNotEqual(pw1, pw2)

    def test_env_dipakai_dan_tidak_dicetak(self):
        code, out = self.run_seed({"DKE_ADMIN_PASSWORD": "Pilihan-Saya-42"})
        self.assertEqual(code, 0, out)
        self.assertTrue(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), "Pilihan-Saya-42"))
        self.assertNotIn("Pilihan-Saya-42", out)
        self.assertNotIn("ACAK", out)

    def test_env_kosong_dianggap_tidak_diisi(self):
        for kosong in ("", "   "):
            with self.subTest(nilai=repr(kosong)):
                self.db = os.path.join(self.tmp, f"k{len(kosong)}.db")
                code, out = self.run_seed({"DKE_ADMIN_PASSWORD": kosong})
                self.assertEqual(code, 0, out)
                pw = self.printed_admin_password(out)
                self.assertFalse(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), kosong))
                self.assertTrue(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), pw))


class DemoPasswordTest(SeedPasswordCase):
    def test_demo_tetap_bisa_dipakai_dengan_kata_sandi_bawaan_disertai_peringatan(self):
        code, out = self.run_seed()
        self.assertEqual(code, 0, out)
        self.assertTrue(check_password_hash(self.hash_of(seed.DEMO_EMAIL), "Demo12345"))   # skenario demo@dke.test
        self.assertIn("PERINGATAN", out)
        self.assertIn("hanya di komputer sendiri", out)

    def test_demo_dari_env_tanpa_peringatan(self):
        code, out = self.run_seed({"DKE_DEMO_PASSWORD": "DemoLain-99"})
        self.assertEqual(code, 0, out)
        self.assertTrue(check_password_hash(self.hash_of(seed.DEMO_EMAIL), "DemoLain-99"))
        self.assertNotIn("PERINGATAN", out)
        self.assertNotIn("DemoLain-99", out)


class IdempotencyTest(SeedPasswordCase):
    def counts(self):
        conn = sqlite3.connect(self.db)
        try:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in seed.EXPECTED_TABLES}
        finally:
            conn.close()

    def test_seed_ulang_tidak_menimpa_kata_sandi_dan_tidak_menggandakan_data(self):
        self.run_seed()
        hashes = {e: self.hash_of(e) for e in (seed.ADMIN_EMAIL, seed.DEMO_EMAIL)}
        counts = self.counts()
        # Ulang dengan env berbeda: kata sandi akun yang sudah ada tetap.
        code, out = self.run_seed({"DKE_ADMIN_PASSWORD": "Baru-Baru-123", "DKE_DEMO_PASSWORD": "Baru-Baru-123"})
        self.assertEqual(code, 0, out)
        self.assertEqual({e: self.hash_of(e) for e in hashes}, hashes)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(out.count("sudah ada; kata sandi tidak diubah"), 2)
        self.assertNotIn("Catat SEKARANG", out)                             # tidak ada kata sandi baru dicetak
        self.assertNotIn("Baru-Baru-123", out)

    def test_seed_ulang_tanpa_env_tidak_mencetak_kata_sandi_apa_pun(self):
        self.run_seed()
        code, out = self.run_seed()
        self.assertEqual(code, 0, out)
        self.assertNotIn("Catat SEKARANG", out)
        self.assertNotIn("Demo12345", out)

    def test_reset_membuat_kata_sandi_acak_baru(self):
        pw1 = self.printed_admin_password(self.run_seed()[1])
        code, out = self.run_seed(extra=("--reset",))
        self.assertEqual(code, 0, out)
        pw2 = self.printed_admin_password(out)
        self.assertNotEqual(pw1, pw2)
        self.assertTrue(check_password_hash(self.hash_of(seed.ADMIN_EMAIL), pw2))


class RepositoryHygieneTest(unittest.TestCase):
    SKIP_DIRS = {".git", "__pycache__", "instance", ".venv", "venv", "node_modules"}

    def text_files(self):
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            for name in files:
                if name.endswith((".py", ".md", ".html", ".txt", ".sql", ".js", ".css")):
                    yield os.path.join(folder, name)

    def test_kata_sandi_admin_lama_tidak_tertulis_di_berkas_mana_pun(self):
        found = []
        for path in self.text_files():
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue                                                    # tes ini menyebut awalan lama
            with open(path, encoding="utf-8", errors="ignore") as f:
                if OLD_ADMIN_PASSWORD in f.read():
                    found.append(os.path.relpath(path, ROOT))
        self.assertEqual(found, [])

    def test_readme_menjelaskan_env_admin_dan_peringatan_demo(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertTrue("DKE_ADMIN_PASSWORD" in readme, "README belum menjelaskan DKE_ADMIN_PASSWORD")
        self.assertTrue("hanya untuk lokal" in readme.lower(), "README belum memuat peringatan akun demo")


if __name__ == "__main__":
    unittest.main()
